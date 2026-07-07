import sys

MAIN = "/root/-av-shield-agents/sasha_qualifier.py"

ANCHOR = 'Q6 — CURRENT SETUP:'

ADDR_BLOCK = '''Q5b — PROPERTY ADDRESS:
"Perfect. What's the property address? I'll pull up a satellite view and map out 
exactly where your cameras should go before our call."
→ Record the full street address under answer key "address".
→ REQUIRED before booking — the survey cannot run without it.
→ If they hesitate, reassure: it's only to prep their custom layout, no spam.

Q6 — CURRENT SETUP:'''

src = open(MAIN).read()

if 'Q5b — PROPERTY ADDRESS' in src:
    print("ALREADY PATCHED"); sys.exit(0)
if ANCHOR not in src:
    print("FAIL: anchor not found - file NOT modified"); sys.exit(1)
if src.count(ANCHOR) != 1:
    print(f"FAIL: anchor appears {src.count(ANCHOR)} times - file NOT modified"); sys.exit(1)

new_src = src.replace(ANCHOR, ADDR_BLOCK, 1)

try:
    compile(new_src, MAIN, "exec")
except SyntaxError as e:
    print("FAIL: syntax error - file NOT modified:", e); sys.exit(1)

open(MAIN, "w").write(new_src)
print("OK: address question added and validated")
