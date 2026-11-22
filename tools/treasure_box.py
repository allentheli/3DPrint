"""A second treasure box, from Allen's other daughter's drawing (2026-11-22): "Don't need to be faithful to her
drawing, make it nicer. Can reuse the basics of the prior treasure box. The last one took a while to print".

Her drawing (the front): a box with a tall lid; on the lid a "bread cat", "2 paw prints" and a "star with face and
feet"; an "ice cream" right on the seam; on the box "puppy hearts", a lattice "heart" and stars. Here:

- The lid top carries her bread cat, two paw prints and the smiling star with feet, inlaid flush in color. The
  lid prints upside down (its top on the bed), so the colors are only in the first 3 layers: few color changes.
- The ice cream is the lock, like the heart on her sister's chest: a loose ice cream gem, scoop in the lid and cone
  in the box, holds the lid shut.
- The box front has her puppy hearts, a lattice heart and stars in relief; the lid front has little paw prints.
- Flat lid, a thin tray (the first chest's domed lid was mostly solid plastic and took most of the time).
- Same hinge as the first chest: printed knuckles, 1.75 mm filament pins, a stop so the lid stays open.

    python tools/treasure_box.py [--out output/treasure-box-2]
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
from treasure_chest import box, centroid, drop_specks, heart, prism_xy, prism_xz, prism_yz, rounded_rect  # noqa: E402

M, CS = m3d.Manifold, m3d.CrossSection
SEG = 64
R = m3d.JoinType.Round

P = dict(
    W=100.0, D=74.0, Hb=60.0, Hl=34.0,   # outside width, depth; box height, lid height (her lid is about 36% of the front)
    corner=6.0, wall=2.0, floor=2.0, top=2.4, chamfer=2.0,
    inlay=0.6,                     # colors on the lid top: 3 layers at 0.2 mm
    relief=1.5, engrave=0.9,       # raised pictures on the fronts; faces cut into them
    fit=0.10, plug=4.0,            # the ice cream gem: gap in its pocket (as the heart gems), depth
    k_r=4.0, k_w=6.0, k_gap=0.4, pin_d=2.2, hinge_x=28.0, stop_shelf=4.0, rail=0.0,
    top_style="raised",            # "raised" (Allen, 2026-11-22: "not colored but raised") or "color" (inlaid, lid upside down)
    ribs=(-16.0, 16.0), rib_t=0.9,   # raised: 2 thin dividers inside the lid hold its top up while printing (31 mm bridges)
)


# ---------- little pictures (mm, "up" is +y) ----------

def poly(pts) -> CS:
    """A polygon either way round."""
    return CS([np.array(pts, float)], m3d.FillRule.NonZero)


def ellipse(cx, cy, rx, ry, rot=0.0) -> CS:
    return CS.circle(1.0, SEG).scale([rx, ry]).rotate(rot).translate([cx, cy])


def smooth(cs: CS, r: float = 0.5) -> CS:
    return cs.offset(-r, R, circular_segments=SEG).offset(r, R, circular_segments=SEG)


def star(Ro: float, ratio: float = 0.5, rot: float = 0.0, round_: float = 0.8) -> CS:
    pts = [((Ro if k % 2 == 0 else Ro * ratio) * math.cos(math.radians(90 + rot + 36 * k)),
            (Ro if k % 2 == 0 else Ro * ratio) * math.sin(math.radians(90 + rot + 36 * k))) for k in range(10)]
    return smooth(poly(pts), round_)


def stroke(points, width: float) -> CS:
    """A line through `points`, `width` wide, with round ends."""
    out = None
    for (x0, y0), (x1, y1) in zip(points[:-1], points[1:]):
        seg = CS.batch_hull([CS.circle(width / 2, 24).translate([x0, y0]), CS.circle(width / 2, 24).translate([x1, y1])])
        out = seg if out is None else out + seg
    return out


def arc(cx, cy, r, a0, a1, width, n=24) -> CS:
    t = np.radians(np.linspace(a0, a1, n))
    return stroke(list(zip(cx + r * np.cos(t), cy + r * np.sin(t))), width)


def paw(w: float) -> CS:
    """A paw print with a heart for its pad (hers had a heart in the pad)."""
    s = w / 16.0
    pad = heart(10.0 * s, stretch=1.0).translate([0, -2.6 * s])
    toes = [ellipse(-6.2 * s, 4.0 * s, 2.0 * s, 2.6 * s, 25), ellipse(-2.3 * s, 7.3 * s, 2.1 * s, 2.7 * s, 8),
            ellipse(2.3 * s, 7.3 * s, 2.1 * s, 2.7 * s, -8), ellipse(6.2 * s, 4.0 * s, 2.0 * s, 2.6 * s, -25)]
    out = pad
    for t in toes:
        out = out + t
    return out


def bread_cat(w: float) -> tuple[CS, CS]:
    """A cat shaped like a slice of bread (puffy top, ears), and its face and crust line (drawn as gaps)."""
    s = w / 28.0
    body = (CS.square([24 * s, 15 * s]).translate([-12 * s, -11 * s])
            + CS.circle(7.6 * s, SEG).translate([-6.2 * s, 2.4 * s]) + CS.circle(7.6 * s, SEG).translate([6.2 * s, 2.4 * s])
            + CS.square([12.4 * s, 7.6 * s]).translate([-6.2 * s, 2.4 * s]))
    ears = [poly([(-11.5 * s, 4.5 * s), (-10.0 * s, 13.5 * s), (-4.5 * s, 9.0 * s)]),
            poly([(11.5 * s, 4.5 * s), (4.5 * s, 9.0 * s), (10.0 * s, 13.5 * s)])]
    body = smooth(body + ears[0] + ears[1], 0.8 * s)
    lw = 0.8
    crust = body.offset(-2.0 * s, R, circular_segments=SEG)
    crust = crust - crust.offset(-lw, R, circular_segments=SEG)
    face = (arc(-4.6 * s, 0.2 * s, 1.8 * s, 20, 160, lw) + arc(4.6 * s, 0.2 * s, 1.8 * s, 20, 160, lw)   # happy closed eyes
            + stroke([(-1.1 * s, -2.4 * s), (0, -1.5 * s), (1.1 * s, -2.4 * s)], lw)                     # nose, her "^"
            + arc(-1.1 * s, -3.4 * s, 1.1 * s, 200, 340, lw) + arc(1.1 * s, -3.4 * s, 1.1 * s, 200, 340, lw)  # mouth
            + stroke([(-6.5 * s, -2.5 * s), (-10.0 * s, -1.6 * s)], lw) + stroke([(-6.5 * s, -4.2 * s), (-10.0 * s, -4.6 * s)], lw)
            + stroke([(6.5 * s, -2.5 * s), (10.0 * s, -1.6 * s)], lw) + stroke([(6.5 * s, -4.2 * s), (10.0 * s, -4.6 * s)], lw))
    return body, crust + face


def happy_star(Ro: float) -> tuple[CS, CS]:
    """Her star with a face and feet, and the face (gaps)."""
    st = star(Ro, 0.52, round_=1.2)
    py = -Ro * math.cos(math.radians(36))
    px = Ro * math.sin(math.radians(36))
    feet = ellipse(-px * 0.95, py - 0.6, 2.7, 2.0) + ellipse(px * 0.95, py - 0.6, 2.7, 2.0)     # under the two lower points
    lw = 0.8
    face = (CS.circle(1.1, 24).translate([-2.8, 1.6]) + CS.circle(1.1, 24).translate([2.8, 1.6])
            + arc(0, 0.2, 3.0, 210, 330, lw))
    return st + feet, face


def puppy_heart(w: float) -> tuple[CS, CS]:
    """A heart with floppy dog ears, and its face (cut in)."""
    s = w / 17.0
    hrt = heart(17 * s, stretch=1.05)
    ears = ellipse(-8.0 * s, 1.0 * s, 3.0 * s, 5.8 * s, -22) + ellipse(8.0 * s, 1.0 * s, 3.0 * s, 5.8 * s, 22)
    lw = 0.7
    face = (CS.circle(0.95 * s, 24).translate([-2.9 * s, 1.6 * s]) + CS.circle(0.95 * s, 24).translate([2.9 * s, 1.6 * s])
            + ellipse(0, -0.9 * s, 1.4 * s, 1.0 * s)
            + arc(-1.05 * s, -2.3 * s, 1.05 * s, 200, 340, lw) + arc(1.05 * s, -2.3 * s, 1.05 * s, 200, 340, lw))
    return smooth(hrt + ears, 0.4), face


def lattice_heart(w: float) -> CS:
    hrt = heart(w, stretch=1.1)
    ring = hrt - hrt.offset(-1.8, R, circular_segments=SEG)
    inside = hrt.offset(-1.0, R, circular_segments=SEG)
    lines = None
    for ang in (45, -45):
        for k in range(-8, 9):
            ln = CS.square([1.3, 3 * w]).translate([-0.65 + k * 5.4, -1.5 * w]).rotate(ang)
            lines = ln if lines is None else lines + ln
    return ring + (lines ^ inside)


def ice_cream() -> CS:
    """Scoop with drips on a cone; the seam runs just under the scoop (y = 0)."""
    scoop = (CS.circle(7.2, SEG).translate([0, 6.4]) + CS.square([14.4, 6.4]).translate([-7.2, 0.6])
             + CS.circle(2.4, 32).translate([-4.8, 0.6]) + CS.circle(2.5, 32).translate([0, 0.1]) + CS.circle(2.4, 32).translate([4.8, 0.6]))
    cone = poly([(-6.3, 0.0), (6.3, 0.0), (0.0, -17.0)])
    return smooth(scoop + smooth(cone, 0.9), 0.4)


# ---------- the box ----------

class TreasureBox:
    def __init__(self, p: dict):
        self.p = p
        self.a = p["W"] / 2
        self.axis = (p["D"] + p["k_r"] + 0.5, p["Hb"] + p["k_r"])

    def footprint(self, inset=0.0) -> CS:
        p = self.p
        return rounded_rect(-self.a + inset, self.a - inset, inset, p["D"] - inset, max(0.5, p["corner"] - inset))

    def lock_center(self) -> float:
        return self.p["Hb"]       # the ice cream's seam line sits on the box/lid seam

    def lock_pocket(self) -> M:
        p = self.p
        ic = ice_cream().offset(p["fit"], R, circular_segments=SEG).translate([0, self.lock_center()])
        return prism_xz(ic, -1.0, p["plug"])

    def base(self) -> M:
        p = self.p
        a, D, H, t = self.a, p["D"], p["Hb"], p["wall"]
        body = prism_xy(self.footprint(), 0.8, H)
        for i in range(4):                          # 0.8 mm chamfer at the bottom edge (no elephant foot)
            body = body + prism_xy(self.footprint(0.8 - 0.2 * i), 0.2 * i, 0.2 * (i + 1))
        body = body - prism_xy(self.footprint(t), p["floor"], H + 1)
        # Boss inside the front wall behind the cone of the lock, its underside at 45 degrees.
        bz = H - 21.0
        boss = poly([(t - 0.2, bz - 5.0), (t + 5.0, bz), (t + 5.0, H), (t - 0.2, H)])
        body = body + prism_yz(boss, -9.0, 9.0)
        # Her lower pictures: puppy hearts left and right, a lattice heart in the middle, stars at the bottom.
        pics, faces = [], []
        for x, z in ((-31.0, 41.0), (31.0, 41.0)):
            pup, face = puppy_heart(19.0)
            pics.append(pup.translate([x, z]))
            faces.append(face.translate([x, z]))
        pics.append(lattice_heart(30.0).translate([0, 23.5]))
        for x, z, rot in ((-31.0, 15.0, -8.0), (31.0, 15.0, 8.0)):
            pics.append(star(9.0, 0.5, rot).translate([x, z]))
        body = body + self.relief(pics, faces)
        body = body - self.lock_pocket()
        body = body + self.knuckles("base")
        body = body - self.pin_holes("base")
        if p["rail"] > 0:
            r = p["rail"]
            rail = prism_yz(poly([(D - 1.0, 0.0), (D + r, 0.0), (D + r, 3.0), (D - 1.0, r + 4.0)]), -a, a)
            body = body + (rail ^ prism_xy(rounded_rect(-a, a, 0.0, D + r, p["corner"]), -1, 30))
        return body

    def relief(self, pics: list[CS], faces: list[CS]) -> M:
        p = self.p
        raised = None
        for c in pics:
            raised = c if raised is None else raised + c
        solid = prism_xz(raised, -p["relief"], 0.3)
        if faces:
            cut = None
            for f in faces:
                cut = f if cut is None else cut + f
            solid = solid - prism_xz(cut, -p["relief"] - 1.0, -p["relief"] + p["engrave"])
        return solid

    def lid_parts(self) -> dict:
        """The lid closed on the box (box coordinates): {"lid": body, "<color>": inlay, ...}."""
        p = self.p
        H, Hl, D, t, c = p["Hb"], p["Hl"], p["D"], p["wall"], p["chamfer"]
        top = H + Hl
        body = prism_xy(self.footprint(), H, top - c)
        n = 8
        for i in range(n):                                     # 45-degree chamfer round the top edge
            body = body + prism_xy(self.footprint(c * (i + 1) / n), top - c + c * i / n, top - c + c * (i + 1) / n)
        body = body - prism_xy(self.footprint(t), H - 1, top - p["top"])
        # Boss inside the front wall behind the scoop: its top slopes at 45 degrees (prints either way up).
        hs = 15.5
        boss = poly([(t - 0.2, H), (t + 5.0, H), (t + 5.0, H + hs), (t - 0.2, H + hs + 5.2)])
        body = body + prism_yz(boss, -10.0, 10.0)
        # Little paw prints walking across the lid's front toward the lock.
        pics = []
        for side in (-1, 1):
            for k, (x, z) in enumerate(((36.0, 10.5), (22.0, 20.5))):
                pics.append(paw(11.5).rotate(side * 14.0).translate([side * x, H + z]))
        body = body + self.relief(pics, [])
        body = body - self.lock_pocket()
        raised = p["top_style"] == "raised"
        if raised:
            # The lid prints right side up, so its flat top is bridged: two thin dividers (two lines of plastic) from
            # the rim to the top keep each bridge about 31 mm (Allen chose these over supports, 2026-11-22).
            for x in p["ribs"]:
                body = body + box(x - p["rib_t"] / 2, x + p["rib_t"] / 2, t - 0.2, D - t + 0.2, H, top - p["top"] + 0.2)
            body = body - self.lock_pocket()        # the middle divider runs past the ice cream's pocket
        body = body + self.knuckles("lid")
        body = body - self.pin_holes("lid")
        # Her lid pictures on top: bread cat, two paw prints, the star with a face and feet.
        cat, cat_face = bread_cat(29.0)
        st, st_face = happy_star(14.5)
        y0 = D / 2 + 1.0
        paws = paw(15.0).rotate(12).translate([-4.0, y0 - 9.0]) + paw(15.0).rotate(-8).translate([6.0, y0 + 10.0])
        layout = {
            "bread-cat": (cat.translate([-28.5, y0]), cat_face.translate([-28.5, y0])),
            "paw-prints": (paws, None),
            "star": (st.translate([29.0, y0 + 1.0]), st_face.translate([29.0, y0 + 1.0])),
        }
        flat = self.footprint(c + 1.0)
        parts = {}
        for name, (shape, lines) in layout.items():
            assert (shape - flat).area() < 1e-3, f"{name} runs off the lid's flat top"
            if raised:
                # Raised like the front pictures; faces, whiskers and the crust line cut into them.
                pic = prism_xy(shape, top - 0.3, top + p["relief"])
                if lines is not None:
                    pic = pic - prism_xy(lines, top + p["relief"] - p["engrave"], top + p["relief"] + 1)
                parts[name] = pic - body
            else:
                inl = prism_xy(shape - lines if lines is not None else shape, top - p["inlay"], top)
                parts[name] = inl
                body = body - inl
        return {"lid": body, **parts}

    def knuckles(self, which: str) -> M:
        p = self.p
        ya, za = self.axis
        D, H, r = p["D"], p["Hb"], p["k_r"]
        circle = CS.circle(r, SEG).translate([ya, za])
        dot = lambda y, z: CS.square([0.01, 0.01]).translate([y, z])
        if which == "base":
            shelf = za + p["stop_shelf"]        # the open lid's back comes down on this
            prof = CS.batch_hull([circle, dot(D + 0.5, H - 9.0), dot(D + 0.5, H), dot(ya + 7.0, shelf - 0.01), dot(ya + 7.0, shelf - 0.6)])
            prof = prof + CS.square([1.6, 9.0]).translate([D - 1.1, H - 9.0])
        elif p["top_style"] == "raised":
            # The lid prints right side up: the knuckle stands on the plate with a flat bottom.
            prof = CS.batch_hull([circle, dot(D - 0.5, H), dot(ya + r, H), dot(D - 0.5, za + r + 2.0)])
        else:
            # The lid prints upside down, so its knuckle's slope (toward the lid's top) must be 45 degrees or steeper.
            prof = CS.batch_hull([circle, dot(D - 0.5, H), dot(D - 0.5, H + 2 * r + 8.0)])
        out = None
        for xc in (-p["hinge_x"], p["hinge_x"]):
            w, g = p["k_w"], p["k_gap"]
            spans = ([(xc - 1.5 * w - g, xc - 0.5 * w - g), (xc + 0.5 * w + g, xc + 1.5 * w + g)] if which == "base"
                     else [(xc - 0.5 * w, xc + 0.5 * w)])
            for x0, x1 in spans:
                k = prism_yz(prof, x0, x1)
                out = k if out is None else out + k
        return out

    def pin_holes(self, which: str) -> M:
        """Teardrop holes, the point up as each part prints (the lid prints upside down), blind at the outer end."""
        p = self.p
        ya, za = self.axis
        rr = p["pin_d"] / 2
        upside_down = which == "lid" and p["top_style"] != "raised"
        tip = rr * math.sqrt(2) * (-1 if upside_down else 1)
        drop = CS.batch_hull([CS.circle(rr, 32), CS.square([0.01, 0.01]).translate([-0.005, tip])]).translate([ya, za])
        w, g = p["k_w"], p["k_gap"]
        out = None
        for side in (-1, 1):
            xc = side * p["hinge_x"]
            inner = xc - side * (1.5 * w + g)
            outer = xc + side * (1.5 * w + g - 1.5)
            x0, x1 = sorted((inner - side * 1.0, outer))
            h = prism_yz(drop, x0, x1)
            out = h if out is None else out + h
        return out

    def gem(self, slack: float = 0.0) -> M:
        """The ice cream, printed standing on its back: plug, a lip that stops at the wall, a round scoop with a
        cherry, and a waffle cone."""
        p = self.p
        ic = ice_cream()
        body = ic.offset(-slack, R, circular_segments=SEG) if slack else ic
        plug = body.offset(-0.3, R).extrude(0.4) + body.extrude(p["plug"] - 0.4).translate([0, 0, 0.4])
        lip = ic.offset(1.0, R, circular_segments=SEG).extrude(0.8).translate([0, 0, p["plug"]])
        z0 = p["plug"] + 0.8
        scoop = (ic ^ CS.square([40, 40]).translate([-20, -2.6])).offset(0.6, R, circular_segments=SEG)
        dome = None
        n, hd = 8, 3.0
        for i in range(n):
            u = (i + 1) / n
            inset = 7.0 * (1 - math.sqrt(1 - u * u)) * 0.9
            layer = scoop.offset(-inset, R, circular_segments=SEG).extrude(hd / n).translate([0, 0, z0 + hd * i / n])
            dome = layer if dome is None else dome + layer
        cherry = M.sphere(2.2, 32).translate([0, 11.4, z0 + hd - 0.6])
        cherry = cherry ^ box(-5, 5, 5, 20, z0, z0 + 20)
        cone = (ic ^ CS.square([40, 40]).translate([-20, -40 + -2.4])).offset(0.6, R, circular_segments=SEG)
        cone_top = cone.extrude(1.4).translate([0, 0, z0])
        grid = None
        for ang in (50, -50):
            for k in range(-6, 7):
                ln = CS.square([0.6, 60]).translate([-0.3 + k * 2.8, -30]).rotate(ang)
                grid = ln if grid is None else grid + ln
        cone_top = cone_top - prism_xy(grid ^ cone, z0 + 0.8, z0 + 2.0)
        return plug + lip + dome + cherry + cone_top

    def lid_opened(self, lid: M, deg: float) -> M:
        ya, za = self.axis
        return lid.translate([0, -ya, -za]).rotate([-deg, 0, 0]).translate([0, ya, za])


def printed_volume(s: M) -> float:
    """Roughly what Bambu Studio prints: 2 mm of walls all round, 15% infill inside."""
    shell = min(s.volume(), s.surface_area() * 2.0)
    return shell + 0.15 * (s.volume() - shell)


def main() -> None:
    ap = argparse.ArgumentParser(description="Treasure box from the second drawing")
    ap.add_argument("--out", default=str(ROOT / "output" / "treasure-box-2"))
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    p = dict(P)
    tb = TreasureBox(p)
    base = drop_specks(tb.base())
    lid_parts = {k: drop_specks(v) for k, v in tb.lid_parts().items()}
    lid = M.batch_boolean(list(lid_parts.values()), m3d.OpType.Add)
    gem, gem2 = drop_specks(tb.gem()), drop_specks(tb.gem(slack=0.1))
    for name, s in [("base", base), ("gem", gem)] + list(lid_parts.items()):
        assert s.status() == m3d.Error.NoError, name
    assert len(base.decompose()) == 1 and len(lid_parts["lid"].decompose()) == 1 and len(gem.decompose()) == 1
    if (lid ^ base).volume() > 0.5:
        print("PROBLEM: lid and base overlap when closed")
    stop = 180
    for deg in range(2, 182, 2):
        if (tb.lid_opened(lid, deg) ^ base).volume() > 0.5:
            stop = deg
            break
    opened = tb.lid_opened(lid, stop)
    wb, wl = printed_volume(base), printed_volume(lid)
    cy = (centroid(base)[1] * wb + centroid(opened)[1] * wl) / (wb + wl)
    tip = p["D"] + p["rail"] - cy
    lock = gem.rotate([90, 0, 0]).translate([0, p["plug"], tb.lock_center()])
    touch = (lock ^ base).volume() + (lock ^ lid).volume()
    print(f"box {p['W']:.0f} x {p['D']:.0f} x {p['Hb'] + p['Hl']:.0f} mm; lid opens to about {stop} degrees; "
          f"open, the balance point is {tip:.0f} mm inside the back edge; gem touches the pocket: {touch:.3f} mm3")
    print(f"printed plastic, roughly: box {wb / 1000:.0f} cm3, lid {wl / 1000:.0f} cm3")
    if tip < 5:
        print("PROBLEM: the open box could tip backward")
    write_files(tb, base, lid_parts, gem, gem2, stop, out)


PLATE1_COLOR = """## Plate 1: `treasure-box.3mf` (the box and the lid)

- The lid prints **upside down** beside the box (its top on the plate), as placed. Don't press **Arrange**.
- Colors: slot 1 the box color (the box and the lid; purple in the pictures), slot 2 tan (bread cat), slot 3 pink
  (paw prints), slot 4 yellow (star). Change any of them in Bambu Studio. The colors are only in the first 3 layers
  (the lid's top), so there are just a few color changes; the rest prints in one color.
- Layer height **0.20 mm**, supports **off**. Smooth plate gives a shiny lid top; textured gives a matte one.
- Use **Arachne** walls (Quality tab, **Wall generator**), as for the flat charms: the faces on the lid top are
  thin lines.
- This lid is a thin tray, so it prints much faster than the first chest's domed lid (that lid was mostly solid
  plastic inside). Bambu Studio shows the real time after **Slice plate**.

"""

PLATE1_RAISED = """## Plate 1: `treasure-box.3mf` (the box and the lid)

- One filament for everything (purple in the pictures). The lid prints right side up beside the box, as placed.
  Don't press **Arrange**.
- The pictures on the lid are raised like the ones on the front, with the faces cut in. They are separate parts
  (`bread-cat`, `paw-prints`, `star`) set to the same filament; to color them later, pick another filament for
  them in Bambu Studio (a few color changes on the top layers only).
- Inside the lid, two thin dividers hold up its top while it prints (3 cm bridges instead of one 7 cm one), so
  no supports are needed.
- Layer height **0.20 mm**, supports **off**.
- The lid is a thin tray, so it prints much faster than the first chest's domed lid (that lid was mostly solid
  plastic inside). Bambu Studio shows the real time after **Slice plate**.

"""


def write_files(tb: TreasureBox, base: M, lid_parts: dict, gem: M, gem2: M, stop: float, out: Path) -> None:
    from charm_maker.bambu3mf import write_bambu_3mf
    from charm_maker.preview import render_shaded

    p = tb.p
    BOX, TAN, PINK, YELLOW, GEM = (150, 118, 205), (224, 178, 118), (240, 120, 165), (250, 205, 50), (245, 150, 185)
    raised = p["top_style"] == "raised"
    colors = {"lid": BOX, "bread-cat": TAN, "paw-prints": PINK, "star": YELLOW}
    slots = {"lid": 1, "bread-cat": 2, "paw-prints": 3, "star": 4}
    if raised:                     # one filament; the pictures stay separate parts in case she wants them colored
        colors = {k: BOX for k in colors}
        slots = {k: 1 for k in slots}
    # Plate 1: the box upright, the lid upside down beside it.
    bb = base.bounding_box()
    flip = p["top_style"] != "raised"           # colored top: the lid prints upside down; raised: right side up
    flipped = {k: (v.rotate([180, 0, 0]) if flip else v) for k, v in lid_parts.items()}
    lb = M.batch_boolean(list(flipped.values()), m3d.OpType.Add).bounding_box()
    flipped = {k: v.translate([0, 0, -lb[2]]) for k, v in flipped.items()}
    gap = 12.0
    depth = (bb[4] - bb[1]) + gap + (lb[4] - lb[1])
    y0 = 128 - depth / 2
    base_on = base.translate([128, y0 - bb[1], 0])
    lid_on = {k: v.translate([128, y0 + (bb[4] - bb[1]) + gap - lb[1], 0]) for k, v in flipped.items()}
    write_bambu_3mf([("box", [("box", base_on, 1, BOX)]),
                     ("lid", [(k, v, slots[k], colors[k]) for k, v in lid_on.items()])],
                    out / "treasure-box.3mf", plate_name="treasure-box")
    g = gem.bounding_box()
    gw = g[3] - g[0]
    write_bambu_3mf([("ice-cream", [("ice-cream", gem.translate([128 - gw * 0.8 - (g[0] + g[3]) / 2, 128, 0]), 1, GEM)]),
                     ("ice-cream-looser", [("ice-cream-looser", gem2.translate([128 + gw * 0.8 - (g[0] + g[3]) / 2, 128, 0]), 1, GEM)])],
                    out / "treasure-box-ice-cream.3mf", plate_name="treasure-box-ice-cream")
    # Pictures.
    lock = gem.rotate([90, 0, 0]).translate([0, p["plug"], tb.lock_center()])
    scene = {"box": base, **lid_parts, "gem": lock}
    cols = {"box": BOX, **colors, "gem": GEM}
    render_shaded(scene, out / "box-closed.png", view=(24.0, -28.0), px_per_mm=6.0, labels=False, colors=cols)
    render_shaded(scene, out / "box-front.png", view=(8.0, -10.0), px_per_mm=6.0, labels=False, colors=cols)
    render_shaded({k: v for k, v in lid_parts.items()}, out / "lid-top.png", view=(45.0 if raised else 88.0, -20.0 if raised else 0.0),
                  px_per_mm=6.0, labels=False,
                  colors=colors)
    opened = {k: tb.lid_opened(v, min(stop - 4, 100)) for k, v in lid_parts.items()}
    render_shaded({"box": base, **opened}, out / "box-open.png", view=(30.0, -30.0), px_per_mm=5.0, labels=False,
                  colors={"box": BOX, **colors})
    render_shaded({"gem": gem.rotate([90, 0, 0])}, out / "ice-cream.png", view=(15.0, -20.0), px_per_mm=12.0, labels=False,
                  colors={"gem": GEM})
    w, g_ = p["k_w"], p["k_gap"]
    pin = 3 * w + 2 * g_ - 1.5
    inside = (p["W"] - 2 * p["wall"]) * (p["D"] - 2 * p["wall"]) * (p["Hb"] - p["floor"]) / 1000
    plate1 = PLATE1_RAISED if raised else PLATE1_COLOR
    (out / "PRINT_NOTES.md").write_text(f"""# Treasure box (the second one): print notes

Her pictures: the bread cat, two paw prints and the star with a face and feet on the lid; puppy hearts,
a lattice heart and stars on the front; little paw prints on the lid's front; the ice cream is the lock.

Size: {p['W']:.0f} mm wide, {p['D']:.0f} mm deep, {p['Hb'] + p['Hl']:.0f} mm tall. The box holds about {inside:.0f} ml.

{plate1}## Plate 2: `treasure-box-ice-cream.3mf` (the ice cream lock)

- One filament (pink in the pictures), layer height 0.12 mm, supports off. About 15 minutes.
- `ice-cream` fits snug, `ice-cream-looser` is 0.1 mm smaller all around. Try the snug one first. If the heart
  gems on the first chest fit well, the snug ice cream will too (same gap).

## Putting it together

1. Hinge pins: cut two pieces of 1.75 mm filament, about {pin:.0f} mm each.
2. Close the lid. At the back, push one into each hinge from the middle toward the side until it stops, trim it
   flush and add a drop of glue on the open end.
3. The lid opens to about {stop:.0f} degrees and stays open.
4. Lock: close the lid and push the ice cream into its shape on the front (scoop on the lid, cone on the box).
""")


if __name__ == "__main__":
    main()
