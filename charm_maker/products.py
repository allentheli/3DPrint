"""Attachments and solids for each product: clip pocket, ring tab, and the flush
color face. Pieces are built face-down: the front face is at z = 0."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import manifold3d as m3d
import shapely
from shapely import affinity
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

from .geom import circle, cylinder, extrude
from .shape import Design, InkRegion, _as_multi


@dataclass
class Piece:
    design: Design
    thickness: float
    parts: dict[str, m3d.Manifold]            # part name -> solid, e.g. "clip-03 white (base)"
    part_colors: dict[str, tuple[int, int, int]]
    base_part: str
    attachment: dict = field(default_factory=dict)   # for the preview
    notes: list[str] = field(default_factory=list)

    @property
    def name(self) -> str:
        return self.design.name

    def size(self) -> tuple[float, float]:
        minx, miny, maxx, maxy = self.design.outline.bounds
        return maxx - minx, maxy - miny


TAB_ANGLES = {"top": 0.0, "top-left": 45.0, "top-right": -45.0, "left": 90.0, "right": -90.0}


def build_piece(cfg: dict, design: Design, *, tab_position: str | None = None) -> Piece:
    prod = cfg["products"][design.product]
    t = float(prod["thickness"])
    attachment = prod.get("attachment")
    info: dict = {}
    holes = []   # 2D shapes removed from every part through the full thickness

    if attachment == "clip_pocket":
        info = _place_clip_pocket(cfg, design)
    elif attachment == "ring_tab":
        info = _add_ring_tab(cfg, design, tab_position or prod.get("tab_position", "top"))
        holes.append(info["hole"])
    elif attachment is None:
        pass
    else:
        raise NotImplementedError(f"attachment {attachment} is not built yet")

    outline = design.outline
    for h in holes:
        outline = outline.difference(h)
        for ink in design.inks:
            before = ink.geometry.area
            ink.geometry = _as_multi(ink.geometry.difference(h))
            if before - ink.geometry.area > 0.05:
                design.fixes.append(f"{ink.name} ink trimmed around the hole")
    design.outline = outline if isinstance(outline, Polygon) else max(outline.geoms, key=lambda g: g.area)

    face = cfg["process"]["color_face_depth"]
    parts: dict[str, m3d.Manifold] = {}
    colors: dict[str, tuple[int, int, int]] = {}
    ink_union = unary_union([ink.geometry for ink in design.inks]) if design.inks else None
    base = extrude(design.outline, t)
    if ink_union is not None and not ink_union.is_empty:
        base = base - extrude(ink_union, face + 1.0, -1.0)
    if attachment == "clip_pocket":
        cx, cy = info["center"]
        base = base - cylinder(info["diameter"], info["depth"] + 1.0, cx, cy, t - info["depth"])
    base_name = f"{design.name} base"
    parts[base_name] = base
    colors[base_name] = design.paper_rgb if cfg["process"]["base_color"] == "white" else design.inks[-1].rgb
    for ink in design.inks:
        name = f"{design.name} {ink.name}"
        parts[name] = extrude(ink.geometry, face)
        colors[name] = ink.rgb
    return Piece(design, t, parts, colors, base_name, info)


# ---------------------------------------------------------------------------
# Hair clip pocket
# ---------------------------------------------------------------------------

def _place_clip_pocket(cfg: dict, design: Design) -> dict:
    hw = cfg["hardware"]
    fit = cfg["fit"]["clip_pocket_diameter"]
    d = float(fit["value"])
    depth = hw["clip_pocket_depth"]
    need_r = d / 2.0 + hw["clip_pocket_min_wall"]
    if not fit["tested"]:
        design.warnings.append(f"clip pocket diameter {d} mm is not from a fit test yet")

    center, r = _deepest_point(design.outline)
    grown = 0.0
    while r < need_r and grown < 3.0:
        grown += 0.5
        design.outline = design.outline.buffer(0.5, join_style="round")
        center, r = _deepest_point(design.outline)
    if grown:
        design.fixes.append(f"border grown by {grown} mm so the clip pad pocket fits")
    if r < need_r:
        disc_d = max(hw["clip_backer_diameter"], 2 * need_r)
        design.outline = Polygon(unary_union([design.outline, circle(disc_d, *center)]).exterior)
        design.fixes.append(f"{disc_d:.0f} mm backer disc added behind the design for the clip pad")
        center, r = _deepest_point(design.outline)
    return {"kind": "clip_pocket", "center": center, "diameter": d, "depth": depth, "wall": r - d / 2.0}


def _deepest_point(poly: Polygon) -> tuple[tuple[float, float], float]:
    seg = shapely.maximum_inscribed_circle(poly, tolerance=0.05)
    c = seg.coords[0]
    return (float(c[0]), float(c[1])), float(seg.length)


# ---------------------------------------------------------------------------
# Keychain ring tab
# ---------------------------------------------------------------------------

def _add_ring_tab(cfg: dict, design: Design, position: str) -> dict:
    hw = cfg["hardware"]
    fit = cfg["fit"]["keyring_hole_diameter"]
    hole_d = float(fit["value"])
    wall = hw["keyring_hole_min_wall"]
    if not fit["tested"]:
        design.warnings.append(f"keyring hole {hole_d} mm is not from a fit test yet")
    angle = TAB_ANGLES.get(position)
    if angle is None:
        raise ValueError(f"unknown tab position {position!r}; use one of {list(TAB_ANGLES)}")
    # Work with the chosen side pointing up, then rotate back.
    origin = design.outline.centroid.coords[0]
    shape = affinity.rotate(design.outline, angle, origin=origin)
    tab_w = hole_d + 2 * wall
    # Where is the top? Ignore spikes thinner than 4 mm when choosing the spot.
    core = shape.buffer(-2.0, join_style="round")
    core = core if not core.is_empty else shape
    core = max(_as_multi(core).geoms, key=lambda g: g.area)
    top_pt = max(core.exterior.coords, key=lambda p: p[1])
    x_tab = top_pt[0]
    minx, miny, maxx, maxy = shape.bounds
    strip = box(x_tab - tab_w / 2, miny - 1, x_tab + tab_w / 2, maxy + 1).intersection(shape)
    y_attach = strip.bounds[3]
    hole_r = hole_d / 2.0
    cy = y_attach + hole_r + wall - 1.0      # tab circle overlaps the shape by 1 mm
    tab = unary_union([circle(tab_w, x_tab, cy), box(x_tab - tab_w / 2, y_attach - 3.0, x_tab + tab_w / 2, cy)])
    merged = unary_union([shape, tab])
    merged = merged.buffer(1.0, join_style="round").buffer(-1.0, join_style="round")   # fillet the junction
    merged = max(_as_multi(merged).geoms, key=lambda g: g.area)
    merged = Polygon(merged.exterior)
    hole = circle(hole_d, x_tab, cy)
    design.outline = affinity.rotate(merged, -angle, origin=origin)
    hole = affinity.rotate(hole, -angle, origin=origin)
    hc = hole.centroid.coords[0]
    design.fixes.append(f"ring tab added at the {position} with a {hole_d} mm hole")
    return {"kind": "ring_tab", "hole": hole, "hole_center": (float(hc[0]), float(hc[1])),
            "hole_diameter": hole_d, "position": position}
