# ============================================================
# AV SHIELD — survey_trigger.py
# Fires the Visual Survey when Sasha QUALIFIES a lead with an
# address. Texts Shad for one-tap approval before the prospect
# sees anything. Prospect gets a short pre-sell (NO pricing).
# ============================================================

import logging

log = logging.getLogger("survey_trigger")

ADDRESS_KEYS = ["address", "Q5b", "property_address"]


def extract_address(state) -> str:
    answers = getattr(state, "answers", {}) or {}
    for k in ADDRESS_KEYS:
        v = answers.get(k)
        if v and len(str(v).strip()) > 5:
            return str(v).strip()
    return ""


def extract_property_type(state) -> str:
    answers = getattr(state, "answers", {}) or {}
    for k in ["Q2", "property_type", "Q1"]:
        v = answers.get(k)
        if v:
            return str(v)
    return ""


def should_run_survey(state) -> bool:
    if getattr(state, "status", "") != "qualified":
        return False
    if getattr(state, "survey_done", False):
        return False
    return bool(extract_address(state))


def run_survey_for_state(state, agent, send_sms, escalation_phone, pending_store) -> dict:
    from sasha_survey import VisualSurveyAgent, SurveyState

    address = extract_address(state)
    prospect_phone = getattr(state, "phone", "") or ""
    name = getattr(state, "contact_name", "") or "there"

    survey_state = SurveyState(
        contact_name=name,
        phone=prospect_phone,
        contact_id=getattr(state, "contact_id", "") or "",
        address=address,
        property_type=extract_property_type(state),
        qualification_data=getattr(state, "answers", {}) or {},
    )

    analysis = agent.analyze_property(survey_state)
    cams = (analysis or {}).get("camera_recommendation", {}).get("total_cameras", "?")
    risk = (analysis or {}).get("property_analysis", {}).get("risk_level", "")

    # --- AUTO-CREATE DRAFT ESTIMATE (additive; draft only, never sends) ---
    try:
        import sasha_ghl, requests as _rq
        _ncam = int(cams) if str(cams).isdigit() else None
        if _ncam:
            _cid = getattr(state, "contact_id", "") or ""
            _email = ""
            if _cid:
                _cr = _rq.get(f"{sasha_ghl.GHL_BASE_URL}/contacts/{_cid}", headers=sasha_ghl._est_headers())
                _email = (_cr.json().get("contact") or {}).get("email", "") or ""
            _contact = {"id": _cid, "name": name, "phone": prospect_phone, "email": _email}
            _est = sasha_ghl.create_estimate(_ncam, _contact)
            if _est and _est.get("id"):
                _inst = _est.get("install")
                _mo = _est.get("monthly")
                log.info("Auto-created draft estimate for %s", name)
                try:
                    send_sms(escalation_phone, f"DRAFT ready for {name}: ${_inst} install + ${_mo}/mo ({_ncam} cam). Reply: !send {name}")
                except Exception as _e2:
                    log.error("draft SMS failed: %s", _e2)
    except Exception as _e:
        log.error("Auto-create estimate failed (survey still OK): %s", _e)
    # --- END AUTO-CREATE ---

    try:
        from config import GHL_BOOKING_LINK as _BOOK
    except Exception:
        _BOOK = ""

    # Short pre-sell (NO pricing). The survey is the hook; the demo paints the picture.
    pre_sell = (
        f"Hi {name}! We just mapped your property at {address} for AV Shield. "
        f"Our AI survey flagged {cams} key areas worth protecting"
        + (f" ({risk} risk)" if risk else "") + ". "
        f"I'd love to walk you through your custom layout live and show how we STOP "
        f"incidents in real time, not just record them. Takes about 20 min. "
        f"Book here: {_BOOK}"
    )

    pending_store[prospect_phone] = {
        "prospect_phone": prospect_phone,
        "prospect_name": name,
        "proposal": pre_sell,
        "analysis": analysis,
        "approved": False,
    }
    state.survey_done = True

    last4 = prospect_phone[-4:] if len(prospect_phone) >= 4 else prospect_phone
    review_msg = (
        f"SURVEY READY for {name} ({prospect_phone}).\n"
        f"~{cams} cameras. Address: {address}\n\n"
        f"Reply 'YES {last4}' to send the pre-sell + booking link to the prospect, "
        f"or 'NO {last4}' to hold."
    )
    try:
        send_sms(escalation_phone, review_msg)
        log.info("Sent survey approval request to %s for prospect %s",
                 escalation_phone, prospect_phone)
    except Exception as e:
        log.error("Failed to send approval request: %s", e)

    return {"surveyed": True, "cameras": cams, "awaiting_approval": True,
            "prospect_phone": prospect_phone}


def handle_approval_reply(message, from_phone, escalation_phone, send_sms, pending_store):
    if not from_phone or _norm(from_phone) != _norm(escalation_phone):
        return None
    text = (message or "").strip().lower()
    if not (text.startswith("yes") or text.startswith("no")):
        return None

    decision = "yes" if text.startswith("yes") else "no"
    digits = "".join(c for c in text if c.isdigit())
    target = None
    if digits:
        for ph, item in pending_store.items():
            if ph.endswith(digits[-4:]):
                target = ph
                break
    if target is None and len(pending_store) == 1:
        target = next(iter(pending_store))

    if target is None:
        send_sms(escalation_phone,
                 "Couldn't match that approval to a pending survey. "
                 "Reply 'YES <last4>' with the prospect's last 4 digits.")
        return {"matched": False}

    item = pending_store.pop(target)
    if decision == "no":
        log.info("Survey HELD for %s by Shad", target)
        return {"matched": True, "decision": "no", "prospect_phone": target}

    try:
        send_sms(item["prospect_phone"], item["proposal"])
        send_sms(escalation_phone, f"Sent. Pre-sell delivered to {item['prospect_name']}.")
        log.info("Pre-sell sent to prospect %s after approval", target)
    except Exception as e:
        log.error("Failed sending approved message: %s", e)
        send_sms(escalation_phone, f"Error sending to prospect: {e}")
    return {"matched": True, "decision": "yes", "prospect_phone": target}


def _norm(phone):
    return "".join(c for c in str(phone) if c.isdigit())[-10:]
