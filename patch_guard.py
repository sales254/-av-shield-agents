import sys, os

MAIN = "/root/-av-shield-agents/sasha_qualifier.py"
GUARD = "/root/-av-shield-agents/dq_guard.py"

GUARD_SRC = '''import re as _re

def hard_disqualify_confirmed(state, result):
    blob = " ".join(str(v).lower() for v in state.answers.values())
    single = any(p in blob for p in ["single family","single-family","my home",
        "house i live","home i live","own home","owner occupied","owner-occupied"])
    biz = any(p in blob for p in ["business","hoa","property management","landlord",
        "multi-family","multi family","apartment","commercial","plaza"])
    if single and not biz:
        return True
    rec = result.get("answer_recorded") or {}
    ql = str(rec.get("question","")).lower()
    if ("8" in ql) or any(w in ql for w in ["budget","invest","range"]):
        bt = str(rec.get("answer","")).lower()
        if not _re.search(r"\\b(?:tier|option|number|#)?\\s*([1-4])\\b", bt):
            for mm in _re.findall(r"\\$\\s*([0-9][0-9,\\.]*)\\s*(k|thousand)?|([0-9][0-9,\\.]*)\\s*(k|thousand)\\b", bt):
                raw = mm[0] or mm[2]; suf = mm[1] or mm[3]
                if raw:
                    num = float(raw.replace(",","")) * (1000 if suf else 1)
                    if 0 < num < 10000:
                        return True
    rebuffed = any("rebuff" in str(t).lower() for t in state.tags)
    if rebuffed and ("recording only" in blob or "recording-only" in blob):
        return True
    return False
'''

OLD = '''        if result.get("status"):
            state.status = result["status"]

        if result.get("is_hot_lead"):
            state.is_hot_lead = True
            state.add_tag(GHL_TAGS["hot_lead"])

        if result.get("answer_recorded"):
            q = result["answer_recorded"].get("question")
            a = result["answer_recorded"].get("answer")
            if q and a:
                state.answers[q] = a'''

NEW = '''        if result.get("answer_recorded"):
            q = result["answer_recorded"].get("question")
            a = result["answer_recorded"].get("answer")
            if q and a:
                state.answers[q] = a

        proposed = result.get("status")
        if proposed == "disqualified":
            if hard_disqualify_confirmed(state, result):
                state.status = "disqualified"
            else:
                state.status = "in_progress"
                result["action"] = "continue"
        elif proposed:
            state.status = proposed

        if result.get("is_hot_lead"):
            state.is_hot_lead = True
            state.add_tag(GHL_TAGS["hot_lead"])'''

IMPORT_AFTER = "import json\n"
IMPORT_LINE = "from dq_guard import hard_disqualify_confirmed\n"

src = open(MAIN).read()

if "hard_disqualify_confirmed" in src:
    print("ALREADY PATCHED"); sys.exit(0)
if OLD not in src:
    print("FAIL: block not found exactly - file NOT modified"); sys.exit(1)

new_src = src.replace(OLD, NEW, 1)
if IMPORT_LINE not in new_src:
    new_src = new_src.replace(IMPORT_AFTER, IMPORT_AFTER + IMPORT_LINE, 1)

try:
    compile(new_src, MAIN, "exec")
    compile(GUARD_SRC, GUARD, "exec")
except SyntaxError as e:
    print("FAIL: syntax error - file NOT modified:", e); sys.exit(1)

open(GUARD, "w").write(GUARD_SRC)
open(MAIN, "w").write(new_src)
print("OK: guard added and validated")
