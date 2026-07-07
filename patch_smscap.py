import sys
MAIN = "/root/-av-shield-agents/webhook.py"

OLD = '''def send_sms(to_phone, message):
    try:
        client = Client(TWILIO_SID, TWILIO_TOKEN)'''

NEW = '''def send_sms(to_phone, message):
    try:
        if message and len(message) > 1500:
            logging.warning(f"SMS too long ({len(message)} chars) for {to_phone} - truncating")
            message = message[:1490] + "\\u2026"
        client = Client(TWILIO_SID, TWILIO_TOKEN)'''

src = open(MAIN).read()
if "SMS too long" in src:
    print("ALREADY PATCHED"); sys.exit(0)
if src.count(OLD) != 1:
    print(f"FAIL: anchor not unique/missing ({src.count(OLD)}x) - NOT modified"); sys.exit(1)
src = src.replace(OLD, NEW, 1)
try:
    compile(src, MAIN, "exec")
except SyntaxError as e:
    print("FAIL: syntax error - NOT modified:", e); sys.exit(1)
open(MAIN, "w").write(src)
print("OK: SMS length cap added")
