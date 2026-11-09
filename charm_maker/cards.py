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
}


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
    return CardLayout(product, type_id, number, (pw, ph), markers,
                      (bx, by, size, size), scale, tuple(c["name_box"]), zones)


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


def write_cards_pdf(cfg: dict, products: list[str], out_path: Path, count: int | None = None) -> Path:
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
    for product in products:
        for n in range(1, count + 1):
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
    """Three small pictures: fat marker, black + 1 color, no pencil or crayon."""
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
