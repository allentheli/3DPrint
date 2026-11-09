"""Design cards: the printable PDF and the exact layout the reader relies on.

Card coordinates are millimetres with the origin at the page's bottom-left and Y
up (PDF convention). Every marker, box and zone position comes from `card_layout`,
which both the PDF writer and the photo reader use, so they always agree.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

CORNER_NAMES = ("TL", "TR", "BR", "BL")   # ArUco corner order, clockwise from top-left
MAX_TYPES = 8
MAX_NUMBERS = 30
CORNER_STRIDE = 250                        # ids: corner*250 + type*30 + number


@dataclass
class CardLayout:
    product: str
    type_id: int
    number: int                      # 1-based, printed as 01, 02...
    page: tuple[float, float]
    markers: dict[str, tuple[float, float, float]]   # corner -> (x, y, size), bottom-left of marker
    box: tuple[float, float, float, float]            # x, y, w, h of the drawing box
    scale: int                                        # card mm per real mm
    name_box: tuple[float, float, float, float]
    zones: dict = field(default_factory=dict)         # product-specific guides (card mm)

    @property
    def stem(self) -> str:
        return f"{SHORT_NAMES[self.product]}-{self.number:02d}"

    def marker_corners_mm(self, corner: str) -> np.ndarray:
        """The four corners (TL, TR, BR, BL) of one marker in card mm."""
        x, y, s = self.markers[corner]
        return np.array([[x, y + s], [x + s, y + s], [x + s, y], [x, y]], dtype=np.float64)


SHORT_NAMES = {
    "hair_clip": "clip", "keychain": "key", "clicker": "click",
    "magnet_figure": "fig", "earrings": "ear", "pendant": "pend",
    "calibration": "calib",
}

HALF_DRAWN_FRACTION = {"hair_clip": 0.75, "keychain": 0.70, "magnet_figure": 0.75, "clicker": 0.75,
                       "earrings": 0.75, "pendant": 0.75}


def half_drawn_shape_name(cfg: dict, number: int) -> str | None:
    c = cfg["cards"]
    shapes = c["half_drawn_shapes"]
    first = c["half_drawn_first_number"]
    i = number - first
    if 0 <= i < len(shapes) * c["half_drawn_copies"]:
        return shapes[i % len(shapes)]
    return None


def outline_shape(name: str):
    """A simple outline for half-drawn cards, as a Shapely polygon about 1 unit across."""
    from shapely import affinity
    from shapely.geometry import Point, Polygon
    from shapely.ops import unary_union

    if name == "heart":
        t = np.linspace(0, 2 * np.pi, 240, endpoint=False)
        poly = Polygon(np.c_[16 * np.sin(t) ** 3, 13 * np.cos(t) - 5 * np.cos(2 * t) - 2 * np.cos(3 * t) - np.cos(4 * t)])
    elif name == "star":
        pts = []
        for i in range(10):
            a = np.pi / 2 + i * np.pi / 5
            r = 0.5 if i % 2 == 0 else 0.27
            pts.append((r * np.cos(a), r * np.sin(a)))
        poly = Polygon(pts).buffer(0.03, join_style="round").buffer(-0.03, join_style="round")
    elif name == "cloud":
        circles = [(-0.30, -0.05, 0.22), (0.0, 0.10, 0.30), (0.30, -0.02, 0.23), (-0.12, -0.16, 0.20), (0.15, -0.16, 0.20)]
        poly = unary_union([Point(x, y).buffer(r, quad_segs=24) for x, y, r in circles])
    elif name == "cat":
        head = Point(0, -0.06).buffer(0.38, quad_segs=24)
        ears = [Polygon([(s * 0.34, 0.08), (s * 0.33, 0.48), (s * 0.06, 0.27)]) for s in (-1, 1)]
        poly = unary_union([head] + ears)
    elif name == "bow":
        wings = [Polygon([(s * 0.5, 0.28), (s * 0.5, -0.28), (s * 0.04, 0.0)]) for s in (-1, 1)]
        knot = Point(0, 0).buffer(0.11, quad_segs=16)
        poly = unary_union(wings + [knot]).buffer(0.04, join_style="round").buffer(-0.02, join_style="round")
    else:
        raise ValueError(f"unknown half-drawn shape {name!r}")
    poly = Polygon(poly.exterior)
    minx, miny, maxx, maxy = poly.bounds
    f = 1.0 / max(maxx - minx, maxy - miny)
    poly = affinity.translate(poly, -(minx + maxx) / 2, -(miny + maxy) / 2)
    return affinity.scale(poly, f, f, origin=(0, 0))


def marker_id(corner_index: int, type_id: int, number: int) -> int:
    assert 0 <= corner_index < 4 and 0 <= type_id < MAX_TYPES and 1 <= number <= MAX_NUMBERS
    return corner_index * CORNER_STRIDE + type_id * MAX_NUMBERS + (number - 1)


def decode_marker_id(mid: int) -> tuple[int, int, int] | None:
    """Returns (corner_index, type_id, number) or None if the id is not one of ours."""
    if mid < 0 or mid >= 4 * CORNER_STRIDE:
        return None
    corner, rem = divmod(mid, CORNER_STRIDE)
    type_id, n = divmod(rem, MAX_NUMBERS)
    if type_id >= MAX_TYPES:
        return None
    return corner, type_id, n + 1


def aruco_dictionary(cfg: dict):
    name = cfg["cards"]["marker_dictionary"]
    return cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, name))


def card_layout(cfg: dict, product: str, number: int) -> CardLayout:
    c = cfg["cards"]
    pw, ph = c["page_size"]
    m, ms = c["margin"], c["marker_size"]
    scale = cfg["process"]["card_scale"]
    prod = cfg["products"][product]
    type_id = c["type_ids"][product]
    markers = {
        "TL": (m, ph - m - ms, ms),
        "TR": (pw - m - ms, ph - m - ms, ms),
        "BR": (pw - m - ms, m, ms),
        "BL": (m, m, ms),
    }
    # Drawing region sits between the title band (below the top markers) and the name box.
    region_top = ph - m - ms - 10
    region_bottom = c["name_box"][1] + c["name_box"][3] + 6
    size = prod["size_max"] * scale
    size = min(size, pw - 2 * m - 4, region_top - region_bottom)
    bx = (pw - size) / 2
    by = region_bottom + (region_top - region_bottom - size) / 2
    zones: dict = {}
    if product == "hair_clip":
        d = cfg["hardware"]["clip_min_circle"] * scale
        zones["cover_circle"] = (bx + size / 2, by + size / 2, d)
    elif product == "keychain":
        zones["ring"] = (bx + size / 2, by + size + 6, 8.0)   # cx, cy, diameter
    elif product == "magnet_figure":
        zones["ground_line"] = (bx + 8, by + 12, bx + size - 8, by + 12)
    elif product == "pendant":
        zones["bail"] = (bx + size / 2, by + size + 5, 6.0)
    shape = half_drawn_shape_name(cfg, number)
    if shape:
        from shapely import affinity

        span = size * HALF_DRAWN_FRACTION.get(product, 0.75)
        poly = affinity.scale(outline_shape(shape), span, span, origin=(0, 0))
        zones["outline"] = (shape, affinity.translate(poly, bx + size / 2, by + size / 2))
    return CardLayout(product, type_id, number, (pw, ph), markers,
                      (bx, by, size, size), scale, tuple(c["name_box"]), zones)


def calibration_layout(cfg: dict, number: int = 1) -> CardLayout:
    """One box per AMS slot at a fixed spot, so box k always means slot k."""
    c = cfg["cards"]
    pw, ph = c["page_size"]
    m, ms = c["margin"], c["marker_size"]
    n = cfg["printer"]["ams_slots"]
    cols = 2
    rows = (n + cols - 1) // cols
    x0, x1 = m + 4, pw - m - 4
    y0, y1 = m + ms + 14, ph - m - ms - 22
    cell_w, cell_h = (x1 - x0) / cols, (y1 - y0) / rows
    cells = {}
    for k in range(n):
        r, col = divmod(k, cols)
        cx = x0 + col * cell_w
        cy = y1 - (r + 1) * cell_h
        cells[k + 1] = (cx + 7, cy + 4, cell_w - 14, cell_h - 18)   # box; label goes above it
    bx = min(v[0] for v in cells.values())
    by = min(v[1] for v in cells.values())
    bw = max(v[0] + v[2] for v in cells.values()) - bx
    bh = max(v[1] + v[3] for v in cells.values()) - by
    return CardLayout("calibration", c["type_ids"]["calibration"], number, (pw, ph),
                      {"TL": (m, ph - m - ms, ms), "TR": (pw - m - ms, ph - m - ms, ms),
                       "BR": (pw - m - ms, m, ms), "BL": (m, m, ms)},
                      (bx, by, bw, bh), 1, (0, 0, 0, 0), {"cells": cells})


def layout_for(cfg: dict, product: str, number: int) -> CardLayout:
    if product == "calibration":
        return calibration_layout(cfg, number)
    return card_layout(cfg, product, number)


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------

def _hex_to_rgb01(h: str) -> tuple[float, float, float]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def _marker_image(dictionary, mid: int, px: int = 400):
    from PIL import Image

    arr = cv2.aruco.generateImageMarker(dictionary, mid, px)
    return Image.fromarray(arr)


def write_cards_pdf(cfg: dict, products: list[str], out_path: Path, count: int | None = None,
                    numbers: list[int] | None = None) -> Path:
    from reportlab.lib.units import mm
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    c = cfg["cards"]
    count = count or c["copies_per_type"]
    pw, ph = c["page_size"]
    dictionary = aruco_dictionary(cfg)
    out_path = Path(out_path)
    out_path.mkdir(parents=True, exist_ok=True) if out_path.suffix == "" else out_path.parent.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(out_path), pagesize=(pw * mm, ph * mm))
    pdf.setTitle("Charm Maker design cards")
    numbers = numbers or list(range(1, count + 1))
    for product in products:
        for n in numbers:
            lay = card_layout(cfg, product, n)
            _draw_card(pdf, cfg, lay, dictionary, ImageReader)
            pdf.showPage()
    pdf.save()
    return out_path


def _draw_card(pdf, cfg: dict, lay: CardLayout, dictionary, ImageReader):
    from reportlab.lib.units import mm

    c = cfg["cards"]
    prod = cfg["products"][lay.product]
    guide = _hex_to_rgb01(c["guide_color"])
    pw, ph = lay.page

    # Markers.
    for ci, corner in enumerate(CORNER_NAMES):
        x, y, s = lay.markers[corner]
        img = _marker_image(dictionary, marker_id(ci, lay.type_id, lay.number))
        pdf.drawImage(ImageReader(img), x * mm, y * mm, s * mm, s * mm)

    # Title band.
    pdf.setFillColorRGB(0, 0, 0)
    pdf.setFont("Helvetica-Bold", 22)
    pdf.drawCentredString(pw / 2 * mm, (ph - c["margin"] - 12) * mm, prod["label"])
    pdf.setFont("Helvetica", 12)
    pdf.drawCentredString(pw / 2 * mm, (ph - c["margin"] - 18) * mm, f"Card {lay.number:02d}")

    # Drawing box and guides (guide color only).
    bx, by, bw, bh = lay.box
    pdf.setStrokeColorRGB(*guide)
    pdf.setFillColorRGB(*guide)
    pdf.setLineWidth(c["guide_line_width"] * mm)
    pdf.roundRect(bx * mm, by * mm, bw * mm, bh * mm, 3 * mm, stroke=1, fill=0)
    pdf.setFont("Helvetica", 9)
    pdf.drawString((bx + 2) * mm, (by + bh - 5) * mm, "draw inside the box")
    if "cover_circle" in lay.zones:
        cx, cy, d = lay.zones["cover_circle"]
        pdf.circle(cx * mm, cy * mm, d / 2 * mm, stroke=1, fill=0)
        pdf.setFont("Helvetica", 8)
        pdf.drawCentredString(cx * mm, (cy - 1.5) * mm, "cover the circle")
    if "ring" in lay.zones:
        cx, cy, d = lay.zones["ring"]
        pdf.setLineWidth(1.0 * mm)
        pdf.circle(cx * mm, cy * mm, d / 2 * mm, stroke=1, fill=0)
        pdf.setLineWidth(c["guide_line_width"] * mm)
        pdf.setFont("Helvetica", 8)
        pdf.drawString((cx + d / 2 + 2) * mm, (cy - 1) * mm, "ring goes here")
    if "ground_line" in lay.zones:
        x0, y0, x1, y1 = lay.zones["ground_line"]
        pdf.line(x0 * mm, y0 * mm, x1 * mm, y1 * mm)
        pdf.setFont("Helvetica", 8)
        pdf.drawString(x0 * mm, (y0 - 4) * mm, "stand here")
    if "bail" in lay.zones:
        cx, cy, d = lay.zones["bail"]
        pdf.setLineWidth(0.8 * mm)
        pdf.circle(cx * mm, cy * mm, d / 2 * mm, stroke=1, fill=0)
        pdf.setLineWidth(c["guide_line_width"] * mm)

    # Half-drawn outline: printed black, read as ink, part of the design.
    if "outline" in lay.zones:
        _, poly = lay.zones["outline"]
        pdf.setStrokeColorRGB(0, 0, 0)
        pdf.setLineWidth(c["half_drawn_line"] * mm)
        pdf.setLineJoin(1)
        pdf.setLineCap(1)
        path = pdf.beginPath()
        pts = list(poly.exterior.coords)
        path.moveTo(pts[0][0] * mm, pts[0][1] * mm)
        for x, y in pts[1:]:
            path.lineTo(x * mm, y * mm)
        path.close()
        pdf.drawPath(path, stroke=1, fill=0)

    # Name box (black, outside the drawing box).
    nx, ny, nw, nh = lay.name_box
    pdf.setStrokeColorRGB(0, 0, 0)
    pdf.setFillColorRGB(0, 0, 0)
    pdf.setLineWidth(0.3 * mm)
    pdf.setFont("Helvetica", 11)
    pdf.drawString((nx - 16) * mm, (ny + 3) * mm, "Name:")
    pdf.line(nx * mm, ny * mm, (nx + nw) * mm, ny * mm)

    # Picture rules.
    _draw_rules(pdf, cfg, lay)

    # Check ruler and print note between the bottom markers.
    m, ms = c["margin"], c["marker_size"]
    rx, ry = m + ms + 10, m + 8
    pdf.setLineWidth(0.3 * mm)
    pdf.line(rx * mm, ry * mm, (rx + 50) * mm, ry * mm)
    for t in range(0, 51, 10):
        pdf.line((rx + t) * mm, (ry - 1.5) * mm, (rx + t) * mm, (ry + 1.5) * mm)
    pdf.setFont("Helvetica", 8)
    pdf.drawString(rx * mm, (ry + 3) * mm, "check: this line is 50 mm")
    pdf.drawRightString((pw - m - ms - 4) * mm, (ry + 3) * mm, 'Print at "Actual size" (100%), not "Fit to page"')
    pdf.drawRightString((pw - m - ms - 4) * mm, (ry - 5) * mm, f"charm maker  {lay.stem}")


def _draw_rules(pdf, cfg: dict, lay: CardLayout):
    if cfg["products"][lay.product]["audience"] == "kids":
        return _draw_kid_rules(pdf, cfg, lay)
    return _draw_adult_rules(pdf, cfg, lay)


def _draw_kid_rules(pdf, cfg: dict, lay: CardLayout):
    """Three small pictures: use the colors in the printer, big and bold, color it in."""
    from reportlab.lib.units import mm

    c = cfg["cards"]
    y = c["name_box"][1] - 17
    x0 = c["margin"] + 8
    pdf.setFillColorRGB(0, 0, 0)
    pdf.setStrokeColorRGB(0, 0, 0)

    # 1. A small printer: frame, a plate, a nozzle, and four spools on top.
    pdf.setLineWidth(0.4 * mm)
    pdf.roundRect(x0 * mm, (y + 0.5) * mm, 22 * mm, 10 * mm, 1.2 * mm, stroke=1, fill=0)
    pdf.line((x0 + 3) * mm, (y + 2.5) * mm, (x0 + 19) * mm, (y + 2.5) * mm)              # plate
    pdf.rect((x0 + 9) * mm, (y + 5.5) * mm, 4 * mm, 2.5 * mm, stroke=1, fill=1)           # toolhead
    pdf.line((x0 + 11) * mm, (y + 5.5) * mm, (x0 + 11) * mm, (y + 4.2) * mm)              # nozzle
    spool_colors = [(0.95, 0.95, 0.95), (0.1, 0.1, 0.1), (0.93, 0.3, 0.55), (0.2, 0.45, 0.9)]
    for i, col in enumerate(spool_colors):
        pdf.setFillColorRGB(*col)
        pdf.circle((x0 + 4 + i * 4.7) * mm, (y + 12.8) * mm, 1.9 * mm, stroke=1, fill=1)
    pdf.setFillColorRGB(0, 0, 0)
    pdf.setFont("Helvetica", 8)
    pdf.drawString(x0 * mm, (y - 3) * mm, "Use the colors in the printer")

    # 2. Big and bold: one fat stroke.
    x1 = x0 + 62
    pdf.setLineCap(1)
    pdf.setLineWidth(4.0 * mm)
    pdf.line((x1 + 2) * mm, (y + 5) * mm, (x1 + 24) * mm, (y + 9) * mm)
    pdf.setLineCap(0)
    pdf.setLineWidth(0.3 * mm)
    pdf.drawString(x1 * mm, (y - 3) * mm, "Big and bold")

    # 3. Color it in: an outline with its inside filled.
    x2 = x1 + 55
    pdf.setFillColorRGB(0.93, 0.3, 0.55)
    pdf.setLineWidth(1.4 * mm)
    pdf.circle((x2 + 7) * mm, (y + 6.5) * mm, 6 * mm, stroke=1, fill=1)
    pdf.setFillColorRGB(0, 0, 0)
    pdf.setLineWidth(0.3 * mm)
    pdf.drawString(x2 * mm, (y - 3) * mm, "Color it in")


def _draw_adult_rules(pdf, cfg: dict, lay: CardLayout):
    """Three small pictures: fat marker, black + colors, no pencil or crayon."""
    from reportlab.lib.units import mm

    c = cfg["cards"]
    audience = cfg["products"][lay.product]["audience"]
    y = c["name_box"][1] - 16
    x0 = c["margin"] + 8
    pdf.setFont("Helvetica", 8)
    pdf.setFillColorRGB(0, 0, 0)
    pdf.setStrokeColorRGB(0, 0, 0)

    # 1. Fat marker: a marker body with a thick stroke coming out of it.
    pdf.setLineWidth(0.4 * mm)
    pdf.roundRect(x0 * mm, (y + 2) * mm, 18 * mm, 5 * mm, 1 * mm, stroke=1, fill=0)
    pdf.rect((x0 + 18) * mm, (y + 3) * mm, 4 * mm, 3 * mm, stroke=1, fill=1)
    pdf.setLineWidth(3.5 * mm)
    pdf.line((x0 + 24) * mm, (y + 4.5) * mm, (x0 + 40) * mm, (y + 4.5) * mm)
    pdf.setLineWidth(0.3 * mm)
    pdf.drawString(x0 * mm, (y - 2.5) * mm, "fat marker, press hard")

    # 2. Black + colors.
    x1 = x0 + 55
    pdf.rect(x1 * mm, (y + 1) * mm, 8 * mm, 8 * mm, stroke=1, fill=1)
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString((x1 + 10) * mm, (y + 2.5) * mm, "+")
    ncolors = cfg["process"]["kid_card_max_colors"] if audience == "kids" else cfg["process"]["adult_card_max_colors"]
    swatches = [(0.95, 0.3, 0.5), (0.2, 0.5, 0.95), (0.3, 0.75, 0.3)][:ncolors]
    for i, col in enumerate(swatches):
        pdf.setFillColorRGB(*col)
        pdf.rect((x1 + 16 + i * 10) * mm, (y + 1) * mm, 8 * mm, 8 * mm, stroke=1, fill=1)
    pdf.setFillColorRGB(0, 0, 0)
    pdf.setFont("Helvetica", 8)
    label = "black + 1 color" if ncolors == 1 else f"black + up to {ncolors} colors"
    pdf.drawString(x1 * mm, (y - 2.5) * mm, label)

    # 3. No pencil, no crayon: a pencil and a crayon with a cross through them.
    x2 = x1 + 55
    pdf.setLineWidth(0.4 * mm)
    pdf.rect(x2 * mm, (y + 5.5) * mm, 16 * mm, 2.5 * mm, stroke=1, fill=0)          # pencil body
    pdf.line((x2 + 16) * mm, (y + 5.5) * mm, (x2 + 20) * mm, (y + 6.75) * mm)       # tip
    pdf.line((x2 + 16) * mm, (y + 8) * mm, (x2 + 20) * mm, (y + 6.75) * mm)
    pdf.roundRect(x2 * mm, (y + 1) * mm, 18 * mm, 3 * mm, 1.2 * mm, stroke=1, fill=0)   # crayon
    pdf.setStrokeColorRGB(0.85, 0.1, 0.1)
    pdf.setLineWidth(0.9 * mm)
    pdf.line((x2 - 1) * mm, (y - 0.5) * mm, (x2 + 21) * mm, (y + 9.5) * mm)
    pdf.line((x2 - 1) * mm, (y + 9.5) * mm, (x2 + 21) * mm, (y - 0.5) * mm)
    pdf.setStrokeColorRGB(0, 0, 0)
    pdf.setLineWidth(0.3 * mm)
    pdf.drawString(x2 * mm, (y - 2.5) * mm, "no pencil, no crayon")


def write_calibration_pdf(cfg: dict, palette, out_path: Path, number: int = 1) -> Path:
    """One box per loaded filament (white gets none: it is the paper)."""
    from reportlab.lib.units import mm
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    c = cfg["cards"]
    lay = calibration_layout(cfg, number)
    pw, ph = lay.page
    guide = _hex_to_rgb01(c["guide_color"])
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(out_path), pagesize=(pw * mm, ph * mm))
    pdf.setTitle("Charm Maker marker calibration card")
    dictionary = aruco_dictionary(cfg)
    for ci, corner in enumerate(CORNER_NAMES):
        x, y, s = lay.markers[corner]
        img = _marker_image(dictionary, marker_id(ci, lay.type_id, lay.number))
        pdf.drawImage(ImageReader(img), x * mm, y * mm, s * mm, s * mm)
    pdf.setFillColorRGB(0, 0, 0)
    pdf.setFont("Helvetica-Bold", 22)
    pdf.drawCentredString(pw / 2 * mm, (ph - c["margin"] - 12) * mm, "Marker calibration")
    pdf.setFont("Helvetica", 10)
    pdf.drawCentredString(pw / 2 * mm, (ph - c["margin"] - 18) * mm,
                          "Fill each box solid with the marker that matches the spool in that slot. Then scan this card.")
    for slot, (bx, by, bw, bh) in lay.zones["cells"].items():
        loaded = palette.slots.get(slot)
        pdf.setFillColorRGB(0, 0, 0)
        pdf.setFont("Helvetica-Bold", 14)
        pdf.drawString(bx * mm, (by + bh + 4) * mm, f"Slot {slot}")
        pdf.setFont("Helvetica", 11)
        if loaded is None or loaded.is_white:
            label = "empty" if loaded is None else loaded.filament.name
            pdf.drawString((bx + 18) * mm, (by + bh + 4) * mm, label)
            pdf.setFont("Helvetica", 10)
            note = "nothing loaded: leave blank" if loaded is None else "white is the paper: leave blank"
            pdf.drawString(bx * mm, (by + bh - 4) * mm, note)
            continue
        pdf.drawString((bx + 18) * mm, (by + bh + 4) * mm, loaded.filament.name)
        pdf.setStrokeColorRGB(*guide)
        pdf.setLineWidth(c["guide_line_width"] * mm)
        pdf.roundRect(bx * mm, by * mm, bw * mm, bh * mm, 3 * mm, stroke=1, fill=0)
    m, ms = c["margin"], c["marker_size"]
    rx, ry = m + ms + 10, m + 8
    pdf.setStrokeColorRGB(0, 0, 0)
    pdf.setLineWidth(0.3 * mm)
    pdf.line(rx * mm, ry * mm, (rx + 50) * mm, ry * mm)
    for t in range(0, 51, 10):
        pdf.line((rx + t) * mm, (ry - 1.5) * mm, (rx + t) * mm, (ry + 1.5) * mm)
    pdf.setFont("Helvetica", 8)
    pdf.drawString(rx * mm, (ry + 3) * mm, "check: this line is 50 mm")
    pdf.drawRightString((pw - m - ms - 4) * mm, (ry + 3) * mm, 'Print at "Actual size" (100%), not "Fit to page"')
    pdf.drawRightString((pw - m - ms - 4) * mm, (ry - 5) * mm, f"charm maker  {lay.stem}")
    pdf.showPage()
    pdf.save()
    return out_path


def half_drawn_numbers(cfg: dict) -> list[int]:
    c = cfg["cards"]
    first = c["half_drawn_first_number"]
    return list(range(first, first + len(c["half_drawn_shapes"]) * c["half_drawn_copies"]))
