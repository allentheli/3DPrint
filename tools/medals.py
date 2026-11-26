"""Thanksgiving award medals: quicker than trophies (Allen, 2026-11-26: the cups take "a long time to print, especially
5 of them"; "medals can be good, but I dont have ribbons").

A 60 mm gold medal, 3 mm thick, face up: a raised rim, two laurel branches round the bottom, the award in raised
letters (one or two lines and the year), and a tab on top with a 13 x 3.6 mm slot that takes whatever is at hand:
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

P = dict(r=30.0, t=3.0, rim_w=2.4, raise_=0.9, slot=(13.0, 3.6), tab_r=9.0)


def rounded_slot(w: float, h: float) -> CS:
    r = h / 2
    return CS.square([w - h, h], center=True).offset(r, m3d.JoinType.Round, circular_segments=32)


def laurel(r: float) -> CS:
    """Two laurel branches round the bottom of the medal (a flat shape): a curved stem from the bottom up each side,
    pairs of leaves along it pointing to the tip, and a leaf at the tip."""
    shapes = []
    for side in (-1, 1):
        angs = np.linspace(266, 196, 8) if side < 0 else np.linspace(274, 344, 8)
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


def award_text(award: str, max_w: float = 37.0) -> CS:
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
    y = (sum(hs) + gap * (len(hs) - 1)) / 2 + 2.5           # a little above the middle, clear of the laurel
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
    leaves = laurel(r - 8.5).extrude(hr).translate([0, 0, t - 0.05])
    gold = body + rim + leaves
    letters = award_text(award).extrude(hr).translate([0, 0, t - 0.05])
    return gold, letters


def layout(n: int, cell=(72.0, 82.0), bed: float = 256.0):
    cols = int((bed - 10) // cell[0])
    rows = -(-n // cols)
    x0 = bed / 2 - (min(n, cols) - 1) * cell[0] / 2
    y0 = bed / 2 + (rows - 1) * cell[1] / 2 - 3.0
    return [(x0 + (i % cols) * cell[0], y0 - (i // cols) * cell[1]) for i in range(n)]


def main() -> None:
    ap = argparse.ArgumentParser(description="Thanksgiving award medals")
    ap.add_argument("--awards", nargs="*", default=AWARDS, help='"LINE 1|LINE 2" for each medal')
    ap.add_argument("--year", default="2026", help="added as a last line where the text has no year ('' for none)")
    ap.add_argument("--per-plate", type=int, default=9)
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
            if gi == 1:
                scene[f"{name}-gold"] = (gold.translate([x - 128, y - 128, 0]), "gold")      # standing, facing you
                scene[f"{name}-ink"] = (letters.translate([x - 128, y - 128, 0]), "ink")
        write_bambu_3mf(objects, args.out / f"medals-{gi}.3mf", plate_name=f"medals-{gi}")
        print(f"medals-{gi}.3mf: {len(group)} medals")
    TS.to_glb(scene, args.out / "mockup.glb")
    (args.out / "medals.txt").write_text("\n".join(f"{i + 1:2d}. {a.replace('|', ' / ')}" for i, a in enumerate(awards)) + "\n")
    print("wrote", args.out)


if __name__ == "__main__":
    main()
