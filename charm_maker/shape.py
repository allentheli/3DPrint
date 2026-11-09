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


def remove_specks(mask: np.ndarray, min_area_px: float) -> tuple[np.ndarray, int]:
    n, labels, stats, _ = cv2.connectedComponentsWithStats(_u8(mask), connectivity=8)
    keep = np.zeros(n, bool)
    keep[1:] = stats[1:, cv2.CC_STAT_AREA] >= min_area_px
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


def thicken_thin_ink(mask: np.ndarray, min_width_px: float) -> tuple[np.ndarray, float]:
    """Make ink at least `min_width_px` wide. Returns (mask, added pixel count)."""
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
    add = cv2.dilate(_u8(skel), _disk(r)).astype(bool)
    result = mask | add
    return result, float((result & ~mask).sum())


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
               name: str, product: str) -> Design:
    """Apply every print fix in spec order and vectorize."""
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
    union, specks = remove_specks(union, speck_px)
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

    masks: list[tuple[InkLayer, np.ndarray]] = []
    for i, layer in enumerate(layers, start=1):
        m = label_map == i
        if not m.any():
            continue
        m, added = thicken_thin_ink(m, width_px)
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
    for layer, m in resolved:
        geom = mask_to_polygons(m, px_per_mm)
        geom = _as_multi(geom.intersection(outline))
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
