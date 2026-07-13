#!/usr/bin/env python3
"""Reyee adapter — READ-ONLY smoke test against the Laquinta project.

This script performs ONLY read operations:
    * list devices (all + switch tab)
    * get switch status (N.E.PoleSwitch / G1T02L0000028)
    * get port status for that switch
    * get global alarms

It NEVER calls reboot_port, reboot_switch, or run_cable_diagnostic. Those are
write/impacting actions and are intentionally not reachable from here.

Usage:
    # put REYEE_USER / REYEE_PASS in .env first, then:
    python scripts/reyee_readonly_test.py
    python scripts/reyee_readonly_test.py --headed     # watch it run
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from av_shield_agents.adapters import ReyeeAdapter, DeviceType  # noqa: E402
from av_shield_agents.config import load_config  # noqa: E402

SITE_ID = "laquinta"
SWITCH_SN = "G1T02L0000028"          # N.E.PoleSwitch, ES206GS-P, 192.168.1.58


def dump(label, obj):
    print(f"\n===== {label} =====")
    if isinstance(obj, list):
        print(f"({len(obj)} item(s))")
        for x in obj:
            print(json.dumps(x.to_dict() if hasattr(x, "to_dict") else x, indent=2))
    elif obj is None:
        print("None")
    else:
        print(json.dumps(obj.to_dict() if hasattr(obj, "to_dict") else obj, indent=2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--headed", action="store_true", help="run with a visible browser")
    args = ap.parse_args()

    cfg = load_config()
    if not cfg.has_credentials:
        print("ERROR: REYEE_USER / REYEE_PASS are not set. Add them to .env.", file=sys.stderr)
        return 2
    if args.headed:
        cfg.headless = False
    # Belt-and-suspenders: guarantee no writes can fire from this script.
    cfg.allow_writes = False

    print(f"Reyee READ-ONLY test | site_id={SITE_ID} | headless={cfg.headless}")
    with ReyeeAdapter(config=cfg) as rx:
        dump("ALL DEVICES", rx.list_devices(SITE_ID))
        dump("SWITCHES", rx.list_devices(SITE_ID, DeviceType.SWITCH))
        dump("SWITCH STATUS (N.E.PoleSwitch)", rx.get_switch_status(SITE_ID, SWITCH_SN))
        dump("PORTS", rx.get_ports(SITE_ID, SWITCH_SN))
        dump("ALARMS", rx.get_alarms())

    print("\nDone. (No write actions were performed.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
