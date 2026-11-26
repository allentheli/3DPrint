"""Thanksgiving awards: a set of funny trophies on the Golden Drumstick's walnut-and-gold base (Allen, 2026-11-26:
"give me a 2nd version ... I want multiple awards/trophies, one is champion of potatoes among others").

    drumstick     GOLDEN DRUMSTICK, the first version (golden_drumstick.py)
    drumstick-2   GOLDEN DRUMSTICK: a two-handled trophy cup with two crossed drumsticks sticking out of it
    potatoes      CHAMPION OF POTATOES: a mashed-potato volcano, gravy in the crater and running down, a butter pat,
                  and a golden fork stuck in it like the sword in the stone
    pie           PIE MASTER: a slice of pumpkin pie with a whipped-cream swirl
    gravy         GRAVY BOAT CAPTAIN: a gravy boat with a mast and a sail
    food-coma     FOOD COMA CHAMPION: a roast turkey asleep on a platter, a "Zzz" thought bubble

Our own designs. Mock-ups for now: one GLB per award and a lineup.

    python tools/thanksgiving_trophies.py [--only potatoes pie] [--out output/thanksgiving-trophies]
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
import golden_drumstick as GD                    # noqa: E402  (base, plaque, drumstick v1)
import turkey_scepter as TS                      # noqa: E402  (shapes, crown, GLB writer)
from star_topper import text_outline             # noqa: E402

M, CS = m3d.Manifold, m3d.CrossSection
ball, ell, chain, union = TS.ball, TS.ell, TS.chain, TS.union

TS.COLORS.update({
    "potato": ("#F2E6C2", False),
    "gravy": ("#6B3B1C", False),
    "butter": ("#F7D65A", False),
    "pumpkin": ("#D47A2A", False),
    "crust": ("#C98F4E", False),
    "cream": ("#FFFBF2", False),
    "porcelain": ("#F3F3EF", False),
    "roast": ("#9A4E24", False),
    "cloud": ("#EEF3FA", False),
})


def revolve(profile, segments: int = 96) -> M:
    """A solid of revolution round the y axis from (radius, height) points."""
    return M.revolve(CS([np.array(profile, float)]), segments).rotate([-90, 0, 0])


def cyl_y(r0: float, r1: float, h: float, y: float, seg: int = 96) -> M:
    return M.cylinder(h, r0, r1, seg).rotate([-90, 0, 0]).translate([0, y, 0])


def plate(parts, y: float, r: float = 30.0) -> float:
    """A little porcelain plate on the pedestal; returns its top."""
    parts["porcelain"].append(revolve([(0, 0), (r - 6, 0), (r - 5, 1.2), (r, 3.2), (r - 0.8, 4.0), (r - 6, 2.2),
                                       (0, 2.2)]).translate([0, y, 0]))
    return y + 2.2


def drumstick_solid(bite: bool) -> tuple[M, M | None]:
    """A cartoon drumstick, meat centre at the origin, bone up the y axis (version 1's shape, 0.62 times)."""
    meat = M.batch_hull([ell([0, 0, 0], [24.0, 29.0, 21.0]), ell([0, 34.0, 0], [9.5, 9.0, 8.5])])
    bone = M.cylinder(38.0, 5.4, 5.0, 48).rotate([-90, 0, 0]).translate([0, 34.0, 0])
    collar = M.cylinder(4.0, 7.0, 7.0, 48).rotate([-90, 0, 0]).translate([0, 36.0, 0])
    knob = union([ball([sx * 6.2, 76.0, 0], 7.6) for sx in (-1, 1)])
    stick = union([meat, bone, collar, knob])
    if not bite:
        return stick.scale([0.62] * 3), None
    bites = [([22.0, 18.0, 10.0], 10.5), ([16.0, 27.0, 9.0], 9.5)]
    bitten = stick - union([ball(c, r) for c, r in bites])
    lining = bitten ^ union([ball(c, r + 1.3) for c, r in bites])
    return (bitten - lining).scale([0.62] * 3), lining.scale([0.62] * 3)


# ---------------------------------------------------------------- toppers (each adds to `parts`, standing on y0)

def drumstick_cup(parts, top: float, y0: float) -> None:
    """A classic trophy cup (foot, knotted stem, bowl, two handles, "#1") with two crossed drumsticks in it."""
    foot = revolve([(0, 0), (17, 0), (17, 2.5), (13.5, 4.0), (6.5, 9.0), (5.2, 13.0), (8.5, 15.0), (8.5, 17.5),
                    (5.2, 19.5), (5.2, 22.0), (0, 22.0)])
    bowl = revolve([(0, 21.0), (6.0, 21.0), (13.0, 24.0), (20.0, 30.5), (24.0, 39.0), (26.0, 48.0), (26.5, 53.0),
                    (28.5, 54.0), (28.5, 56.5), (26.0, 57.5), (0, 57.5)])
    parts["gold"] += [foot.translate([0, y0, 0]), bowl.translate([0, y0, 0])]
    for side in (-1, 1):                    # handles: C-shaped loops on each side
        pts = [(side * (25.5 + 13 * math.sin(t)), y0 + 41 + 11 * math.cos(t), 0) for t in np.linspace(0.15, 2.9, 12)]
        parts["gold"].append(chain(pts, [2.6] * len(pts)))
    one = text_outline("#1", 13.0).extrude(4.0).translate([0, y0 + 40.0, 21.6])
    parts["red"].append(one)                # raised 1.4 mm off the bowl's front
    for side, tilt, z, bite in ((-1, 24.0, -5.0, False), (1, -24.0, 5.0, True)):
        stick, lining = drumstick_solid(bite)
        place = lambda s: s.rotate([0, 0, tilt]).translate([side * 3.0, y0 + 50.0, z])
        parts["gold"].append(place(stick))
        if lining is not None:
            parts["palegold"].append(place(lining))


def potatoes(parts, top: float, y0: float) -> None:
    """A mashed-potato volcano: lumpy mound, gravy in the crater and running down the front, a butter pat in the
    gravy, a golden fork stuck in the side like the sword in the stone."""
    y = plate(parts, y0, 32.0)
    prof = [(0, 0), (29, 0), (28, 3), (25.5, 9), (21.5, 16), (17, 23), (13.5, 29), (12, 32), (0, 32)]
    mound = revolve(prof).translate([0, y, 0])
    r_at = lambda h: float(np.interp(h, [q[1] for q in prof[1:-1]], [q[0] for q in prof[1:-1]]))
    lumps = []
    rng = np.random.default_rng(7)
    for i, h in enumerate(np.linspace(4, 28, 6)):
        n = 7 - i // 2
        for k in range(n):
            a = 2 * math.pi * (k + 0.5 * (i % 2)) / n + rng.uniform(-0.15, 0.15)
            rb = 8.0 + rng.uniform(-1.0, 1.0)
            rr = r_at(h) + 1.6 - rb                 # big and sunk, so each is a soft dollop
            lumps.append(ball([rr * math.sin(a), y + h, rr * math.cos(a)], rb))
    crater = ell([0, y + 33.5, 0], [10.0, 6.0, 10.0])
    potato = union([mound] + lumps) - crater
    parts["potato"].append(potato)
    pool = (ell([0, y + 33.5, 0], [10.2, 6.2, 10.2]) ^ M.cube([40, 40, 40], center=True).translate([0, y + 30.5 - 20, 0]))
    parts["gravy"].append(pool)
    for a_deg, drop in ((-10.0, 21.0), (28.0, 13.0), (-48.0, 9.0)):     # gravy running down over the rim
        a = math.radians(a_deg)
        pts, rads = [], []
        for t in np.linspace(0, 1, 10):
            h = 30.5 - drop * t
            rb = 3.6 - 0.8 * t + (1.0 if t == 1 else 0.0)
            rr = (r_at(min(h, 29.5)) + 2.0 - rb) if h < 30 else 8.5 + 3.0 * t
            pts.append((rr * math.sin(a), y + h, rr * math.cos(a)))
            rads.append(rb)
        parts["gravy"].append(chain(pts, rads))
    butter = M.batch_hull([ball([sx * 4.0, sy * 1.3, sz * 4.0], 0.9) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)])
    parts["butter"].append(butter.rotate([6, 25, -8]).translate([0.5, y + 31.2, 0.5]))
    # The fork: handle, neck, four tines going into the mash at an angle.
    fork = [M.batch_hull([ball([0, 0, 0], 2.2), ball([0, 26.0, 0], 3.0)]).scale([1.0, 1.0, 0.45]),
            M.batch_hull([ball([0, 26.0, 0], 2.0), ball([0, 33.0, 0], 4.0)]).scale([1.0, 1.0, 0.45])]
    for t in (-3, -1, 1, 3):
        fork.append(M.batch_hull([ball([t * 1.25, 33.0, 0], 0.7), ball([t * 1.25, 46.0, 0], 0.55)]))
    fork = union(fork).rotate([0, 0, 180]).rotate([0, 0, 32]).translate([-28.4, y + 61.0, 4.0])  # tines in the mash
    parts["gold"].append(fork)


def pie(parts, top: float, y0: float) -> None:
    """A slice of pumpkin pie, point to the front, crimped crust at the back, a whipped-cream swirl on top."""
    y = plate(parts, y0, 36.0)
    apex, R, half = np.array([0.0, 30.0]), 56.0, math.radians(24)
    arc = [apex + R * np.array([math.sin(t), -math.cos(t)]) for t in np.linspace(-half, half, 24)]
    wedge = [apex] + arc
    poly = CS([np.array([(x, -z) for x, z in wedge])], m3d.FillRule.NonZero)      # either winding
    crust_b = poly.extrude(4.0).rotate([-90, 0, 0]).translate([0, y, 0])
    filling = poly.offset(-1.2, m3d.JoinType.Round).extrude(17.0).rotate([-90, 0, 0]).translate([0, y + 3.9, 0])
    parts["crust"].append(crust_b)
    parts["pumpkin"].append(filling)
    rim = []
    for i, t in enumerate(np.linspace(-half, half, 15)):
        q = apex + (R - 2.5) * np.array([math.sin(t), -math.cos(t)])
        rim.append(ell([q[0], y + 18.5, q[1]], [4.2, 5.0, 4.8]))
    wall = (poly - poly.offset(-5.0, m3d.JoinType.Round)).extrude(18.5)
    parts["crust"] += [union(rim), (wall.rotate([-90, 0, 0]).translate([0, y + 1.0, 0]))]
    # Whipped cream: a swirl getting smaller as it rises, and a little tip.
    c = apex + 26.0 * np.array([0, -1])
    pts, rads = [], []
    for k, t in enumerate(np.linspace(0, 2.6, 30)):
        a = 2 * math.pi * t
        rr = 8.5 * (1 - t / 3.0)
        pts.append((c[0] + rr * math.cos(a), y + 22.5 + 4.2 * t, c[1] + rr * math.sin(a)))
        rads.append(4.6 * (1 - t / 3.6))
    parts["cream"] += [chain(pts, rads), ball([c[0], y + 35.0, c[1]], 2.0)]


def gravy_boat(parts, top: float, y0: float) -> None:
    """A gravy boat on a saucer: spout at the front right, handle at the back left, gravy inside, a drip down the
    spout, and a mast with a sail (the captain's ship)."""
    y = plate(parts, y0, 30.0)
    outer = M.batch_hull([ell([-4, y + 11.0, 0], [21.0, 11.0, 13.5]), ell([22.0, y + 17.0, 0], [3.0, 3.0, 2.6])])
    inner = M.batch_hull([ell([-4, y + 12.5, 0], [18.5, 9.5, 11.0]), ell([20.0, y + 18.5, 0], [1.6, 2.0, 1.2])])
    cut = M.cube([100, 50, 100], center=True).translate([0, y + 20.5 + 25, 0])
    boat = outer - cut - inner
    foot = cyl_y(8.0, 9.5, 2.5, y)
    parts["porcelain"] += [boat, foot]
    gravy = (inner ^ M.cube([100, 50, 100], center=True).translate([0, y + 17.0 - 25, 0]))
    drip = chain([(23.0, y + 18.0, 0), (24.0, y + 13.0, 0.5), (23.5, y + 9.5, 1.0)], [1.4, 1.2, 1.6])
    parts["gravy"] += [gravy, drip]
    handle = [(-24.0 - 9 * math.sin(t), y + 13 + 8 * math.cos(t), 0) for t in np.linspace(0.2, math.pi - 0.2, 10)]
    parts["porcelain"].append(chain(handle, [2.2] * len(handle)))
    mast = cyl_y(1.3, 1.1, 40.0, y + 12.0).translate([-2.0, 0, 0])
    sail = CS([np.array([(0, 0), (22.0, 0), (0, 30.0)], float)]).extrude(1.4).translate([0.0, 0.0, -0.7])
    flag = CS([np.array([(0, 0), (8.0, 2.5), (0, 5.0)], float)]).extrude(1.0).translate([0, 0, -0.5])
    parts["gold"] += [mast, sail.translate([-0.8, y + 21.0, 0]), ball([-2.0, y + 52.3, 0], 1.6)]
    parts["red"].append(flag.translate([-1.0, y + 45.0, 0]))


def food_coma(parts, top: float, y0: float) -> None:
    """A roast turkey asleep on its back on a platter, drumsticks in the air with paper frills, and a "Zzz" thought
    bubble."""
    y = plate(parts, y0, 33.0)
    roast = []                                   # turned so the drumsticks face front right
    spin = lambda s: s.translate([0, -y, 0]).rotate([0, -40, 0]).translate([0, y, 0])
    body = M.batch_hull([ell([0, y + 13.0, 0], [24.0, 14.0, 18.0]), ell([-8, y + 15.0, 0], [16.0, 15.0, 15.0])])
    roast.append(body)
    for side in (-1, 1):                         # drumsticks up and outward, frills on the bone ends
        meat = M.batch_hull([ell([0, 0, 0], [7.5, 9.0, 7.0]), ell([0, 12.0, 0], [3.5, 3.0, 3.5])])
        bone = M.cylinder(9.0, 2.2, 2.0, 32).rotate([-90, 0, 0]).translate([0, 11.0, 0])
        turn = lambda s: s.rotate([0, 0, 30]).rotate([side * 42, 0, 0]).translate([12.0, y + 21.0, side * 9.0])
        roast.append(turn(union([meat, bone])))
        frill_c = np.asarray(turn(ball([0, 21.0, 0], 1.0)).bounding_box()).reshape(2, 3).mean(0)
        parts["cream"].append(spin(union([ball(frill_c + 1.6 * np.array([math.cos(a), 0, math.sin(a)]), 2.0)
                                          for a in np.linspace(0, 2 * math.pi, 7)[:-1]] + [ball(frill_c, 2.4)])))
        roast.append(ell([-6, y + 14.0, side * 15.5], [9.0, 5.0, 4.0]))       # wings tucked
    parts["roast"].append(spin(union(roast)))
    # Thought bubble: little bubbles rising to a cloud with raised "Zzz".
    for (bx, by_, r) in ((-14.0, 28.0, 2.6), (-19.0, 35.0, 3.4)):
        parts["cloud"].append(ball([bx, y + by_, 6.0], r))
    cc = np.array([-20.0, y + 52.0])
    cloud = union([ball([cc[0] + dx, cc[1] + dy, 6.0], r) for dx, dy, r in
                   ((0, 0, 9.0), (-9, -2, 7.0), (9, -2, 7.0), (-5, 5, 7.0), (5, 6, 7.5), (0, -5, 7.5))])
    parts["cloud"].append(cloud)
    zzz = text_outline("Zzz", 8.5).extrude(2.0).translate([cc[0], cc[1], 13.5])
    parts["ink"].append(zzz)


AWARDS = {
    "drumstick": ("GOLDEN DRUMSTICK", "BIGGEST EATER 2026", None),
    "drumstick-2": ("GOLDEN DRUMSTICK", "BIGGEST EATER 2026", drumstick_cup),
    "potatoes": ("CHAMPION OF POTATOES", "MOST MASHED 2026", potatoes),
    "pie": ("PIE MASTER", "LAST SLICE 2026", pie),
    "gravy": ("GRAVY BOAT CAPTAIN", "MOST GRAVY 2026", gravy_boat),
    "food-coma": ("FOOD COMA CHAMPION", "FIRST ASLEEP 2026", food_coma),
}


def award(key: str) -> dict[str, M]:
    title, sub, topper = AWARDS[key]
    parts, top, ped = GD.base(title, sub)
    (topper or GD.drumstick)(parts, top, ped)
    return {k: union(v) for k, v in parts.items() if v}


def main() -> None:
    ap = argparse.ArgumentParser(description="Thanksgiving award trophies (mock-ups)")
    ap.add_argument("--only", nargs="*", default=list(AWARDS))
    ap.add_argument("--out", type=Path, default=ROOT / "output" / "thanksgiving-trophies")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    lineup = {}
    for i, key in enumerate(args.only):
        parts = award(key)
        for k, s in parts.items():
            assert s.status() == m3d.Error.NoError and not s.is_empty(), (key, k)
        b = union(list(parts.values())).bounding_box()
        print(f"{key}: {b[3] - b[0]:.0f} wide x {b[4] - b[1]:.0f} tall x {b[5] - b[2]:.0f} deep mm")
        TS.to_glb({f"{key}-{k}": (s, k) for k, s in parts.items()}, args.out / f"{key}.glb")
        lineup.update({f"{key}-{k}": (s.translate([i * 130.0, 0, 0]), k) for k, s in parts.items()})
    TS.to_glb(lineup, args.out / "lineup.glb")
    print("wrote", args.out)


if __name__ == "__main__":
    main()
