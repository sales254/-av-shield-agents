import sys
MAIN = "/root/-av-shield-agents/webhook.py"

OLD = '''            # Clear state if conversation is done
            if state.status in ["qualified", "disqualified"]:
                logging.info(f"Conversation complete for {phone} — status: {state.status}")
                del conversation_states[phone]
                save_states()'''

NEW = '''            # Clear state only when disqualified. Qualified leads stay in
            # memory so the booking conversation can continue.
            if state.status == "disqualified":
                logging.info(f"Conversation complete for {phone} — status: {state.status}")
                del conversation_states[phone]
                save_states()'''

src = open(MAIN).read()
if 'Clear state only when disqualified' in src:
    print("ALREADY PATCHED"); sys.exit(0)
if src.count(OLD) != 1:
    print(f"FAIL: anchor not unique/missing ({src.count(OLD)}x) - NOT modified"); sys.exit(1)

src = src.replace(OLD, NEW, 1)
try:
    compile(src, MAIN, "exec")
except SyntaxError as e:
    print("FAIL: syntax error - NOT modified:", e); sys.exit(1)

open(MAIN, "w").write(src)
print("OK: loop fix applied and validated")
