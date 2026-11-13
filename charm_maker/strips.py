"""Flexi: a kid's flat drawing cut into strips that wiggle (Allen, 2026-11-13, from two flat
Pusheen flexis he showed). The drawing is only cut, never changed.

Strips run across the drawing's long side (a tall drawing gets level cuts). Each cut is a thin
gap with T-shaped tabs: a narrow neck from the strip above, ending in a wider head, sits in a
roomy slot in the strip below. The head can't pull out past the slot's lips, and the slot
leaves room to slide sideways and turn a little: that is the wiggle. Everything prints flat,
already linked. Cuts go where they cross the least ink and never through a small dot or a
small closed mark (eyes, a nose), so the face stays whole. All 2D: the cut is removed from
every part through the full thickness.
"""
from __future__ import annotations

from shapely import affinity
from shapely.geometry import LineString, MultiLineString, Point, Polygon, box
from shapely.ops import unary_union

from .shape import Design, _as_multi


def joint_shapes(st: dict, gap: float, x: float, y: float):
    """One T-joint at x on a cut at height y: the tab (part of the strip above) and the slot
    it moves in (cut out of the strip below, gap included)."""
    wn, ln, wh, hh, s = st["neck_width"], st["neck_length"], st["head_width"], st["head_height"], st["slide"]
    tab = unary_union([box(x - wn / 2, y - ln, x + wn / 2, y + gap),
                       box(x - wh / 2, y - ln - hh, x + wh / 2, y - ln)])
    room = unary_union([box(x - wn / 2 - s, y - ln, x + wn / 2 + s, y),
                        box(x - wh / 2 - s, y - ln - hh, x + wh / 2 + s, y - ln)])
    return tab, room.buffer(gap, join_style=2)


def cut_shape(st: dict, gap: float, y: float, xs: list[float], x0: float, x1: float):
    """Everything removed along one cut: the gap across, and around each T the slot minus its tab."""
    depth = st["neck_length"] + st["head_height"] + gap + 1.0
    band = box(x0, y - depth, x1, y + gap + 1.0)
    upper = box(x0, y + gap / 2, x1, y + gap + 1.0)
    lower = box(x0, y - depth, x1, y - gap / 2)
    tabs, slots = [], []
    for x in xs:
        tab, slot = joint_shapes(st, gap, x, y)
        tabs.append(tab)
        slots.append(slot)
    keep = unary_union([upper, *tabs, lower.difference(unary_union(slots))])
    return band.difference(keep)


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
    gap = float(cfg["fit"]["flexi_strip_gap"]["value"])
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
    depth = st["neck_length"] + st["head_height"] + gap
    min_h = max(st["min_height"], depth + st["wall"] + 1.0)
    n = max(2, min(round(H / st["height"]), int(H // min_h)))
    min_width = st["head_width"] + 2 * (st["slide"] + gap + st["wall"]) + 2.0

    def joint_fits(x, y):
        _, slot = joint_shapes(st, gap, x, y)
        return outline.contains(slot.buffer(st["wall"], join_style=2))

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
                tab, slot = joint_shapes(st, gap, x, y)
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
            cost += line.buffer(0.6, cap_style=2).intersection(inks).area / 1.2
        if forbid is not None and line.buffer(gap / 2).intersects(forbid):
            cost += 1000
        elif near is not None and line.buffer(gap / 2).intersects(near):
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
    shape = unary_union([cut_shape(st, gap, c["y"], c["joints"], X0, X1) for c in cuts]) if cuts else None
    notes, warnings = [], []
    joints = sum(len(c["joints"]) for c in cuts)
    crossed = sum(c["crosses_small_mark"] for c in cuts)
    if cuts:
        notes.append(f"cut into {len(cuts) + 1} strips linked by {joints} T-joints ({gap} mm gap), "
                     f"cuts {'top to bottom' if turn else 'across'}" +
                     ("" if crossed else ", clear of the eyes and other small marks"))
    else:
        warnings.append("too small or too thin to cut into strips: it prints as one piece")
    if crossed:
        warnings.append(f"{crossed} cut(s) had to go through a small closed shape or dot (an eye? a toe?); "
                        "look at the preview")
    if not cfg["fit"]["flexi_strip_gap"].get("tested"):
        warnings.append(f"the flexi gap ({gap} mm) is not tested on your printer yet (fit-test pieces 23-26)")
    cut = back(shape) if shape is not None else None
    expected = len(cuts) + 1
    if cut is not None:
        parts = _as_multi(design.outline.difference(cut))
        real = [p for p in parts.geoms if p.area > 1.0]
        if len(real) != expected:
            warnings.append(f"the cuts make {len(real)} pieces, not {expected}; look at the preview")
            expected = len(real)
    return {"kind": "strips", "cut": cut, "strips": expected, "joints": joints, "notes": notes,
            "warnings": warnings, "cuts_y": [c["y"] for c in cuts], "turned": turn, "bodies": expected}


def scale_up_small(cfg: dict, design: Design) -> None:
    """A flexi needs room for its strips: a drawing shorter than size_min on its long side is
    scaled up to it (like the clicker; Allen: kids don't think in sizes)."""
    from .shape import scale_design

    prod = cfg["products"][design.product]
    minx, miny, maxx, maxy = design.outline.bounds
    long_ = max(maxx - minx, maxy - miny)
    if long_ < prod["size_min"] - 0.05:
        k = prod["size_min"] / long_
        scale_design(design, k)
        design.fixes.append(f"drawing scaled up {k:.2f}x to {prod['size_min']} mm, so the strips have room")
