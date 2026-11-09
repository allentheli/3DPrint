"""Raised number labels built from a simple stroke font (no font files needed)."""

from __future__ import annotations

from shapely.ops import unary_union

from .geom import stroke_polygon

# Each glyph is a list of polylines on a 2 wide x 4 tall grid.
_GLYPHS: dict[str, list[list[tuple[float, float]]]] = {
    "0": [[(0, 0), (2, 0), (2, 4), (0, 4), (0, 0)]],
    "1": [[(0, 3), (1, 4), (1, 0)], [(0, 0), (2, 0)]],
    "2": [[(0, 4), (2, 4), (2, 2), (0, 2), (0, 0), (2, 0)]],
    "3": [[(0, 4), (2, 4), (2, 0), (0, 0)], [(0.4, 2), (2, 2)]],
    "4": [[(0, 4), (0, 2), (2, 2)], [(2, 4), (2, 0)]],
    "5": [[(2, 4), (0, 4), (0, 2), (2, 2), (2, 0), (0, 0)]],
    "6": [[(2, 4), (0, 4), (0, 0), (2, 0), (2, 2), (0, 2)]],
    "7": [[(0, 4), (2, 4), (2, 0)]],
    "8": [[(0, 0), (2, 0), (2, 4), (0, 4), (0, 0)], [(0, 2), (2, 2)]],
    "9": [[(2, 0), (2, 4), (0, 4), (0, 2), (2, 2)]],
    "S": [[(2, 4), (0, 4), (0, 2), (2, 2), (2, 0), (0, 0)]],
    "-": [[(0, 2), (2, 2)]],
    ".": [[(1, 0), (1, 0.01)]],
}

GLYPH_W = 2.0
GLYPH_H = 4.0
GLYPH_GAP = 1.0


def label_shape(text: str, height: float, stroke: float, cx: float = 0.0, cy: float = 0.0):
    """Return a Shapely polygon for `text`, centred on (cx, cy)."""
    scale = height / GLYPH_H
    n = len(text)
    total_w = (n * GLYPH_W + (n - 1) * GLYPH_GAP) * scale
    x0 = cx - total_w / 2.0
    y0 = cy - height / 2.0
    pieces = []
    for i, ch in enumerate(text):
        glyph = _GLYPHS.get(ch)
        if glyph is None:
            raise ValueError(f"no glyph for {ch!r}")
        ox = x0 + i * (GLYPH_W + GLYPH_GAP) * scale
        for line in glyph:
            pts = [(ox + x * scale, y0 + y * scale) for x, y in line]
            pieces.append(stroke_polygon(pts, stroke))
    return unary_union(pieces)


def label_width(text: str, height: float, stroke: float) -> float:
    scale = height / GLYPH_H
    n = len(text)
    return (n * GLYPH_W + (n - 1) * GLYPH_GAP) * scale + stroke
