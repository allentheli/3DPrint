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
    slot: int | None = None           # loaded AMS slot this ink prints in
    off_palette: dict | None = None   # set when the color is not loaded


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


def ink_mask(cfg: dict, rgb: np.ndarray, ignore: np.ndarray | None = None,
             guide_zone: np.ndarray | None = None):
    """Ink pixels in a lighting-flattened crop.

    Strong ink is dark, or strongly colored, or a faint line that is still clearly
    colored (a thin pink pen). Gray marks that are only a little darker than the paper
    (shadows, pencil) are not ink. The soft edge of a line next to strong ink is ink.
    Guide-colored pixels are removed only near where guides are printed
    (`guide_zone`), so a light-blue pen elsewhere survives."""
    from .filaments import _srgb_to_lab

    rd = cfg["reader"]
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)   # H 0..360, S 0..1, V 0..1 for float input
    H, S, V = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    lab = _srgb_to_lab(rgb.reshape(-1, 3) * 255.0).reshape(rgb.shape)
    chroma = np.hypot(lab[..., 1], lab[..., 2])
    delta = np.sqrt((100.0 - lab[..., 0]) ** 2 + chroma ** 2)
    strong = (V < rd["ink_value_max"]) | (S > rd["ink_saturation_min"]) | (
        (chroma > rd["faint_chroma_min"]) & (delta > rd["faint_delta_min"]))
    dh = np.abs(((H - rd["guide_hue"]) + 180.0) % 360.0 - 180.0)
    guide = (dh < rd["guide_hue_tolerance"]) & (S < rd["guide_saturation_max"]) & (V > 0.55)
    if guide_zone is not None:
        guide &= guide_zone
    strong &= ~guide
    if ignore is not None:
        strong &= ~ignore
    # Drop isolated noise dots, but keep lines only 1-2 pixels wide.
    n, labels, stats, _ = cv2.connectedComponentsWithStats(strong.astype(np.uint8), connectivity=8)
    small = np.flatnonzero(stats[:, cv2.CC_STAT_AREA] < rd["min_blob_px"])
    small = small[small > 0]
    if small.size:
        strong &= ~np.isin(labels, small)
    # Soft edges: a little different from paper and right next to strong ink.
    k = 2 * rd["halo_px"] + 1
    near = cv2.dilate(strong.astype(np.uint8), np.ones((k, k), np.uint8)).astype(bool)
    ink = strong | (near & (delta > rd["halo_delta_min"]) & ~guide)
    if ignore is not None:
        ink &= ~ignore
    return ink, H, S, V


def separate_inks(cfg: dict, bgr: np.ndarray, max_colors: int, ignore: np.ndarray | None = None) -> InkResult:
    rd = cfg["reader"]
    rgb = flatten_lighting(bgr)
    ink, H, S, V = ink_mask(cfg, rgb, ignore)
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


# ---------------------------------------------------------------------------
# Color separation: every distinct ink color becomes its own part
# ---------------------------------------------------------------------------

def separate_colors(cfg: dict, bgr: np.ndarray, *, px_per_mm: float, max_colors: int | None = None,
                    ignore: np.ndarray | None = None, guide_zone: np.ndarray | None = None) -> InkResult:
    """Find the distinct ink colors in a drawing, whatever they are. Colors are told
    apart mostly by hue, so streaky or pale fill of one marker stays one color while an
    orange next to a yellow stays two. Patches smaller than a few mm² or thin fringes
    between two inks are camera noise and join their neighbor."""
    from .filaments import _srgb_to_lab
    from .palette import color_word, lab_distance

    pr = cfg["process"]
    pc = cfg["palette"]
    thr = pr["color_merge_distance"]
    lw, cw = pc["lightness_weight"], pc["chroma_weight"]
    max_colors = max_colors or pr["max_ink_colors"]
    min_area_px = pr["min_color_area_mm2"] * px_per_mm ** 2

    rgb = flatten_lighting(bgr)
    ink, _, _, _ = ink_mask(cfg, rgb, ignore, guide_zone)
    paper = rgb[~ink] if (~ink).any() else rgb.reshape(-1, 3)
    paper_rgb = tuple(int(v * 255) for v in np.median(paper.reshape(-1, 3), axis=0))
    notes: list[str] = []
    if not ink.any():
        return InkResult([], paper_rgb, notes)

    idx = np.flatnonzero(ink.ravel())
    lab = _srgb_to_lab(rgb.reshape(-1, 3)[idx] * 255.0)

    # Seeds: the most common colors, each far enough from the ones already taken.
    q = np.floor(lab / np.array([6.0, 6.0, 6.0])).astype(np.int32)
    keys, inverse, counts = np.unique(q, axis=0, return_inverse=True, return_counts=True)
    inverse = inverse.ravel()
    order = np.argsort(-counts)
    seeds: list[np.ndarray] = []
    for k in order:
        if counts[k] < 0.3 * min_area_px:
            break
        center = lab[inverse == k].mean(axis=0)
        if all(float(lab_distance(center[None, :], sd, lw, cw)[0]) > thr for sd in seeds):
            seeds.append(center)
        if len(seeds) >= 40:      # crayon texture makes many in-between shades; small colors
            break                 # (eyes) must still get a seed, merging sorts them out later
    if not seeds:
        seeds = [lab.mean(axis=0)]

    def assign(seed_list):
        dist = np.stack([lab_distance(lab, sd, lw, cw) for sd in seed_list])
        return dist, np.argmin(dist, axis=0)

    # Two refinement rounds: move each seed to the middle of its pixels.
    for _ in range(2):
        dist, near = assign(seeds)
        seeds = [np.median(lab[near == i], axis=0) if (near == i).any() else seeds[i] for i in range(len(seeds))]
    dist, near = assign(seeds)

    # Drop colors that are only fringe: too small, or nothing left after a 0.3 mm opening.
    r = max(1, int(round(0.3 * px_per_mm)))
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))
    alive = list(range(len(seeds)))
    changed = True
    while changed and len(alive) > 1:
        changed = False
        for i in list(alive):
            mask = np.zeros(ink.shape, np.uint8)
            mask.ravel()[idx[near == i]] = 1
            solid = int(cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel).sum())
            if solid < min_area_px:
                alive.remove(i)
                dist[i] = np.inf
                near = np.argmin(dist, axis=0)
                changed = True
                break

    # More colors than one AMS can hold: merge the two most alike, and say so. (Merging
    # the smallest instead would wipe out small but important colors, like black eyes.)
    sizes = {i: int((near == i).sum()) for i in alive}
    flat_rgb = rgb.reshape(-1, 3)
    before_cap = near.copy()
    capped: list[int] = []
    while len(alive) > max_colors:
        # Compare each color as the pen really is (its strongest pixels, not its pale
        # edges), on full color difference with lightness included: dark brown eyes on an
        # orange body are not "alike" even though their hues are close.
        rep = {i: _srgb_to_lab(np.asarray(_representative(flat_rgb[idx[near == i]], lab[near == i]), float))
               for i in alive}
        pairs = [(float(np.linalg.norm(rep[i] - rep[j])), i, j)
                 for a, i in enumerate(alive) for j in alive[a + 1:]]
        _, i, j = min(pairs)
        drop, keep = (i, j) if sizes[i] < sizes[j] else (j, i)
        alive.remove(drop)
        capped.append(drop)
        w_drop = color_word(tuple(int(v) for v in _lab_to_rgb(rep[drop])))
        w_keep = color_word(tuple(int(v) for v in _lab_to_rgb(rep[keep])))
        dist[drop] = np.inf
        near[near == drop] = keep          # the merged color's pixels join its partner
        sizes = {i: int((near == i).sum()) for i in alive}
        notes.append(f"more than {max_colors} colors: the two most alike ({w_drop} and {w_keep}) print as one")

    flat_rgb = rgb.reshape(-1, 3)
    notes += _lost_marks(cfg, ink, idx, lab, flat_rgb, near, seeds, before_cap, capped, px_per_mm)
    layers: list[InkLayer] = []
    used: dict[str, int] = {}
    for i in sorted(alive, key=lambda i: float(np.median(lab[near == i][:, 0])) if (near == i).any() else 0):
        sel = idx[near == i]
        if sel.size == 0:
            continue
        mask = np.zeros(ink.shape, bool)
        mask.ravel()[sel] = True
        rep = _representative(flat_rgb[sel], lab[near == i])
        word = color_word(rep)
        used[word] = used.get(word, 0) + 1
        name = word if used[word] == 1 else f"{word} {used[word]}"
        layers.append(InkLayer(name, rep, mask, None, int(sel.size)))
    return InkResult(layers, paper_rgb, notes)


def _lost_marks(cfg, ink, idx, lab, flat_rgb, near, seeds, before_cap, capped, px_per_mm) -> list[str]:
    """Never change a drawn color silently. A small but real mark (a tongue on a hair
    clip) can be too small to be its own color and print in its neighbor's color. It is a
    solid, strongly colored blob at the card's own scale, unlike camera fringe along a
    line. Colors merged because of the color limit already have their own note."""
    from .palette import color_word, lab_distance

    pr, pc = cfg["process"], cfg["palette"]
    px_card = px_per_mm / pr["card_scale"]
    far = np.zeros(len(idx), bool)
    for j in np.unique(near):
        sel = near == j
        far[sel] = lab_distance(lab[sel], seeds[j], pc["lightness_weight"], pc["chroma_weight"]) > pr["color_merge_distance"]
    chroma = np.hypot(lab[:, 1], lab[:, 2])
    far &= (chroma >= 20.0) & ~np.isin(before_cap, capped)
    if not far.any():
        return []
    mask = np.zeros(ink.shape, np.uint8)
    mask.ravel()[idx[far]] = 1
    rc = max(1, int(round(0.25 * px_card)))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * rc + 1, 2 * rc + 1)))
    n, lbl, stats, _ = cv2.connectedComponentsWithStats(mask)
    pos = {int(p): k for k, p in enumerate(idx)}
    notes = []
    for c in range(1, n):
        if stats[c, cv2.CC_STAT_AREA] < 1.0 * px_card ** 2:
            continue
        ks = np.array([pos[int(p)] for p in np.flatnonzero(lbl.ravel() == c) if int(p) in pos])
        if ks.size == 0:
            continue
        word = color_word(_representative(flat_rgb[idx[ks]], lab[ks]))
        j = int(np.bincount(near[ks]).argmax())
        into = color_word(_representative(flat_rgb[idx[near == j]], lab[near == j]))
        if word == into:
            continue
        area = stats[c, cv2.CC_STAT_AREA] / px_per_mm ** 2
        notes.append(f"a small {word} mark ({area:.1f} mm² at real size) is too small to print as its own color "
                     f"and prints {into}; it would show on a bigger piece")
    return notes


def _representative(rgb01: np.ndarray, lab: np.ndarray) -> tuple[int, int, int]:
    """The color a pen or marker really is: thin lines are mostly soft, pale edge, so the
    average looks washed out. Use the strongest pixels instead: the darkest ones for dark
    or gray inks, the most colorful ones for bright inks."""
    chroma = np.hypot(lab[:, 1], lab[:, 2])
    if np.median(chroma) < 15 or np.median(lab[:, 0]) < 55:
        sel = lab[:, 0] <= np.percentile(lab[:, 0], 30)
    else:
        sel = chroma >= np.percentile(chroma, 70)
    return tuple(int(v) for v in np.median(rgb01[sel] * 255, axis=0))


def _lab_to_rgb(lab: np.ndarray) -> np.ndarray:
    from skimage.color import lab2rgb

    return np.clip(lab2rgb(np.asarray(lab, dtype=np.float64)[None, None, :])[0, 0] * 255, 0, 255)
