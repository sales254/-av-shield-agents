import sys
MAIN = "/root/-av-shield-agents/sasha_survey.py"

OLD = "            result = json.loads(response.content[0].text)"

NEW = ('            import re as _re\n'
       '            _raw = response.content[0].text\n'
       '            _raw = _re.sub(r"```json\\s*", "", _raw)\n'
       '            _raw = _re.sub(r"```\\s*", "", _raw)\n'
       '            _m = _re.search(r"\\{.*\\}", _raw, _re.DOTALL)\n'
       '            result = json.loads(_m.group(0) if _m else _raw.strip())')

src = open(MAIN).read()
if "_re.search(r\"\\{.*\\}\"" in src:
    print("ALREADY PATCHED"); sys.exit(0)
if src.count(OLD) != 1:
    print(f"FAIL: anchor not unique/missing ({src.count(OLD)}x) - NOT modified"); sys.exit(1)

src = src.replace(OLD, NEW, 1)
try:
    compile(src, MAIN, "exec")
except SyntaxError as e:
    print("FAIL: syntax error - NOT modified:", e); sys.exit(1)

open(MAIN, "w").write(src)
print("OK: vision JSON parse fixed and validated")
