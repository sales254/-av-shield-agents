import sys
MAIN = "/root/-av-shield-agents/sasha_survey.py"

edits = []
edits.append((
    "from sasha_ghl import (\n    add_note, add_tags, send_sms,\n    update_opportunity_stage\n)",
    "from sasha_ghl import (\n    add_note, add_tags, send_sms,\n    update_opportunity_stage, upload_media\n)"
))
edits.append((
    "        satellite_img = get_satellite_image(formatted_address)\n        street_view_img = get_street_view_image(formatted_address)",
    "        satellite_img = get_satellite_image(formatted_address)\n"
    "        street_view_img = get_street_view_image(formatted_address)\n"
    "        survey_image_url = \"\"\n"
    "        try:\n"
    "            if satellite_img:\n"
    "                _safe = \"\".join(c if c.isalnum() else \"_\" for c in formatted_address)[:50]\n"
    "                _img_path = f\"/root/-av-shield-agents/survey_{_safe}.png\"\n"
    "                with open(_img_path, \"wb\") as _f:\n"
    "                    _f.write(satellite_img)\n"
    "                survey_image_url = upload_media(_img_path)\n"
    "        except Exception as _e:\n"
    "            logger.error(f\"[SURVEY] image upload failed: {_e}\")\n"
    "        state.survey_image_url = survey_image_url"
))
edits.append((
    "                f\"Summary: {result.get('proposal_summary', '')}\"\n            )",
    "                f\"Summary: {result.get('proposal_summary', '')}\\n\"\n"
    "                f\"Property Image: {getattr(state, 'survey_image_url', '') or 'N/A'}\"\n            )"
))

src = open(MAIN).read()
if "survey_image_url" in src:
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
print("OK: image-to-note wiring applied and validated")
