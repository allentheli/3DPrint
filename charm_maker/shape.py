"""Turn ink masks into a printable outline and color regions, logging every fix."""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np
from scipy import ndimage
from shapely import affinity
from shapely.geometry import LineString, MultiPolygon, Polygon
from shapely.ops import nearest_points, unary_union
from skimage.morphology import skeletonize

from .inks import InkLayer


@dataclass
class InkRegion:
    name: str
    rgb: tuple[int, int, int]
    geometry: MultiPolygon        # real mm, Y up
    slot: int | None = None
    off_palette: dict | None = None


@dataclass
class Design:
    name: str                     # file stem, e.g. clip-03
    product: str
    outline: Polygon              # real mm, Y up, one polygon (may have holes? no: filled)
    inks: list[InkRegion]
    fixes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    name_image: np.ndarray | None = None
    source: str = ""
    paper_rgb: tuple[int, int, int] = (250, 250, 250)
    card: str = ""                # the card it came from (key-03), when named after the kid
    extras: dict = field(default_factory=dict)   # attachment info filled by products
    dots: list = field(default_factory=list)     # small dots kept (eyes), real mm, circled on the preview


def _disk(radius_px: float) -> np.ndarray:
    r = max(1, int(round(radius_px)))
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))


def _u8(mask: np.ndarray) -> np.ndarray:
    return mask.astype(np.uint8)


def remove_specks(mask: np.ndarray, min_area_px: float, min_extent_px: float = 0.0,
                  min_dot_px: float | None = None) -> tuple[np.ndarray, int]:
    """Remove small dots. A mark is only a speck if it is both small in area and short:
    a thin smile, an eyelash or a whisker is small in area but long, and stays (it gets
    thickened). Length is measured along the mark, so a slanted whisker counts in full.
    A small round, solid dot of at least `min_dot_px` is an eye (the cat's and the
    butterfly's eyes were 0.25 to 0.6 mm² at real size) and stays too; it is thickened
    to the printable size later. Only dust-sized marks are removed."""
    n, labels, stats, _ = cv2.connectedComponentsWithStats(_u8(mask), connectivity=8)
    keep = np.zeros(n, bool)
    keep[1:] = stats[1:, cv2.CC_STAT_AREA] >= min_area_px
    for i in np.flatnonzero(~keep[1:]) + 1:
        x, y, w, h = stats[i, :4]
        one = labels[y:y + h, x:x + w] == i
        pts = np.column_stack(np.nonzero(one))[:, ::-1].astype(np.float32)
        (_, _), (rw, rh), _ = cv2.minAreaRect(pts)
        long_side = max(rw, rh) + 1.0
        if min_extent_px > 0 and long_side >= min_extent_px:
            keep[i] = True
        elif min_dot_px is not None and stats[i, cv2.CC_STAT_AREA] >= min_dot_px:
            keep[i] = bool(round_dots(one, np.inf).any())       # round and solid: an eye
    removed = int((~keep[1:]).sum())
    return keep[labels], removed


def fill_small_holes(mask: np.ndarray, max_area_px: float,
                     keep: np.ndarray | None = None) -> tuple[np.ndarray, int]:
    """Fill paper holes smaller than `max_area_px` (pinholes in colored-in areas), except
    the ones in `keep` (the inside of a ring eye)."""
    inv = ~mask
    n, labels, stats, _ = cv2.connectedComponentsWithStats(_u8(inv), connectivity=4)
    h, w = mask.shape
    filled = mask.copy()
    count = 0
    for i in range(1, n):
        x, y, bw, bh, area = stats[i]
        touches = x == 0 or y == 0 or x + bw >= w or y + bh >= h
        if not touches and area <= max_area_px:
            hole = labels[y:y + bh, x:x + bw] == i
            if keep is not None and keep[y:y + bh, x:x + bw][hole].any():
                continue
            filled[y:y + bh, x:x + bw] |= hole
            count += 1
    return filled, count


def small_mark_holes(mask: np.ndarray, max_hole_px: float, min_width_px: float,
                     max_mark_px: float, min_sliver_px: float = np.inf) -> np.ndarray:
    """The paper inside small closed marks: the white ring of a ring eye, the inside of a
    little heart (Allen, 2026-11-12: the bird's ring eyes came out as black blobs). A hole
    counts when the mark around it is small (its outline encloses at most `max_mark_px`)
    and the hole is at least `min_width_px` wide, so it prints. A thinner sliver at least
    `min_sliver_px` long (the hairline white between the bird's inner and outer eye
    rings, 0.3 mm wide) is widened to `min_width_px` along its middle, like marks drawn
    almost touching. Pinholes in colored-in areas (inside a big mark, or tiny) are not
    kept."""
    n, labels, stats, _ = cv2.connectedComponentsWithStats(_u8(~mask), connectivity=4)
    keep = np.zeros_like(mask)
    if n <= 2:
        return keep
    _, comp, cstats, _ = cv2.connectedComponentsWithStats(_u8(mask), connectivity=8)
    h, w = mask.shape
    hull_area: dict[int, float] = {}
    for i in range(1, n):
        x, y, bw, bh, area = stats[i]
        if x == 0 or y == 0 or x + bw >= w or y + bh >= h or area > max_hole_px:
            continue
        hole = labels[y:y + bh, x:x + bw] == i
        inner = cv2.distanceTransform(np.pad(_u8(hole), 1), cv2.DIST_L2, 5).max()
        sliver = 2.0 * inner < min_width_px
        if sliver and skeletonize(hole).sum() < min_sliver_px:
            continue
        y0, y1, x0, x1 = max(0, y - 1), min(h, y + bh + 1), max(0, x - 1), min(w, x + bw + 1)
        around = cv2.dilate(_u8(labels[y0:y1, x0:x1] == i), np.ones((3, 3), np.uint8)).astype(bool)
        marks = comp[y0:y1, x0:x1][around & mask[y0:y1, x0:x1]]
        if not len(marks):
            continue
        c = int(np.bincount(marks).argmax())
        if c not in hull_area:
            cx, cy, cw, ch = cstats[c, :4]
            if cw * ch > 4 * max_mark_px:
                hull_area[c] = np.inf
            else:
                pts = np.column_stack(np.nonzero(comp[cy:cy + ch, cx:cx + cw] == c))[:, ::-1].astype(np.int32)
                hull_area[c] = cv2.contourArea(cv2.convexHull(pts))
        if hull_area[c] > max_mark_px:
            continue
        # Widen the gap along its whole middle to `min_width_px`, taking the room only from
        # ink that keeps at least that much on its other side: an outer ring gives way (it
        # grows outward later), an inner ring between two gaps keeps its thickness.
        r = int(np.ceil(min_width_px)) + 2
        wy0, wy1, wx0, wx1 = max(0, y - r), min(h, y + bh + r), max(0, x - r), min(w, x + bw + r)
        here = labels[wy0:wy1, wx0:wx1] == i
        wide = cv2.dilate(_u8(skeletonize(here)), _disk(min_width_px / 2.0)).astype(bool)
        other_paper = (~mask[wy0:wy1, wx0:wx1] | keep[wy0:wy1, wx0:wx1]) & ~here
        room = cv2.distanceTransform(_u8(~other_paper), cv2.DIST_L2, 5) >= min_width_px
        keep[wy0:wy1, wx0:wx1] |= here | (wide & (comp[wy0:wy1, wx0:wx1] == c) & room)
    return keep


def fill_all_holes(mask: np.ndarray) -> np.ndarray:
    """Everything enclosed by ink becomes part of the silhouette."""
    h, w = mask.shape
    paper = np.ones((h + 2, w + 2), np.uint8)      # a paper frame so the outside is one region
    paper[1:-1, 1:-1] = ~mask
    n, labels = cv2.connectedComponents(paper, connectivity=4)
    outside = labels[0, 0]
    return labels[1:-1, 1:-1] != outside


def smooth_labels(label_map: np.ndarray, n_labels: int, radius_px: int) -> np.ndarray:
    """Majority vote among ink labels in a window, for ink pixels only. Removes the
    color fringe that cameras and JPEG leave where two inks meet."""
    k = 2 * radius_px + 1
    ink = label_map > 0
    counts = []
    for lab in range(1, n_labels + 1):
        ind = (label_map == lab).astype(np.float32)
        counts.append(cv2.boxFilter(ind, -1, (k, k), normalize=False))
    best = np.argmax(np.stack(counts), axis=0) + 1
    out = np.where(ink, best, 0).astype(label_map.dtype)
    return out


def _between_marks(mask: np.ndarray, gap_px: float) -> np.ndarray:
    """A band `gap_px` wide along the line halfway between separate marks (8-connected,
    so a stroke that only touches itself at a corner is still one mark)."""
    n, comp = cv2.connectedComponents(_u8(mask), connectivity=8)
    if n <= 2 or gap_px <= 0:
        return np.zeros_like(mask)
    _, (iy, ix) = ndimage.distance_transform_edt(~mask, return_indices=True)
    near = comp[iy, ix]
    edge = np.zeros_like(mask)
    edge[:, 1:] |= near[:, 1:] != near[:, :-1]
    edge[1:, :] |= near[1:, :] != near[:-1, :]
    return cv2.dilate(_u8(edge), _disk(gap_px / 2.0)).astype(bool)


def _keep_apart(mask: np.ndarray, gap_px: float) -> np.ndarray:
    """Where separate marks may not grow: a band around the line halfway between them, so
    two marks thickened toward each other stop `gap_px` apart. Eyes next to a mouth stay
    eyes."""
    return _between_marks(mask, gap_px) & ~mask


def round_dots(mask: np.ndarray, max_area_px: float) -> np.ndarray:
    """Small round, solid marks (eyes, dots on a wing): not much longer than wide and
    filling most of their box. These keep their round shape through every fix."""
    n, comp, stats, _ = cv2.connectedComponentsWithStats(_u8(mask), connectivity=8)
    out = np.zeros_like(mask)
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if area >= max_area_px:
            continue
        one = comp[y:y + h, x:x + w] == i
        pts = np.column_stack(np.nonzero(one))[:, ::-1].astype(np.float32)
        (_, _), (rw, rh), _ = cv2.minAreaRect(pts)
        long_side, short_side = max(rw, rh) + 1.0, min(rw, rh) + 1.0
        contours = cv2.findContours(_u8(one), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)[0]
        hull = cv2.contourArea(cv2.convexHull(np.vstack(contours))) + cv2.arcLength(
            cv2.convexHull(np.vstack(contours)), True) / 2.0 + 1.0    # pixel-area of the hull
        if long_side <= 1.8 * short_side and area >= 0.8 * hull:
            out[y:y + h, x:x + w] |= one
    return out


def _signed(m: np.ndarray) -> np.ndarray:
    return (cv2.distanceTransform(_u8(m), cv2.DIST_L2, 5)
            - cv2.distanceTransform(_u8(~m), cv2.DIST_L2, 5))


def eye_pairs(dots: np.ndarray) -> list[tuple[np.ndarray, np.ndarray]]:
    """Pairs of round dots that look like a pair of eyes: about the same size, side by side
    (within 35 degrees of level), and between 1.5 and 6 eye-widths apart. Each dot is in
    one pair at most, closest pairs first. Returns the two dots' masks, left one first."""
    n, comp, stats, cents = cv2.connectedComponentsWithStats(_u8(dots), connectivity=8)
    cand = []
    for a in range(1, n):
        for b in range(a + 1, n):
            aa, ab = stats[a, 4], stats[b, 4]
            if max(aa, ab) > 2.5 * min(aa, ab):
                continue
            d = np.hypot(*(cents[a] - cents[b]))
            size = np.sqrt(4.0 * (aa + ab) / 2.0 / np.pi)
            dx, dy = abs(cents[a][0] - cents[b][0]), abs(cents[a][1] - cents[b][1])
            if 1.5 * size <= d <= 6.0 * size and dy <= np.tan(np.radians(35)) * dx:
                cand.append((d / size, a, b))
    used: set[int] = set()
    out = []
    for _, a, b in sorted(cand):
        if a in used or b in used:
            continue
        used |= {a, b}
        if cents[a][0] > cents[b][0]:
            a, b = b, a
        out.append((comp == a, comp == b))
    return out


def symmetric_eyes(left: np.ndarray, right: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Give a pair of eyes the same shape and size (Allen: eyes symmetrical when they can
    be): the average of the left eye and the mirrored right eye, mirrored back for the
    right one. Each stays where it was drawn."""
    def window(m):
        ys, xs = np.nonzero(m)
        return int(round(ys.mean())), int(round(xs.mean()))
    r = int(max(np.ptp(np.nonzero(left)[0]), np.ptp(np.nonzero(left)[1]),
                np.ptp(np.nonzero(right)[0]), np.ptp(np.nonzero(right)[1]))) + 4
    pad = lambda m: np.pad(m, r)
    (cy_l, cx_l), (cy_r, cx_r) = window(left), window(right)
    lw = pad(left)[cy_l:cy_l + 2 * r + 1, cx_l:cx_l + 2 * r + 1]
    rw = pad(right)[cy_r:cy_r + 2 * r + 1, cx_r:cx_r + 2 * r + 1]
    mean = (_signed(lw) + _signed(np.fliplr(rw))) / 2.0 > 0
    out_l, out_r = np.zeros_like(pad(left)), np.zeros_like(pad(right))
    out_l[cy_l:cy_l + 2 * r + 1, cx_l:cx_l + 2 * r + 1] = mean
    out_r[cy_r:cy_r + 2 * r + 1, cx_r:cx_r + 2 * r + 1] = np.fliplr(mean)
    return out_l[r:-r, r:-r], out_r[r:-r, r:-r]


def _count(mask: np.ndarray) -> int:
    return cv2.connectedComponents(_u8(mask), connectivity=8)[0] - 1


def _window(one: np.ndarray, pad: int) -> tuple[slice, slice]:
    ys, xs = np.nonzero(one)
    return (slice(max(0, ys.min() - pad), min(one.shape[0], ys.max() + 1 + pad)),
            slice(max(0, xs.min() - pad), min(one.shape[1], xs.max() + 1 + pad)))


def _grow(one: np.ndarray, add: float) -> np.ndarray:
    return cv2.dilate(_u8(one), _disk(add)).astype(bool) if add >= 0.5 else one


def _dot_fit(one: np.ndarray, lines: np.ndarray, other_dots: np.ndarray,
             min_width_px: float, gap_px: float) -> float | None:
    """How much this dot may grow toward the printable width: it stays `gap_px` from other
    dots, and the lines nearby may give way but must not be cut in two. None when even the
    dot as drawn would cut a line."""
    want = max(0.0, min_width_px / 2.0 - float(cv2.distanceTransform(_u8(one), cv2.DIST_L2, 5).max()))
    win = _window(one, int(np.ceil(want + 3 * gap_px)) + 2)
    o, ln, od = one[win], lines[win], other_dots[win]
    near_dot = cv2.distanceTransform(_u8(~od), cv2.DIST_L2, 5)[o].min() if od.any() else np.inf
    top = min(want, max(0.0, float(near_dot) - gap_px))
    pieces = _count(ln)
    for add in sorted({top, *range(int(top), -1, -1)}, reverse=True):
        trimmed = ln & (cv2.distanceTransform(_u8(~_grow(o, add)), cv2.DIST_L2, 5) > gap_px)
        if _count(trimmed) <= pieces:
            return float(add)
    return None


def _dot_place(one: np.ndarray, lines: np.ndarray, add: float | None,
               gap_px: float) -> tuple[np.ndarray, np.ndarray, int]:
    """Grow the dot by `add` and make the lines give way to it; with `add` None, split the
    gap between the dot and the line instead. Returns (dot, lines, 1 if a line moved)."""
    win = _window(one, int(np.ceil((add or 0.0) + 3 * gap_px)) + 2)
    o, ln = one[win], lines[win]
    if add is None:
        band = _between_marks(ln | o, gap_px)
        g, trimmed = o & ~band, ln & ~band
    else:
        g = _grow(o, add)
        trimmed = ln & (cv2.distanceTransform(_u8(~g), cv2.DIST_L2, 5) > gap_px)
    gave = int((trimmed != ln).any())
    dot, lines = np.zeros_like(one), lines.copy()
    dot[win] = g
    lines[win] = trimmed
    return dot, lines, gave


def pull_apart(mask: np.ndarray, gap_px: float, min_width_px: float = 0.0,
               small_px: float = 0.0) -> tuple[np.ndarray, np.ndarray, int, int]:
    """Separate marks drawn closer than `gap_px` (an eye 0.3 mm from a cheek line) get
    `gap_px` of paper between them, so they print as two marks instead of fusing.

    A round dot (an eye) stays round (Allen: a cut eye looks scary): a dot thinner than
    `min_width_px` grows evenly to that size as far as it can while staying `gap_px` from
    everything else, and when it was drawn too close to a line, the line gives way (unless
    that would cut the line in two; then both give way). Between two other marks, the bits
    facing each other are trimmed. Returns (mask, the round dots, number of places, number
    of eye pairs made alike)."""
    dots = round_dots(mask, small_px) if small_px > 0 else np.zeros_like(mask)
    others = mask & ~dots
    places = 0
    groups: list[list[np.ndarray]] = []
    paired = np.zeros_like(mask)
    drawn_pairs = np.zeros_like(mask)
    for left, right in eye_pairs(dots):
        new_l, new_r = symmetric_eyes(left, right)
        new_l, new_r = new_l & ~others, new_r & ~others
        if new_l.any() and new_r.any():
            groups.append([new_l, new_r])
            paired |= new_l | new_r
            drawn_pairs |= left | right
    single = dots & ~drawn_pairs
    n, comp = cv2.connectedComponents(_u8(single), connectivity=8)
    groups += [[comp == i] for i in range(1, n)]
    all_dots = paired | single
    grown = np.zeros_like(mask)
    for group in groups:
        # The same growth for both eyes of a pair, so they stay alike.
        fits = [_dot_fit(one, others, (all_dots & ~one) | grown, min_width_px, gap_px) for one in group]
        add = None if any(f is None for f in fits) else min(fits)
        for one in group:
            g, others, gave = _dot_place(one, others, add, gap_px)
            places += gave
            grown |= g
    between = _between_marks(others, gap_px)
    band = between & others
    if band.any():
        lbl = cv2.connectedComponents(_u8(between), connectivity=8)[1]
        places += len(np.unique(lbl[band]))
        others &= ~band
    return others | grown, grown, places, sum(len(g) == 2 for g in groups)


def small_mark_bridges(mask: np.ndarray, fill: np.ndarray, small_px: float) -> np.ndarray:
    """The pixels of `fill` that would join a small face mark (an eye, a smile, a nose:
    smaller than `small_px` and not a long dash) to the one mark beside it. Closing the
    paper gaps in scribbled coloring must not glue a face together: the cat's eye sat
    0.3 mm from her cheek line and became one blob. A long dash is a bit of a sketchy
    line, and joins it. Judged by shape and position only, never by how dark the ink is
    (Allen: that depends on the pen)."""
    n, comp, stats, _ = cv2.connectedComponentsWithStats(_u8(mask), connectivity=8)
    fn, flab = cv2.connectedComponents(_u8(fill), connectivity=8)
    if n <= 2 or fn <= 1:
        return np.zeros_like(mask)
    is_dot = np.zeros(n, bool)
    for i in np.flatnonzero(stats[1:, cv2.CC_STAT_AREA] < small_px) + 1:
        x, y, w, h = stats[i, :4]
        pts = np.column_stack(np.nonzero(comp[y:y + h, x:x + w] == i))[:, ::-1].astype(np.float32)
        (_, _), (rw, rh), _ = cv2.minAreaRect(pts)
        is_dot[i] = max(rw, rh) + 1.0 <= 2.5 * (min(rw, rh) + 1.0)
    if not is_dot.any():
        return np.zeros_like(mask)
    h, w = mask.shape
    padded = np.pad(flab, 1)
    pairs = []
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dy or dx:
                nb = padded[1 + dy:1 + dy + h, 1 + dx:1 + dx + w]
                sel = (nb > 0) & (comp > 0)
                pairs.append(np.column_stack([nb[sel], comp[sel]]))
    pairs = np.unique(np.concatenate(pairs), axis=0)
    if not len(pairs):
        return np.zeros_like(mask)
    face = np.bincount(pairs[:, 0], weights=is_dot[pairs[:, 1]], minlength=fn)
    other = np.bincount(pairs[:, 0], weights=~is_dot[pairs[:, 1]], minlength=fn)
    # A gap between a face mark and one other mark stays (an eye by a cheek line); a gap
    # touching two other marks is a gap in a line, and closes.
    return ((face >= 1) & (face + other >= 2) & (other <= 1))[flab] & fill


def thin_strips(label_map: np.ndarray, n_labels: int, min_width_px: float, min_area_px: float) -> np.ndarray:
    """Separate bits of color that are thin all along (a straw colored in between two
    lines), at least `min_area_px` big. A line made thicker grows over the paper instead
    of over these. The pointed tips of a bigger colored area are not strips: a line may
    still cover those, as before."""
    out = np.zeros(label_map.shape, bool)
    for j in range(1, n_labels + 1):
        m = label_map == j
        if not m.any():
            continue
        wide = cv2.morphologyEx(_u8(m), cv2.MORPH_OPEN, _disk(min_width_px / 2.0)).astype(bool)
        n, lbl, stats, _ = cv2.connectedComponentsWithStats(_u8(m), connectivity=8)
        for i in range(1, n):
            x, y, w, h, area = stats[i]
            if area < min_area_px:
                continue
            comp = lbl[y:y + h, x:x + w] == i
            if (wide[y:y + h, x:x + w] & comp).sum() < 0.25 * area:
                out[y:y + h, x:x + w] |= comp
    return out


def thicken_thin_ink(mask: np.ndarray, min_width_px: float, gap_px: float = 0.0,
                     blocked: np.ndarray | None = None,
                     fixed: np.ndarray | None = None) -> tuple[np.ndarray, float]:
    """Make ink at least `min_width_px` wide, without merging separate marks: they keep
    at least `gap_px` between them (or the gap that was drawn, if smaller), even if a mark
    then stays a little thinner. It never grows into `blocked` (thin strips of other
    colors), so there it grows on the other side only. Returns (mask, added pixel count)."""
    r = min_width_px / 2.0
    opened = cv2.morphologyEx(_u8(mask), cv2.MORPH_OPEN, _disk(r)).astype(bool)
    thin_zone = mask & ~opened
    if fixed is not None:      # round dots keep their shape (already grown as far as they can)
        thin_zone &= ~fixed
    if not thin_zone.any():
        return mask, 0.0
    # Keep only thin parts that are not just ragged edges of thick parts.
    dist_to_thick = cv2.distanceTransform(_u8(~opened), cv2.DIST_L2, 5)
    thin_zone &= dist_to_thick > max(2.0, 0.3 * r)
    if not thin_zone.any():
        return mask, 0.0
    skel = skeletonize(mask) & cv2.dilate(_u8(thin_zone), np.ones((3, 3), np.uint8)).astype(bool)
    add = cv2.dilate(_u8(skel), _disk(r)).astype(bool) & ~_keep_apart(mask, gap_px)
    if blocked is not None:
        add &= ~blocked
    result = mask | add
    return result, float((result & ~mask).sum())



# --- Tidy (optional, per card) -------------------------------------------------------
# A clean, sticker-like version of the kid's own lines: the outline color's strokes are
# redrawn along their own middle at one even thickness, wobbly and grainy edges are
# smoothed, and dots, blobs and colored-in areas keep their shape. Nothing is added,
# moved or straightened; no AI.


def _neighbors(mask: np.ndarray) -> np.ndarray:
    m = mask.astype(np.uint8)
    return cv2.filter2D(m, -1, np.ones((3, 3), np.float32), borderType=cv2.BORDER_CONSTANT).astype(np.int32) - m


def prune_spurs(skel: np.ndarray, length_px: int) -> np.ndarray:
    """Remove side branches shorter than `length_px` (made by grain and wobbly edges),
    keeping the real ends of lines and anything that would vanish entirely (a dot)."""
    s = skel.copy()
    for _ in range(length_px):
        ends = s & (_neighbors(s) <= 1)
        if not ends.any():
            break
        s &= ~ends
    grow = (s & (_neighbors(s) == 1)).astype(np.uint8)
    k = np.ones((3, 3), np.uint8)
    for _ in range(length_px):
        grow = cv2.dilate(grow, k) & skel.astype(np.uint8)
    s |= grow.astype(bool)
    n, lbl = cv2.connectedComponents(skel.astype(np.uint8), connectivity=8)
    lost = np.setdiff1d(np.arange(1, n), np.unique(lbl[s]))
    if lost.size:
        s |= np.isin(lbl, lost)
    return s


def _compact(comp: np.ndarray, dist: np.ndarray) -> bool:
    """A blob (an eye, a nose, a filled foot) rather than a stroke: not much longer than wide."""
    width = 2.0 * float(dist[comp].max())
    length = int((skeletonize(comp)).sum())
    return length < 2.5 * width


def _split_tidy(cfg: dict, mask: np.ndarray, px_per_mm: float, blob_px: float):
    """Smooth the grain away, then split one color's ink into keep (colored-in areas,
    blobs wider than `blob_px`, separate dots: their shape is kept) and strokes
    (redrawn at one width)."""
    tc = cfg["tidy"]
    smooth_px = tc["smooth"] * px_per_mm
    sm = cv2.GaussianBlur(mask.astype(np.float32), (0, 0), max(0.5, smooth_px)) > 0.5
    dist = cv2.distanceTransform(_u8(sm), cv2.DIST_L2, 5)
    keep = cv2.morphologyEx(_u8(sm), cv2.MORPH_OPEN, _disk(tc["fill_min_width"] * px_per_mm / 2.0)).astype(bool)
    thick = cv2.morphologyEx(_u8(sm), cv2.MORPH_OPEN, _disk(blob_px / 2.0)).astype(bool) & ~keep
    # A bold outline is thick in stretches with short thinner bits between: judge the
    # stretches together, so a line that runs thicker in places is evened, and only
    # compact thick parts (a pupil, a nose, a filled foot) keep their shape.
    joined = cv2.morphologyEx(_u8(thick), cv2.MORPH_CLOSE, _disk(0.4 * blob_px)).astype(bool) & sm
    n, lbl, stats, _ = cv2.connectedComponentsWithStats(_u8(joined & ~keep), connectivity=8)
    for i in range(1, n):
        x, y, w, h, _ = stats[i]
        comp = lbl[y:y + h, x:x + w] == i
        if _compact(comp, dist[y:y + h, x:x + w]):
            keep[y:y + h, x:x + w] |= comp & thick[y:y + h, x:x + w]
    n, lbl, stats, _ = cv2.connectedComponentsWithStats(_u8(sm & ~keep), connectivity=8)
    for i in range(1, n):                      # small separate dots (eyes) keep their shape
        x, y, w, h, _ = stats[i]
        comp = lbl[y:y + h, x:x + w] == i
        if _compact(comp, dist[y:y + h, x:x + w]):
            keep[y:y + h, x:x + w] |= comp
    strokes = sm & ~keep
    return sm, keep, strokes


def tidy_line_width(cfg: dict, mask: np.ndarray, px_per_mm: float) -> tuple[float, float]:
    """(width to redraw at, her typical stroke width), in mm. The redraw width is her
    typical width, at least the printable minimum and at most `max_line_width`."""
    tc, pr = cfg["tidy"], cfg["process"]
    sm = cv2.GaussianBlur(mask.astype(np.float32), (0, 0), max(0.5, tc["smooth"] * px_per_mm)) > 0.5
    lines = sm & ~cv2.morphologyEx(_u8(sm), cv2.MORPH_OPEN, _disk(tc["fill_min_width"] * px_per_mm / 2.0)).astype(bool)
    typical = pr["min_ink_width"]
    if lines.any():
        dist = cv2.distanceTransform(_u8(lines), cv2.DIST_L2, 5)
        typical = float(np.median(2.0 * dist[skeletonize(lines)])) / px_per_mm
    if tc["line_width"] != "auto":
        return max(float(tc["line_width"]), pr["min_ink_width"]), typical
    return float(np.clip(typical, pr["min_ink_width"], tc["max_line_width"])), typical


def tidy_strokes(cfg: dict, mask: np.ndarray, px_per_mm: float, width_mm: float, typical_mm: float) -> np.ndarray:
    """The outline color, tidied: strokes redrawn along their middle at `width_mm`;
    blobs (compact and at least 2.5x her typical line), separate dots and colored-in
    areas kept with smoothed edges. A line that only runs thicker in places is evened."""
    w_px = width_mm * px_per_mm
    # Blobs are far thicker than her usual line (a pupil, a filled foot: about 3x); a
    # marker line that only ran thicker in places (about 2x) is not a blob.
    blob_px = max(1.5 * width_mm, 2.5 * typical_mm) * px_per_mm
    sm, keep, strokes = _split_tidy(cfg, mask, px_per_mm, blob_px)
    out = smooth_edges(cfg, keep, px_per_mm)
    if strokes.any():
        skel = prune_spurs(skeletonize(strokes), max(2, int(round(0.35 * w_px))))
        redrawn = cv2.dilate(_u8(skel), _disk(w_px / 2.0)).astype(bool)
        # A stroke redrawn thicker must not grow into a separate mark next to it.
        apart = _keep_apart(sm, cfg["process"]["min_gap"] * px_per_mm)
        out |= (redrawn & ~apart) | (strokes & redrawn)
    return out


def smooth_edges(cfg: dict, mask: np.ndarray, px_per_mm: float) -> np.ndarray:
    """Wobble and grain smoothed off the edge; the shape and its size stay. A mark small
    enough to vanish in the smoothing (a tiny eye) is kept as drawn."""
    sigma = max(0.5, 2.0 * cfg["tidy"]["smooth"] * px_per_mm)
    out = cv2.GaussianBlur(mask.astype(np.float32), (0, 0), sigma) > 0.5
    n, lbl = cv2.connectedComponents(_u8(mask), connectivity=8)
    lost = np.setdiff1d(np.arange(1, n), np.unique(lbl[out]))
    if lost.size:
        out |= np.isin(lbl, lost)
    return out


def tidy_labels(cfg: dict, label_map: np.ndarray, layers: list[InkLayer], px_per_mm: float):
    """Tidy a whole drawing. The outline color (the darkest ink, or the only one) gets its
    strokes redrawn evenly; other colors only get smooth edges, and they fill any gap a
    thinner outline leaves next to them, as on a sticker. Returns (labels, width mm)."""
    from .palette import rgb_to_lab

    present = [i for i in range(1, len(layers) + 1) if (label_map == i).any()]
    if not present:
        return label_map, cfg["process"]["min_ink_width"]
    line = min(present, key=lambda i: rgb_to_lab(layers[i - 1].rgb)[0])
    width, typical = tidy_line_width(cfg, label_map == line, px_per_mm)
    new = np.zeros_like(label_map)
    # The redrawn line never covers a thin strip she colored next to it (a straw).
    pr = cfg["process"]
    thin = thin_strips(label_map, len(layers), pr["min_ink_width"] * px_per_mm, pr["thin_strip_min_area"] * px_per_mm ** 2)
    keep_colors = thin & (label_map > 0) & (label_map != line)
    new[tidy_strokes(cfg, label_map == line, px_per_mm, width, typical) & ~keep_colors] = line
    colors = [i for i in present if i != line]
    for i in colors:
        m = smooth_edges(cfg, label_map == i, px_per_mm) & (new == 0)
        new[m] = i
    lost = (label_map > 0) & (new == 0)
    if colors and lost.any():
        # Colors may also cross the thin white sliver kids often leave between their
        # coloring and the outline, but only right next to where the outline used to be.
        sliver = (label_map == 0) & cv2.dilate(_u8(lost), _disk(0.3 * px_per_mm)).astype(bool)
        open_to = lost | sliver
        grow = np.where(np.isin(new, colors), new, 0).astype(np.uint8)
        k = np.ones((3, 3), np.uint8)
        for _ in range(int(np.ceil(cfg["tidy"]["max_line_width"] * px_per_mm))):
            g = cv2.dilate(grow, k)
            add = open_to & (grow == 0) & (g > 0)
            if not add.any():
                break
            grow[add] = g[add]
        fill = open_to & (grow > 0) & (new == 0)
        new[fill] = grow[fill]
    return new, width

def mask_to_polygons(mask: np.ndarray, px_per_mm: float, simplify_mm: float = 0.02, smooth_mm: float = 0.15) -> MultiPolygon:
    """Vectorize a mask into real-mm polygons with holes, Y up."""
    h = mask.shape[0]
    contours, hierarchy = cv2.findContours(_u8(mask), cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    if hierarchy is None:
        return MultiPolygon()
    hierarchy = hierarchy[0]

    def to_mm(c):
        pts = c.reshape(-1, 2).astype(np.float64)
        # Pixel centers; +0.5 so the polygon runs along pixel edges.
        return [((x + 0.5) / px_per_mm, (h - (y + 0.5)) / px_per_mm) for x, y in pts]

    polys = []
    for i, (nxt, prv, child, parent) in enumerate(hierarchy):
        if parent != -1:
            continue
        if len(contours[i]) < 3:
            continue
        holes = []
        j = child
        while j != -1:
            if len(contours[j]) >= 3:
                holes.append(to_mm(contours[j]))
            j = hierarchy[j][0]
        p = Polygon(to_mm(contours[i]), holes)
        if not p.is_valid:
            p = p.buffer(0)
        if not p.is_empty:
            polys.append(p)
    geom = unary_union(polys)
    # Closing only: it fills pixel-sized notches without shrinking the shape.
    r = smooth_mm
    geom = geom.buffer(r, join_style="round").buffer(-r, join_style="round")
    geom = geom.simplify(simplify_mm, preserve_topology=True)
    return _as_multi(geom)


def _as_multi(geom) -> MultiPolygon:
    if geom.is_empty:
        return MultiPolygon()
    if isinstance(geom, Polygon):
        return MultiPolygon([geom])
    if isinstance(geom, MultiPolygon):
        return geom
    polys = [g for g in getattr(geom, "geoms", []) if isinstance(g, Polygon) and not g.is_empty]
    return MultiPolygon(polys)


def bridge_components(shape, width_mm: float) -> tuple[Polygon, int]:
    """Join separate pieces with short strips between their nearest points."""
    parts = sorted(_as_multi(shape).geoms, key=lambda p: -p.area)
    if len(parts) <= 1:
        return (parts[0] if parts else Polygon()), 0
    main = parts[0]
    rest = parts[1:]
    bridges = 0
    while rest:
        # Connect the piece nearest to the main body.
        rest.sort(key=lambda p: main.distance(p))
        p = rest.pop(0)
        a, b = nearest_points(main, p)
        strip = LineString([a, b]).buffer(width_mm / 2.0, cap_style="round")
        main = unary_union([main, p, strip])
        bridges += 1
        if isinstance(main, MultiPolygon):
            main = max(main.geoms, key=lambda g: g.area)
    return main, bridges


def fix_design(cfg: dict, layers: list[InkLayer], px_per_mm: float, *, border_on: bool,
               name: str, product: str, tidy: bool = False, keep_dots: bool = True) -> Design:
    """Apply every print fix in spec order and vectorize. `tidy` redraws every stroke at
    one even thickness with smooth edges (off unless asked for)."""
    pr = cfg["process"]
    fixes: list[str] = []
    warnings: list[str] = []
    speck_px = pr["min_speck_area_mm2"] * px_per_mm ** 2
    width_px = pr["min_ink_width"] * px_per_mm

    if not layers:
        raise ValueError("no ink found in the drawing box")
    # One label map, black first so it wins where layers overlap.
    label_map = np.zeros(layers[0].mask.shape, np.int32)
    for i, layer in enumerate(layers, start=1):
        label_map[(label_map == 0) & layer.mask] = i
    label_map = smooth_labels(label_map, len(layers), max(1, int(round(0.2 * px_per_mm))))
    union = label_map > 0
    union, specks = remove_specks(union, speck_px, pr["speck_max_extent"] * px_per_mm,
                                  pr["min_dot_area_mm2"] * px_per_mm ** 2 if keep_dots else None)
    if specks:
        fixes.append(f"{specks} speck(s) smaller than {pr['min_speck_area_mm2']} mm² removed")
    # Small round dots are kept (eyes, dots on a wing). A speck of pencil dust looks the
    # same, so they are circled on the preview; --no-dots removes them for a card.
    kept_dots = []
    n_d, _, _, cents = cv2.connectedComponentsWithStats(_u8(round_dots(union, speck_px)), connectivity=8)
    hh = union.shape[0]
    for cx, cy in cents[1:]:
        kept_dots.append(((cx + 0.5) / px_per_mm, (hh - (cy + 0.5)) / px_per_mm))
    if kept_dots:
        fixes.append(f"{len(kept_dots)} small dot(s) kept, circled in blue (eyes or dots in the drawing)")
    # The inside of a ring eye or a little heart stays paper (and nothing grows into it).
    ring_px = pr["ring_mark_max_area"] * px_per_mm ** 2
    eye_holes = small_mark_holes(union, ring_px, pr["min_gap"] * px_per_mm, ring_px,
                                 pr["sliver_min_length"] * px_per_mm)
    union &= ~eye_holes                 # widened slivers: that ink becomes paper
    filled, holes = fill_small_holes(union, speck_px, keep=eye_holes)
    if holes:
        fixes.append(f"{holes} tiny hole(s) filled")
    if eye_holes.any():
        fixes.append(f"{cv2.connectedComponents(_u8(eye_holes), connectivity=4)[0] - 1} small hole(s) inside "
                     "little closed marks kept (ring eyes, small hearts)")
    label_map[~union] = 0
    new_px = filled & ~union
    if new_px.any():
        # Give filled holes the label of the ink around them.
        grown = smooth_labels(np.where(new_px, 0, label_map), len(layers), max(1, int(round(0.3 * px_per_mm))))
        label_map[new_px] = grown[new_px]
        dil = cv2.dilate(label_map.astype(np.uint8), np.ones((5, 5), np.uint8))
        still = new_px & (label_map == 0)
        label_map[still] = dil[still]

    # Scribbled coloring (crayon, fast marker) leaves thin slivers of paper between
    # strokes. Close gaps narrower than about half a millimeter inside each color.
    r = max(1, int(round(pr["coloring_gap"] / 2 * px_per_mm)))
    disk = _disk(r)
    gap_px = 0
    small_px = pr["small_mark_area"] * px_per_mm ** 2
    for i in range(1, len(layers) + 1):
        m = label_map == i
        closed = cv2.morphologyEx(_u8(m), cv2.MORPH_CLOSE, disk).astype(bool)
        fill = closed & (label_map == 0) & ~eye_holes
        fill &= ~small_mark_bridges(m, fill, small_px)
        label_map[fill] = i
        gap_px += int(fill.sum())
    if gap_px / px_per_mm ** 2 > 0.5:
        fixes.append(f"gaps in the coloring narrower than {pr['coloring_gap']} mm filled ({gap_px / px_per_mm ** 2:.0f} mm²)")

    if tidy:
        label_map, tidy_w = tidy_labels(cfg, label_map, layers, px_per_mm)
        fixes.append(f"tidy: outlines redrawn at an even {tidy_w:.1f} mm, edges smoothed")
    masks: list[tuple[InkLayer, np.ndarray]] = []
    # A line next to a thin strip of another color (a straw colored in between two lines)
    # thickens over the paper side, so the strip she colored stays.
    thin = thin_strips(label_map, len(layers), width_px, pr["thin_strip_min_area"] * px_per_mm ** 2)
    for i, layer in enumerate(layers, start=1):
        m = label_map == i
        if not m.any():
            continue
        m, dots, pulled, pairs = pull_apart(m, pr["min_gap"] * px_per_mm, width_px, small_px)
        if pairs:
            fixes.append(f"{layer.name}: {pairs} pair(s) of side-by-side dots (eyes) made the same shape and size")
        if pulled:
            fixes.append(f"{layer.name}: {pulled} place(s) where separate marks almost touched "
                         f"opened to a {pr['min_gap']} mm gap, so they print apart")
        m, added = thicken_thin_ink(m, width_px, pr["min_gap"] * px_per_mm,
                                    blocked=(thin & (label_map > 0) & (label_map != i)) | eye_holes, fixed=dots)
        if added > 0.5 * px_per_mm ** 2:
            fixes.append(f"{layer.name}: thin lines thickened to {pr['min_ink_width']} mm "
                         f"({added / px_per_mm ** 2:.1f} mm² added)")
        masks.append((layer, m))

    # Black wins where layers overlap after thickening, then colors in order.
    taken = np.zeros(layers[0].mask.shape, bool) if layers else None
    resolved: list[tuple[InkLayer, np.ndarray]] = []
    for layer, m in masks:
        m = m & ~taken
        taken |= m
        resolved.append((layer, m))
    if taken is None or not taken.any():
        raise ValueError("no ink found in the drawing box")

    silhouette = fill_all_holes(taken)
    sil_poly = unary_union(mask_to_polygons(silhouette, px_per_mm))
    outline = sil_poly

    border = pr["border"] if border_on else 0.0
    if border > 0:
        outline = outline.buffer(border, join_style="round")
        fixes.append(f"{border} mm border added in the base color")
    outline = _as_multi(outline)
    n_parts = len(outline.geoms)
    if n_parts > 1:
        outline, bridges = bridge_components(outline, 2.5)
        fixes.append(f"{n_parts} separate pieces joined with {bridges} bridge(s) in the base color")
    else:
        outline = outline.geoms[0]

    # Outer features narrower than min_outer_feature get smoothed into the border;
    # never cut into the ink itself.
    r = pr["min_outer_feature"] / 2.0
    smoothed = outline.buffer(-r, join_style="round").buffer(r, join_style="round")
    smoothed = unary_union([smoothed, sil_poly])
    smoothed = _largest(smoothed)
    if abs(smoothed.area - outline.area) > 0.2:
        fixes.append(f"outer bits thinner than {pr['min_outer_feature']} mm smoothed into the border")
    outline = smoothed

    cr = pr["corner_round"]
    rounded = outline.buffer(cr, join_style="round").buffer(-2 * cr, join_style="round").buffer(cr, join_style="round")
    rounded = _largest(unary_union([rounded, sil_poly]))
    fixes.append(f"corners rounded {cr} mm")
    outline = Polygon(rounded.exterior)   # holes in the outline are filled: one solid plate
    outline = outline.simplify(0.02, preserve_topology=True)

    inks: list[InkRegion] = []
    claimed = Polygon()
    for layer, m in resolved:
        geom = mask_to_polygons(m, px_per_mm)
        # The pixel masks never overlap, but their traced outlines can bulge a hair into a
        # neighbour's; earlier inks keep the shared border, so color parts never overlap.
        geom = geom.intersection(outline).difference(claimed)
        geom = _as_multi(MultiPolygon([g for g in _as_multi(geom).geoms if g.area > 0.005]))
        claimed = claimed.union(geom)
        if geom.is_empty:
            warnings.append(f"{layer.name} ink vanished after clean-up")
            continue
        inks.append(InkRegion(layer.name, layer.rgb, geom, layer.slot, layer.off_palette))
    return Design(name, product, outline, inks, fixes, warnings, dots=kept_dots)


def _largest(geom) -> Polygon:
    multi = _as_multi(geom)
    return max(multi.geoms, key=lambda g: g.area)


def scale_design(design: Design, factor: float) -> Design:
    design.outline = affinity.scale(design.outline, factor, factor, origin=(0, 0))
    for ink in design.inks:
        ink.geometry = _as_multi(affinity.scale(ink.geometry, factor, factor, origin=(0, 0)))
    design.dots = [(x * factor, y * factor) for x, y in design.dots]
    return design
