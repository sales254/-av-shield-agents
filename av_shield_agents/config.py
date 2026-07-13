"""Config for the Reyee adapter. Reads from environment (.env via python-dotenv).

Follows the repo convention (``load_dotenv()`` + ``os.getenv``).
"""

from __future__ import annotations

import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:  # dotenv optional at import time
    pass


# Portal URLs (from the Phase 5 brief).
LOGIN_URL = "https://cloud.ruijienetworks.com/sso/login"
OVERVIEW_URL = "https://cloud-us.ruijienetworks.com/macc5/adminIntl/#/monitor_overview_global_menu"
PORTAL_ORIGIN = "https://cloud-us.ruijienetworks.com/macc5/adminIntl/#"

# Hash routes.
ROUTE_OVERVIEW = "#/monitor_overview_global_menu"
ROUTE_POE = "#/monitor_overview_poe_menu"
ROUTE_DEVICES = "#/monitor_devicesV2_menu"
ROUTE_ALARMS = "#/monitor_overview_global_menu?hash=alarm&level=NORMAL"


@dataclass
class ReyeeConfig:
    user: str
    password: str
    headless: bool = True
    storage_state_path: str = "storage_state_reyee.json"
    # Optional: point at a specific Chromium binary (e.g. a pre-installed one in
    # a managed environment). Empty => let Playwright use its bundled browser.
    chromium_path: str = ""
    # Rate limiting / politeness (do NOT hammer the portal — it can lock).
    min_nav_interval: float = 2.0        # min seconds between navigations
    nav_timeout_ms: int = 45000          # per-navigation / element wait ceiling
    max_retries: int = 4                 # network/nav retries
    backoff_base: float = 2.0            # exponential backoff base seconds
    # Hard safety gate for destructive actions. Even with confirm=True on a
    # call, writes are refused unless this is also enabled.
    allow_writes: bool = False

    @property
    def has_credentials(self) -> bool:
        return bool(self.user and self.password)


def load_config() -> ReyeeConfig:
    return ReyeeConfig(
        user=os.getenv("REYEE_USER", ""),
        password=os.getenv("REYEE_PASS", ""),
        headless=os.getenv("REYEE_HEADLESS", "1") not in ("0", "false", "False"),
        storage_state_path=os.getenv("REYEE_STORAGE_STATE", "storage_state_reyee.json"),
        chromium_path=os.getenv("REYEE_CHROMIUM_PATH", ""),
        allow_writes=os.getenv("REYEE_ALLOW_WRITES", "0") in ("1", "true", "True"),
    )
