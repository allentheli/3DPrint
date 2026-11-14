"""Flexi: a kid's flat drawing cut into strips that wiggle (Allen, 2026-11-13, from two flat
Pusheen flexis he showed). The drawing is only cut, never changed.

Strips run across the drawing's long side (a tall drawing gets level cuts). The joint is the
one Bambu Lab's MakerLab Flexi tool makes (Allen: "lets do the joint like this"), measured on
Lawk3t's Pusheen Cat Flexi Toy (CC0) and copied size for size: the strips stand 1.5 mm apart;
the strip above reaches down with a tab into a wider notch in the strip below, and a round pin
of the strip below runs across the notch, through a round tunnel in the tab, with a gap all
around. The pin holds the strips together in every direction; the extra room in the notch lets
them slide along the pin and bend: that is the wiggle. Everything prints flat, already linked.
Cuts go where they cross the least ink and never through a small dot or a small closed mark
(eyes, a nose), so the face stays whole.
"""
from __future__ import annotations

import manifold3d as m3d
from shapely import affinity
from shapely.geometry import LineString, MultiLineString, Point, Polygon, box
from shapely.ops import unary_union

from .shape import Design, _as_multi


def joint_shapes(j: dict, x: float, y: float):
    """One joint at x on a cut whose middle is at height y (2D): the tab (part of the strip above)
    and the notch it sits in (cut out of the strip below)."""
    g = j["seam_gap"] / 2
    tab = box(x - j["tab_width"] / 2, y + g - j["tab_length"], x + j["tab_width"] / 2, y + g + 0.01)
    notch = box(x - j["notch_width"] / 2, y - g - j["notch_depth"], x + j["notch_width"] / 2, y - g)
    return tab, notch


def cut_shape(j: dict, y: float, xs: list[float], x0: float, x1: float):
    """Everything removed through the full thickness along one cut: the gap between the strips,
    and each notch around its tab."""
    g = j["seam_gap"] / 2
    depth = g + j["notch_depth"] + 1.0
    band = box(x0, y - depth, x1, y + g + 1.0)
    upper = box(x0, y + g, x1, y + g + 1.0)
    lower = box(x0, y - depth, x1, y - g)
    tabs, notches = zip(*(joint_shapes(j, x, y) for x in xs)) if xs else ((), ())
    keep = unary_union([upper, *tabs, lower.difference(unary_union(list(notches)))])
    return band.difference(keep)


def _rod(x: float, y: float, z: float, radius: float, length: float) -> m3d.Manifold:
    """A round rod lying along X, centered at (x, y, z)."""
    return (m3d.Manifold.cylinder(length, radius, radius, 64, True)
            .rotate([0.0, 90.0, 0.0]).translate([x, y, z]))


def joint_solids(j: dict, y: float, xs: list[float], thickness: float):
    """The 3D part of the joints on one cut: the tunnels through the tabs (removed from every part)
    and the pins (added to the strip below), at mid-thickness."""
    g = j["seam_gap"] / 2
    yc, zc = y - g - j["pin_below_edge"], thickness / 2
    tunnels = [_rod(x, yc, zc, j["tunnel_radius"], j["tab_width"] + 0.4) for x in xs]
    pins = [_rod(x, yc, zc, j["pin_radius"], j["notch_width"] + 1.0) for x in xs]
    return tunnels, pins


def _segments(geom) -> list[LineString]:
    if geom.is_empty:
        return []
    if isinstance(geom, LineString):
        return [geom]
    if isinstance(geom, MultiLineString):
        return list(geom.geoms)
    return [g for g in getattr(geom, "geoms", []) if isinstance(g, LineString)]


def plan_strips(cfg: dict, design: Design) -> dict:
    """Where the cuts go and the 2D shape to remove. Returns {"cut", "strips", "joints", "notes",
    "warnings", "cuts_y"} in the drawing's own coordinates."""
    prod = cfg["products"][design.product]
    st = prod["strips"]
    j = st["joint"]
    minx, miny, maxx, maxy = design.outline.bounds
    turn = (maxx - minx) > (maxy - miny) * 1.05             # wide: cut it top to bottom instead
    to_work = (lambda g: affinity.rotate(g, 90, origin=(0, 0))) if turn else (lambda g: g)    # noqa: E731
    back = (lambda g: affinity.rotate(g, -90, origin=(0, 0))) if turn else (lambda g: g)      # noqa: E731
    outline = to_work(design.outline)
    inks = to_work(unary_union([ink.geometry for ink in design.inks])) if design.inks else None
    # Face features the cuts must not touch: kept dots (eyes), small separate ink marks, and
    # small closed marks with their paper inside (a ring eye, teeth, a nose), line and all.
    # A cut through one is refused unless nothing else works; a cut close beside one is avoided.
    def compact(g, solid=0.6, aspect=2.5) -> bool:
        mrr = g.minimum_rotated_rectangle
        if mrr.geom_type != "Polygon":
            return False
        ex = [((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5
              for a, b in zip(mrr.exterior.coords[:2], mrr.exterior.coords[1:3])]
        return g.area >= solid * g.convex_hull.area and max(ex) <= aspect * max(min(ex), 1e-6)
    edge = design.outline.exterior
    small = [Point(x, y).buffer(0.8) for x, y in design.dots]
    for ink in design.inks:
        for g in _as_multi(ink.geometry).geoms:
            # A small, roughly round mark inside the drawing (a nose, a dot); slivers of color
            # spilled along the edge do not count.
            if 0.5 <= g.area < st["small_mark_area"] and compact(g, 0.5, 3.0) and g.distance(edge) > 2.0:
                small.append(g.buffer(0.3))
            for ring in g.interiors:
                hole = Polygon(ring)
                if hole.area < st["closed_mark_area"] and compact(hole):   # round or neat: an eye, a tooth
                    small.append(hole.convex_hull.buffer(1.2))              # paper and its ring line
    forbid = to_work(unary_union(small)) if small else None
    near = forbid.buffer(1.0) if forbid is not None else None
    X0, Y0, X1, Y1 = outline.bounds
    X0, X1 = X0 - 5, X1 + 5
    H = Y1 - Y0
    depth = j["seam_gap"] / 2 + j["notch_depth"]
    min_h = max(st["min_height"], depth + st["wall"] + j["seam_gap"] / 2)
    n = max(2, min(round(H / st["height"]), int(H // min_h)))
    min_width = j["notch_width"] + 2 * st["wall"] + 2.0

    def joint_fits(x, y):
        _, notch = joint_shapes(j, x, y)
        return outline.contains(notch.buffer(st["wall"], join_style=2))

    def place_joints(y, xl, xr):
        """T positions on a cut from xl to xr: the best spot near each target, in the base color if it can."""
        w = xr - xl
        targets = [xl + w / 4, xr - w / 4] if w >= st["two_joints_from"] else [(xl + xr) / 2]
        found = []
        for tx in targets:
            best = None
            for k in range(-16, 17):
                x = tx + 0.25 * k
                if not joint_fits(x, y):
                    continue
                tab, slot = joint_shapes(j, x, y)
                cost = 0.2 * abs(x - tx)
                if inks is not None:
                    cost += slot.boundary.intersection(inks).length
                if forbid is not None and slot.intersects(forbid):
                    cost += 1000
                elif near is not None and slot.intersects(near):
                    cost += 20
                if best is None or cost < best[0]:
                    best = (cost, x)
            if best is not None:
                found.append(best)
        if len(targets) == 2 and len(found) < 2:            # two did not fit: try one in the middle
            return place_joints_one(y, xl, xr)
        return found

    def place_joints_one(y, xl, xr):
        saved = st["two_joints_from"]
        st["two_joints_from"] = 1e9
        try:
            return place_joints(y, xl, xr)
        finally:
            st["two_joints_from"] = saved

    def evaluate(y):
        segs = [s for s in _segments(outline.intersection(LineString([(X0, y), (X1, y)]))) if s.length > 0.5]
        if len(segs) != 1:
            return None
        xs = [c[0] for c in segs[0].coords]
        xl, xr = min(xs), max(xs)
        if xr - xl < min_width:
            return None
        line = LineString([(xl, y), (xr, y)])
        cost = 0.0
        if inks is not None:      # ink cut through, or run along closely (a cut beside a line shows)
            w = j["seam_gap"] / 2 + 0.6
            cost += line.buffer(w, cap_style=2).intersection(inks).area / (2 * w)
        if forbid is not None and line.buffer(j["seam_gap"] / 2).intersects(forbid):
            cost += 1000
        elif near is not None and line.buffer(j["seam_gap"] / 2).intersects(near):
            cost += 20
        joints = place_joints(y, xl, xr)
        if not joints:
            return None
        cost += sum(c for c, _ in joints)
        return cost, xl, xr, [x for _, x in joints]

    # Every height a cut could go, scored once; then the cuts are chosen together (so one cut can
    # move to give the next a clean spot), keeping the strips close to even.
    step = 0.25
    ys = [Y0 + min_h + step * i for i in range(int((H - 2 * min_h) / step) + 1)]
    scored = {y: evaluate(y) for y in ys}
    ys = [y for y in ys if scored[y] is not None]

    def choose(n_strips: int):
        ideal = [Y1 - k * H / n_strips for k in range(1, n_strips)]
        win = 0.6 * H / n_strips
        best: list[dict] = []
        for k, target in enumerate(ideal):
            row = {}
            for y in ys:
                if abs(y - target) > win or Y1 - y < min_h * (k + 1) or y - Y0 < min_h * (len(ideal) - k):
                    continue
                own = scored[y][0] + 0.3 * abs(y - target)
                if k == 0:
                    row[y] = (own, None)
                    continue
                prev = [(v[0], py) for py, v in best[-1].items() if py - y >= min_h]
                if prev:
                    c, py = min(prev)
                    row[y] = (c + own, py)
            if not row:
                return None
            best.append(row)
        total, y = min((v[0], y) for y, v in best[-1].items())
        chosen = [y]
        for k in range(len(best) - 1, 0, -1):
            y = best[k][y][1]
            chosen.append(y)
        return total, sorted(chosen, reverse=True)

    picked = None
    for n_try in range(n, 1, -1):                 # fewer strips if that keeps the face whole
        got = choose(n_try)
        if got is None:
            continue
        crosses = any(scored[y][0] >= 1000 for y in got[1])
        if picked is None or (picked[2] and not crosses):
            picked = (n_try, got[1], crosses)
        if not crosses:
            break
    cuts = []
    for y in (picked[1] if picked else []):
        cost, xl, xr, xs = scored[y]
        cuts.append({"y": y, "x": (xl, xr), "joints": xs, "crosses_small_mark": cost >= 1000})
    shape = unary_union([cut_shape(j, c["y"], c["joints"], X0, X1) for c in cuts]) if cuts else None
    tunnels, pins = [], []
    for c in cuts:
        t, p = joint_solids(j, c["y"], c["joints"], float(prod["thickness"]))
        tunnels += t
        pins += p
    turn3d = (lambda m: m.rotate([0.0, 0.0, -90.0])) if turn else (lambda m: m)    # noqa: E731
    tunnels = [turn3d(m) for m in tunnels]
    pins = [turn3d(m) for m in pins]
    notes, warnings = [], []
    joints = sum(len(c["joints"]) for c in cuts)
    crossed = sum(c["crosses_small_mark"] for c in cuts)
    if cuts:
        notes.append(f"cut into {len(cuts) + 1} strips linked by {joints} pin joints (Bambu's MakerLab flexi joint), "
                     f"cuts {'top to bottom' if turn else 'across'}" +
                     ("" if crossed else ", clear of the eyes and other small marks"))
    else:
        warnings.append("too small or too thin to cut into strips: it prints as one piece")
    if crossed:
        warnings.append(f"{crossed} cut(s) had to go through a small closed shape or dot (an eye? a toe?); "
                        "look at the preview")
    cut = back(shape) if shape is not None else None
    expected = len(cuts) + 1
    if cut is not None:
        parts = _as_multi(design.outline.difference(cut))
        real = [p for p in parts.geoms if p.area > 1.0]
        if len(real) != expected:
            warnings.append(f"the cuts make {len(real)} pieces, not {expected}; look at the preview")
            expected = len(real)
    return {"kind": "strips", "cut": cut, "tunnels": tunnels, "pins": pins, "strips": expected, "joints": joints,
            "notes": notes,
            "warnings": warnings, "cuts_y": [c["y"] for c in cuts], "turned": turn, "bodies": expected}


def scale_up_small(cfg: dict, design: Design) -> None:
    """A flexi is about default_size (80 mm) on its long side, like Allen's examples: a drawing
    drawn smaller is scaled up to it (like the clicker; Allen: kids don't think in sizes), so the
    strips and joints have room and the cuts can go around the face."""
    from .shape import scale_design

    prod = cfg["products"][design.product]
    minx, miny, maxx, maxy = design.outline.bounds
    long_ = max(maxx - minx, maxy - miny)
    target = float(prod["default_size"])
    if long_ < target - 2.0:
        k = target / long_
        scale_design(design, k)
        design.fixes.append(f"drawing scaled up {k:.2f}x to {target:g} mm, the flexi's size, so the strips have room")
