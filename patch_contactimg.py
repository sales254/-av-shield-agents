import sys
MAIN = "/root/-av-shield-agents/sasha_survey.py"
edits = []
edits.append((
    "    update_opportunity_stage, upload_media\n)",
    "    update_opportunity_stage, upload_media, upload_to_contact\n)"
))
edits.append((
    "                survey_image_url = upload_media(_img_path)\n",
    "                survey_image_url = upload_media(_img_path)\n"
    "                if state.contact_id:\n"
    "                    upload_to_contact(_img_path, state.contact_id)\n"
))
src = open(MAIN).read()
if src.count("upload_to_contact") >= 1:
    print("ALREADY PATCHED"); sys.exit(0)
for old, new in edits:
    if src.count(old) != 1:
        print(f"FAIL: anchor not unique/missing ({src.count(old)}x) - NOT modified"); sys.exit(1)
    src = src.replace(old, new, 1)
try:
    compile(src, MAIN, "exec")
except SyntaxError as e:
    print("FAIL: syntax error - NOT modified:", e); sys.exit(1)
open(MAIN, "w").write(src)
print("OK: contact-image wiring applied and validated")
