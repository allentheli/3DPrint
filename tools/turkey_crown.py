"""A Thanksgiving crown, funny but fancy, for a family photo every year (Allen, 2026-11-25: "make a funny but
fancy Thanksgiving turkey crown, so we can start a funny tradition of taking picture with it on").

"King of the Feast": a gold crown with a raised border, a row of pearls, red domed jewels and a faceted orange gem;
the tall middle point is a medallion with a cartoon turkey (fanned tail, googly eyes, red wattle, its own tiny
crown); the side points are tipped with feast food instead of jewels (drumstick, pie, pumpkin, corn); the back
band says GOBBLE GOBBLE.

It prints flat and thin in two pieces, a front and a back, that bend round the head; two hair ties hooked over
the buttons at their ends join them at the sides, so one crown fits kids and grown-ups. Face-up, so the colors
are only in the raised top layers (few color changes); the jewels and buttons are red, so above the raised
layer only one color prints.

    python tools/turkey_crown.py [--out output/turkey-crown]
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
from star_topper import text_outline  # noqa: E402
from treasure_box import arc, ellipse, poly, smooth, stroke  # noqa: E402
from treasure_chest import rounded_rect  # noqa: E402

M, CS = m3d.Manifold, m3d.CrossSection
R = m3d.JoinType.Round
SEG = 64

T = 1.6            # base thickness (bends round a head)
RAISE = 0.8        # colored and gold details stand up this much (4 layers at 0.2 mm)
GAP = 0.6          # gold showing between neighboring colors
BAND = 26.0        # band height
FRONT_L, BACK_L = 230.0, 170.0
COLORS = {"gold": (232, 182, 40), "brown": (120, 70, 35), "orange": (240, 130, 30), "red": (200, 30, 45)}
SLOTS = {"gold": 1, "brown": 2, "orange": 3, "red": 4}


def circle(cx, cy, r) -> CS:
    return CS.circle(r, SEG).translate([cx, cy])


def union(items) -> CS | None:
    out = None
    for c in items:
        if c is None:
            continue
        out = c if out is None else out + c
    return out


class Layout:
    """Raised regions by color; anything added later keeps a gold gap from what came before."""

    def __init__(self):
        self.by_color: dict[str, CS] = {}
        self.taken: CS | None = None

    def add(self, color: str | None, cs: CS, gap: float = GAP):
        eff = cs if self.taken is None else cs - self.taken.offset(gap, R, circular_segments=32)
        if color is not None:
            self.by_color[color] = eff if color not in self.by_color else self.by_color[color] + eff
        self.taken = cs if self.taken is None else self.taken + cs


# ---------- the front ----------

POINTS = [(-92.0, 62.0, 28.0, "drumstick"), (-48.0, 77.0, 30.0, "pie"), (48.0, 77.0, 30.0, "pumpkin"), (92.0, 62.0, 28.0, "corn")]
MEDALLION = (0.0, 64.0, 27.0)       # center x, y and radius of the turkey's medallion


def front_outline() -> CS:
    a = FRONT_L / 2
    parts = [rounded_rect(-a, a, 0.0, BAND, 5.0)]
    for x, h, w, _ in POINTS:
        parts.append(poly([(x - w / 2, BAND - 2), (x + w / 2, BAND - 2), (x + 3.2, h - 19), (x - 3.2, h - 19)]))
        parts.append(circle(x, h - 10, 13.0))       # room for the food inside the border
    mx, my, mr = MEDALLION
    parts.append(poly([(-24, BAND - 2), (24, BAND - 2), (7, my - mr + 3), (-7, my - mr + 3)]))
    parts.append(circle(mx, my, mr))
    out = union(parts)
    out = out.offset(2.0, R, circular_segments=SEG).offset(-2.0, R, circular_segments=SEG)    # fillet the joins
    return out.offset(-0.8, R, circular_segments=SEG).offset(0.8, R, circular_segments=SEG)


def gold_trim(outline: CS, length: float, pearls_between=()) -> CS:
    ring = outline.offset(-1.2, R, circular_segments=SEG) - outline.offset(-3.2, R, circular_segments=SEG)
    a = length / 2
    top_line = CS.square([length - 8.0, 1.6]).translate([-a + 4.0, BAND - 3.6])
    pearls = []
    for x0, x1 in pearls_between:
        n = max(1, int((x1 - x0) / 4.2))
        for k in range(n):
            pearls.append(circle(x0 + (k + 0.5) * (x1 - x0) / n, BAND / 2, 1.3))
    return union([ring, top_line] + pearls)


def turkey(lay: Layout):
    """The royal turkey in the medallion, front view, highest-priority regions first."""
    cx, cy = 0.0, 59.0
    head = circle(0, 68.5, 6.2)
    # Googly eyes: gold eye holes, pupils looking two ways.
    for ex, (px, py) in ((-2.6, (-0.55, -0.45)), (2.6, (0.55, 0.35))):
        lay.add("brown", circle(ex + px, 69.2 + py, 0.8), gap=0.4)
    for ex in (-2.6, 2.6):
        lay.add(None, circle(ex, 69.2, 1.6))
    lay.add("orange", poly([(-2.0, 66.3), (2.0, 66.3), (0.0, 63.4)]))                      # beak
    lay.add("red", ellipse(1.4, 62.0, 1.3, 2.6, 8))                                         # wattle
    crown = union([poly([(-4.2, 74.4), (4.2, 74.4), (4.2, 77.2), (2.8, 79.6), (1.4, 77.0), (0, 80.2),
                         (-1.4, 77.0), (-2.8, 79.6), (-4.2, 77.2)])])
    lay.add("red", circle(0, 75.9, 0.9), gap=0.4)                                           # a jewel on it
    lay.add("gold", crown)                                                                  # its own tiny crown
    lay.add("brown", head)
    body = circle(0, 54.0, 10.0)
    for side in (-1, 1):                                                                    # little feet
        foot = union([stroke([(side * 4.0, 44.2), (side * 4.0 + d, 41.0)], 1.1) for d in (-1.6, 0.0, 1.6)])
        lay.add("orange", foot)
    lay.add("brown", body)
    wing = arc(-3.6, 54.0, 5.2, 115, 245, 1.0) + arc(3.6, 54.0, 5.2, -65, 65, 1.0)           # wings, not a smile
    # Tail feathers fanned behind the body, each with a gold band near its tip like a real turkey's.
    fx, fy = 0.0, 54.5
    colors = ["brown", "orange", "red", "orange", "red", "orange", "red", "orange", "brown"]
    band = CS.circle(18.6, SEG).translate([fx, fy]) - CS.circle(17.6, SEG).translate([fx, fy])
    for k, col in enumerate(colors):
        ang = -16.0 + 212.0 * k / (len(colors) - 1)
        rad = math.radians(ang)
        d = 12.0
        lay.add(col, ellipse(fx + d * math.cos(rad), fy + d * math.sin(rad), 3.9, 10.2, ang - 90.0) - band, gap=0.5)
    return wing


def food(kind: str, x: float, y: float, lay: Layout):
    """The feast food at the tip of a crown point (center x, y, about 20 mm across)."""
    if kind == "drumstick":
        k = 0.8
        bone = union([stroke([(x + 1.6 * k, y - 2.4 * k), (x + 5.4 * k, y - 6.2 * k)], 2.6 * k),
                      circle(x + 5.0 * k, y - 7.9 * k, 1.9 * k), circle(x + 7.1 * k, y - 5.8 * k, 1.9 * k)])
        lay.add("brown", ellipse(x - 1.8 * k, y + 2.0 * k, 5.6 * k, 7.8 * k, 45))           # the meat
        lay.add("gold", bone)                                                                 # gold bone...
        lay.add("brown", bone.offset(0.9, R, circular_segments=32) - bone.offset(0.1, R, circular_segments=32), gap=0.0)  # ...outlined
    elif kind == "pie":
        lay.add("gold", circle(x, y + 2.8, 1.7))                                              # whipped cream
        crust = poly([(x - 7.8, y + 5.0), (x + 7.8, y + 5.0), (x, y - 7.6)])
        crust = smooth(crust, 0.8)
        filling = crust.offset(-2.0, R, circular_segments=32) - CS.square([30, 6]).translate([x - 15, y + 2.6])
        lay.add("orange", filling)
        lay.add("brown", crust)
    elif kind == "pumpkin":
        lay.add("brown", poly([(x - 1.2, y + 5.6), (x + 1.2, y + 5.6), (x + 2.2, y + 9.0), (x - 0.2, y + 9.0)]))
        lobes = [ellipse(x - 3.8, y - 0.2, 4.2, 6.0), ellipse(x + 3.8, y - 0.2, 4.2, 6.0), ellipse(x, y, 3.8, 6.6)]
        lay.add("orange", lobes[2])
        lay.add("orange", lobes[0])
        lay.add("orange", lobes[1])
    elif kind == "corn":
        cob = ellipse(x, y + 1.6, 4.6, 8.0)
        grid = union([CS.square([0.6, 30]).translate([x - 0.3 + k * 2.3, y - 14]).rotate(0) for k in range(-3, 4)]
                     + [CS.square([30, 0.6]).translate([x - 15, y - 0.3 + k * 2.4]) for k in range(-5, 6)])
        lay.add("orange", cob - grid)
        for side in (-1, 1):
            leaf = poly([(x, y - 9.4), (x + side * 7.2, y - 1.0), (x + side * 2.6, y - 5.6)])
            lay.add("brown", smooth(leaf.offset(0.6, R), 0.3))


def jewel_dome(cs: CS, z0: float, height: float, n: int = 6) -> M:
    out = None
    r = 3.0
    for i in range(n):
        u = (i + 1) / n
        inset = r * (1 - math.sqrt(max(0.0, 1 - u * u)))
        layer = cs.offset(-inset, R, circular_segments=32)
        if layer.is_empty():
            break
        s = layer.extrude(height / n).translate([0, 0, z0 + height * i / n])
        out = s if out is None else out + s
    return out


def button(x: float, y: float) -> M:
    """A mushroom button the hair tie hooks over (45-degree underside, prints without supports)."""
    stem = M.cylinder(3.0 + 0.01, 2.6, 2.6, 48).translate([x, y, T])
    flare = M.cylinder(1.4, 2.6, 4.0, 48).translate([x, y, T + 3.0])
    cap = M.cylinder(0.8, 4.0, 4.0, 48).translate([x, y, T + 4.4])
    return stem + flare + cap


def front_piece() -> dict[str, M]:
    out_cs = front_outline()
    a = FRONT_L / 2
    lay = Layout()
    lay.add(None, out_cs - out_cs.offset(-3.6, R, circular_segments=SEG))      # keep the border clear
    lay.add(None, CS.square([FRONT_L, 3.6]).translate([-a, BAND - 4.8]))
    wing = turkey(lay)
    for x, h, w, kind in POINTS:
        food(kind, x, h - 10, lay)
    gems = [circle(x, BAND / 2, 5.0) for x in (-70.0, -24.0, 24.0, 70.0)]
    diamond = poly([(0, BAND / 2 - 8.0), (7.0, BAND / 2), (0, BAND / 2 + 8.0), (-7.0, BAND / 2)])
    pearls = [(-102.0, -76.0), (-64.0, -30.0), (-18.0, -9.0), (9.0, 18.0), (30.0, 64.0), (76.0, 102.0)]
    trim = gold_trim(out_cs, FRONT_L, pearls)
    parts = {"crown": out_cs.extrude(T)}
    # Drop slivers thinner than about 0.6 mm (cut-off corn kernels, feather tips): too thin to print cleanly.
    lay.by_color = {c: cs.offset(-0.3, R, circular_segments=24).offset(0.3, R, circular_segments=24)
                    for c, cs in lay.by_color.items()}
    raised = {c: cs.extrude(RAISE).translate([0, 0, T]) for c, cs in lay.by_color.items()}
    gold = trim + (lay.by_color.get("gold") or CS())
    parts["gold-details"] = gold.extrude(RAISE).translate([0, 0, T]) - (wing.extrude(1).translate([0, 0, T + RAISE - 0.4]))
    for c in ("brown", "orange"):
        parts[c] = raised[c]
    parts["brown"] = parts["brown"] - wing.extrude(1).translate([0, 0, T + RAISE - 0.4])          # wing line in the body
    red = raised["red"]
    for g in gems:
        red = red + jewel_dome(g, T, RAISE + 1.0)
    red = red + button(-a + 7.5, BAND / 2) + button(a - 7.5, BAND / 2)
    parts["red"] = red
    parts["orange"] = parts["orange"] + diamond.extrude(RAISE + 0.4, scale_top=(1.0, 1.0)).translate([0, 0, T]) \
        + diamond.translate([0, -BAND / 2]).extrude(0.8, scale_top=(0.45, 0.45)).translate([0, BAND / 2, T + RAISE + 0.4])
    return parts


def back_piece() -> dict[str, M]:
    a = BACK_L / 2
    out_cs = rounded_rect(-a, a, 0.0, BAND, 5.0)
    text = text_outline("GOBBLE GOBBLE", 10.5).translate([0, BAND / 2])
    gems = [circle(x, BAND / 2, 4.5) for x in (-62.0, 62.0)]
    ring = out_cs.offset(-1.2, R, circular_segments=SEG) - out_cs.offset(-3.2, R, circular_segments=SEG)
    parts = {"crown": out_cs.extrude(T),
             "gold-details": ring.extrude(RAISE).translate([0, 0, T]),
             "brown": text.extrude(RAISE).translate([0, 0, T])}
    red = None
    for g in gems:
        d = jewel_dome(g, T, RAISE + 1.0)
        red = d if red is None else red + d
    parts["red"] = red + button(-a + 7.5, BAND / 2) + button(a - 7.5, BAND / 2)
    return parts


PART_COLOR = {"crown": "gold", "gold-details": "gold", "brown": "brown", "orange": "orange", "red": "red"}


# ---------- worn picture ----------

def bend(s: M, radius: float, phi0: float) -> M:
    """Wrap a flat piece (x along it, y up, z outward) round a head of `radius`, centered at angle phi0."""
    s = s.refine_to_length(2.5)

    def f(v):
        v = np.asarray(v, float).copy()
        phi = phi0 + v[:, 0] / radius
        r = radius + v[:, 2]
        out = np.empty_like(v)
        out[:, 0] = r * np.sin(phi)
        out[:, 1] = -r * np.cos(phi)
        out[:, 2] = v[:, 1]
        return out
    return s.warp_batch(f)


def main() -> None:
    ap = argparse.ArgumentParser(description="Thanksgiving turkey crown")
    ap.add_argument("--out", default=str(ROOT / "output" / "turkey-crown"))
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    front, back = front_piece(), back_piece()
    for name, piece in (("front", front), ("back", back)):
        for k, s in piece.items():
            assert s.status() == m3d.Error.NoError and not s.is_empty(), (name, k)
    fb = front["crown"].bounding_box()
    print(f"front {fb[3] - fb[0]:.0f} x {fb[4] - fb[1]:.0f} mm, back {BACK_L:.0f} x {BAND:.0f} mm")
    write_files(front, back, out)


def write_files(front: dict, back: dict, out: Path) -> None:
    from charm_maker.bambu3mf import write_bambu_3mf
    from charm_maker.preview import render_shaded

    fb = M.batch_boolean(list(front.values()), m3d.OpType.Add).bounding_box()
    bb = M.batch_boolean(list(back.values()), m3d.OpType.Add).bounding_box()
    gap = 12.0
    depth = (fb[4] - fb[1]) + gap + (bb[4] - bb[1])
    y0 = 128 - depth / 2
    f_on = {k: v.translate([128, y0 + (bb[4] - bb[1]) + gap - fb[1], 0]) for k, v in front.items()}
    b_on = {k: v.translate([128, y0 - bb[1], 0]) for k, v in back.items()}
    objs = []
    for oname, piece in (("crown-front", f_on), ("crown-back", b_on)):
        objs.append((oname, [(f"{oname}-{k}", s, SLOTS[PART_COLOR[k]], COLORS[PART_COLOR[k]]) for k, s in piece.items()]))
    write_bambu_3mf(objs, out / "turkey-crown.3mf", plate_name="turkey-crown")
    # Pictures: flat from above, and worn (bent round a head, hair ties at the sides).
    cols = {}
    flat = {}
    for name, piece, dy in (("f", front, 0.0), ("b", back, -40.0)):
        for k, s in piece.items():
            flat[f"{name}-{k}"] = s.translate([0, dy, 0])
            cols[f"{name}-{k}"] = COLORS[PART_COLOR[k]]
    render_shaded(flat, out / "crown-flat.png", view=(70.0, 0.0), px_per_mm=5.0, labels=False, colors=cols)
    radius = 86.0
    worn, wcols = {}, {}
    for k, s in front.items():
        worn[f"f-{k}"] = bend(s, radius, 0.0)
        wcols[f"f-{k}"] = COLORS[PART_COLOR[k]]
    for k, s in back.items():
        worn[f"b-{k}"] = bend(s, radius, math.pi)
        wcols[f"b-{k}"] = COLORS[PART_COLOR[k]]
    # The hair ties, round the sides between the buttons.
    arc_len = math.pi * radius - (FRONT_L - 15) / 2 - (BACK_L - 15) / 2
    for side in (-1, 1):
        start = side * (FRONT_L / 2 - 7.5)
        tie = M.cube([arc_len, 2.0, 2.0]).translate([0 if side > 0 else -arc_len, BAND / 2 - 1.0, T + 1.5])
        worn[f"tie{side}"] = bend(tie.translate([start, 0, 0]), radius, 0.0)
        wcols[f"tie{side}"] = (60, 60, 70)
    render_shaded(worn, out / "crown-worn.png", view=(14.0, -18.0), px_per_mm=4.0, labels=False, colors=wcols)
    (out / "PRINT_NOTES.md").write_text(f"""# Turkey crown: print notes

"King of the Feast": a gold crown with jewels, a turkey in its own tiny crown in the middle, a drumstick, pie,
pumpkin and corn on the points, and GOBBLE GOBBLE on the back. Two flat pieces joined at the sides by two hair
ties, so it fits kids and grown-ups.

## Plate: `turkey-crown.3mf`

- Both pieces lie flat, decorated side up. Don't press **Arrange**.
- **Slot 1: gold** (or yellow), **slot 2: brown**, **slot 3: orange**, **slot 4: red**. The colors are only in
  the raised top layers, so there are only a few color changes; above them only red prints (jewels and buttons).
- Layer height **0.20 mm**, supports **off**. In the **Quality** tab set **Wall generator** to **Arachne** (fine
  details: the turkey's eyes, the corn).

## Putting it on

1. Gently bend each piece into a curve with your hands (it is thin on purpose).
2. Hook one hair tie over the button at the left end of the front piece and the button at the left end of the
   back piece; the same on the right.
3. Put it on with the turkey at the front. Bigger heads stretch the ties more; for a small head, wrap a tie twice.
4. To keep the curve for good: dip each piece in hot tap water (not boiling) for 30 seconds, wrap it round a big
   bowl or pot until it cools.
""")


if __name__ == "__main__":
    main()
