import sys
MAIN = "/root/-av-shield-agents/sasha_survey.py"

OLD = '''            if satellite_img:
                _safe = "".join(c if c.isalnum() else "_" for c in formatted_address)[:50]
                _img_path = f"/root/-av-shield-agents/survey_{_safe}.png"
                with open(_img_path, "wb") as _f:
                    _f.write(satellite_img)
                survey_image_url = upload_media(_img_path)
                if state.contact_id:
                    upload_to_contact(_img_path, state.contact_id)'''

NEW = '''            if satellite_img:
                _safe = "".join(c if c.isalnum() else "_" for c in formatted_address)[:50]
                _img_path = f"/root/-av-shield-agents/survey_{_safe}.png"
                with open(_img_path, "wb") as _f:
                    _f.write(satellite_img)
                _upload_path = _img_path
                try:
                    import survey_overlay, property_survey as _ps
                    _lat = geo.get("lat", 0)
                    _qual = state.qualification_data or {}
                    _area = _qual.get("Q5") or _qual.get("area_sqft") or 0
                    _zoom = _ps.zoom_for_area(_lat, _ps._coerce_int(_area, 0)) if _lat else 19
                    _ov = survey_overlay.render_camera_overlay(
                        satellite_img, _lat, _zoom, _qual,
                        out_path=f"/root/-av-shield-agents/survey_{_safe}_layout.png")
                    if _ov:
                        _upload_path = _ov
                except Exception as _oe:
                    logger.error(f"[SURVEY] overlay failed, using plain image: {_oe}")
                survey_image_url = upload_media(_upload_path)
                if state.contact_id:
                    upload_to_contact(_upload_path, state.contact_id)'''

src = open(MAIN).read()
if "render_camera_overlay" in src:
    print("ALREADY PATCHED"); sys.exit(0)
if src.count(OLD) != 1:
    print(f"FAIL: anchor not unique/missing ({src.count(OLD)}x) - NOT modified"); sys.exit(1)
src = src.replace(OLD, NEW, 1)
try:
    compile(src, MAIN, "exec")
except SyntaxError as e:
    print("FAIL: syntax error - NOT modified:", e); sys.exit(1)
open(MAIN, "w").write(src)
print("OK: overlay wiring applied and validated")
