# AV Shield — Network Device Control Layer

Provider-agnostic adapters the brain uses to read status and drive **verified**
actions on physical network gear. **Phase 5 ships the Reyee / Ruijie Cloud
adapter.** Lysora and UNV are untouched by this phase.

> **Heads-up (Phase 5 build note):** the Phase 5 brief referred to an *existing*
> `adapters/base.py`, `VerifiedHands`, a `brain`, and a site→project registry.
> None of those existed in this repo (it's the Sasha/GHL sales+survey codebase),
> so this package was created fresh and self-contained. Nothing in the existing
> Sasha code was modified.

## Layout

```
av_shield_agents/
  adapters/
    base.py        # NetworkAdapter interface + data models (Device, PortStatus,
                   #   CableDiagnostic, Alarm, ActionResult)
    reyee.py       # ReyeeAdapter — Playwright automation of the Ruijie SPA
  verified_hands.py# VerifiedHands: execute -> wait -> re-poll -> confirm
  registry.py      # site_id -> Reyee project name  (seeded: laquinta -> Laquinta)
  config.py        # env-driven config (REYEE_USER/PASS, safety gate, etc.)
scripts/
  reyee_readonly_test.py   # READ-ONLY smoke test against Laquinta
```

## Setup

```bash
pip install -r requirements.txt
playwright install chromium          # one-time browser download
cp av_shield_agents/.env.reyee.example .env    # then fill in creds
```

## Capabilities (behind `NetworkAdapter`)

| Method | Route | Kind |
| --- | --- | --- |
| `list_devices` / `list_cameras` / `list_switches` | `#/monitor_devicesV2_menu` | read |
| `get_switch_status` / `get_camera_status` | devices list | read |
| `get_ports` | `#/monitor_overview_poe_menu` | read |
| `get_alarms` | `#/monitor_overview_global_menu?hash=alarm` | read |
| `run_cable_diagnostic` | devices → Cable Test | read-ish (runs a test) |
| `reboot_port` | PoE → Port Operation → **PoE Restart** | **write** |
| `reboot_switch` | devices → power icon → Confirm | **write** |

### Safety model for writes

`reboot_port` and `reboot_switch` are **double-gated**. A write only fires when
**both** hold:

1. `REYEE_ALLOW_WRITES=1` in the environment, **and**
2. the call passes `confirm=True`.

Otherwise the call returns an `ActionResult` with `ok=False` and a `refused:`
message. Every write is driven through `VerifiedHands`, which executes the
action, waits for the device to settle, then re-polls until the expected
post-condition holds (port back Up / switch back online) or it times out.

## Read-only test (do this first)

```bash
python scripts/reyee_readonly_test.py            # headless
python scripts/reyee_readonly_test.py --headed   # watch it
```

It only lists devices, reads switch/port status, and reads alarms. It never
calls a write action.

## Verification status (as of this commit)

- Package imports, compiles, and passes offline logic self-tests: VerifiedHands
  (confirm + timeout paths), diagnosis parsing, write safety guards, registry.
- Chromium launches cleanly.
- **Live portal verification is still pending** on two things:
  1. `REYEE_USER` / `REYEE_PASS` are not yet set.
  2. The build/CI environment's egress policy currently **blocks**
     `cloud.ruijienetworks.com` and `cloud-us.ruijienetworks.com` (403 at the
     proxy). Run the read-only test from a network that can reach the portal, or
     allowlist those hosts.
- The selectors in `reyee.py` (`_S` table + inline locators) are written from the
  UI description and are resilient (role/text based), but should get one tuning
  pass against a live session — that first read-only run is exactly where to do
  it.
```
