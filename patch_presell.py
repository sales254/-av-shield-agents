import sys
MAIN = "/root/-av-shield-agents/survey_trigger.py"

OLD = '''    analysis = agent.analyze_property(survey_state)
    proposal = agent.generate_full_proposal(survey_state)

    cams = (analysis or {}).get("camera_recommendation", {}).get("total_cameras", "?")

    # Park the proposal awaiting Shad's approval.
    pending_store[prospect_phone] = {
        "prospect_phone": prospect_phone,
        "prospect_name": name,
        "proposal": proposal,
        "analysis": analysis,
        "approved": False,
    }'''

NEW = '''    analysis = agent.analyze_property(survey_state)

    cams = (analysis or {}).get("camera_recommendation", {}).get("total_cameras", "?")
    risk = (analysis or {}).get("property_analysis", {}).get("risk_level", "")
    try:
        from config import GHL_BOOKING_LINK as _BOOK
    except Exception:
        _BOOK = ""

    # Short pre-sell (NO pricing) — survey is the hook, demo paints the picture.
    pre_sell = (
        f"Hi {name}! We just mapped your property at {address} for AV Shield. "
        f"Our AI survey flagged {cams} key areas worth protecting"
        + (f" ({risk} risk)" if risk else "") + ". "
        f"I'd love to walk you through your custom layout live and show how we STOP "
        f"incidents in real time, not just record them. Takes about 20 min. "
        f"Book here: {_BOOK}"
    )

    # Park the pre-sell awaiting Shad's approval.
    pending_store[prospect_phone] = {
        "prospect_phone": prospect_phone,
        "prospect_name": name,
        "proposal": pre_sell,
        "analysis": analysis,
        "approved": False,
    }'''

src = open(MAIN).read()
if "Short pre-sell" in src:
    print("ALREADY PATCHED"); sys.exit(0)
if src.count(OLD) != 1:
    print(f"FAIL: anchor not unique/missing ({src.count(OLD)}x) - NOT modified"); sys.exit(1)
src = src.replace(OLD, NEW, 1)
try:
    compile(src, MAIN, "exec")
except SyntaxError as e:
    print("FAIL: syntax error - NOT modified:", e); sys.exit(1)
open(MAIN, "w").write(src)
print("OK: pre-sell message wired (no pricing in SMS)")
