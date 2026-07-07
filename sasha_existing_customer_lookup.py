# ============================================================
# AV SHIELD — Sasha existing-customer routing
# sasha_existing_customer_lookup.py
#
# Silent GHL check used BEFORE Sasha's qualification flow on both
# channels (SMS: webhook.py, Voice: voice_agent.py).
#
# If the caller's phone matches a contact carrying the signed-contract
# tag, qualification is skipped and the caller is routed to a support
# greeting instead.
#
# Fails OPEN: any GHL error/timeout is treated as "new lead" so a CRM
# hiccup never blocks or delays an inbound call/text.
# ============================================================

import re
import logging

import sasha_ghl  # reuse existing GHL auth + contact search (get_headers / search_contact)

logger = logging.getLogger("ExistingCustomerLookup")

# ------------------------------------------------------------
# EXISTING-CUSTOMER SIGNAL — single source of truth.
# Per CRM confirmation (2026-06-30): the ONLY tag that marks a
# won/active customer is the completed DocuSign installation agreement.
# Deliberately NOT included (too broad / not-yet-closed):
#   - "reactivation"                  (~64% of all contacts)
#   - "customer tags -> new customer"
#   - "installation agreement - sent" / "- viewed"  (unsigned)
# Matching is normalized + contains, so add full tag strings here.
# ------------------------------------------------------------
EXISTING_CUSTOMER_TAGS = [
    "parsey docusign -> installation agreement - completed",
]


def _norm(s: str) -> str:
    """Lowercase + collapse internal whitespace for tolerant matching."""
    return re.sub(r"\s+", " ", (s or "").strip().lower())


_SIGNALS_NORM = [_norm(t) for t in EXISTING_CUSTOMER_TAGS]


def normalize_phone(phone: str) -> str:
    """Strip formatting; compare on the last 10 digits."""
    return "".join(ch for ch in (phone or "") if ch.isdigit())[-10:]


def is_existing_customer(contact: dict) -> bool:
    """
    Pure tag check on an already-fetched GHL contact dict.
    True only if the contact carries the signed-contract signal tag.
    Used by the voice path, which already fetches the contact.
    """
    if not contact:
        return False
    tags = [_norm(t) for t in (contact.get("tags") or [])]
    return any(sig in t for sig in _SIGNALS_NORM for t in tags)


def lookup_existing_customer(phone: str):
    """
    Phone -> contact dict if (and only if) this caller is an existing
    customer, else None. Fails OPEN (returns None) on any GHL error.
    Used by the SMS path, which has no prior contact fetch.
    """
    if not phone:
        return None
    try:
        contact = sasha_ghl.search_contact(phone=phone)
    except Exception as e:  # network/GHL error -> treat as new lead
        logger.error("lookup_existing_customer GHL error: %s", e)
        return None
    if not contact:
        return None

    # Defensive: confirm the returned contact's phone actually matches the
    # caller before trusting its tags (guards against fuzzy search hits).
    cphone = normalize_phone(contact.get("phone", ""))
    if cphone and normalize_phone(phone) and cphone != normalize_phone(phone):
        return None

    return contact if is_existing_customer(contact) else None


def route_inbound(phone: str, caller_name: str = None) -> dict:
    """
    Step zero for any inbound voice/SMS event. Returns a routing decision.
    Convenience wrapper around lookup_existing_customer().
    """
    contact = lookup_existing_customer(phone)
    if contact:
        name = contact.get("firstName") or caller_name or "there"
        return {
            "route": "support",
            "skip_qualification": True,
            "contact": contact,
            "greeting": (
                f"Hi {name}, thanks for reaching out to AV Surveillance — "
                f"great to hear from you! How can we help today?"
            ),
        }
    return {
        "route": "qualification",
        "skip_qualification": False,
        "contact": None,
        "greeting": None,
    }


if __name__ == "__main__":
    import sys
    test_phone = sys.argv[1] if len(sys.argv) > 1 else ""
    print(f"Signal tags: {EXISTING_CUSTOMER_TAGS}")
    print(f"Lookup for {test_phone!r}:")
    c = lookup_existing_customer(test_phone)
    if c:
        print(f"  EXISTING CUSTOMER -> {c.get('firstName')} {c.get('lastName')} "
              f"(id={c.get('id')}) tags={c.get('tags')}")
    else:
        print("  not an existing customer (or not found / fail-open)")
