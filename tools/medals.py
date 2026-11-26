"""Thanksgiving award medals: quicker than trophies (Allen, 2026-11-26: the cups take "a long time to print, especially
5 of them"; "medals can be good, but I dont have ribbons").

A 68 mm gold medal, 3 mm thick, face up: a raised rim, a low-relief turkey (googly eyes, little crown) in the upper
half, two laurel branches round the bottom, the award in raised letters (one or two lines and the year), and a tab on top with a 13 x 3.6 mm slot that takes whatever is at hand:
kitchen twine, yarn, a shoelace, gift-wrap ribbon. Gold in slot 1, the letters in slot 2 (one color change at the
top). Our own design.

    python tools/medals.py [--awards "LEFTOVER|LEGEND" ...] [--year 2026] [--out output/medals]
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from pathlib import Path

import manifold3d as m3d
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
from cup_awards import AWARDS                    # noqa: E402  (the same award texts as the cup plates)
from star_topper import text_outline             # noqa: E402

M, CS = m3d.Manifold, m3d.CrossSection
SEG = 96
GOLD, BROWN = (224, 172, 52), (92, 58, 36)

P = dict(r=34.0, t=3.0, rim_w=2.4, raise_=0.9, slot=(13.0, 3.6), tab_r=9.0,
         turkey=True, turkey_y=9.5, text_y=-2.6, max_w=38.0)
# Allen (2026-11-26): "I want it to have a somewhat 3D turkey on top that doesnt stuck out too much": a low-relief
# turkey in the upper half (at most about 2.6 mm above the face), the words underneath; the medal grew to 68 mm.


def rounded_slot(w: float, h: float) -> CS:
    r = h / 2
    return CS.square([w - h, h], center=True).offset(r, m3d.JoinType.Round, circular_segments=32)


def laurel(r: float) -> CS:
    """Two laurel branches round the bottom of the medal (a flat shape): a curved stem from the bottom up each side,
    pairs of leaves along it pointing to the tip, and a leaf at the tip."""
    shapes = []
    for side in (-1, 1):
        angs = np.linspace(262, 214, 7) if side < 0 else np.linspace(278, 326, 7)
        pts = [r * np.array([math.cos(math.radians(a)), math.sin(math.radians(a))]) for a in angs]
        for p0, p1 in zip(pts, pts[1:]):
            shapes.append(CS.hull_points(np.array([p0, p1])).offset(0.55, m3d.JoinType.Round, circular_segments=12))
        for i in range(1, len(pts)):
            t = (pts[i] - pts[i - 1]) / np.linalg.norm(pts[i] - pts[i - 1])
            base = math.degrees(math.atan2(t[1], t[0]))
            for k in ((-1, 1) if i < len(pts) - 1 else (0,)):
                ang = base + 38 * k
                d = np.array([math.cos(math.radians(ang)), math.sin(math.radians(ang))])
                c = pts[i] + 2.1 * d
                shapes.append(CS.circle(1.0, 24).scale([2.5, 1.05]).rotate(ang).translate(list(c)))
    out = shapes[0]
    for sh in shapes[1:]:
        out = out + sh
    return out


def award_text(award: str, max_w: float = 37.0, top: float | None = None) -> CS:
    """The award's lines, centred in x; with `top`, the block hangs from that height, else it sits a little above
    the middle."""
    texts = [t.strip() for t in award.split("|") if t.strip()]
    sizes = {1: [7.0], 2: [5.4, 5.4], 3: [4.8, 4.8, 3.6]}[len(texts)]
    gap = {1: 0.0, 2: 2.4, 3: 1.9}[len(texts)]
    shapes = []
    for t, c in zip(texts, sizes):
        cs = text_outline(t, c)
        w = cs.bounds()[2] - cs.bounds()[0]
        if w > max_w:
            cs = text_outline(t, c * max_w / w)
        shapes.append(cs.offset(-0.16, m3d.JoinType.Round).offset(0.16, m3d.JoinType.Round))
    hs = [s.bounds()[3] - s.bounds()[1] for s in shapes]
    y = top if top is not None else (sum(hs) + gap * (len(hs) - 1)) / 2 + 2.5
    out = None
    for s, h in zip(shapes, hs):
        b = s.bounds()
        s = s.translate([-(b[0] + b[2]) / 2, y - b[3]])
        out = s if out is None else out + s
        y -= h + gap
    return out


def medal(award: str, p: dict = P) -> tuple[M, M]:
    """(gold body, raised letters), face up, back on z = 0, centred on the disc."""
    r, t, hr = p["r"], p["t"], p["raise_"]
    disc = CS.circle(r, SEG)
    tab = CS.hull_points(np.array([[x, y] for x, y in CS.circle(p["tab_r"], SEG).translate([0, r + 3.0]).to_polygons()[0]]
                                  + [[-p["tab_r"], r - 8.0], [p["tab_r"], r - 8.0]]))
    outline = disc + tab
    slot = rounded_slot(*p["slot"]).translate([0, r + 3.0])
    body = (outline - slot).extrude(t)
    rim = ((disc - CS.circle(r - p["rim_w"], SEG)) + (tab - disc) - slot).extrude(hr).translate([0, 0, t - 0.05])
    leaves = laurel(r - 7.0).extrude(hr).translate([0, 0, t - 0.05])
    gold = body + rim + leaves
    text = award_text(award, p["max_w"], p["text_y"] if p["turkey"] else None)
    letters = text.extrude(hr).translate([0, 0, t - 0.05])
    if p["turkey"]:
        tg, tk = turkey_relief(0.0, p["turkey_y"], t)
        gold = gold + tg
        letters = letters + tk
    return gold, letters


def _dome(c, r, z0: float) -> M:
    """An ellipsoid's top half standing on z = z0 (c is x, y; r is rx, ry, height)."""
    e = M.sphere(1.0, 48).scale(list(r)).translate([c[0], c[1], z0])
    return e ^ M.cube([400, 400, 50]).translate([-200, -200, z0])


def turkey_relief(cx: float, cy: float, t: float) -> tuple[M, M]:
    """A low-relief cartoon turkey (gold) with dark pupils, standing on the face at z = t: a fan of feathers in two
    rows, a round body with little wings, a head with googly eyes looking two ways, a beak, a wattle and a tiny
    crown. At most about 2.6 mm high."""
    gold = []
    fan_c = np.array([cx, cy + 1.0])
    for row, (R, n, h, w) in enumerate(((15.0, 9, 1.1, 3.0), (11.0, 8, 1.6, 2.7))):
        angs = np.linspace(-8, 188, n) if row == 0 else np.linspace(-8, 188, n + 1)[:-1] + 196 / n / 2
        for a in angs:
            u = np.array([np.cos(np.radians(a)), np.sin(np.radians(a))])
            tip, base = fan_c + (R - w) * u, fan_c + 3.0 * u
            gold.append(M.batch_hull([_dome(base, (2.4, 2.4, h * 0.85), t), _dome(tip, (w, w, h), t)]))
    gold.append(_dome((cx, cy - 1.0), (7.2, 8.0, 2.0), t))                     # body
    for side in (-1, 1):
        gold.append(_dome((cx + side * 6.3, cy - 2.0), (2.6, 4.6, 1.9), t).rotate([0, 0, 0]))   # wings
    hx, hy = cx, cy + 9.2
    gold.append(_dome((hx, hy), (4.9, 5.2, 2.2), t))                            # head
    gold.append(M.batch_hull([_dome((hx, hy - 2.4), (1.6, 1.2, 2.3), t), _dome((hx + 0.3, hy - 5.0), (0.55, 0.55, 2.0), t)]))  # beak
    gold.append(_dome((hx + 1.7, hy - 5.3), (1.05, 2.1, 1.9), t))              # wattle
    dark = []
    for side, look in ((-1, (-0.45, 0.35)), (1, (0.35, -0.45))):               # googly eyes, looking two ways
        ex, ey = hx + side * 2.2, hy + 1.3
        eye = _dome((ex, ey), (2.2, 2.2, 2.6), t)
        gold.append(eye)
        # The pupil: a thin dark cap lying on the eye's surface (nothing over air), off-centre so they look two ways.
        px, py = ex + look[0] * 1.2, ey + look[1] * 1.2          # the whole pupil stays on the eye
        cap = _dome((ex, ey), (2.45, 2.45, 3.0), t) ^ M.cylinder(5.0, 0.9, 0.9, 24).translate([px, py, t])
        dark.append(cap - _dome((ex, ey), (2.2, 2.2, 2.48), t))     # sunk 0.1 mm into the eye, like the letters
    # The crown: one tapered solid (sides lean in, so it shades as 3D: a flat top would look like the medal face),
    # with a ball on each point.
    pts = np.array([(-2.6, 0), (2.6, 0), (2.9, 2.9), (1.4, 1.5), (0, 3.4), (-1.4, 1.5), (-2.9, 2.9)]) * 1.3
    mid = np.array([0.0, 1.6 * 1.3])
    crown = CS([pts - mid], m3d.FillRule.NonZero).extrude(2.6, scale_top=[0.62, 0.62])
    place = lambda m: m.rotate([0, 0, -12]).translate([hx + 0.8 + mid[0], hy + 3.8 + mid[1], t - 0.05])
    gold.append(place(crown))
    for q in ((pts[2] - mid) * 0.64, (pts[4] - mid) * 0.64, (pts[6] - mid) * 0.64):
        gold.append(place(M.sphere(0.6, 20).translate([q[0], q[1], 2.55])))
    return union_all(gold), union_all(dark)


def union_all(parts) -> M:
    return M.batch_boolean([p for p in parts if not p.is_empty()], m3d.OpType.Add)


def layout(n: int, cell=(78.0, 82.0), bed: float = 256.0):
    cols = int((bed - 10) // cell[0])
    rows = -(-n // cols)
    x0 = bed / 2 - (min(n, cols) - 1) * cell[0] / 2
    y0 = bed / 2 + (rows - 1) * cell[1] / 2 - 3.0
    return [(x0 + (i % cols) * cell[0], y0 - (i // cols) * cell[1]) for i in range(n)]


def main() -> None:
    ap = argparse.ArgumentParser(description="Thanksgiving award medals")
    ap.add_argument("--awards", nargs="*", default=AWARDS, help='"LINE 1|LINE 2" for each medal')
    ap.add_argument("--year", default="2026", help="added as a last line where the text has no year ('' for none)")
    ap.add_argument("--per-plate", type=int, default=6)
    ap.add_argument("--out", type=Path, default=ROOT / "output" / "medals")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    awards = [a if not args.year or args.year in a else f"{a}|{args.year}" for a in args.awards]
    from charm_maker.bambu3mf import write_bambu_3mf
    import turkey_scepter as TS
    TS.COLORS.update({"ink": ("#3A2416", False)})
    groups = [awards[i:i + args.per_plate] for i in range(0, len(awards), args.per_plate)]
    scene, n = {}, 0
    for gi, group in enumerate(groups, start=1):
        objects = []
        for (x, y), a in zip(layout(len(group)), group):
            n += 1
            gold, letters = medal(a)
            for s in (gold, letters):
                assert s.status() == m3d.Error.NoError and not s.is_empty(), a
            name = f"{n:02d}-" + re.sub(r"[^a-z0-9]+", "-", a.replace("|", " ").lower()).strip("-")
            objects.append((name, [("medal", gold.translate([x, y, 0]), 1, GOLD), ("letters", letters.translate([x, y, 0]), 2, BROWN)]))
            dy = -(gi - 1) * 185.0                                  # each plate's medals below the last, in the picture
            scene[f"{name}-gold"] = (gold.translate([x - 128, y - 128 + dy, 0]), "gold")      # standing, facing you
            scene[f"{name}-ink"] = (letters.translate([x - 128, y - 128 + dy, 0]), "ink")
        write_bambu_3mf(objects, args.out / f"medals-{gi}.3mf", plate_name=f"medals-{gi}")
        print(f"medals-{gi}.3mf: {len(group)} medals")
    TS.to_glb(scene, args.out / "mockup.glb")
    (args.out / "medals.txt").write_text("\n".join(f"{i + 1:2d}. {a.replace('|', ' / ')}" for i, a in enumerate(awards)) + "\n")
    print("wrote", args.out)


if __name__ == "__main__":
    main()
