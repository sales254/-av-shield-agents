# ============================================================
# AV SHIELD — building_detect.py
# Detect the building footprint in a satellite image with Claude
# Vision, then re-map the draft camera layout so the icons land on
# the building instead of the generic centered frame.
#
# The camera COUNT and TYPES are never touched here — they come from
# property_survey.estimate_cameras(). This module only moves the
# existing icon positions onto the detected footprint. If detection
# fails for any reason, callers fall back to the original layout.
# ============================================================

import io
import os
import re
import json
import base64
import logging

from PIL import Image

try:
    import anthropic
except Exception:  # library not installed / import error
    anthropic = None

try:
    from config import ANTHROPIC_API_KEY
except Exception:
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Footprint detection needs precise vision. Sonnet boxes the parcel instead of
# the roofline on cluttered multi-wing properties; Opus 4.8 boxes the roof
# consistently, so detection defaults to it independent of the global agent
# model. Override with BUILDING_DETECT_MODEL if needed.
DETECT_MODEL = os.getenv("BUILDING_DETECT_MODEL", "claude-opus-4-8")

log = logging.getLogger("building_detect")

# The building box is inset slightly so corner/perimeter icons sit
# clearly ON the roof rather than exactly on the footprint edge.
_INSET = 0.04

_VISION_SYSTEM = (
    "You are a remote-sensing assistant. You are given a top-down satellite "
    "image. Identify the main building footprint of the property being "
    "surveyed — the largest/most central permanent structure (house, warehouse, "
    "apartment complex, or main commercial building).\n\n"
    "IMPORTANT: many properties have L-, U-, or E-shaped buildings, or several "
    "connected wings sharing one roofline. Treat ALL connected wings of the "
    "primary structure as ONE building and return the union bounding box that "
    "encloses every wing. Do NOT box just one wing.\n\n"
    "Exclude driveways, parking lots, pools, sheds, detached garages, trees, "
    "cars, roads, and buildings on neighboring parcels. Also exclude carports, "
    "shade canopies, and any long narrow roof strips covering parking stalls — "
    "those are not part of the main building even when attached to the parcel.\n\n"
    "Return ONLY a JSON object, no prose, of the form:\n"
    '{"found": true, "box": {"x0": 0.0, "y0": 0.0, "x1": 1.0, "y1": 1.0}}\n\n'
    "Coordinates are normalized to [0,1] with the origin at the TOP-LEFT of the "
    "image: x increases to the right, y increases downward. box is the tight "
    "axis-aligned bounding rectangle around the roof(s) of that one structure — "
    "the box edges should touch the outermost roof edges, not the surrounding "
    "pavement or lot lines. "
    'If no clear building is visible, return {"found": false}.'
)


def _to_pil(image) -> Image.Image:
    """Accept a PIL image or raw PNG/JPEG bytes and return an RGB PIL image."""
    if isinstance(image, Image.Image):
        return image.convert("RGB")
    return Image.open(io.BytesIO(image)).convert("RGB")


def _parse_box(raw: str):
    """Pull the JSON object out of the model reply and return a normalized box."""
    raw = re.sub(r"```json\s*", "", raw)
    raw = re.sub(r"```\s*", "", raw)
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    data = json.loads(m.group(0) if m else raw.strip())

    if not data.get("found") or "box" not in data:
        return None

    b = data["box"]
    x0, y0, x1, y1 = (float(b["x0"]), float(b["y0"]),
                      float(b["x1"]), float(b["y1"]))

    # normalize ordering + clamp to the image
    x0, x1 = sorted((x0, x1))
    y0, y1 = sorted((y0, y1))
    x0, y0 = max(0.0, x0), max(0.0, y0)
    x1, y1 = min(1.0, x1), min(1.0, y1)

    w, h = x1 - x0, y1 - y0
    # Reject implausible detections: too small, or basically the whole frame.
    if w < 0.05 or h < 0.05 or (w > 0.97 and h > 0.97):
        return None

    return {"x0": x0, "y0": y0, "x1": x1, "y1": y1}


def detect_building_box(image, img_size=640, api_key=None, model=None):
    """
    Detect the main building footprint using Claude Vision.

    Returns a PIXEL-space box {x0, y0, x1, y1} (origin top-left) sized for an
    img_size x img_size image, or None if detection is unavailable or fails.
    """
    if anthropic is None:
        log.info("[BUILDING] anthropic library unavailable — skipping detection")
        return None

    key = api_key or ANTHROPIC_API_KEY
    if not key:
        log.info("[BUILDING] no ANTHROPIC_API_KEY — skipping detection")
        return None

    try:
        pil = _to_pil(image)
        buf = io.BytesIO()
        pil.save(buf, format="PNG")
        b64 = base64.standard_b64encode(buf.getvalue()).decode("utf-8")

        client = anthropic.Anthropic(api_key=key)
        resp = client.messages.create(
            model=model or DETECT_MODEL,
            max_tokens=300,
            system=_VISION_SYSTEM,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": b64,
                        },
                    },
                    {"type": "text",
                     "text": "Return the JSON bounding box for the main building."},
                ],
            }],
        )
        norm = _parse_box(resp.content[0].text)
    except Exception as e:
        log.info("[BUILDING] detection failed: %s", e)
        return None

    if not norm:
        log.info("[BUILDING] no building found in image")
        return None

    box = {
        "x0": norm["x0"] * img_size,
        "y0": norm["y0"] * img_size,
        "x1": norm["x1"] * img_size,
        "y1": norm["y1"] * img_size,
    }
    log.info("[BUILDING] footprint box (px): %s", box)
    return box


def _source_frame(est):
    """
    Recover the generic square frame that estimate_cameras() laid the icons
    out against, from its corner positions. Returns (left, right, top, bot)
    or None if corners are missing.
    """
    corners = [p for p in est.get("positions", []) if p.get("kind") == "corner"]
    if len(corners) < 2:
        return None
    xs = [p["x"] for p in corners]
    ys = [p["y"] for p in corners]
    left, right, top, bot = min(xs), max(xs), min(ys), max(ys)
    if right - left < 1 or bot - top < 1:
        return None
    return left, right, top, bot


def remap_positions_to_building(est, box, img_size=640, inset=_INSET):
    """
    Return a copy of `est` with every icon position affine-mapped from the
    generic centered frame onto the detected building box. Counts, kinds, and
    labels are preserved exactly — only x/y change.
    """
    frame = _source_frame(est)
    if not frame or not box:
        return est

    left, right, top, bot = frame

    # Inset the target so corner/perimeter icons sit inside the footprint.
    bw, bh = box["x1"] - box["x0"], box["y1"] - box["y0"]
    tx0 = box["x0"] + inset * bw
    tx1 = box["x1"] - inset * bw
    ty0 = box["y0"] + inset * bh
    ty1 = box["y1"] - inset * bh

    new_positions = []
    for p in est["positions"]:
        fx = (p["x"] - left) / (right - left)
        fy = (p["y"] - top) / (bot - top)
        nx = tx0 + fx * (tx1 - tx0)
        ny = ty0 + fy * (ty1 - ty0)
        q = dict(p)
        q["x"] = float(min(img_size - 8, max(8, nx)))
        q["y"] = float(min(img_size - 8, max(8, ny)))
        new_positions.append(q)

    new_est = dict(est)
    new_est["positions"] = new_positions
    new_est["building_box"] = box
    return new_est


def place_cameras_on_building(image, est, img_size=640, api_key=None, model=None):
    """
    Convenience wrapper: detect the building footprint and re-map the draft
    camera layout onto it.

    Returns (new_est, box). On any failure returns (est unchanged, None) so
    callers transparently fall back to the generic-frame placement.
    """
    box = detect_building_box(image, img_size=img_size, api_key=api_key, model=model)
    if not box:
        return est, None
    return remap_positions_to_building(est, box, img_size=img_size), box
