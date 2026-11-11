"""Attachments and solids for each product: clip pocket, ring tab, and the flush
color face. Pieces are built face-down: the front face is at z = 0."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import manifold3d as m3d
import numpy as np
import shapely
from shapely import affinity
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

from .geom import circle, cylinder, extrude, plus, rounded_rect, square
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
    part_slots: dict[str, int | None] = field(default_factory=dict)
    part_off_palette: dict[str, dict] = field(default_factory=dict)
    style: str = "flat"
    group: str = "charms"          # plates are packed per group: charms, cases (clicker), figurines
    face_up: bool = False          # True for puffy and outlined styles: colors on top
    mirrored: bool = False         # flat pieces print face-down, so they are built mirrored
    supports: bool = False         # round-back figurines lie on their backs on tree supports

    def solid_xy(self, x: float, y: float) -> tuple[float, float]:
        """Where a point of the drawing ends up in the printed solid."""
        return (-x, y) if self.mirrored else (x, y)

    @property
    def name(self) -> str:
        return self.design.name

    def size(self) -> tuple[float, float]:
        minx, miny, maxx, maxy = self.design.outline.bounds
        return maxx - minx, maxy - miny


TAB_ANGLES = {"top": 0.0, "top-left": 45.0, "top-right": -45.0, "left": 90.0, "right": -90.0}


def build_piece(cfg: dict, design: Design, *, tab_position: str | None = None, style: str = "flat",
                figurine_back: str | None = None, figurine_base: str | None = None) -> Piece:
    prod0 = cfg["products"][design.product]
    if prod0.get("attachment") == "stem_socket" and not prod0.get("glue_on_fallback") and style != "flat":
        design.warnings.append(f"clicker keycaps are flat: the stem post is on the back ({style} not used)")
        style = "flat"
    if style == "figurine":
        back = figurine_back or cfg["figurine"]["back"]
        if back != "flat":
            return _build_figurine(cfg, design, back, figurine_base)
        # Flat back: the card's product as usual (size, clip pad, magnet, ring, loop),
        # with a rounded figurine front. No supports.
        if figurine_base and figurine_base != cfg["figurine"]["base"]:
            design.warnings.append(f"figurine base '{figurine_base}' is only for round-back figurines; ignored")
    prod = cfg["products"][design.product]
    t = float(prod["thickness"])
    attachment = prod.get("attachment")
    if attachment in ("side_loop", "jump_ring_tab") and prod.get("style") == "stud":
        attachment = None            # stud earrings: flat back, glue-on post
    info: dict = {}
    holes = []   # 2D shapes removed from every part through the full thickness

    if attachment == "clip_pocket":
        info = _place_clip_pocket(cfg, design)
    elif attachment == "ring_tab":
        info = _add_ring_tab(cfg, design, tab_position or prod.get("tab_position", "top"))
        holes.append(info["hole"])
    elif attachment == "jump_ring_tab":
        # Earrings: a jump ring through a small hole near the top, then the hook on the ring.
        info = _add_ring_tab(cfg, design, "top", fit_key="earring_hole_diameter",
                             wall=cfg["hardware"]["earring_tab_wall"], balance=True)
        holes.append(info["hole"])
        attachment = "ring_tab"      # from here on, built like a keychain's tab
    elif attachment == "side_loop":
        info = _add_side_loop(cfg, design, prod["loop"])
    elif attachment == "flat_back":
        info = {"kind": "flat_back"}
    elif attachment == "stem_socket":
        if prod.get("glue_on_fallback"):
            design.fixes.append("glue-on keycap: a flat charm to glue onto a store-bought blank flat-top MX keycap")
            attachment = None
        else:
            _keycap_min_size(design, prod)
            info = _place_stem_post(cfg, design)
    elif attachment is None:
        if prod.get("style") == "stud":
            design.fixes.append("stud style: flat back for a glue-on post")
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

    if style != "flat":
        from .relief import build_relief_parts

        parts, base_name, height, notes = build_relief_parts(cfg, design, attachment, info, style)
        design.fixes.extend(notes)
        colors = {base_name: design.paper_rgb if cfg["process"]["base_color"] == "white" else design.inks[-1].rgb}
        slots: dict[str, int | None] = {base_name: None}
        off: dict[str, dict] = {}
        for ink in design.inks:
            name = f"{design.name} {ink.name}"
            colors[name] = ink.rgb
            slots[name] = ink.slot
        info = {k: v for k, v in info.items() if k not in ("solid", "hole_solid", "hole")} | (
            {"hole": info["hole"]} if "hole" in info else {})
        return Piece(design, round(height, 2), parts, colors, base_name, info, part_slots=slots,
                     part_off_palette=off, style=style, face_up=True)

    face = cfg["process"]["color_face_depth"]
    parts: dict[str, m3d.Manifold] = {}
    colors: dict[str, tuple[int, int, int]] = {}
    ink_union = unary_union([ink.geometry for ink in design.inks]) if design.inks else None
    base = extrude(design.outline, t)
    if attachment == "side_loop":
        base = (base + info["solid"]) - info["hole_solid"]
    if ink_union is not None and not ink_union.is_empty:
        base = base - extrude(ink_union, face + 1.0, -1.0)
    if attachment == "clip_pocket":
        cx, cy = info["center"]
        base = base - cylinder(info["diameter"], info["depth"] + 1.0, cx, cy, t - info["depth"])
    if attachment == "stem_socket":
        base = base + info.pop("post") - info.pop("socket")
    base_name = f"{design.name} base"
    parts[base_name] = base
    colors[base_name] = design.paper_rgb if cfg["process"]["base_color"] == "white" else design.inks[-1].rgb
    slots: dict[str, int | None] = {base_name: None}
    off: dict[str, dict] = {}
    for ink in design.inks:
        name = f"{design.name} {ink.name}"
        parts[name] = extrude(ink.geometry, face)
        colors[name] = ink.rgb
        slots[name] = ink.slot
        if ink.off_palette:
            off[name] = ink.off_palette
    # Face-down: the face is the side that touched the bed. Seen from the front after
    # flipping the piece over, it reads mirrored unless the solid is built mirrored.
    parts = {n: solid.mirror([1.0, 0.0, 0.0]) for n, solid in parts.items()}
    return Piece(design, t, parts, colors, base_name, info, part_slots=slots, part_off_palette=off,
                 mirrored=True)



# ---------------------------------------------------------------------------
# Clicker: keycap post and case
# ---------------------------------------------------------------------------

def _keycap_min_size(design: Design, prod: dict) -> None:
    """A keycap must cover the switch under it. A drawing smaller than the card's square
    is scaled up (only its size changes) so its short side is size_min, without letting
    its long side pass size_max."""
    from .shape import scale_design

    minx, miny, maxx, maxy = design.outline.bounds
    short, long_ = min(maxx - minx, maxy - miny), max(maxx - minx, maxy - miny)
    if short >= prod["size_min"] - 0.05:
        return
    k = min(prod["size_min"] / short, prod["size_max"] / long_)
    if k > 1.0:
        scale_design(design, k)
        design.fixes.append(f"drawing scaled up {k:.2f}x so the keycap covers the switch "
                            f"(at least {prod['size_min']} mm, at most {prod['size_max']} mm)")


def _place_stem_post(cfg: dict, design: Design) -> dict:
    """The keycap's round post with the cross socket for the MX stem, on the back of the
    drawing (which prints face-down, so the post points up). At the drawing's balance point
    when it fits there, else at the nearest spot where it fits; if the drawing is too thin
    everywhere, a backer disc behind the balance point carries it."""
    hw, prod = cfg["hardware"], cfg["products"][design.product]
    fit = cfg["fit"]["stem_socket_clearance"]
    c = float(fit["value"])
    if not fit["tested"]:
        design.warnings.append(f"keycap stem fit {c} mm is not from a fit test yet")
    d = hw["mx_keycap_post_diameter"]
    need_r = d / 2.0 + prod["post_margin"]
    # As near the balance point as the post fits, so the keycap presses evenly.
    from shapely.ops import nearest_points

    ctr = design.outline.centroid
    room = design.outline.buffer(-need_r)
    if not room.is_empty:
        p = ctr if room.contains(ctr) else nearest_points(room, ctr)[0]
    else:
        p = ctr if design.outline.contains(ctr) else nearest_points(design.outline, ctr)[0]
        disc = circle(2 * need_r, p.x, p.y)
        design.outline = Polygon(unary_union([design.outline, disc]).exterior)
        design.fixes.append(f"{2 * need_r:.1f} mm backer disc added behind the drawing for the keycap post")
    center = (p.x, p.y)
    cx, cy = center
    t, h, depth = float(prod["thickness"]), prod["post_height"], prod["socket_depth"]
    span = hw["mx_stem_span"] + cfg["fit_test"]["stem_span_clearance"]
    post = cylinder(d, h, cx, cy, t)
    socket = extrude(plus(span, hw["mx_stem_arm_x"] + c, hw["mx_stem_arm_y"] + c, cx, cy), depth + 1.0, t + h - depth)
    # At full travel the post's end sits where the stem's cross ends; the keycap's back
    # must still clear the top of the switch housing.
    end_full = hw["mx_stem_top_above_plate"] - hw["mx_full_travel"] - min(depth, hw["mx_stem_height"])
    travel_clear = end_full + h - hw["mx_housing_above_plate"]
    if travel_clear < 0.5:
        design.warnings.append(f"keycap clears the switch by only {travel_clear:.1f} mm when pressed")
    design.fixes.append(f"keycap post {d} mm with a cross socket on the back, under the drawing's middle")
    # The keycap sits in the case's opening and must hide the switch's square top under it.
    cav = hw["mx_cavity_size"]
    before = design.outline.area
    square_back = rounded_rect(cav, cav, 1.0, cx, cy)
    design.outline = Polygon(max(_as_multi(unary_union([design.outline, square_back])).geoms, key=lambda g: g.area).exterior)
    if design.outline.area - before > 0.5:
        design.fixes.append(f"keycap filled out to a {cav} mm square behind the drawing, so it covers the switch")
    return {"kind": "stem_socket", "center": center, "post": post, "socket": socket, "post_diameter": d,
            "post_height": h, "socket_depth": depth, "clearance": c, "travel_clearance": round(travel_clear, 2)}


def build_clicker_case(cfg: dict, keycap: "Piece") -> "Piece":
    """The case is a cup shaped like the drawing (Allen, after the first print: the switch
    showed and the keycap floated high above the case). The switch snaps into a plate at
    the bottom of an opening shaped like the keycap; the keycap sits in that opening,
    `case_keycap_clearance` all round, its face `case_keycap_proud` above the rim, and
    presses down into it. Nothing of the switch shows. Below the plate: a hollow for the
    switch body and pins, and a floor with a push-out hole. A ring post at the top, the
    hole at half height, so the clicker sits flat on a table. Prints upright, one filament,
    no supports."""
    hw, prod = cfg["hardware"], cfg["products"]["clicker"]
    cut_fit = cfg["fit"]["switch_cutout"]
    cut = float(cut_fit["value"])
    name = f"{keycap.name}-case"
    cav, depth, lid = hw["mx_cavity_size"], hw["mx_cavity_depth"], hw["mx_plate_thickness"]
    floor, wall, r = prod["case_floor"], prod["case_wall"], prod["case_corner_radius"]
    cx, cy = keycap.attachment["center"]                 # the post: the switch sits right under it
    att = keycap.attachment
    # Where the keycap rests, above the switch plate: the post's end on the stem's cross.
    back_rest = hw["mx_stem_top_above_plate"] - min(att["socket_depth"], hw["mx_stem_height"]) + att["post_height"]
    proud = min(prod["case_keycap_proud"], keycap.thickness - 0.5)     # the rim always hides the gap under the keycap
    rim = back_rest + keycap.thickness - proud
    plate_z = floor + depth + lid                        # top of the plate the switch clips into
    height = plate_z + rim
    clr = prod["case_keycap_clearance"]
    opening = affinity.translate(keycap.design.outline, -cx, -cy).buffer(clr, join_style="round")
    shape = unary_union([opening.buffer(wall, join_style="round"), rounded_rect(cav + 2 * wall, cav + 2 * wall, r, 0.0, 0.0)])
    smooth = prod["case_smooth"]
    shape = shape.buffer(smooth, join_style="round").buffer(-smooth, join_style="round")
    shape = Polygon(max(_as_multi(shape).geoms, key=lambda g: g.area).exterior)
    design = Design(name, "clicker", shape, [], [], [])
    if not cut_fit["tested"]:
        design.warnings.append(f"switch hole {cut} mm is not from a fit test yet")
    # The ring hangs from a post at the top that stands the case's full height, with the
    # hole running left to right at half height: the ring never passes under the case, so
    # the clicker sits flat on a table. A teardrop hole prints upright without supports.
    ring_fit = cfg["fit"]["keyring_hole_diameter"]
    hole_d = float(ring_fit["value"])
    if not ring_fit["tested"]:
        design.warnings.append(f"keyring hole {hole_d} mm is not from a fit test yet")
    r_h = hole_d / 2.0
    core = shape.buffer(-2.0, join_style="round")
    core = max(_as_multi(core if not core.is_empty else shape).geoms, key=lambda g: g.area)
    hx = max(core.exterior.coords, key=lambda q: q[1])[0]
    length = max(prod["ring_post_length"], hole_d + 1.0)
    y_attach = box(hx - length / 2, shape.bounds[1] - 1, hx + length / 2, shape.bounds[3] + 1).intersection(shape).bounds[3]
    hy, hz = y_attach + prod["ring_post_gap"] + r_h, height / 2
    outer = hy + r_h + hw["keyring_hole_min_wall"]
    post_shape = rounded_rect(length, outer - (y_attach - 2.0), min(2.0, length / 2 - 0.1), hx, (outer + y_attach - 2.0) / 2)
    merged = unary_union([shape, post_shape]).buffer(1.0, join_style="round").buffer(-1.0, join_style="round")
    design.outline = Polygon(max(_as_multi(merged).geoms, key=lambda g: g.area).exterior)
    k = r_h / 2 ** 0.5
    drop = unary_union([Point(hy, hz).buffer(r_h, 48), Polygon([(hy - k, hz + k), (hy + k, hz + k), (hy, hz + r_h * 2 ** 0.5)])])
    body = extrude(design.outline, height) - _xsection_along_x(drop, length + 4.0, hx - length / 2 - 2.0)
    design.fixes.append(f"ring post at the top: a {hole_d} mm hole running left to right at half height, "
                        "so the clicker sits flat on a table")
    body = body - extrude(opening, rim + 1.0, plate_z)                       # the cup the keycap sits in
    body = body - extrude(square(cav), depth, floor)                         # the hollow under the plate
    body = body - extrude(square(cut), lid + 2.0, plate_z - lid - 1.0)       # the switch hole
    body = body - cylinder(prod["case_pushout_hole"], floor + 2.0, 0.0, 0.0, -1.0)
    minx, miny, maxx, maxy = shape.bounds
    design.fixes.insert(0, f"case is a cup shaped like the drawing ({maxx - minx:.1f} x {maxy - miny:.1f} mm, "
                           f"{height:.1f} mm tall): the keycap sits in its opening with {clr} mm to spare and "
                           f"stands {proud:.1f} mm above the rim, so the switch and the gap under the keycap are "
                           f"hidden; switch hole {cut} mm in a {lid} mm plate, room for the switch below, "
                           "push-out hole in the floor")
    design.paper_rgb = keycap.design.paper_rgb
    design.source = keycap.design.source
    base_name = f"{name} base"
    info = {"kind": "clicker_case", "switch_hole": cut, "hole_diameter": hole_d, "height": round(height, 2),
            "lid": lid, "cavity": cav, "cavity_depth": depth, "floor": floor, "plate_z": round(plate_z, 2),
            "rim": round(rim, 2), "proud": round(proud, 2), "clearance": clr, "opening": opening,
            "hole_center": (round(hx, 2), round(hy, 2)), "hole_z": round(hz, 2), "post_length": length,
            "post_from_y": round(y_attach - 2.0, 2)}
    return Piece(design, round(height, 2), {base_name: body}, {base_name: design.paper_rgb}, base_name, info,
                 part_slots={base_name: None}, style="case", group="cases", face_up=True)

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

def _add_ring_tab(cfg: dict, design: Design, position: str, *, fit_key: str = "keyring_hole_diameter",
                  wall: float | None = None, balance: bool = False) -> dict:
    """A round tab with a hole through it, front to back. Keychains: a split ring, a
    2.5 mm wall. Earrings (`balance`): a small tab right above the balance point, so the
    earring hangs straight, with a thin wall a small jump ring closes around."""
    hw = cfg["hardware"]
    fit = cfg["fit"][fit_key]
    hole_d = float(fit["value"])
    wall = hw["keyring_hole_min_wall"] if wall is None else wall
    if not fit["tested"]:
        design.warnings.append(f"{fit_key.replace('_diameter', '').replace('_', ' ')} {hole_d} mm is not from a fit test yet")
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
    # A hanging piece turns until its weight is right under the hole.
    x_tab = float(origin[0]) if balance else top_pt[0]
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
    if balance:
        design.fixes.append(f"small tab added on top, above the balance point, with a {hole_d} mm hole front to "
                            f"back for a {hw['jump_ring_diameter']:g} mm jump ring ({wall:g} mm of plastic around it)")
    else:
        design.fixes.append(f"ring tab added at the {position} with a {hole_d} mm hole")
    return {"kind": "ring_tab", "hole": hole, "hole_center": (float(hc[0]), float(hc[1])),
            "hole_diameter": hole_d, "position": position, "wall": wall,
            "ring": "jump ring" if balance else "split ring"}


# ---------------------------------------------------------------------------
# Side loop for pendants and earrings: the hole runs left to right
# ---------------------------------------------------------------------------

def _xsection_along_x(section, length: float, x0: float) -> m3d.Manifold:
    """Extrude a shape drawn in (world Y, world Z) along world X, from x0 to x0 + length."""
    from .geom import to_cross_section
    import numpy as np

    solid = m3d.Manifold.extrude(to_cross_section(section), length)
    # (u, v, w) -> (x = w + x0, y = u, z = v)
    return solid.transform(np.array([[0, 0, 1, x0], [1, 0, 0, 0], [0, 1, 0, 0]], dtype=float))


def _add_side_loop(cfg: dict, design: Design, kind: str) -> dict:
    """A loop on top whose hole runs left to right, parallel to the face, so a chain or
    earring hook goes straight through and the piece hangs facing forward. The loop's
    front is flush with the face (on the bed); it stands taller than the charm on the
    back. The hole is a flat-topped teardrop so it prints without supports."""
    from .geom import teardrop

    hw = cfg["hardware"]
    loop = hw[f"{kind}_loop"]
    fit = cfg["fit"][f"{kind}_hole_diameter"]
    d = float(fit["value"])
    if not fit["tested"]:
        design.warnings.append(f"{kind} hole {d} mm is not from a fit test yet")
    r = d / 2.0
    wall = loop["wall"]
    R = r + wall
    L = loop["length"]
    overlap, gap = hw["loop_overlap"], hw["loop_gap"]

    shape = design.outline
    minx, miny, maxx, maxy = shape.bounds
    # A hanging piece turns until its weight is right under the hole, so the loop goes
    # above the balance point (the centroid), not on the highest bump.
    x_c = float(shape.centroid.x)

    def top_at(x):
        cut = LineString([(x, miny - 1), (x, maxy + 1)]).intersection(shape)
        return None if cut.is_empty else cut.bounds[3]

    import numpy as np

    tops = [t for t in (top_at(x) for x in np.linspace(x_c - L / 2, x_c + L / 2, 15)) if t is not None]
    if not tops:
        raise ValueError("could not find the top of the drawing above its balance point")
    y_low = min(tops)                     # e.g. the dip of a heart
    # Nothing within 3 mm either side of the loop may stand above the hole, so the chain passes.
    clear = 3.0
    side = [t for t in (top_at(x) for x in np.linspace(x_c - L / 2 - clear, x_c + L / 2 + clear, 31)) if t is not None]
    y_c = max(side) + gap + r

    # Cross-section in (y, z): flat bottom on the bed, round top, hole through the middle.
    # The post reaches down into the drawing so it bridges a dip.
    section = unary_union([
        box(y_low - overlap, 0.0, y_c, 2 * R),
        box(y_c, 0.0, y_c + R, R),
        Point(y_c, R).buffer(R, quad_segs=24),
    ])
    hole = teardrop(d, y_c, R).intersection(box(y_c - R, R - R, y_c + R, R + 1.15 * r))
    solid = _xsection_along_x(section, L, x_c - L / 2)
    hole_solid = _xsection_along_x(hole, L + 2.0, x_c - L / 2 - 1.0)

    footprint = box(x_c - L / 2, y_low - overlap, x_c + L / 2, y_c + R)
    merged = unary_union([shape, footprint]).buffer(0.8, join_style="round").buffer(-0.8, join_style="round")
    design.outline = Polygon(max(_as_multi(merged).geoms, key=lambda g: g.area).exterior)
    word = "chain" if kind == "necklace" else "hook"
    design.fixes.append(f"loop added on top with a {d} mm hole running left to right for the {word}")
    return {"kind": "side_loop", "loop": kind, "hole_diameter": d, "center": (x_c, y_c),
            "height": 2 * R, "length": L, "solid": solid, "hole_solid": hole_solid}


def _build_figurine(cfg: dict, design: Design, back: str | None, base: str | None) -> Piece:
    """Any card's drawing as a standalone round-back figurine (the card's own attachment is not used)."""
    from .figurine import build_figurine_parts, scale_to_figurine

    scale_to_figurine(cfg, design)
    parts, colors, base_name, notes, info = build_figurine_parts(cfg, design, back, base)
    design.fixes.extend(notes)
    slots = {n: None for n in parts}
    for ink in design.inks:
        slots[f"{design.name} {ink.name}"] = ink.slot
    height = max(float(np.asarray(s.bounding_box())[5]) for s in parts.values())
    return Piece(design, round(height, 2), parts, colors, base_name, info, part_slots=slots,
                 style="figurine", face_up=True, supports=True)
