"""Milestone 0: the fit-test plate.

Numbered coupons, one per candidate size, for every fit-critical value in config,
plus one figure stand. Allen prints the plate once, tries the real hardware, and
reports the numbers that fit.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import manifold3d as m3d
import numpy as np

from .geom import (
    circle,
    cylinder,
    extrude,
    move_to,
    plus,
    rounded_rect,
    size,
    square,
)
from .labels import label_shape
from .stand import build_stand


@dataclass
class Coupon:
    number: int
    group: str          # config key under `fit:`
    candidate: float    # the size this coupon tests
    description: str
    solid: m3d.Manifold
    feature_center: tuple[float, float]   # where the pocket/hole is, local mm
    feature_size: float                    # diameter or square side
    outline: object                        # Shapely polygon of the coupon outline (local)
    extras: dict = field(default_factory=dict)


@dataclass
class FitPlate:
    coupons: list[Coupon]
    stand: m3d.Manifold
    placed: dict[str, m3d.Manifold]        # name -> solid moved into plate position
    positions: dict[str, tuple[float, float]]
    plate_size: tuple[float, float]


def _coupon_body(cfg: dict, key: str, number: int):
    """A rounded tag. Feature goes in the lower square, label in the top strip."""
    ft = cfg["fit_test"]
    w, length, t = ft[key]
    r = ft["coupon_corner_radius"]
    outline = rounded_rect(w, length, r, w / 2, length / 2)
    body = extrude(outline, t)
    feature_center = (w / 2, w / 2)
    label_cy = w + (length - w) / 2
    label = label_shape(str(number), ft["label_height"], ft["label_stroke"], w / 2, label_cy)
    body = body + extrude(label, ft["label_raise"], t)
    return body, outline, feature_center, t



def _switch_housing(cfg: dict, number: int, cutout: float):
    """A small closed box like the clicker case: a floor, a hollow big enough for the
    switch's bottom housing and pins, and a 1.5 mm lid with the square hole the switch
    snaps into. A push-out hole in the floor lets a pen push the switch back out between
    tests. The number sits on a flat tab beside the box."""
    ft, hw = cfg["fit_test"], cfg["hardware"]
    w, length, t = ft["switch_coupon"]
    r = ft["coupon_corner_radius"]
    floor, depth, cav = ft["switch_housing_floor"], hw["mx_cavity_depth"], hw["mx_cavity_size"]
    height = floor + depth + t
    cx, cy = w / 2, w / 2
    outline = rounded_rect(w, length, r, w / 2, length / 2)
    body = extrude(rounded_rect(w, w, r, cx, cy), height) + extrude(outline, t)
    body = body - extrude(square(cav, cx, cy), depth, floor)                     # the hollow
    body = body - extrude(square(cutout, cx, cy), t + 2.0, height - t - 1.0)     # hole in the lid
    body = body - cylinder(ft["switch_pushout_hole"], floor + 2.0, cx, cy, -1.0)
    label = label_shape(str(number), ft["label_height"], ft["label_stroke"], w / 2, w + (length - w) / 2)
    body = body + extrude(label, ft["label_raise"], t)
    extras = {"height": height, "floor": floor, "cavity": cav, "cavity_depth": depth,
              "pushout": ft["switch_pushout_hole"]}
    return body, outline, (cx, cy), t, extras

def _loop_coupon(cfg: dict, n: int, kind: str, d: float) -> Coupon:
    """A small tag with the same side loop a pendant or earring gets."""
    import copy

    from shapely.geometry import Polygon

    from .products import _add_side_loop
    from .shape import Design

    ft = cfg["fit_test"]
    w, length, t = ft[f"{kind}_loop_coupon"]
    outline = rounded_rect(w, length, ft["coupon_corner_radius"], w / 2, length / 2)
    c2 = copy.deepcopy(cfg)
    c2["fit"][f"{kind}_hole_diameter"]["value"] = d
    design = Design(f"fit-{n:02d}", kind, outline, [])
    info = _add_side_loop(c2, design, kind)
    body = (extrude(design.outline, t) + info["solid"]) - info["hole_solid"]
    label = label_shape(str(n), ft["label_height"], ft["label_stroke"], w / 2, length / 2)
    body = body + extrude(label, ft["label_raise"], t)
    word = "earring hook" if kind == "earring" else "necklace chain"
    return Coupon(n, f"{kind}_hole_diameter", d, f"{word} loop, {d} mm hole running left to right",
                  body, info["center"], d, Polygon(design.outline.exterior), {"loop_height": info["height"]})


def _earring_tab_coupon(cfg: dict, n: int, d: float) -> Coupon:
    """A small tag with the same top tab and jump-ring hole an earring gets."""
    import copy

    from shapely.geometry import Polygon

    from .products import _add_ring_tab
    from .shape import Design

    ft, hw = cfg["fit_test"], cfg["hardware"]
    w, length, t = ft["earring_tab_coupon"]
    outline = rounded_rect(w, length, ft["coupon_corner_radius"], w / 2, length / 2)
    c2 = copy.deepcopy(cfg)
    c2["fit"]["earring_hole_diameter"]["value"] = d
    design = Design(f"fit-{n:02d}", "earrings", outline, [])
    info = _add_ring_tab(c2, design, "top", fit_key="earring_hole_diameter", wall=hw["earring_tab_wall"], balance=True)
    body = extrude(design.outline.difference(info["hole"]), t)
    label = label_shape(str(n), ft["label_height"], ft["label_stroke"], w / 2, length / 2)
    body = body + extrude(label, ft["label_raise"], t)
    return Coupon(n, "earring_hole_diameter", d,
                  f"earring tab, {d} mm hole front to back for a {hw['jump_ring_diameter']:g} mm jump ring",
                  body, info["hole_center"], d, Polygon(design.outline.exterior), {"wall": info["wall"]})


def _revolve(profile) -> m3d.Manifold:
    """Spin a Shapely (radius, height) profile around the z axis."""
    from .geom import CIRCLE_SEGMENTS, to_cross_section

    return m3d.Manifold.revolve(to_cross_section(profile), CIRCLE_SEGMENTS)


def flexi_joint(cfg: dict, gap: float, cx: float, cy: float, end_r: float | None = None) -> dict:
    """The common flexi-toy joint (like the shark Allen showed): the front piece has a pocket
    with an upright pin standing in it; the back piece reaches in with a tongue that ends in
    a closed ring around the pin, `gap` apart all around. The ring turns around the pin, so
    the toy wiggles side to side, and it can't come off: the pin goes through it and the
    pocket's floor and ceiling hold it. The ring's edges are chamfered at 45 degrees and the
    pin flares to match above and below it (slimmer in the middle, like the shark's). The
    pocket's opening for the tongue stops the swing at about `swing` degrees each way.
    Returns the ring-and-tongue solid, the pocket void and the sizes; the front piece's
    rounded end has radius `lobe_r` around the pin (or `end_r`, if the piece's round end is
    bigger, as in a toy), the back piece's cupped end that plus `gap`; the tongue reaches it."""
    from shapely.geometry import Polygon, box

    j = cfg["fit_test"]["flexi_joint"]
    t = j["thickness"]
    zm = t / 2
    rp, w, h, c = j["pin_radius"], j["ring_width"], j["ring_height"], j["ring_chamfer"]
    ri, ro = rp + gap, rp + gap + w
    z0, z1 = zm - h / 2, zm + h / 2
    ring_profile = Polygon([(ri, z0 + c), (ri + c, z0), (ro - c, z0), (ro, z0 + c),
                            (ro, z1 - c), (ro - c, z1), (ri + c, z1), (ri, z1 - c)])
    ring = _revolve(ring_profile)
    pocket = _revolve(ring_profile.buffer(gap, join_style=2).intersection(box(0, -1, 50, t + 1)))
    neck_w = j["neck_width"]
    lobe_r = ro + gap + j["cup_wall"]
    end_r = max(end_r or 0.0, lobe_r)
    # The tongue: same height and chamfers as the ring, from the ring out into the back piece.
    tongue_yz = Polygon([(-neck_w / 2, z0 + c), (-neck_w / 2 + c, z0), (neck_w / 2 - c, z0), (neck_w / 2, z0 + c),
                         (neck_w / 2, z1 - c), (neck_w / 2 - c, z1), (-neck_w / 2 + c, z1), (-neck_w / 2, z1 - c)])
    from .geom import to_cross_section
    length = end_r + gap + 1.5 - (ro - 0.5)
    tongue = (m3d.Manifold.extrude(to_cross_section(tongue_yz), length)       # along +z, then lay it along +x
              .rotate([0.0, 90.0, 0.0]).rotate([90.0, 0.0, 0.0]))
    tb = tongue.bounding_box()
    tongue = tongue.translate([ro - 0.5 - tb[0], -(tb[1] + tb[4]) / 2, z0 - tb[2]])
    # The pocket's opening for the tongue: a slice of the pocket's height, swing degrees wider.
    half = np.degrees(np.arcsin((neck_w / 2 + gap) / ro)) + j["swing"]
    far = end_r + 5
    wedge = Polygon([(0, 0)] + [(far * np.cos(np.radians(a)), far * np.sin(np.radians(a)))
                                for a in np.linspace(-half, half, 25)])
    channel_yz = tongue_yz.buffer(gap, join_style=2)
    zc0, zc1 = channel_yz.bounds[1], channel_yz.bounds[3]
    channel = extrude(wedge, zc1 - zc0, zc0)
    channel = channel - _revolve(box(0, -1, rp, t + 1))                  # never cut the pin
    move = lambda m: m.translate([cx, cy, 0.0])                            # noqa: E731
    return {"ring": move(ring + tongue), "void": move(pocket + channel), "lobe_r": lobe_r,
            "slot_half_angle": float(half), "t": t, "pin_r": rp, "ring_in": ri, "ring_out": ro,
            "ring_z": (z0, z1)}


def _flexi_joint_coupon(cfg: dict, n: int, gap: float) -> Coupon:
    """A block with an arm on the ring joint. Hold the block, swing the arm."""
    from shapely.geometry import Point, Polygon
    from shapely.ops import unary_union

    ft = cfg["fit_test"]
    j = ft["flexi_joint"]
    bw, bh = j["body"]
    cx, cy = bw, bh / 2                               # the pin sits at the block's right end
    jt = flexi_joint(cfg, gap, cx, cy)
    t = jt["t"]
    block = rounded_rect(bw, bh, ft["coupon_corner_radius"], bw / 2, bh / 2)
    body2d = unary_union([block, Point(cx, cy).buffer(jt["lobe_r"], 96)])
    body = extrude(body2d, t) - jt["void"]
    label = label_shape(str(n), ft["label_height"], ft["label_stroke"], bw / 2 - 1.5, bh / 2)
    body = body + extrude(label, ft["label_raise"], t)
    cup = Point(cx, cy).buffer(jt["lobe_r"] + gap, 96)                 # the arm's end hugs the round end
    bar = rounded_rect(j["arm_length"], j["arm_width"], j["arm_width"] / 2 - 0.01,
                       cx + jt["lobe_r"] + j["arm_length"] / 2, cy)
    front = Polygon.from_bounds(cx + 2.0, cy - j["arm_width"] / 2, cx + jt["lobe_r"] + 2.0, cy + j["arm_width"] / 2)
    arm2d = unary_union([bar, front]).difference(cup)
    arm = extrude(arm2d, t) + jt["ring"]
    outline = unary_union([body2d, arm2d])
    return Coupon(n, "flexi_joint_gap", gap,
                  f"flexi ring joint, {gap} mm gap all around the ring (swings about {j['swing'] + 5:g} degrees each way)",
                  body + arm, (cx, cy), 2 * jt["ring_out"], outline,
                  {"body": body, "arm": arm, "joint": jt})


def build_coupons(cfg: dict) -> list[Coupon]:
    fit = cfg["fit"]
    hw = cfg["hardware"]
    ft = cfg["fit_test"]
    coupons: list[Coupon] = []
    n = 0

    # 1. Clip pad pockets (0.6 mm deep, on the up-facing side).
    for d in fit["clip_pocket_diameter"]["candidates"]:
        n += 1
        body, outline, (cx, cy), t = _coupon_body(cfg, "clip_coupon", n)
        depth = hw["clip_pocket_depth"]
        body = body - cylinder(d, depth + 1.0, cx, cy, t - depth)
        coupons.append(Coupon(n, "clip_pocket_diameter", d, f"clip pad pocket {d} mm, {depth} mm deep",
                              body, (cx, cy), d, outline, {"depth": depth}))

    # 2. Keyring holes (through).
    for d in fit["keyring_hole_diameter"]["candidates"]:
        n += 1
        body, outline, (cx, cy), t = _coupon_body(cfg, "keyring_coupon", n)
        body = body - cylinder(d, t + 2.0, cx, cy, -1.0)
        coupons.append(Coupon(n, "keyring_hole_diameter", d, f"split-ring hole {d} mm",
                              body, (cx, cy), d, outline))

    # 3. Earring tabs: the real small tab with a front-to-back hole for a jump ring.
    for d in fit["earring_hole_diameter"]["candidates"]:
        n += 1
        coupons.append(_earring_tab_coupon(cfg, n, d))

    # 4. MX switch housings: built like the clicker case, so the test covers the snap fit,
    #    the room under the switch (body and pins) and the lid printed over the hollow.
    for s in fit["switch_cutout"]["candidates"]:
        n += 1
        body, outline, (cx, cy), t, extras = _switch_housing(cfg, n, s)
        coupons.append(Coupon(n, "switch_cutout", s, f"switch housing, {s} mm square hole in a {t} mm lid",
                              body, (cx, cy), s, outline, extras))

    # 5. Keycap stem sockets: a boss with a plus-shaped hole, open at the top.
    for c in fit["stem_socket_clearance"]["candidates"]:
        n += 1
        body, outline, (cx, cy), t = _coupon_body(cfg, "stem_coupon", n)
        boss_h = ft["stem_boss_height"]
        boss = cylinder(hw["mx_keycap_post_diameter"], boss_h, cx, cy, t)
        arm_x = hw["mx_stem_arm_x"] + c
        arm_y = hw["mx_stem_arm_y"] + c
        # The grip comes from the arms' thickness, so only that varies; the cross length
        # gets a small fixed allowance, which keeps ~0.5 mm of plastic at the tips of a
        # real-size 5.5 mm post.
        span = hw["mx_stem_span"] + ft["stem_span_clearance"]
        socket = extrude(plus(span, arm_x, arm_y, cx, cy), ft["stem_socket_depth"] + 1.0,
                         t + boss_h - ft["stem_socket_depth"])
        body = body + boss - socket
        coupons.append(Coupon(n, "stem_socket_clearance", c,
                              f"stem socket arms {arm_x:.2f} x {arm_y:.2f} mm (clearance {c} mm)",
                              body, (cx, cy), hw["mx_keycap_post_diameter"], outline,
                              {"arm_x": arm_x, "arm_y": arm_y, "span": span,
                               "depth": ft["stem_socket_depth"]}))
    # 6. Necklace loops, same idea, bigger hole.
    for d in fit["necklace_hole_diameter"]["candidates"]:
        n += 1
        coupons.append(_loop_coupon(cfg, n, "necklace", d))
    # 7. Flexi joints: a body and an arm, printed already joined (two pieces by design).
    for g in fit["flexi_joint_gap"]["candidates"]:
        n += 1
        coupons.append(_flexi_joint_coupon(cfg, n, g))
    # 8. Flat flexi strips: two strips linked by a T-joint, printed already linked.
    for g in fit["flexi_strip_gap"]["candidates"]:
        n += 1
        coupons.append(_strip_joint_coupon(cfg, n, g))
    return coupons


def _strip_joint_coupon(cfg: dict, n: int, gap: float) -> Coupon:
    """Two strips of a flat flexi, the real thickness, linked by one T-joint as on the toy.
    Hold one strip, slide and wiggle the other."""
    from shapely.ops import unary_union

    from .strips import cut_shape

    ft = cfg["fit_test"]
    prod = cfg["products"]["flexi"]
    st, t = prod["strips"], float(prod["thickness"])
    w, h = 30.0, 11.0                                   # each strip
    outline = rounded_rect(w, 2 * h, ft["coupon_corner_radius"], w / 2, h)
    cut = cut_shape(st, gap, h, [w / 2], -5.0, w + 5.0)
    pieces = sorted(outline.difference(cut).geoms, key=lambda g: -g.bounds[3])
    upper, lower = (extrude(g, t) for g in pieces[:2])
    label = label_shape(str(n), ft["label_height"], ft["label_stroke"], w * 0.2, h + h / 2 + 1.0)
    upper = upper + extrude(label, ft["label_raise"], t)
    return Coupon(n, "flexi_strip_gap", gap, f"flat flexi strips, {gap} mm gap around a T-joint",
                  upper + lower, (w / 2, h), st["head_width"], unary_union([outline]),
                  {"body": lower, "arm": upper})


def build_fit_plate(cfg: dict, only: str | None = None) -> FitPlate:
    """The whole fit test, or with `only` (a `fit:` group) just that group's coupons,
    to reprint one group after a change. The numbers stay the full plate's numbers."""
    coupons = build_coupons(cfg)
    if only:
        coupons = [c for c in coupons if c.group == only]
        if not coupons:
            raise ValueError(f"no fit-test group {only!r}; use one of {', '.join(cfg['fit'])}")
    stand = None if only else build_stand(cfg)
    gap = cfg["fit_test"]["gap"]

    placed: dict[str, m3d.Manifold] = {}
    positions: dict[str, tuple[float, float]] = {}

    # Lay coupons out in rows, one row per group.
    x = y = 0.0
    row_h = 0.0
    max_x = 0.0
    current_group = None
    for c in coupons:
        if c.group != current_group and current_group is not None:
            x = 0.0
            y += row_h + gap
            row_h = 0.0
        current_group = c.group
        name = f"fit-{c.number:02d}"
        placed[name] = move_to(c.solid, x, y)
        positions[name] = (x, y)
        w, h, _ = size(c.solid)
        x += w + gap
        row_h = max(row_h, h)
        max_x = max(max_x, x)
    if stand is None:
        return FitPlate(coupons, None, placed, positions, (max_x - gap, y + row_h))
    # Stand goes to the right of the rows.
    sx = max_x + gap
    placed["stand"] = move_to(stand, sx, 0.0)
    positions["stand"] = (sx, 0.0)
    sw, sh, _ = size(stand)
    plate_w = sx + sw
    plate_h = max(y + row_h, sh)
    return FitPlate(coupons, stand, placed, positions, (plate_w, plate_h))


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

GROUP_TITLES = {
    "clip_pocket_diameter": ("Hair clip pad pocket", "Press the clip's round pad into each pocket. Best = snug, pad fully seated, no rocking."),
    "keyring_hole_diameter": ("Split-ring hole", "Thread a 25 mm split key ring through each hole. Best = goes on without forcing and turns freely."),
    "earring_hole_diameter": ("Earring jump-ring hole", "Put a 4 mm jump ring through each small hole and twist it shut. Best = the ring goes through and closes easily around the tab without bending it open; the smallest hole that does."),
    "switch_cutout": ("Switch housing", "Each piece is a small closed box, like the clicker case will be. Push the switch into the square hole in the lid until it clicks in, then press it a few times: it should click all the way down without hitting the floor. Best = snaps in, no wobble. To move the switch to the next box, push a pen through the hole in the floor (or use a switch puller from the top)."),
    "stem_socket_clearance": ("Keycap stem socket", "Each round post is the real keycap size (5.5 mm). Press each one onto the switch's cross stem. Best = firm push-on, stays on when you shake it, comes off with a pull. If a post cracks when pushed on, tell Claude: the keycap post needs to be thicker."),
    "flexi_joint_gap": ("Flexi joint", "Each piece is a block with an arm, printed already joined by a ring around a pin (the usual flexi-toy joint). Hold the block and swing the arm left and right; give it a firm wiggle first if it is stuck. Best = the arm swings freely and stops by itself at each side, does not wobble up and down, and does not come out. Pick the tightest one that swings freely."),
    "flexi_strip_gap": ("Flat flexi strips", "Each piece is two strips printed already linked by a T-shaped tab, like the flat flexi toys. Hold the bottom strip and slide the top one left and right, then bend them a little. Best = the strips slide and wiggle freely but stay together when you pull gently. Pick the tightest one that moves freely."),
    "necklace_hole_diameter": ("Necklace loop", "Thread your necklace chain (end first, clasp included) through each loop, left to right. Best = it goes through without forcing; the smallest that does."),
}


def fit_guide_markdown(cfg: dict, plate: "FitPlate") -> str:
    hw = cfg["hardware"]
    whole = plate.stand is not None
    intro = (["Print this plate once, try the real hardware on every numbered piece, and tell",
              f"Claude which number fits best in each group. There are {len(plate.coupons)} numbered coupons and one",
              "figure stand."] if whole else
             ["A small plate to retest one group after a change: "
              + ", ".join(str(c.number) for c in plate.coupons) + ". The numbers are the same as on the",
              "full fit-test plate, so report them the same way."])
    lines = [
        "# Fit test (milestone 0)" if whole else "# Fit test: one group again",
        "",
        *intro,
        "",
        "## 1. Print it",
        "",
        "1. Open Bambu Studio.",
        "2. Click **File > Import > Import 3MF/STL/STEP/SVG/OBJ/AMF...** and pick `fit-test.3mf` from this folder.",
        "   If Bambu Studio asks whether to load it as a project or geometry, choose **Load geometry only**.",
        "3. Leave every piece where it lands. If any piece is off the plate, click **Arrange** (the A key).",
        "4. In the **Process** panel set **Layer height** to **0.12 mm**. Supports stay **off**.",
        "5. Pick any one filament. Click **Slice plate**, then **Print plate**, and send it to the printer as usual.",
        "6. When it is done, pop the pieces off. Every piece has its number raised on the top face.",
        "",
        "## 2. Try the hardware",
        "",
    ]
    by_group: dict[str, list[Coupon]] = {}
    for c in plate.coupons:
        by_group.setdefault(c.group, []).append(c)
    step = 1
    for group, coupons in by_group.items():
        title, how = GROUP_TITLES[group]
        lines.append(f"### {step}. {title}")
        lines.append("")
        lines.append("| Piece | Tests |")
        lines.append("| --- | --- |")
        for c in coupons:
            lines.append(f"| **{c.number}** | {c.description} |")
        lines.append("")
        lines.append(how)
        lines.append("")
        step += 1
    if whole:
        lines += [
            f"### {step}. Stand and washer",
            "",
            "1. Put a 1 inch zinc-plated steel fender washer into the round recess on the back of the stand's upright.",
            "   It should drop in and sit flush or just below the surface. Glue it with gel super glue.",
            f"2. Glue a magnet flat onto the back of any coupon, about {hw['magnet_height_above_bottom']:.0f} mm above its bottom edge, with gel super glue. Let it cure.",
            "3. Stick that piece on the fridge. It should hold its own weight.",
            "4. Stand the same piece on the stand, magnet side toward the upright, bottom edge in the slot behind the lip.",
            "   It should snap gently to the upright and stay standing.",
            "",
        ]
    lines += [
        "## 3. Report",
        "",
        "Tell Claude one number per group, for example:",
        "",
        "> clip 2, keyring 5, earring 8, switch 11, stem 14, necklace 17, joint 20. Washer fits. Fridge and stand hold.",
        "",
        "If nothing fits in a group, say whether everything was too tight or too loose, and Claude",
        "will make a second plate with new sizes. Claude then runs `python -m charm_maker fit-results`",
        "and the values go into `config.yaml`.",
        "",
        "## Legend",
        "",
        "| Group | Pieces | Candidates (mm) |",
        "| --- | --- | --- |",
    ]
    for group, coupons in by_group.items():
        nums = ", ".join(str(c.number) for c in coupons)
        cands = ", ".join(str(c.candidate) for c in coupons)
        lines.append(f"| {GROUP_TITLES[group][0]} | {nums} | {cands} |")
    lines.append("")
    return "\n".join(lines)


def fit_guide_pdf(markdown_text: str, path):
    """A plain one-or-two-page PDF of the guide, for printing and keeping by the printer."""
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    from reportlab.lib import colors

    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(str(path), pagesize=letter, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=16 * mm, bottomMargin=16 * mm)
    flow = []
    table_rows: list[list[str]] = []

    def flush_table():
        nonlocal table_rows
        if not table_rows:
            return
        body = [[Paragraph(_md_inline(c), styles["BodyText"]) for c in row] for row in table_rows]
        t = Table(body, hAlign="LEFT")
        t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                               ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                               ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        flow.append(t)
        flow.append(Spacer(1, 3 * mm))
        table_rows = []

    for line in markdown_text.splitlines():
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if all(set(c) <= set("-: ") for c in cells):
                continue
            table_rows.append(cells)
            continue
        flush_table()
        if line.startswith("# "):
            flow.append(Paragraph(line[2:], styles["Title"]))
        elif line.startswith("## "):
            flow.append(Paragraph(line[3:], styles["Heading2"]))
        elif line.startswith("### "):
            flow.append(Paragraph(line[4:], styles["Heading3"]))
        elif line.startswith("> "):
            flow.append(Paragraph(_md_inline(line[2:]), styles["Italic"]))
        elif line.strip():
            flow.append(Paragraph(_md_inline(line), styles["BodyText"]))
        else:
            flow.append(Spacer(1, 2 * mm))
    flush_table()
    doc.build(flow)
    return path


def _md_inline(text: str) -> str:
    import re

    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"`(.+?)`", r"<font face='Courier'>\1</font>", text)
    return text


def write_fit_test(cfg: dict, plate: "FitPlate", out_dir) -> dict:
    from pathlib import Path

    from .export import write_plate
    from .preview import render_plan, render_shaded

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = write_plate(plate.placed, out_dir, "fit-test")
    paths["plan"] = render_plan(plate, out_dir / "fit-test-plan.png", title="Charm Maker fit-test plate (top view)")
    paths["preview"] = render_shaded(plate.placed, out_dir / "fit-test-preview.png")
    if "stand" in plate.placed:
        paths["stand-front"] = render_shaded({"stand": plate.placed["stand"]}, out_dir / "stand-front.png",
                                             view=(20.0, 20.0), px_per_mm=10, labels=False)
        paths["stand-back"] = render_shaded({"stand": plate.placed["stand"]}, out_dir / "stand-back.png",
                                            view=(20.0, 200.0), px_per_mm=10, labels=False)
    guide = fit_guide_markdown(cfg, plate)
    md = out_dir / "fit-test-guide.md"
    md.write_text(guide, encoding="utf-8")
    paths["guide-md"] = md
    paths["guide-pdf"] = fit_guide_pdf(guide, out_dir / "fit-test-guide.pdf")
    return paths
