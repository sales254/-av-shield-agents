#!/usr/bin/env python
# ============================================================
# patch_existing_customer.py — drop-safe wiring of the
# existing-customer gate into the SMS (webhook.py) and Voice
# (voice_agent.py) paths.
#
# - Timestamped backups before any write.
# - Idempotent: re-running is a no-op once markers are present.
# - Fails loudly if an expected anchor is missing (no silent partial).
# Run:  ./venv/bin/python patch_existing_customer.py
# ============================================================
import os
import shutil
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
MARKER = "EXISTING CUSTOMER GATE"  # idempotency sentinel


def backup(path):
    dst = f"{path}.bak_excustomer_{STAMP}"
    shutil.copy2(path, dst)
    print(f"  backup -> {os.path.basename(dst)}")


def patch_file(path, edits, marker=MARKER):
    with open(path) as f:
        src = f.read()
    if marker in src:
        print(f"[skip] {os.path.basename(path)} already patched ({marker!r} present)")
        return False
    backup(path)
    for anchor, replacement in edits:
        if anchor not in src:
            raise SystemExit(f"[FAIL] anchor not found in {path}:\n---\n{anchor}\n---")
        if src.count(anchor) != 1:
            raise SystemExit(f"[FAIL] anchor not unique ({src.count(anchor)}x) in {path}")
        src = src.replace(anchor, replacement, 1)
    with open(path, "w") as f:
        f.write(src)
    print(f"[ok]   patched {os.path.basename(path)}")
    return True


# ----------------------------------------------------------------
# webhook.py  (SMS)
# ----------------------------------------------------------------
WEBHOOK = os.path.join(HERE, "webhook.py")

# Hunk 1: module-level state for support-routed numbers.
WH_ANCHOR_1 = "pending_survey = {}\n"
WH_REPLACE_1 = (
    "pending_survey = {}\n"
    "support_routed = set()  # phones already routed to support (existing customers)\n"
)

# Hunk 2: the gate itself, just before the qualification-state block.
WH_ANCHOR_2 = (
    "            # Get or create conversation state for this phone number\n"
    "            if phone not in conversation_states:\n"
)
WH_REPLACE_2 = (
    "            # --- EXISTING CUSTOMER GATE: existing customers skip qualification ---\n"
    "            # Already-routed support thread: keep logging, never qualify.\n"
    "            if phone in support_routed:\n"
    "                try:\n"
    "                    import sasha_ghl\n"
    "                    _c = sasha_ghl.search_contact(phone=phone)\n"
    "                    if _c and _c.get('id'):\n"
    "                        sasha_ghl.add_note(_c['id'],\n"
    "                            f'INBOUND SMS (existing customer, support thread)\\nMessage: {message}',\n"
    "                            agent='Sasha')\n"
    "                except Exception as e:\n"
    "                    logging.error(f'support-thread log error: {e}')\n"
    "                event_queue.task_done()\n"
    "                continue\n"
    "\n"
    "            # New phone: silent CRM check before running the qualifier.\n"
    "            if phone not in conversation_states:\n"
    "                try:\n"
    "                    from sasha_existing_customer_lookup import lookup_existing_customer\n"
    "                    _cust = lookup_existing_customer(phone)\n"
    "                except Exception as e:\n"
    "                    _cust = None\n"
    "                    logging.error(f'existing-customer lookup error: {e}')\n"
    "                if _cust:\n"
    "                    import sasha_ghl\n"
    "                    _cid = _cust.get('id', '')\n"
    "                    _cname = _cust.get('firstName') or contact_name or 'there'\n"
    "                    _kw = ['camera','offline','not working','down','issue','problem','help','broken','recording','access']\n"
    "                    _is_support = any(k in message.lower() for k in _kw)\n"
    "                    if _cid:\n"
    "                        try:\n"
    "                            sasha_ghl.add_note(_cid,\n"
    "                                f'INBOUND SMS (existing customer)\\nMessage: {message}', agent='Sasha')\n"
    "                            if _is_support:\n"
    "                                sasha_ghl.add_tags(_cid, ['support-request'])\n"
    "                                sasha_ghl.create_support_ticket(_cid, f'Inbound SMS — {message}', priority='normal')\n"
    "                        except Exception as e:\n"
    "                            logging.error(f'existing-customer GHL log error: {e}')\n"
    "                    send_sms(phone,\n"
    "                        f'Hi {_cname}, thanks for reaching out to AV Surveillance — great to hear from you! '\n"
    "                        f\"I've passed this to our team and someone will follow up shortly.\")\n"
    "                    support_routed.add(phone)\n"
    "                    logging.info(f'EXISTING CUSTOMER routed to support: {phone}')\n"
    "                    event_queue.task_done()\n"
    "                    continue\n"
    "\n"
    "            # Get or create conversation state for this phone number\n"
    "            if phone not in conversation_states:\n"
)

# ----------------------------------------------------------------
# voice_agent.py  (Voice) — replace the broad inline tag check.
# ----------------------------------------------------------------
VOICE = os.path.join(HERE, "voice_agent.py")

VC_ANCHOR = (
    "    # Check CRM — existing customer or new lead?\n"
    "    contact = search_contact(phone=from_number)\n"
    "    is_existing = False\n"
    "\n"
    "    if contact:\n"
    "        existing_tags = contact.get(\"tags\", [])\n"
    "        existing_customer_tags = [\n"
    "            \"parsey\", \"installation agreement\",\n"
    "            \"new customer\", \"reactivation\"\n"
    "        ]\n"
    "        if any(t in existing_tags for t in existing_customer_tags):\n"
    "            is_existing = True\n"
)
VC_REPLACE = (
    "    # Check CRM — existing customer or new lead?  (EXISTING CUSTOMER GATE)\n"
    "    # Single signal = signed installation agreement; see\n"
    "    # sasha_existing_customer_lookup.EXISTING_CUSTOMER_TAGS. Fail-open.\n"
    "    from sasha_existing_customer_lookup import is_existing_customer\n"
    "    contact = search_contact(phone=from_number)\n"
    "    is_existing = is_existing_customer(contact)\n"
)


def main():
    print(f"== patch_existing_customer.py  ({STAMP}) ==")
    changed = False
    changed |= patch_file(WEBHOOK, [(WH_ANCHOR_1, WH_REPLACE_1), (WH_ANCHOR_2, WH_REPLACE_2)])
    changed |= patch_file(VOICE, [(VC_ANCHOR, VC_REPLACE)])
    print("== done ==" if changed else "== no changes (already patched) ==")


if __name__ == "__main__":
    main()
