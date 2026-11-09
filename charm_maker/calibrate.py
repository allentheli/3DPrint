"""Read a scanned marker calibration card: the photographed color of each marker."""

from __future__ import annotations

import numpy as np

from .inks import flatten_lighting
from .reader import CardRead


def measure_markers(cfg: dict, read: CardRead) -> tuple[dict[int, tuple[int, int, int]], list[str]]:
    """Median ink color in each slot's box. Boxes with too little ink are skipped."""
    assert read.layout is not None and read.layout.product == "calibration"
    min_cov = cfg["palette"]["calibration_min_coverage"]
    ppm = read.px_per_card_mm
    lay = read.layout
    H = lay.page[1]
    # Flatten the light over the whole box area at once so every box is measured alike.
    bx, by, bw, bh = lay.box
    m = 6.0
    x0, x1 = int((bx - m) * ppm), int((bx + bw + m) * ppm)
    y0, y1 = int((H - (by + bh + m)) * ppm), int((H - (by - m)) * ppm)
    crop = read.page[max(y0, 0):y1, max(x0, 0):x1]
    rgb = flatten_lighting(crop)
    import cv2

    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    S, V = hsv[:, :, 1], hsv[:, :, 2]
    ink = (V < 0.70) | (S > 0.25)
    markers: dict[int, tuple[int, int, int]] = {}
    notes: list[str] = []
    inset = 4.0
    for slot, (cx, cy, cw, ch) in lay.zones["cells"].items():
        sx0 = int((cx + inset - bx + m) * ppm)
        sx1 = int((cx + cw - inset - bx + m) * ppm)
        sy0 = int(((by + bh + m) - (cy + ch - inset)) * ppm)
        sy1 = int(((by + bh + m) - (cy + inset)) * ppm)
        cell_ink = ink[sy0:sy1, sx0:sx1]
        if cell_ink.size == 0:
            continue
        coverage = float(cell_ink.mean())
        if coverage < min_cov:
            if coverage > 0.05:
                notes.append(f"slot {slot}: box only {coverage:.0%} filled in; fill it solid and rescan")
            continue
        px = rgb[sy0:sy1, sx0:sx1][cell_ink]
        markers[slot] = tuple(int(round(v * 255)) for v in np.median(px, axis=0))
    return markers, notes
