"""Choices the kid ticks on the card itself: a shape (flat, puffy, raised lines, puffy with
raised lines, figurine) and "neat lines" (tidy). The boxes are printed in the light guide
color below the drawing box; the reader finds which box is marked.

Cards printed before the boxes existed have other printing in the same place, so a box
only counts if its light-blue outline is really there.
"""

from __future__ import annotations

import cv2
import numpy as np

# (style key, word on the card). The order is the order on the card.
SHAPES = [
    ("flat", "Flat"),
    ("puffy", "Puffy"),
    ("outlined", "Raised lines"),
    ("puffy-outlined", "Puffy + lines"),
    ("figurine", "Figurine"),
]
WORDS = dict(SHAPES)
BOX = 8.0            # card mm, square
STEP = 37.5          # card mm between shape boxes
PICTURE = (26.0, 14.0)   # card mm: the room for each shape's picture, right of its box


def option_zones(cfg: dict, product: str) -> dict:
    """Where the option boxes go on a card (card mm, y up, bottom-left corners)."""
    c = cfg["cards"]
    nx, ny, nw, nh = c["name_box"]
    zones = {"tidy_box": (nx + nw + 6.0, ny + 0.5, BOX)}
    x0, y = c["margin"] + 8.0, ny - 19.0              # every card, clicker too (Allen: figurine clickers)
    zones["shape_boxes"] = [(key, x0 + i * STEP, y, BOX) for i, (key, _) in enumerate(SHAPES)]
    return zones


def _crop(page: np.ndarray, ppm: float, x: float, y: float, w: float, h: float) -> np.ndarray:
    H = page.shape[0]
    c0, c1 = int(round(x * ppm)), int(round((x + w) * ppm))
    r0, r1 = int(round(H - (y + h) * ppm)), int(round(H - y * ppm))
    return page[max(r0, 0):max(r1, 0), max(c0, 0):max(c1, 0)]


def _guide_pixels(cfg: dict, bgr: np.ndarray) -> np.ndarray:
    rd = cfg["reader"]
    hsv = cv2.cvtColor(bgr.astype(np.float32) / 255.0, cv2.COLOR_BGR2HSV)
    dh = np.abs(((hsv[..., 0] - rd["guide_hue"]) + 180.0) % 360.0 - 180.0)
    return (dh < rd["guide_hue_tolerance"]) & (hsv[..., 1] > 0.06) & (hsv[..., 1] < rd["guide_saturation_max"]) & \
        (hsv[..., 2] > 0.55)


def _box_present(cfg: dict, page: np.ndarray, ppm: float, x: float, y: float, s: float) -> bool:
    """The printed light-blue outline is there (not an older card with a picture here)."""
    band = 0.8
    outer = _crop(page, ppm, x - band, y - band, s + 2 * band, s + 2 * band)
    if outer.size == 0:
        return False
    g = _guide_pixels(cfg, outer)
    k = int(round(2 * band * ppm))
    ring = np.ones(g.shape, bool)
    ring[k:-k, k:-k] = False
    return float(g[ring].mean()) >= 0.12


def _mark_fraction(cfg: dict, page: np.ndarray, ppm: float, x: float, y: float, s: float, paper_l: float) -> float:
    """How much of the box's inside is marked: a tick, an X, a scribble or a colored-in box."""
    from .filaments import _srgb_to_lab

    inset = 1.3
    inner = _crop(page, ppm, x + inset, y + inset, s - 2 * inset, s - 2 * inset)
    if inner.size == 0:
        return 0.0
    rgb = cv2.cvtColor(inner, cv2.COLOR_BGR2RGB).reshape(-1, 3).astype(np.float64)
    lab = _srgb_to_lab(rgb)
    chroma = np.hypot(lab[:, 1], lab[:, 2])
    ink = (lab[:, 0] < paper_l - 28.0) | ((chroma > 25.0) & (lab[:, 0] < paper_l - 6.0))
    ink &= ~_guide_pixels(cfg, inner).reshape(-1)
    return float(ink.mean())


def read_options(cfg: dict, read) -> dict:
    """The kid's choices from a straightened card: {"style": key or None, "tidy": bool,
    "notes": [...], "warnings": [...]}. Empty for cards without option boxes."""
    lay, page, ppm = read.layout, read.page, read.px_per_card_mm
    if lay is None or page is None:
        return {}
    zones = option_zones(cfg, lay.product)
    gray = cv2.cvtColor(page, cv2.COLOR_BGR2GRAY)
    paper_l = float(np.percentile(gray, 90)) / 255.0 * 100.0
    out: dict = {"style": None, "tidy": False, "notes": [], "warnings": []}
    found_any = False
    marks = []
    for key, x, y, s in zones.get("shape_boxes", []):
        if not _box_present(cfg, page, ppm, x, y, s):
            continue
        found_any = True
        marks.append((_mark_fraction(cfg, page, ppm, x, y, s, paper_l), key))
    picked = sorted([m for m in marks if m[0] >= cfg["reader"]["option_mark_min"]], reverse=True)
    if picked:
        out["style"] = picked[0][1]
        out["notes"].append(f"shape ticked on the card: {WORDS[picked[0][1]]}")
        if len(picked) > 1:
            out["warnings"].append("more than one shape ticked on the card ("
                                   + ", ".join(WORDS[k] for _, k in picked) + f"); used {WORDS[picked[0][1]]}")
    x, y, s = zones["tidy_box"]
    if _box_present(cfg, page, ppm, x, y, s):
        found_any = True
        if _mark_fraction(cfg, page, ppm, x, y, s, paper_l) >= cfg["reader"]["option_mark_min"]:
            out["tidy"] = True
            out["notes"].append("neat lines ticked on the card")
    return out if found_any else {}


_PICTURES: dict = {}


def shape_pictures(cfg: dict) -> dict:
    """A real render of each shape, made by the tool itself from a sample heart with a face:
    {style key: PIL image}, all at one scale so the heights compare. Built once per run
    (about 5 seconds). Height is drawn 1.6x so thin raised lines show at this small size."""
    import json
    import math

    from PIL import Image
    from shapely.geometry import LineString, Point, Polygon

    from .preview import render_shaded
    from .products import build_piece
    from .shape import Design, InkRegion, _as_multi

    key = json.dumps([cfg["relief"], cfg.get("figurine")], sort_keys=True, default=str)
    if key in _PICTURES:
        return _PICTURES[key]
    import tempfile
    from pathlib import Path

    heart = Point(-7, 4).buffer(8).union(Point(7, 4).buffer(8)).union(
        Polygon([(-14.6, 1.5), (14.6, 1.5), (0, -16)])).buffer(1.0).buffer(-1.0)
    inside = heart.buffer(-1.4)
    eyes = Point(-4.5, 2).buffer(1.7).union(Point(4.5, 2).buffer(1.7))
    smile = LineString([(5 * math.cos(a), -2.5 + 5 * math.sin(a))
                        for a in np.linspace(math.radians(200), math.radians(340), 20)]).buffer(0.7)
    black = heart.difference(inside).union(eyes).union(smile)
    elev, stretch, eps, ppm, shrink = 28.0, 1.6, 0.06, 16.0, 2
    out = {}
    with tempfile.TemporaryDirectory() as tmp:
        for style, _ in SHAPES:
            d = Design("shape", "magnet_figure", heart, [
                InkRegion("black", (30, 30, 30), _as_multi(black)),
                InkRegion("pink", (240, 110, 160), _as_multi(inside.difference(black)))])
            p = build_piece(cfg, d, style=style)
            parts = p.parts if p.face_up else {n: s.rotate([0.0, 180.0, 0.0]) for n, s in p.parts.items()}
            # Colors a hair toward the viewer, so they win where their sides meet the base's.
            e = math.radians(elev)
            parts = {n: (s if n == p.base_part else s.translate([0.0, -eps * math.cos(e), eps * math.sin(e) / stretch]))
                     .scale([1.0, 1.0, stretch]) for n, s in parts.items()}
            f = Path(tmp) / f"{style}.png"
            render_shaded(parts, f, view=(elev, 0.0), px_per_mm=ppm * shrink, labels=False, colors=dict(p.part_colors))
            a = np.asarray(Image.open(f).convert("RGB")).copy()
            a[(a == (245, 245, 240)).all(axis=2)] = 255            # the render's backdrop: white paper
            im = Image.fromarray(a)
            out[style] = im.resize((im.width // shrink, im.height // shrink), Image.LANCZOS)
    _PICTURES[key] = {"images": out, "px_per_mm": ppm}
    return _PICTURES[key]
