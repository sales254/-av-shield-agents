import sys
MAIN = "/root/-av-shield-agents/sasha_survey.py"

OLD = "                max_tokens=2000,\n                system=SURVEY_SYSTEM_PROMPT,"
NEW = "                max_tokens=4000,\n                system=SURVEY_SYSTEM_PROMPT,"

src = open(MAIN).read()
if src.count(OLD) != 1:
    print(f"FAIL: anchor not unique/missing ({src.count(OLD)}x) - NOT modified"); sys.exit(1)

src = src.replace(OLD, NEW, 1)
try:
    compile(src, MAIN, "exec")
except SyntaxError as e:
    print("FAIL: syntax error - NOT modified:", e); sys.exit(1)

open(MAIN, "w").write(src)
print("OK: max_tokens raised to 4000")
