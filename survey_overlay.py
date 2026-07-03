# ============================================================
# AV SHIELD — survey_overlay.py
# Draws camera icons on the satellite image for the survey.
# ============================================================
import io
from PIL import Image
import property_survey as ps
import building_detect as bd


def render_camera_overlay(satellite_bytes, lat, zoom, qualifier=None,
                          out_path="/tmp/survey_layout.png", camera_count=None):
    try:
        base = Image.open(io.BytesIO(satellite_bytes)).convert("RGB")
    except Exception as e:
        print(f"[OVERLAY] could not open satellite bytes: {e}")
        return ""

    if base.size != (ps.IMG_SIZE, ps.IMG_SIZE):
        base = base.resize((ps.IMG_SIZE, ps.IMG_SIZE))

    est = ps.estimate_cameras(lat, zoom, qualifier or {})

    # Try to land the icons on the actual building footprint. Counts/types are
    # unchanged; on any failure we fall back to the generic-frame placement.
    try:
        est, box = bd.place_cameras_on_building(base, est, img_size=ps.IMG_SIZE)
        if box:
            print(f"[OVERLAY] cameras placed on detected building footprint")
        else:
            print(f"[OVERLAY] building not detected — using generic frame")
    except Exception as e:
        print(f"[OVERLAY] building detection error, using generic frame: {e}")

    overlay = ps.render_overlay(base, est)
    try:
        overlay.save(out_path)
        print(f"[OVERLAY] saved {out_path} with {est['count']} icons")
        return out_path
    except Exception as e:
        print(f"[OVERLAY] save failed: {e}")
        return ""

