# ============================================================
# AV SHIELD — property_survey.py — Visual Survey + Draft Camera Layout
# ============================================================

import os
import math
import logging

import requests
from PIL import Image, ImageDraw, ImageFont

try:
    from config import GOOGLE_MAPS_API_KEY
except Exception:
    GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")

log = logging.getLogger("property_survey")

IMG_SIZE = 640
DEFAULT_ZOOM = 19
PERIMETER_FT_PER_CAM = 90
MIN_CAMERAS = 4
MAX_CAMERAS = 40


def geocode(address: str) -> dict:
    r = requests.get(
        "https://maps.googleapis.com/maps/api/geocode/json",
        params={"address": address, "key": GOOGLE_MAPS_API_KEY},
        timeout=15,
    )
    r.raise_for_status()
    data = r.json()
    if data.get("status") != "OK" or not data.get("results"):
        raise ValueError(f"Geocode failed: {data.get('status')} {data.get('error_message','')}")
    top = data["results"][0]
    loc = top["geometry"]["location"]
    return {"lat": loc["lat"], "lng": loc["lng"],
            "formatted_address": top.get("formatted_address", address)}


def meters_per_pixel(lat: float, zoom: int) -> float:
    return 156543.03392 * math.cos(math.radians(lat)) / (2 ** zoom)


def feet_per_pixel(lat: float, zoom: int) -> float:
    return meters_per_pixel(lat, zoom) * 3.28084


def zoom_for_area(lat: float, area_sqft: float) -> int:
    if not area_sqft or area_sqft <= 0:
        return DEFAULT_ZOOM
    side_ft = math.sqrt(area_sqft)
    target_ft = side_ft * 1.6
    for z in range(21, 14, -1):
        frame_ft = feet_per_pixel(lat, z) * IMG_SIZE
        if frame_ft >= target_ft:
            return z
    return 16


def fetch_satellite(lat: float, lng: float, zoom: int) -> Image.Image:
    r = requests.get(
        "https://maps.googleapis.com/maps/api/staticmap",
        params={
            "center": f"{lat},{lng}",
            "zoom": zoom,
            "size": f"{IMG_SIZE}x{IMG_SIZE}",
            "maptype": "satellite",
            "key": GOOGLE_MAPS_API_KEY,
        },
        timeout=20,
    )
    r.raise_for_status()
    from io import BytesIO
    return Image.open(BytesIO(r.content)).convert("RGB")


def fetch_streetview(address: str):
    meta = requests.get(
        "https://maps.googleapis.com/maps/api/streetview/metadata",
        params={"location": address, "key": GOOGLE_MAPS_API_KEY},
        timeout=15,
    ).json()
    if meta.get("status") != "OK":
        log.info("No Street View available: %s", meta.get("status"))
        return None
    r = requests.get(
        "https://maps.googleapis.com/maps/api/streetview",
        params={"location": address, "size": f"{IMG_SIZE}x{IMG_SIZE}",
                "fov": 90, "key": GOOGLE_MAPS_API_KEY},
        timeout=20,
    )
    r.raise_for_status()
    from io import BytesIO
    return Image.open(BytesIO(r.content)).convert("RGB")


def _coerce_int(v, default=None):
    if v is None:
        return default
    try:
        return int(str(v).replace(",", "").strip())
    except Exception:
        return default


def estimate_cameras(lat: float, zoom: int, qualifier) -> dict:
    qualifier = qualifier or {}
    entries = _coerce_int(qualifier.get("entry_points"), default=None)
    area = _coerce_int(qualifier.get("area_sqft"), default=None)
    mode = "A" if (entries is not None or area is not None) else "B"

    fpp = feet_per_pixel(lat, zoom)
    frame_ft = fpp * IMG_SIZE

    if area and area > 0:
        side_ft = math.sqrt(area)
    else:
        side_ft = frame_ft * 0.55
    side_px = min(IMG_SIZE * 0.9, side_ft / fpp)
    half = side_px / 2
    cx = cy = IMG_SIZE / 2
    left, right = cx - half, cx + half
    top, bot = cy - half, cy + half

    positions = []

    corners = [(left, top, "NW"), (right, top, "NE"),
               (right, bot, "SE"), (left, bot, "SW")]
    for x, y, tag in corners:
        positions.append({"x": x, "y": y, "kind": "corner", "label": tag})

    side_ft_actual = side_px * fpp
    extra_per_side = max(0, int(side_ft_actual // PERIMETER_FT_PER_CAM) - 1)
    for i in range(extra_per_side):
        f = (i + 1) / (extra_per_side + 1)
        positions.append({"x": left + f * (right - left), "y": top,
                          "kind": "perimeter", "label": "P"})
        positions.append({"x": left + f * (right - left), "y": bot,
                          "kind": "perimeter", "label": "P"})

    n_entries = entries if entries is not None else 1
    for i in range(max(0, n_entries)):
        f = (i + 1) / (n_entries + 1)
        positions.append({"x": left + f * (right - left), "y": bot + 12,
                          "kind": "entry", "label": "E"})

    if len(positions) > MAX_CAMERAS:
        positions = positions[:MAX_CAMERAS]

    for p in positions:
        p["x"] = float(min(IMG_SIZE - 8, max(8, p["x"])))
        p["y"] = float(min(IMG_SIZE - 8, max(8, p["y"])))

    return {
        "count": len(positions),
        "positions": positions,
        "mode": mode,
        "zoom": zoom,
        "feet_per_pixel": round(fpp, 3),
        "assumptions": {
            "entry_points": n_entries,
            "area_sqft": area,
            "perimeter_ft_per_cam": PERIMETER_FT_PER_CAM,
        },
    }


_KIND_COLOR = {
    "corner": (0, 200, 255),
    "perimeter": (0, 255, 120),
    "entry": (255, 90, 90),
}


def render_overlay(base: Image.Image, est: dict, title: str = "") -> Image.Image:
    img = base.copy()
    draw = ImageDraw.Draw(img, "RGBA")
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
        small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
    except Exception:
        font = small = ImageFont.load_default()

    for i, p in enumerate(est["positions"], 1):
        x, y = p["x"], p["y"]
        c = _KIND_COLOR.get(p["kind"], (255, 255, 0))
        r = 11
        draw.ellipse([x - r, y - r, x + r, y + r], fill=c + (230,),
                     outline=(0, 0, 0, 255), width=2)
        draw.text((x - 4, y - 7), str(i), fill=(0, 0, 0, 255), font=small)

    banner = f"DRAFT LAYOUT - {est['count']} cameras (mode {est['mode']}) - confirm before sending"
    if title:
        banner = title
    draw.rectangle([0, 0, IMG_SIZE, 26], fill=(0, 0, 0, 180))
    draw.text((8, 6), banner, fill=(255, 255, 255, 255), font=font)

    ly = IMG_SIZE - 58
    draw.rectangle([0, ly - 6, 150, IMG_SIZE], fill=(0, 0, 0, 150))
    for label, kind in [("Corner", "corner"), ("Perimeter", "perimeter"), ("Entry", "entry")]:
        c = _KIND_COLOR[kind]
        draw.ellipse([8, ly, 18, ly + 10], fill=c + (255,), outline=(0, 0, 0, 255))
        draw.text((24, ly - 2), label, fill=(255, 255, 255, 255), font=small)
        ly += 16
    return img


def survey(address: str, qualifier=None, out_dir: str = ".") -> dict:
    if not GOOGLE_MAPS_API_KEY:
        raise RuntimeError("GOOGLE_MAPS_API_KEY is not set")

    geo = geocode(address)
    lat, lng = geo["lat"], geo["lng"]

    area = (qualifier or {}).get("area_sqft")
    zoom = zoom_for_area(lat, _coerce_int(area, 0))

    sat = fetch_satellite(lat, lng, zoom)
    est = estimate_cameras(lat, zoom, qualifier)
    overlay = render_overlay(sat, est)

    safe = "".join(ch if ch.isalnum() else "_" for ch in address)[:50]
    sat_path = os.path.join(out_dir, f"survey_{safe}_satellite.png")
    overlay_path = os.path.join(out_dir, f"survey_{safe}_layout.png")
    sat.save(sat_path)
    overlay.save(overlay_path)

    result = {
        "address": geo["formatted_address"],
        "lat": lat, "lng": lng, "zoom": zoom,
        "camera_count": est["count"],
        "positions": est["positions"],
        "mode": est["mode"],
        "assumptions": est["assumptions"],
        "satellite_image": sat_path,
        "layout_image": overlay_path,
        "streetview_image": None,
    }

    try:
        sv = fetch_streetview(address)
        if sv is not None:
            sv_path = os.path.join(out_dir, f"survey_{safe}_streetview.png")
            sv.save(sv_path)
            result["streetview_image"] = sv_path
    except Exception as e:
        log.info("Street View skipped: %s", e)

    return result


if __name__ == "__main__":
    import json, sys
    addr = sys.argv[1] if len(sys.argv) > 1 else "1600 Amphitheatre Parkway, Mountain View, CA"
    q = {"area_sqft": 12000, "entry_points": 2, "property_type": "warehouse"}
    out = survey(addr, qualifier=q, out_dir=".")
    print(json.dumps({k: v for k, v in out.items() if k != "positions"}, indent=2))
    print(f"positions: {len(out['positions'])} camera icons")
