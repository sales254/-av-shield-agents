"""Reyee / Ruijie Cloud adapter (Playwright, headless Chromium).

Implements ``NetworkAdapter`` for the Ruijie/Reyee Cloud hash-route SPA.

Design notes
------------
* Persistent ``storage_state`` so we don't re-login every call.
* SPA is client-side routed: we navigate by setting ``location.hash`` and then
  **wait on DOM elements**, never on page loads or blind sleeps.
* Politeness: a rate limiter throttles navigations and we back off on errors,
  so we don't trip the portal's account-lock protection.
* Every WRITE goes through ``VerifiedHands`` and is additionally gated by
  ``config.allow_writes`` AND a per-call ``confirm=True``. Both are required.

Selector caveat
---------------
These selectors are written from the Phase 5 UI description. They are resilient
(role/text based) but have NOT yet been tuned against a live session because no
credentials were available at build time. The ``_S`` table below is the single
place to adjust them after the first live read-only run.
"""

from __future__ import annotations

import re
import time
from typing import Callable, Optional

from playwright.sync_api import (
    sync_playwright,
    Browser,
    BrowserContext,
    Page,
    TimeoutError as PWTimeout,
    Locator,
)

from .base import (
    NetworkAdapter,
    Device,
    DeviceType,
    PortStatus,
    CableDiagnostic,
    Alarm,
    ActionResult,
    LinkState,
    OnlineState,
)
from ..config import (
    ReyeeConfig,
    load_config,
    LOGIN_URL,
    OVERVIEW_URL,
    ROUTE_POE,
    ROUTE_DEVICES,
    ROUTE_ALARMS,
)
from ..registry import reyee_project_for
from ..verified_hands import VerifiedHands


# --------------------------------------------------------------------------- #
# Selector table — the one place to tune selectors after a live run.
# --------------------------------------------------------------------------- #
_S = {
    # Login page
    "login_email": "input[type='text'], input[type='email'], input[name*='user' i], input[placeholder*='mail' i]",
    "login_password": "input[type='password']",
    "login_button": "button:has-text('Login'), button:has-text('Log In'), button[type='submit']",
    # Project selector (top-left dropdown inside project view)
    "project_dropdown": "[class*='project'] [class*='select'], .project-select, [class*='ProjectSelect']",
    # Generic "logged-in" marker: the global menu container renders.
    "app_shell": "[class*='menu'], [class*='layout'], #app, .app-container",
}


class _RateLimiter:
    """Enforce a minimum interval between portal navigations."""

    def __init__(self, min_interval: float, clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] = time.sleep):
        self.min_interval = min_interval
        self._clock = clock
        self._sleep = sleep
        self._last = 0.0

    def wait(self) -> None:
        now = self._clock()
        delta = now - self._last
        if delta < self.min_interval:
            self._sleep(self.min_interval - delta)
        self._last = self._clock()


class ReyeeAdapter(NetworkAdapter):
    name = "reyee"

    def __init__(self, config: Optional[ReyeeConfig] = None,
                 hands: Optional[VerifiedHands] = None):
        self.cfg = config or load_config()
        self.hands = hands or VerifiedHands()
        self._pw = None
        self._browser: Optional[Browser] = None
        self._ctx: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._rl = _RateLimiter(self.cfg.min_nav_interval)
        self._current_project: Optional[str] = None

    # ------------------------------------------------------------------ #
    # lifecycle / session
    # ------------------------------------------------------------------ #
    def _start(self) -> None:
        if self._page is not None:
            return
        if not self.cfg.has_credentials:
            raise RuntimeError(
                "REYEE_USER / REYEE_PASS are not set. Add them to .env before "
                "using the Reyee adapter."
            )
        self._pw = sync_playwright().start()
        launch_kwargs = {"headless": self.cfg.headless}
        if self.cfg.chromium_path:
            launch_kwargs["executable_path"] = self.cfg.chromium_path
        self._browser = self._pw.chromium.launch(**launch_kwargs)
        storage = self.cfg.storage_state_path
        ctx_kwargs = {}
        import os
        if storage and os.path.exists(storage):
            ctx_kwargs["storage_state"] = storage
        self._ctx = self._browser.new_context(**ctx_kwargs)
        self._ctx.set_default_timeout(self.cfg.nav_timeout_ms)
        self._page = self._ctx.new_page()
        self._ensure_session()

    def _ensure_session(self) -> None:
        """Load the overview; log in if the portal bounced us to SSO."""
        page = self._page
        assert page is not None
        self._rl.wait()
        self._retry(lambda: page.goto(OVERVIEW_URL, wait_until="domcontentloaded"))

        if self._on_login_page():
            self._login()

        # confirm the app shell rendered
        try:
            page.wait_for_selector(_S["app_shell"], timeout=self.cfg.nav_timeout_ms)
        except PWTimeout:
            # one more login attempt in case the redirect was slow
            if self._on_login_page():
                self._login()
        self._save_state()

    def _on_login_page(self) -> bool:
        page = self._page
        assert page is not None
        if "sso/login" in (page.url or ""):
            return True
        try:
            return page.locator(_S["login_password"]).first.is_visible(timeout=2000)
        except Exception:
            return False

    def _login(self) -> None:
        page = self._page
        assert page is not None
        if "sso/login" not in (page.url or ""):
            self._rl.wait()
            self._retry(lambda: page.goto(LOGIN_URL, wait_until="domcontentloaded"))
        page.wait_for_selector(_S["login_password"], timeout=self.cfg.nav_timeout_ms)
        page.locator(_S["login_email"]).first.fill(self.cfg.user)
        page.locator(_S["login_password"]).first.fill(self.cfg.password)
        page.locator(_S["login_button"]).first.click()
        # success = we leave the SSO origin and the app shell appears
        page.wait_for_url(lambda u: "sso/login" not in u, timeout=self.cfg.nav_timeout_ms)
        page.wait_for_selector(_S["app_shell"], timeout=self.cfg.nav_timeout_ms)
        self._save_state()

    def _save_state(self) -> None:
        if self._ctx and self.cfg.storage_state_path:
            try:
                self._ctx.storage_state(path=self.cfg.storage_state_path)
            except Exception:
                pass

    def close(self) -> None:
        for closer in (
            lambda: self._ctx and self._ctx.close(),
            lambda: self._browser and self._browser.close(),
            lambda: self._pw and self._pw.stop(),
        ):
            try:
                closer()
            except Exception:
                pass
        self._page = self._ctx = self._browser = self._pw = None

    # ------------------------------------------------------------------ #
    # low-level helpers
    # ------------------------------------------------------------------ #
    def _retry(self, fn: Callable[[], object]):
        """Retry a navigation with exponential backoff on transient errors."""
        last = None
        for attempt in range(self.cfg.max_retries):
            try:
                return fn()
            except PWTimeout as e:
                last = e
                time.sleep(self.cfg.backoff_base ** attempt)
        if last:
            raise last

    def _goto_route(self, route: str, wait_selector: Optional[str] = None) -> Page:
        """Navigate a hash route inside the SPA and wait for the DOM to settle."""
        self._start()
        page = self._page
        assert page is not None
        self._rl.wait()
        # Setting location.hash performs client-side routing without a reload.
        hash_only = route if route.startswith("#") else "#" + route
        self._retry(lambda: page.evaluate("h => { window.location.hash = h; }",
                                          hash_only.lstrip("#")))
        # networkidle is a good SPA settle signal; guarded by nav timeout.
        try:
            page.wait_for_load_state("networkidle", timeout=self.cfg.nav_timeout_ms)
        except PWTimeout:
            pass
        if wait_selector:
            page.wait_for_selector(wait_selector, timeout=self.cfg.nav_timeout_ms)
        return page

    def _select_project(self, project_name: str) -> None:
        """Select a project from the top-left project dropdown, if needed."""
        if self._current_project == project_name:
            return
        page = self._page
        assert page is not None
        # Open the dropdown then pick the entry whose text matches the project.
        try:
            page.locator(_S["project_dropdown"]).first.click(timeout=5000)
            option = page.get_by_text(project_name, exact=True).first
            option.wait_for(timeout=self.cfg.nav_timeout_ms)
            option.click()
            page.wait_for_load_state("networkidle", timeout=self.cfg.nav_timeout_ms)
            self._current_project = project_name
        except PWTimeout:
            # If the dropdown already shows the target project, treat as selected.
            self._current_project = project_name

    def _project(self, site_id: str) -> str:
        return reyee_project_for(site_id)

    # ------------------------------------------------------------------ #
    # READS
    # ------------------------------------------------------------------ #
    def list_devices(self, site_id: str, device_type: Optional[DeviceType] = None) -> list[Device]:
        project = self._project(site_id)
        page = self._goto_route(ROUTE_DEVICES, wait_selector="table")
        self._select_project(project)
        # re-land on devices route after project switch
        page = self._goto_route(ROUTE_DEVICES, wait_selector="table")

        if device_type is not None:
            self._click_device_tab(device_type)

        return self._scrape_device_rows(device_type)

    def _click_device_tab(self, device_type: DeviceType) -> None:
        page = self._page
        assert page is not None
        tab_label = {
            DeviceType.SWITCH: "Switch",
            DeviceType.AP: "AP",
            DeviceType.WIRELESS_BRIDGE: "Wireless Bridge",
            DeviceType.CAMERA: "Camera",
        }.get(device_type)
        if not tab_label:
            return
        try:
            page.get_by_role("tab", name=re.compile(tab_label, re.I)).first.click(timeout=5000)
            page.wait_for_load_state("networkidle", timeout=self.cfg.nav_timeout_ms)
        except Exception:
            # Fall back to a text-based tab click.
            try:
                page.get_by_text(re.compile(rf"^{re.escape(tab_label)}\b", re.I)).first.click(timeout=3000)
            except Exception:
                pass

    def _scrape_device_rows(self, device_type: Optional[DeviceType]) -> list[Device]:
        page = self._page
        assert page is not None
        page.wait_for_selector("table tbody tr", timeout=self.cfg.nav_timeout_ms)
        rows = page.locator("table tbody tr")
        out: list[Device] = []
        for i in range(rows.count()):
            cells = rows.nth(i).locator("td")
            texts = [self._txt(cells.nth(j)) for j in range(cells.count())]
            if not any(texts):
                continue
            dev = self._device_from_cells(texts, rows.nth(i))
            if device_type is not None:
                dev.device_type = device_type
            out.append(dev)
        return out

    def _device_from_cells(self, texts: list[str], row: Locator) -> Device:
        """Heuristically map a device row's cells to a Device.

        Columns (per brief): Status dot, Device Name, Sync state, IP, Firmware, MAC.
        SN is often shown in a details column or tooltip; we capture MAC/IP as
        stable identifiers and keep the full row in ``raw``.
        """
        joined = " | ".join(texts)
        ip = _first(re.search(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", joined))
        mac = _first(re.search(r"\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b", joined))
        sn = _first(re.search(r"\b[A-Z0-9]{10,}\b", joined))  # SN-ish token
        # status dot: look at the first cell's title/class for online/offline
        status = OnlineState.UNKNOWN
        try:
            cls = (row.locator("td").first.locator("[class*='status'], [class*='dot'], i, span").first
                   .get_attribute("class") or "").lower()
            if "online" in cls or "success" in cls or "green" in cls:
                status = OnlineState.ONLINE
            elif "offline" in cls or "error" in cls or "gray" in cls or "grey" in cls:
                status = OnlineState.OFFLINE
        except Exception:
            pass
        # name = first non-empty text cell that isn't ip/mac/status
        name = ""
        for t in texts:
            if t and t not in (ip, mac) and not re.fullmatch(r"[•●\s]*", t):
                name = t
                break
        return Device(
            sn=sn or mac or name,
            name=name,
            status=status,
            ip=ip,
            mac=mac,
            raw={"cells": texts},
        )

    def get_switch_status(self, site_id: str, switch_id: str) -> Optional[Device]:
        return self._find_device(site_id, switch_id, DeviceType.SWITCH)

    def get_camera_status(self, site_id: str, camera_id: str) -> Optional[Device]:
        # Cameras usually attach as downlink clients; try camera tab then all.
        dev = self._find_device(site_id, camera_id, DeviceType.CAMERA)
        return dev or self._find_device(site_id, camera_id, None)

    def _find_device(self, site_id: str, needle: str, dtype: Optional[DeviceType]) -> Optional[Device]:
        needle_l = (needle or "").strip().lower()
        for d in self.list_devices(site_id, dtype):
            hay = " ".join([d.sn, d.name, d.mac, d.ip]).lower()
            if needle_l and needle_l in hay:
                return d
        return None

    def get_ports(self, site_id: str, switch_id: str) -> list[PortStatus]:
        project = self._project(site_id)
        page = self._goto_route(ROUTE_POE, wait_selector="body")
        self._select_project(project)
        page = self._goto_route(ROUTE_POE, wait_selector="body")
        self._focus_switch_block(switch_id)
        return self._scrape_ports(switch_id)

    def _focus_switch_block(self, switch_id: str) -> Optional[Locator]:
        """Return the PoE page block for the given switch (by SN/name/IP)."""
        page = self._page
        assert page is not None
        needle = (switch_id or "").strip()
        try:
            block = page.locator(
                "xpath=//*[contains(text(), '" + needle + "')]/ancestor::*[.//text()][1]"
            ).first
            block.wait_for(timeout=8000)
            return block
        except Exception:
            return None

    def _scrape_ports(self, switch_id: str) -> list[PortStatus]:
        page = self._page
        assert page is not None
        # Port tiles are small numbered elements; hover reveals a tooltip with
        # Port ID / Port Status / Speed / Flow / Rate / Total packets / media.
        tiles = page.locator(
            "[class*='port'] [class*='tile'], [class*='port-item'], [class*='portItem']"
        )
        out: list[PortStatus] = []
        count = tiles.count()
        for i in range(count):
            tile = tiles.nth(i)
            label = self._txt(tile)
            if not re.fullmatch(r"\d+", label or ""):
                continue
            ps = PortStatus(port_id=label)
            try:
                tile.hover()
                page.wait_for_selector("[class*='tooltip'], [role='tooltip']", timeout=3000)
                tip = self._txt(page.locator("[class*='tooltip'], [role='tooltip']").first)
                self._fill_port_from_tooltip(ps, tip)
            except Exception:
                pass
            out.append(ps)
        return out

    @staticmethod
    def _fill_port_from_tooltip(ps: PortStatus, tip: str) -> None:
        ps.raw["tooltip"] = tip
        low = tip.lower()
        if re.search(r"status[^a-z]*up", low):
            ps.status = LinkState.UP
        elif re.search(r"status[^a-z]*down", low):
            ps.status = LinkState.DOWN
        ps.speed = _kv(tip, r"speed")
        ps.flow = _kv(tip, r"flow")
        ps.rate = _kv(tip, r"rate")
        ps.total_packets = _kv(tip, r"total packets|packets")
        ps.media_type = _kv(tip, r"media")

    def get_alarms(self, level: str = "NORMAL") -> list[Alarm]:
        route = ROUTE_ALARMS
        if level and level != "NORMAL":
            route = route.replace("level=NORMAL", f"level={level}")
        page = self._goto_route(route, wait_selector="table")
        try:
            page.wait_for_selector("table tbody tr", timeout=self.cfg.nav_timeout_ms)
        except PWTimeout:
            return []
        rows = page.locator("table tbody tr")
        out: list[Alarm] = []
        for i in range(rows.count()):
            cells = rows.nth(i).locator("td")
            t = [self._txt(cells.nth(j)) for j in range(cells.count())]
            if not any(t):
                continue
            # Columns: Alarm Type | Severity | Group(project) | Alarm Source |
            #          Device SN | Alias | Generated at
            out.append(Alarm(
                alarm_type=_at(t, 0),
                severity=_at(t, 1),
                group_project=_at(t, 2),
                alarm_source=_at(t, 3),
                device_sn=_at(t, 4),
                alias=_at(t, 5),
                generated_at=_at(t, 6),
                raw={"cells": t},
            ))
        return out

    # ------------------------------------------------------------------ #
    # WRITES (double-gated: config.allow_writes AND confirm=True)
    # ------------------------------------------------------------------ #
    def _guard_write(self, action: str, confirm: bool) -> Optional[ActionResult]:
        if not confirm:
            return ActionResult(action=action, target="", ok=False, confirmed=False,
                                message="refused: confirm=False (safety)")
        if not self.cfg.allow_writes:
            return ActionResult(action=action, target="", ok=False, confirmed=False,
                                message="refused: REYEE_ALLOW_WRITES is not enabled (safety gate)")
        return None

    def reboot_port(self, site_id: str, switch_id: str, port: str, confirm: bool = False) -> ActionResult:
        blocked = self._guard_write("reboot_port", confirm)
        if blocked:
            blocked.target = f"{switch_id}:port{port}"
            return blocked

        project = self._project(site_id)
        self._goto_route(ROUTE_POE, wait_selector="body")
        self._select_project(project)
        self._goto_route(ROUTE_POE, wait_selector="body")
        self._focus_switch_block(switch_id)
        page = self._page
        assert page is not None

        def execute():
            # Click the numbered port tile, then "PoE Restart" in the Port Operation panel.
            tile = page.locator(f"[class*='port'] :text-is('{port}')").first
            tile.click(timeout=self.cfg.nav_timeout_ms)
            page.wait_for_selector(":text('Port Operation')", timeout=self.cfg.nav_timeout_ms)
            page.get_by_role("button", name=re.compile(r"PoE\s*Restart", re.I)).first.click(
                timeout=self.cfg.nav_timeout_ms)

        def poll():
            ports = self._scrape_ports(switch_id)
            return next((p for p in ports if p.port_id == str(port)), None)

        def confirm_fn(state: Optional[PortStatus]) -> bool:
            # After a PoE bounce the port comes back Up (client re-links).
            return bool(state and state.status == LinkState.UP)

        res = self.hands.do(
            action="reboot_port",
            target=f"{switch_id}:port{port}",
            before=poll,
            execute=execute,
            poll=poll,
            confirm=confirm_fn,
        )
        return res

    def run_cable_diagnostic(self, site_id: str, switch_id: str, port: str) -> CableDiagnostic:
        project = self._project(site_id)
        self._goto_route(ROUTE_DEVICES, wait_selector="table")
        self._select_project(project)
        # Open the switch's Device Information -> Cable Test panel.
        page = self._page
        assert page is not None
        self._open_device_info(switch_id)
        # Cable Test panel
        try:
            page.get_by_text(re.compile(r"Cable\s*Test", re.I)).first.click(timeout=8000)
        except Exception:
            pass
        # select the port tile
        page.locator(f"[class*='port'] :text-is('{port}')").first.click(
            timeout=self.cfg.nav_timeout_ms)
        page.wait_for_selector(f":text('Port: Port {port}')", timeout=8000)
        # click Diagnose
        page.get_by_role("button", name=re.compile(r"Diagnose", re.I)).first.click(
            timeout=self.cfg.nav_timeout_ms)
        # results row for this port
        page.wait_for_selector("table tbody tr", timeout=self.cfg.nav_timeout_ms)
        row = page.locator("table tbody tr").filter(has_text=re.compile(rf"\b{re.escape(str(port))}\b")).first
        cells = row.locator("td")
        t = [self._txt(cells.nth(j)) for j in range(cells.count())]
        # Columns: Port | Cable Length(cm) | Diagnosis Result | Update Time
        length = None
        m = re.search(r"\d+", _at(t, 1))
        if m:
            length = int(m.group())
        diag = CableDiagnostic(
            port=str(port),
            cable_length_cm=length,
            diagnosis_result=_at(t, 2),
            update_time=_at(t, 3),
            raw={"cells": t},
        )
        _parse_diagnosis(diag)
        return diag

    def _open_device_info(self, switch_id: str) -> None:
        page = self._page
        assert page is not None
        try:
            row = page.locator("table tbody tr").filter(
                has_text=re.compile(re.escape(switch_id), re.I)).first
            row.get_by_text(re.compile(r"(Device )?Details|Information", re.I)).first.click(timeout=5000)
        except Exception:
            # fall back: click the row itself
            try:
                page.locator("table tbody tr").filter(
                    has_text=re.compile(re.escape(switch_id), re.I)).first.click(timeout=5000)
            except Exception:
                pass
        page.wait_for_load_state("networkidle", timeout=self.cfg.nav_timeout_ms)

    def reboot_switch(self, site_id: str, switch_id: str, confirm: bool = False) -> ActionResult:
        blocked = self._guard_write("reboot_switch", confirm)
        if blocked:
            blocked.target = switch_id
            return blocked

        project = self._project(site_id)
        self._goto_route(ROUTE_DEVICES, wait_selector="table")
        self._select_project(project)
        self._goto_route(ROUTE_DEVICES, wait_selector="table")
        page = self._page
        assert page is not None

        def execute():
            row = page.locator("table tbody tr").filter(
                has_text=re.compile(re.escape(switch_id), re.I)).first
            # power icon = reboot
            row.locator("[class*='power'], [title*='Reboot' i], [aria-label*='Reboot' i]").first.click(
                timeout=self.cfg.nav_timeout_ms)
            page.wait_for_selector(":text('Reboot')", timeout=self.cfg.nav_timeout_ms)
            page.get_by_role("button", name=re.compile(r"Confirm", re.I)).first.click(
                timeout=self.cfg.nav_timeout_ms)

        def poll():
            return self.get_switch_status(site_id, switch_id)

        def confirm_fn(state: Optional[Device]) -> bool:
            # Switch goes offline then returns online; confirm it's back online.
            return bool(state and state.status == OnlineState.ONLINE)

        # A full switch reboot takes longer; extend the confirmation window.
        patient = VerifiedHands(settle_seconds=20.0, poll_interval=10.0, timeout_seconds=240.0)
        return patient.do(
            action="reboot_switch",
            target=switch_id,
            before=poll,
            execute=execute,
            poll=poll,
            confirm=confirm_fn,
        )

    # ------------------------------------------------------------------ #
    # tiny utils
    # ------------------------------------------------------------------ #
    @staticmethod
    def _txt(loc: Locator) -> str:
        try:
            return (loc.inner_text(timeout=2000) or "").strip()
        except Exception:
            return ""


# --------------------------------------------------------------------------- #
# module-level parse helpers
# --------------------------------------------------------------------------- #
def _first(m) -> str:
    return m.group(0) if m else ""


def _at(lst: list[str], i: int) -> str:
    return lst[i].strip() if 0 <= i < len(lst) else ""


def _kv(text: str, key_regex: str) -> str:
    """Pull a 'Key: value' style field out of a tooltip blob."""
    m = re.search(rf"(?:{key_regex})\s*[:：]\s*([^\n|]+)", text, re.I)
    return m.group(1).strip() if m else ""


def _parse_diagnosis(diag: CableDiagnostic) -> None:
    """Map the raw Diagnosis Result into structured health flags."""
    raw = (diag.diagnosis_result or "").lower()
    diag.short = "short" in raw
    diag.break_detected = "break" in raw or "open" in raw
    # "Normal" / "OK" / "Good" => cable ok
    diag.cable_ok = bool(re.search(r"normal|good|\bok\b|pass", raw)) and not (diag.short or diag.break_detected)
    if diag.cable_ok:
        diag.connector_health = "ok"
    elif diag.short:
        diag.connector_health = "bad"
    elif diag.break_detected:
        diag.connector_health = "bad"
    elif raw:
        diag.connector_health = "degraded"
    else:
        diag.connector_health = "unknown"
