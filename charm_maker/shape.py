"""Turn ink masks into a printable outline and color regions, logging every fix."""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np
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
    extras: dict = field(default_factory=dict)   # attachment info filled by products


def _disk(radius_px: float) -> np.ndarray:
    r = max(1, int(round(radius_px)))
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))


def _u8(mask: np.ndarray) -> np.ndarray:
    return mask.astype(np.uint8)


def remove_specks(mask: np.ndarray, min_area_px: float, min_extent_px: float = 0.0) -> tuple[np.ndarray, int]:
    """Remove small dots. A mark is only a speck if it is both small in area and short:
    a thin smile, an eyelash or a whisker is small in area but long, and stays (it gets
    thickened). Length is measured along the mark, so a slanted whisker counts in full."""
    n, labels, stats, _ = cv2.connectedComponentsWithStats(_u8(mask), connectivity=8)
    keep = np.zeros(n, bool)
    keep[1:] = stats[1:, cv2.CC_STAT_AREA] >= min_area_px
    if min_extent_px > 0:
        for i in np.flatnonzero(~keep[1:]) + 1:
            x, y, w, h = stats[i, :4]
            pts = np.column_stack(np.nonzero(labels[y:y + h, x:x + w] == i))[:, ::-1].astype(np.float32)
            (_, _), (rw, rh), _ = cv2.minAreaRect(pts)
            keep[i] = max(rw, rh) + 1.0 >= min_extent_px
    removed = int((~keep[1:]).sum())
    return keep[labels], removed


def fill_small_holes(mask: np.ndarray, max_area_px: float) -> tuple[np.ndarray, int]:
    inv = ~mask
    n, labels, stats, _ = cv2.connectedComponentsWithStats(_u8(inv), connectivity=4)
    h, w = mask.shape
    filled = mask.copy()
    count = 0
    for i in range(1, n):
        x, y, bw, bh, area = stats[i]
        touches = x == 0 or y == 0 or x + bw >= w or y + bh >= h
        if not touches and area <= max_area_px:
            filled[labels == i] = True
            count += 1
    return filled, count


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


def _keep_apart(mask: np.ndarray, gap_px: float) -> np.ndarray:
    """Where separate marks may not grow: a band around the line halfway between them, so
    two marks thickened toward each other stop `gap_px` apart (or as far apart as they
    were drawn, if closer). Eyes next to a mouth stay eyes."""
    n = cv2.connectedComponents(_u8(mask), connectivity=8)[0]
    if n <= 2 or gap_px <= 0:
        return np.zeros_like(mask)
    _, near = cv2.distanceTransformWithLabels(_u8(~mask), cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_CCOMP)
    edge = np.zeros_like(mask)
    edge[:, 1:] |= near[:, 1:] != near[:, :-1]
    edge[1:, :] |= near[1:, :] != near[:-1, :]
    return cv2.dilate(_u8(edge), _disk(gap_px / 2.0)).astype(bool) & ~mask


def thicken_thin_ink(mask: np.ndarray, min_width_px: float, gap_px: float = 0.0) -> tuple[np.ndarray, float]:
    """Make ink at least `min_width_px` wide, without merging separate marks: they keep
    at least `gap_px` between them (or the gap that was drawn, if smaller), even if a mark
    then stays a little thinner. Returns (mask, added pixel count)."""
    r = min_width_px / 2.0
    opened = cv2.morphologyEx(_u8(mask), cv2.MORPH_OPEN, _disk(r)).astype(bool)
    thin_zone = mask & ~opened
    if not thin_zone.any():
        return mask, 0.0
    # Keep only thin parts that are not just ragged edges of thick parts.
    dist_to_thick = cv2.distanceTransform(_u8(~opened), cv2.DIST_L2, 5)
    thin_zone &= dist_to_thick > max(2.0, 0.3 * r)
    if not thin_zone.any():
        return mask, 0.0
    skel = skeletonize(mask) & cv2.dilate(_u8(thin_zone), np.ones((3, 3), np.uint8)).astype(bool)
    add = cv2.dilate(_u8(skel), _disk(r)).astype(bool) & ~_keep_apart(mask, gap_px)
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
    new[tidy_strokes(cfg, label_map == line, px_per_mm, width, typical)] = line
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
               name: str, product: str, tidy: bool = False) -> Design:
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
    union, specks = remove_specks(union, speck_px, pr["speck_max_extent"] * px_per_mm)
    if specks:
        fixes.append(f"{specks} speck(s) smaller than {pr['min_speck_area_mm2']} mm² removed")
    filled, holes = fill_small_holes(union, speck_px)
    if holes:
        fixes.append(f"{holes} tiny hole(s) filled")
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
    for i in range(1, len(layers) + 1):
        closed = cv2.morphologyEx(_u8(label_map == i), cv2.MORPH_CLOSE, disk).astype(bool)
        fill = closed & (label_map == 0)
        label_map[fill] = i
        gap_px += int(fill.sum())
    if gap_px / px_per_mm ** 2 > 0.5:
        fixes.append(f"gaps in the coloring narrower than {pr['coloring_gap']} mm filled ({gap_px / px_per_mm ** 2:.0f} mm²)")

    if tidy:
        label_map, tidy_w = tidy_labels(cfg, label_map, layers, px_per_mm)
        fixes.append(f"tidy: outlines redrawn at an even {tidy_w:.1f} mm, edges smoothed")
    masks: list[tuple[InkLayer, np.ndarray]] = []
    for i, layer in enumerate(layers, start=1):
        m = label_map == i
        if not m.any():
            continue
        m, added = thicken_thin_ink(m, width_px, pr["min_gap"] * px_per_mm)
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
    return Design(name, product, outline, inks, fixes, warnings)


def _largest(geom) -> Polygon:
    multi = _as_multi(geom)
    return max(multi.geoms, key=lambda g: g.area)


def scale_design(design: Design, factor: float) -> Design:
    design.outline = affinity.scale(design.outline, factor, factor, origin=(0, 0))
    for ink in design.inks:
        ink.geometry = _as_multi(affinity.scale(ink.geometry, factor, factor, origin=(0, 0)))
    return design
