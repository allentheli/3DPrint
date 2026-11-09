"""Separate the inks in a drawing-box crop: paper and printed guides go away, black
and up to N colors remain, each as a mask at a known resolution."""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

COLOR_NAMES = [  # hue degrees -> plain name, used for part names
    (0, "red"), (20, "orange"), (50, "yellow"), (80, "lime"), (120, "green"),
    (170, "teal"), (200, "sky blue"), (230, "blue"), (270, "purple"), (300, "magenta"),
    (330, "pink"), (360, "red"),
]


@dataclass
class InkLayer:
    name: str                 # "black", "pink"...
    rgb: tuple[int, int, int] # representative color, 0-255
    mask: np.ndarray          # bool, same shape as the crop
    hue: float | None = None
    pixels: int = 0


@dataclass
class InkResult:
    layers: list[InkLayer]
    paper_rgb: tuple[int, int, int]
    notes: list[str] = field(default_factory=list)


def flatten_lighting(bgr: np.ndarray) -> np.ndarray:
    """Divide each channel by a smooth estimate of the paper brightness, so shadows
    and uneven light go away. Returns float32 RGB in 0..1."""
    img = bgr[:, :, ::-1].astype(np.float32) / 255.0
    h, w = img.shape[:2]
    tile = max(16, min(h, w) // 24)
    ys = np.arange(0, h, tile)
    xs = np.arange(0, w, tile)
    out = np.empty_like(img)
    gray = img.mean(axis=2)
    # Tiles that are mostly paper: their 95th percentile is near the brightest in the image.
    tile_vals = np.array([[np.percentile(gray[y:y + tile, x:x + tile], 95) for x in xs] for y in ys])
    bright = np.percentile(tile_vals, 98)
    paper_tiles = tile_vals >= bright * 0.85
    cy = (ys[:, None] + tile / 2).repeat(len(xs), 1)
    cx = (xs[None, :] + tile / 2).repeat(len(ys), 0)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    for ch in range(3):
        vals = np.array([[np.percentile(img[y:y + tile, x:x + tile, ch], 95) for x in xs] for y in ys])
        if paper_tiles.sum() >= 8:
            A = _quad_terms(cx[paper_tiles] / w, cy[paper_tiles] / h)
            coef, *_ = np.linalg.lstsq(A, vals[paper_tiles], rcond=None)
            field_ = (_quad_terms(xx.ravel() / w, yy.ravel() / h) @ coef).reshape(h, w)
            field_ = np.clip(field_, 0.2, 1.5)
        else:
            field_ = np.full((h, w), max(float(np.percentile(vals, 95)), 0.2), np.float32)
        out[:, :, ch] = np.clip(img[:, :, ch] / field_, 0.0, 1.0)
    return out


def _quad_terms(x, y):
    return np.stack([np.ones_like(x), x, y, x * y, x * x, y * y], axis=1)


def separate_inks(cfg: dict, bgr: np.ndarray, max_colors: int, ignore: np.ndarray | None = None) -> InkResult:
    rd = cfg["reader"]
    rgb = flatten_lighting(bgr)
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)   # H 0..360, S 0..1, V 0..1 for float input
    H, S, V = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    ink = (V < rd["ink_value_max"]) | (S > rd["ink_saturation_min"])
    dh = np.abs(((H - rd["guide_hue"]) + 180.0) % 360.0 - 180.0)
    guide = (dh < rd["guide_hue_tolerance"]) & (S < rd["guide_saturation_max"]) & (V > 0.55)
    ink &= ~guide
    if ignore is not None:
        ink &= ~ignore
    # Light clean-up of single-pixel noise before classifying.
    ink = cv2.morphologyEx(ink.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)).astype(bool)
    black = ink & (S < rd["black_saturation_max"]) & (V < rd["black_value_max"])
    color = ink & ~black
    notes: list[str] = []
    layers: list[InkLayer] = []
    if black.any():
        layers.append(InkLayer("black", (20, 20, 20), black, None, int(black.sum())))

    n_color = int(color.sum())
    if n_color > 0:
        hues = H[color]
        weights = S[color]
        hist, _ = np.histogram(hues, bins=72, range=(0, 360), weights=weights)
        # Circular smoothing.
        k = np.array([1, 2, 3, 2, 1], dtype=np.float64)
        sm = np.convolve(np.concatenate([hist[-2:], hist, hist[:2]]), k / k.sum(), mode="valid")
        peaks = [i for i in range(72) if sm[i] >= sm[(i - 1) % 72] and sm[i] >= sm[(i + 1) % 72] and sm[i] > 0]
        peaks.sort(key=lambda i: -sm[i])
        centers: list[float] = []
        for i in peaks:
            hue = i * 5.0 + 2.5
            if all(_hue_dist(hue, c) >= rd["hue_merge_deg"] for c in centers):
                centers.append(hue)
        # Assign pixels to the nearest center, then drop tiny colors and merge extras.
        assign = np.argmin([_hue_dist(hues, c) for c in centers], axis=0)
        counts = np.bincount(assign, minlength=len(centers))
        order = np.argsort(-counts)
        keep = [i for i in order if counts[i] >= rd["min_color_fraction"] * n_color][:max_colors]
        if not keep:
            keep = [int(order[0])]
        dropped = [i for i in range(len(centers)) if i not in keep and counts[i] >= rd["min_color_fraction"] * n_color]
        if dropped:
            dropped_names = sorted({_hue_name(centers[i]) for i in dropped})
            notes.append(f"extra color(s) {', '.join(dropped_names)} merged into the nearest kept color")
        keep_centers = [centers[i] for i in keep]
        assign2 = np.argmin([_hue_dist(hues, c) for c in keep_centers], axis=0)
        idx = np.flatnonzero(color.ravel())
        used_names: dict[str, int] = {}
        for j, c in enumerate(keep_centers):
            mask = np.zeros(color.shape, bool)
            sel = idx[assign2 == j]
            mask.ravel()[sel] = True
            px = (rgb.reshape(-1, 3)[sel] * 255).astype(int)
            rep = tuple(int(v) for v in np.median(px, axis=0)) if len(px) else (128, 128, 128)
            name = _hue_name(c)
            if name in used_names:
                used_names[name] += 1
                name = f"{name} {used_names[name]}"
            else:
                used_names[name] = 1
            layers.append(InkLayer(name, rep, mask, c, int(mask.sum())))
    paper = rgb[~ink] if (~ink).any() else rgb.reshape(-1, 3)
    paper_rgb = tuple(int(v * 255) for v in np.median(paper.reshape(-1, 3), axis=0))
    return InkResult(layers, paper_rgb, notes)


def _hue_dist(a, b):
    return np.abs((np.asarray(a) - b + 180.0) % 360.0 - 180.0)


def _hue_name(hue: float) -> str:
    best = min(COLOR_NAMES, key=lambda t: _hue_dist(hue, t[0]))
    return best[1]
