"""The Golden Drumstick: a funny Thanksgiving trophy for the biggest eater (Allen, 2026-11-26: "'Golden Drumstick'
trophy thats a good idea, give me a mock up").

A two-tier walnut base with a gold plaque ("GOLDEN DRUMSTICK", "BIGGEST EATER 2026"), a round gold pedestal, and a
giant golden drumstick on it, the cartoon way (meat down, bone up at an angle): a big bite out of its side, a little
crown on crooked on the bone's knob, and two gold laurel branches round it. Our own design (the crown is the scepter turkey's).

    python tools/golden_drumstick.py [--out output/golden-drumstick]
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import manifold3d as m3d
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
import turkey_scepter as TS                      # noqa: E402  (shapes, crown, GLB writer)
from star_topper import text_outline             # noqa: E402

M = m3d.Manifold
ball, ell, chain, union = TS.ball, TS.ell, TS.chain, TS.union

TS.COLORS.update({
    "walnut": ("#4A2C1A", False),
    "palegold": ("#EBD38E", True),
    "ink": ("#24160D", False),
})

P = dict(
    lower=(110.0, 18.0, 72.0), upper=(96.0, 22.0, 58.0), trim=3.0, chamfer=2.0,
    plaque=(84.0, 17.0, 1.2), title="GOLDEN DRUMSTICK", sub="BIGGEST EATER 2026", title_h=6.0, sub_h=4.0,
)


def bevel_box(w: float, h: float, d: float, b: float) -> M:
    """A box w (x) by h (y) by d (z), bottom at y = 0, centred in x and z, with its edges chamfered by b."""
    parts = [M.cube([w - 2 * b, h, d - 2 * b], center=True), M.cube([w, h - 2 * b, d - 2 * b], center=True),
             M.cube([w - 2 * b, h - 2 * b, d], center=True)]
    return M.batch_hull(parts).translate([0, h / 2, 0])


def text_relief(text: str, height: float, raise_: float, max_w: float) -> M:
    """Raised letters `height` tall, made smaller if they would be wider than max_w."""
    cs = text_outline(text, height)
    b = cs.bounds()
    w = b[2] - b[0]
    if w > max_w:
        cs = text_outline(text, height * max_w / w)
    return cs.extrude(raise_)


def build(p: dict = P) -> dict[str, M]:
    parts: dict[str, list[M]] = {k: [] for k in ("walnut", "gold", "palegold", "ink", "red")}
    lw, lh, ld = p["lower"]
    uw, uh, ud = p["upper"]
    b = p["chamfer"]
    # Base: two walnut tiers with a gold moulding between them.
    parts["walnut"].append(bevel_box(lw, lh, ld, b))
    parts["gold"].append(bevel_box(uw + 8, p["trim"], ud + 8, 1.0).translate([0, lh, 0]))
    y_up = lh + p["trim"]
    parts["walnut"].append(bevel_box(uw, uh, ud, b).translate([0, y_up, 0]))
    top = y_up + uh

    # The plaque on the front of the top tier, with raised letters.
    pw, ph, pt = p["plaque"]
    pc = y_up + uh / 2
    plaque = bevel_box(pw, ph, pt * 2, 0.6).translate([0, pc - ph / 2, ud / 2 - pt * 0.5])
    parts["gold"].append(plaque)
    zf = ud / 2 + pt * 0.5
    parts["ink"].append(text_relief(p["title"], p["title_h"], 0.8, pw - 8).translate([0, pc + 3.2, zf - 0.05]))
    parts["ink"].append(text_relief(p["sub"], p["sub_h"], 0.8, pw - 14).translate([0, pc - 4.4, zf - 0.05]))

    # Gold pedestal.
    y = top
    for r, h in ((21.0, 3.0), (16.0, 8.0), (18.5, 2.5)):
        parts["gold"].append(M.cylinder(h, r, r, 96).rotate([-90, 0, 0]).translate([0, y, 0]))
        y += h
    ped = y

    # The drumstick, the classic cartoon way: the meaty end down on the pedestal, the bone sticking up at a jaunty
    # angle with its two-ball knob on top, wearing the crown. A big bite out of the meat's right side.
    tilt = 18.0                                            # leans left
    cy = ped + 27.0                                        # meat centre
    meat = M.batch_hull([ell([0, cy, 0], [24.0, 29.0, 21.0]), ell([0, cy + 34.0, 0], [9.5, 9.0, 8.5])])
    bone = M.cylinder(38.0, 5.4, 5.0, 48).rotate([-90, 0, 0]).translate([0, cy + 34.0, 0])
    collar = M.cylinder(4.0, 7.0, 7.0, 48).rotate([-90, 0, 0]).translate([0, cy + 36.0, 0])
    ky = cy + 76.0
    knob = union([ball([sx * 6.2, ky, 0], 7.6) for sx in (-1, 1)])
    stick = union([meat, bone, collar, knob])
    bites = [([25.0, cy + 5.0, 9.0], 11.5), ([26.5, cy - 9.0, 8.0], 11.0), ([21.0, cy + 18.0, 9.0], 10.5)]
    scoops = union([ball(c, r) for c, r in bites])
    bitten = stick - scoops
    lining = bitten ^ union([ball(c, r + 1.3) for c, r in bites])     # the inside of the bite, paler
    turn = lambda x: x.translate([0, -(ped - 2.0), 0]).rotate([0, 0, tilt]).translate([0, ped - 2.0, 0])
    parts["gold"].append(turn(bitten - lining))
    parts["palegold"].append(turn(lining))

    # A little crown, on crooked, on the bone's knob.
    place = lambda s: turn(s.rotate([0, 0, -12]).translate([0.0, ky + 3.0, 0]))
    parts["gold"].append(union([place(c) for c in TS.crown_pieces()]))
    parts["red"].append(place(ball([0, 4.0, 12.0], 2.2)))

    # Laurel branches curving up round the foot of the drumstick.
    for side in (-1, 1):
        xs = [side * (23 + 15 * math.sin(math.pi / 2 * t)) for t in np.linspace(0, 1, 9)]
        ys = [top + 0.5 + 54 * t for t in np.linspace(0, 1, 9)]          # rooted on the wooden base
        stem = chain([(x, yy, 9.0) for x, yy in zip(xs, ys)], [1.3] * 9)
        parts["gold"].append(stem)
        for i in range(1, 9):
            x0, y0 = xs[i], ys[i]
            dx, dy = xs[i] - xs[i - 1], ys[i] - ys[i - 1]
            ang = math.degrees(math.atan2(dy, dx))
            for s2 in (-1, 1):
                lean = ang + s2 * 38
                leaf = ell([0, 0, 0], [5.2, 2.2, 1.5]).rotate([0, 0, lean])
                off = 3.6 * np.array([math.cos(math.radians(lean)), math.sin(math.radians(lean))])
                parts["gold"].append(leaf.translate([x0 + off[0], y0 + off[1], 9.0]))
        parts["gold"].append(ell([0, 0, 0], [5.0, 2.2, 1.5]).rotate([0, 0, 90 - side * 25]).translate([xs[-1] + side * 1.5, ys[-1] + 4.0, 9.0]))
    return {k: union(v) for k, v in parts.items() if v}


def main() -> None:
    ap = argparse.ArgumentParser(description="Golden Drumstick trophy mock-up")
    ap.add_argument("--out", type=Path, default=ROOT / "output" / "golden-drumstick")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    parts = build()
    for k, s in parts.items():
        assert s.status() == m3d.Error.NoError and not s.is_empty(), k
    b = union(list(parts.values())).bounding_box()
    print(f"trophy {b[3] - b[0]:.0f} wide x {b[4] - b[1]:.0f} tall x {b[5] - b[2]:.0f} deep mm")
    TS.to_glb({f"trophy-{k}": (s, k) for k, s in parts.items()}, args.out / "mockup.glb")
    print("wrote", args.out / "mockup.glb")


if __name__ == "__main__":
    main()
