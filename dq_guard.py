import re as _re

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
        if not _re.search(r"\b(?:tier|option|number|#)?\s*([1-4])\b", bt):
            for mm in _re.findall(r"\$\s*([0-9][0-9,\.]*)\s*(k|thousand)?|([0-9][0-9,\.]*)\s*(k|thousand)\b", bt):
                raw = mm[0] or mm[2]; suf = mm[1] or mm[3]
                if raw:
                    num = float(raw.replace(",","")) * (1000 if suf else 1)
                    if 0 < num < 10000:
                        return True
    rebuffed = any("rebuff" in str(t).lower() for t in state.tags)
    if rebuffed and ("recording only" in blob or "recording-only" in blob):
        return True
    return False
