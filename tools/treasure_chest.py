"""A treasure chest from Allen's daughter's own design (2026-11-17): "a 3-D printed treasure chest that she can
put stuff in ... actually 3-D and functional". Her drawing (the front of the chest), labels in her words:

- C, "a base that looks like it's made of wood": the box, with her diagonal wood grain cut into the walls.
- "A taller part that looks like wood plank with round holes": two raised planks up the front, round holes.
- D, "just like C but a top": the lid, wood too, domed like her drawing (round corners, a higher middle),
  with the planks carried over the top (her little strips with dots on the lid's top edge).
- A, "a shorter part that can hold B": a short plate at the front middle, where lid and base meet, with a
  heart-shaped hole across the seam (her notch).
- B, "heart gem that can fit in A": a separate gem. Pushed into A it locks the lid; when the chest is open it
  sits in a heart setting on top of the lid, where she drew it.

The lid opens on a hinge at the back: printed knuckles, with a short piece of 1.75 mm filament as the pin.
Everything prints with no supports: the base upright, the lid rim-down beside it (solid, with infill), the
gems flat on their backs (a separate plate, so the gem can be another color without a color change on every
layer of the chest).

    python tools/treasure_chest.py [--out output/treasure-chest] [--width 120]
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

M, CS = m3d.Manifold, m3d.CrossSection

# Sizes in mm at the default 120 mm width (her drawing's proportions: base 0.56 of the width tall, lid 0.22
# at the sides and 0.37 in the middle). Everything else is fixed for strength and fit.
P = dict(
    W=120.0, D=80.0, H=66.0,      # base outside: width, depth, height
    h0=25.0, ha=44.0, sf=0.53,    # lid: height at the sides, at the very top, and the front edge's share of the dome
    wall=2.4, corner=3.0,         # base wall, rounded upright corners (top view)
    foot_r=6.0,                   # rounded bottom corners (front view), cut at 45 degrees underneath
    plank_x=32.0, plank_w=11.0, plank_t=1.2, plank_holes=7, hole_d=2.4, hole_depth=0.9,
    groove_w=0.8, groove_depth=0.6,
    heart_w=15.0, fit=0.10, stop_shelf=4.0, rail=8.0,       # gem width; gap around it in its pockets (the keycap socket's tested 0.10 mm)
    plug=4.0,                     # how deep the gem goes in
    plate_w=24.0, plate_t=1.6,    # the lock plate A
    k_r=4.0, k_w=6.0, k_gap=0.4, pin_d=2.2,   # hinge knuckles; the pin is 1.75 mm filament in a 2.2 mm hole
)

SEG = 72


# ---------- small builders ----------

def prism_xz(cs: CS, y0: float, y1: float) -> M:
    """A cross-section drawn in (x, z), pushed back from y0 to y1."""
    return cs.extrude(y1 - y0).rotate([90, 0, 0]).translate([0, y1, 0])


def prism_yz(cs: CS, x0: float, x1: float) -> M:
    """A cross-section drawn in (y, z), pushed sideways from x0 to x1."""
    return cs.extrude(x1 - x0).rotate([90, 0, 90]).translate([x0, 0, 0])


def prism_xy(cs: CS, z0: float, z1: float) -> M:
    return cs.extrude(z1 - z0).translate([0, 0, z0])


def box(x0, x1, y0, y1, z0, z1) -> M:
    return M.cube([x1 - x0, y1 - y0, z1 - z0]).translate([x0, y0, z0])


def rounded_rect(x0, x1, y0, y1, r) -> CS:
    return CS.square([x1 - x0 - 2 * r, y1 - y0 - 2 * r]).translate([x0 + r, y0 + r]).offset(r, m3d.JoinType.Round,
                                                                                             circular_segments=SEG)


def heightfield(xs: np.ndarray, ys: np.ndarray, ztop, z0: float = 0.0) -> M:
    """A closed solid from z0 up to ztop(x, y) over the grid xs by ys."""
    nx, ny = len(xs), len(ys)
    X, Y = np.meshgrid(xs, ys, indexing="ij")
    Z = np.maximum(ztop(X, Y), z0 + 0.05)
    top = np.stack([X, Y, Z], -1).reshape(-1, 3)
    bot = np.stack([X, Y, np.full_like(X, z0)], -1).reshape(-1, 3)
    verts = np.concatenate([top, bot])
    t = lambda i, j: i * ny + j
    b = lambda i, j: nx * ny + i * ny + j
    tris = []
    for i in range(nx - 1):
        for j in range(ny - 1):
            tris += [[t(i, j), t(i + 1, j), t(i + 1, j + 1)], [t(i, j), t(i + 1, j + 1), t(i, j + 1)]]
            tris += [[b(i, j), b(i + 1, j + 1), b(i + 1, j)], [b(i, j), b(i, j + 1), b(i + 1, j + 1)]]
    for i in range(nx - 1):                              # front (j = 0) and back (j = ny - 1)
        for j, sgn in ((0, 1), (ny - 1, -1)):
            q = [b(i, j), b(i + 1, j), t(i + 1, j), t(i, j)]
            tris += ([[q[0], q[1], q[2]], [q[0], q[2], q[3]]] if sgn > 0 else [[q[0], q[2], q[1]], [q[0], q[3], q[2]]])
    for j in range(ny - 1):                              # left (i = 0) and right (i = nx - 1)
        for i, sgn in ((0, 1), (nx - 1, -1)):
            q = [b(i, j), b(i, j + 1), t(i, j + 1), t(i, j)]
            tris += ([[q[0], q[2], q[1]], [q[0], q[3], q[2]]] if sgn > 0 else [[q[0], q[1], q[2]], [q[0], q[2], q[3]]])
    mesh = m3d.Mesh(vert_properties=verts.astype(np.float32), tri_verts=np.array(tris, np.uint32))
    out = M(mesh)
    if out.status() != m3d.Error.NoError or out.volume() <= 0:
        raise RuntimeError(f"heightfield is not a closed solid: {out.status()}")
    return out


def heart(width: float, stretch: float = 1.4) -> CS:
    """A heart, tip down, centered on its bounding box's middle; `width` across the lobes. Hers is drawn
    tall, so it is stretched upward."""
    t = np.linspace(0, 2 * math.pi, 240, endpoint=False)
    x = 16 * np.sin(t) ** 3
    y = 13 * np.cos(t) - 5 * np.cos(2 * t) - 2 * np.cos(3 * t) - np.cos(4 * t)
    k = width / (x.max() - x.min())
    x, y = x * k, y * k * stretch
    y -= (y.max() + y.min()) / 2
    return CS([np.stack([x, y], 1)[::-1]]).simplify(0.01)       # counterclockwise


def heart_height(width: float) -> float:
    b = heart(width).bounds()
    return b[3] - b[1]


def wavy_lines(origin, direction_deg, spacing, count, length, amp, wavelength, width, seed=1) -> CS:
    """Wood grain: `count` gently wavy grooves across a face, as one cross-section."""
    rng = np.random.default_rng(seed)
    d = np.array([math.cos(math.radians(direction_deg)), math.sin(math.radians(direction_deg))])
    n = np.array([-d[1], d[0]])
    polys = []
    for k in range(count):
        base = np.asarray(origin, float) + n * (k - (count - 1) / 2) * spacing + n * rng.uniform(-0.2, 0.2) * spacing
        s = np.linspace(-length / 2, length / 2, 160)
        ph = rng.uniform(0, 2 * math.pi)
        a = amp * rng.uniform(0.6, 1.3)
        wave = a * np.sin(2 * math.pi * s / wavelength + ph) + 0.4 * a * np.sin(2 * math.pi * s / (wavelength * 0.37) + 2 * ph)
        c = base + np.outer(s, d) + np.outer(wave, n)
        polys.append(np.concatenate([c + n * width / 2, (c - n * width / 2)[::-1]]))
    return CS(polys, m3d.FillRule.NonZero)


def knot(cx, cy, rx, ry, width) -> CS:
    outer = CS.circle(1.0, SEG).scale([rx, ry]).translate([cx, cy])
    return outer - CS.circle(1.0, SEG).scale([rx - width, ry - width]).translate([cx, cy])


# ---------- the chest ----------

class Chest:
    def __init__(self, p: dict):
        self.p = p
        W, D = p["W"], p["D"]
        self.a = W / 2
        self.axis = (D + p["k_r"] + 0.5, p["H"] + p["k_r"])      # hinge axis (y, z), along x

    # lid top surface, lid frame (z = 0 at the seam)
    def lid_z(self, x, y):
        p = self.p
        e = np.sqrt(np.clip(1 - (x / self.a) ** 2, 0, 1))
        u = (2 * y - p["D"]) / p["D"]
        s = np.sqrt(np.clip(1 - (1 - p["sf"] ** 2) * u ** 2, 0, 1))
        return p["h0"] + (p["ha"] - p["h0"]) * e * s

    def heart_center_z(self) -> float:
        """The lock heart's middle, in base coordinates: its top 40% (the lobes) is in the lid."""
        hh = heart_height(self.p["heart_w"])
        return self.p["H"] + 0.40 * hh - hh / 2

    def footprint(self, inset=0.0) -> CS:
        p = self.p
        return rounded_rect(-self.a + inset, self.a - inset, inset, p["D"] - inset, max(0.5, p["corner"] - inset))

    def base_profile(self, top: float) -> CS:
        """Front view of the base: square top corners, rounded bottom corners cut at 45 degrees underneath."""
        a, r = self.a, self.p["foot_r"]
        pts = []
        for side in (-1, 1):
            cx, cz = side * (a - r), r
            arc = [(cx + side * r * math.cos(math.radians(t)), cz - r * math.sin(math.radians(t)))
                   for t in np.linspace(0, 45, 10)]
            ex, ez = arc[-1]
            foot = (ex - side * ez, 0.0)                      # 45 degrees down to the bed
            pts.append(arc + [foot])
        left, right = pts
        poly = [(-a, top)] + left + right[::-1] + [(a, top)]
        return CS([np.array(poly)], m3d.FillRule.NonZero)

    def base(self) -> M:
        p = self.p
        a, D, H, t = self.a, p["D"], p["H"], p["wall"]
        outer = prism_xz(self.base_profile(H), -1, D + 1) ^ prism_xy(self.footprint(), -1, H + 1)
        # Cavity: the outside shrunk by the wall, open at the top.
        cav_prof = self.base_profile(H + 20).offset(-t, m3d.JoinType.Round, circular_segments=SEG)
        cavity = prism_xz(cav_prof, -1, D + 1) ^ prism_xy(self.footprint(t), -1, H + 10)
        body = outer - cavity
        body = body - self.grain_base(outer)
        # Boss behind the lock, inside the front wall, its underside at 45 degrees.
        hz = self.heart_center_z()
        hh = heart_height(p["heart_w"])
        bz0 = hz - hh / 2 - 3
        boss_prof = CS([np.array([(t - 0.2, bz0 - 5.0), (t + 5.0, bz0), (t + 5.0, H), (t - 0.2, H)])])
        body = body + (prism_yz(boss_prof, -p["plate_w"] / 2, p["plate_w"] / 2))
        # Planks up the front, with round holes.
        for xc in (-p["plank_x"], p["plank_x"]):
            plank = box(xc - p["plank_w"] / 2, xc + p["plank_w"] / 2, -p["plank_t"], 0.2, 0, H)
            plank = plank ^ prism_xz(self.base_profile(H), -5, 5)       # follows the rounded feet
            body = body + plank
            for k in range(p["plank_holes"]):
                z = 7 + k * (H - 14) / (p["plank_holes"] - 1)
                hole = M.cylinder(p["hole_depth"] + 1, p["hole_d"] / 2, circular_segments=32).rotate([-90, 0, 0])
                body = body - hole.translate([xc, -p["plank_t"] - 1, z])
        # Lock plate A (the short plank), then the heart hole across the seam.
        plate = box(-p["plate_w"] / 2, p["plate_w"] / 2, -p["plate_t"], 0.2, bz0 - 2, H)
        body = body + plate
        body = body - self.lock_pocket()
        body = body + self.knuckles("base")
        body = body - self.pin_holes()
        # A low foot along the back of the bottom: the open lid sits behind the hinge, so this keeps the chest
        # from tipping backward. Only seen from behind; its top slopes at 45 degrees.
        r = p["rail"]
        rail = prism_yz(CS([np.array([(D - 1.0, 0.0), (D + r, 0.0), (D + r, 3.0), (D - 1.0, r + 4.0)])]), -a, a)
        body = body + (rail ^ prism_xy(rounded_rect(-a, a, 0.0, D + r, p["corner"]), -1, 30))
        return body

    def lock_pocket(self) -> M:
        """The heart hole for the gem across the seam (base coordinates), plug deep from the plate's face."""
        p = self.p
        h = heart(p["heart_w"]).offset(p["fit"], m3d.JoinType.Round, circular_segments=SEG)
        y0 = -p["plate_t"]
        return prism_xz(h.translate([0, self.heart_center_z()]), y0 - 1, y0 + p["plug"])

    def lid(self) -> M:
        """The lid in base coordinates (sitting closed on the base)."""
        p = self.p
        a, D, H = self.a, p["D"], p["H"]
        xs = a * np.sin(np.linspace(-math.pi / 2, math.pi / 2, 161))
        ys = np.linspace(0, D, 81)
        body = heightfield(xs, ys, self.lid_z) ^ prism_xy(self.footprint(), -1, 100)
        body = body - self.grain_lid(body, xs, ys)
        # Planks over the top (her strips with dots on the lid's top edge).
        for xc in (-p["plank_x"], p["plank_x"]):
            x0, x1 = xc - p["plank_w"] / 2, xc + p["plank_w"] / 2
            bx = np.linspace(x0, x1, 12)
            strap = heightfield(bx, ys, lambda X, Y: self.lid_z(X, Y) + p["plank_t"])
            body = body + strap
            for y in np.arange(6.0, D - 5.0, 9.0):
                zt = float(self.lid_z(np.array(xc), np.array(y))) + p["plank_t"]
                hole = M.cylinder(p["hole_depth"] + 2, p["hole_d"] / 2, circular_segments=32)
                body = body - hole.translate([xc, y, zt - p["hole_depth"]])
        body = body - self.lid_cavity(xs, ys)      # after the planks, so they stay on the outside
        # The upper part of lock plate A, on the lid's front.
        hz = self.heart_center_z() - H
        hh = heart_height(p["heart_w"])
        body = body + box(-p["plate_w"] / 2, p["plate_w"] / 2, -p["plate_t"], 0.2, 0, hz + hh / 2 + 3)
        body = body.translate([0, 0, H])
        body = body - self.lock_pocket()
        # B's setting on top, at the front middle, where she drew it.
        body = body + self.setting()
        body = body - self.setting_pocket()
        body = body + self.knuckles("lid")
        body = body - self.pin_holes()
        return body

    def lid_cavity(self, xs, ys) -> M:
        """The lid's inside: open at the bottom, a roof of 45-degree slopes from each wall, and at least the wall
        thickness under the dome everywhere; solid behind the lock."""
        p = self.p
        a, D, t = self.a, p["D"], p["wall"]
        tent = lambda X, Y: np.minimum(np.minimum(Y - t, D - t - Y), np.minimum(X + a - t, a - t - X))
        roof = lambda X, Y: np.minimum(tent(X, Y), self.lid_z(X, Y) - t - 3.0)
        cx = np.linspace(-a + t, a - t, 121)
        cy = np.linspace(t, D - t, 81)
        cav = heightfield(cx, cy, roof, z0=-1.0)
        hh = heart_height(p["heart_w"])
        keep = box(-p["plate_w"] / 2 - 2, p["plate_w"] / 2 + 2, -1, t + 5.0, -2, self.heart_center_z() - p["H"] + hh / 2 + 4)
        return cav - keep

    def setting_center_z(self) -> float:
        p = self.p
        front = float(self.lid_z(np.array(0.0), np.array(0.0)))
        hh = heart_height(p["heart_w"])
        rim = hh + 5.2
        return p["H"] + front - 4.0 + rim / 2    # the tip sinks into the lid's front edge, the lobes stand above

    def setting(self) -> M:
        p = self.p
        rim = heart(p["heart_w"]).offset(2.6, m3d.JoinType.Round, circular_segments=SEG)
        return prism_xz(rim.translate([0, self.setting_center_z()]), 0.0, p["plug"] + 3.0)

    def setting_pocket(self) -> M:
        p = self.p
        h = heart(p["heart_w"]).offset(p["fit"], m3d.JoinType.Round, circular_segments=SEG)
        return prism_xz(h.translate([0, self.setting_center_z()]), -1.0, p["plug"])

    def knuckles(self, which: str) -> M:
        p = self.p
        ya, za = self.axis
        D, H, r = p["D"], p["H"], p["k_r"]
        circle = CS.circle(r, SEG).translate([ya, za])
        if which == "base":
            shelf = za + p["stop_shelf"]        # the open lid's back face comes down on this
            prof = CS.batch_hull([circle, CS.square([0.01, 0.01]).translate([D + 0.5, H - 9.0]),
                            CS.square([0.01, 0.01]).translate([D + 0.5, H]),
                            CS.square([0.01, 0.01]).translate([ya + 7.0, shelf - 0.01]),
                            CS.square([0.01, 0.01]).translate([ya + 7.0, shelf - 0.6])])
            prof = prof + CS.square([1.6, 9.0]).translate([D - 1.1, H - 9.0])
        else:
            prof = CS.batch_hull([circle, CS.square([0.01, 0.01]).translate([D - 0.5, H]),
                            CS.square([0.01, 0.01]).translate([D - 0.5, za + r + 2.0])])
        out = None
        for xc in (-p["plank_x"], p["plank_x"]):
            w, g = p["k_w"], p["k_gap"]
            spans = ([(xc - 1.5 * w - g, xc - 0.5 * w - g), (xc + 0.5 * w + g, xc + 1.5 * w + g)] if which == "base"
                     else [(xc - 0.5 * w, xc + 0.5 * w)])
            for x0, x1 in spans:
                k = prism_yz(prof, x0, x1)
                out = k if out is None else out + k
        return out

    def pin_holes(self) -> M:
        """Teardrop holes (point up, prints without supports) through each hinge, blind at the outer end:
        the filament pin goes in from the middle of the chest's back."""
        p = self.p
        ya, za = self.axis
        rr = p["pin_d"] / 2
        drop = CS.batch_hull([CS.circle(rr, 32), CS.square([0.01, 0.01]).translate([-0.005, rr * math.sqrt(2)])])
        drop = drop.translate([ya, za])
        w, g = p["k_w"], p["k_gap"]
        out = None
        for side in (-1, 1):
            xc = side * p["plank_x"]
            inner = xc - side * (1.5 * w + g)
            outer = xc + side * (1.5 * w + g - 1.5)
            x0, x1 = sorted((inner - side * 1.0, outer))
            h = prism_yz(drop, x0, x1)
            out = h if out is None else out + h
        return out

    # ---------- wood grain ----------

    def _face_cut(self, pattern_solid: M, skin: M) -> M:
        return pattern_solid ^ skin

    def grain_base(self, outer: M) -> M:
        p = self.p
        a, D, H = self.a, p["D"], p["H"]
        gw, gd = p["groove_w"], p["groove_depth"]
        cuts = []
        front = wavy_lines((0, H / 2), -65, 13.0, 13, 160, 0.9, 26, gw, seed=3)
        face = CS.square([2 * a - 2.0, H - 2.4]).translate([-a + 1.0, 1.2])
        cuts.append(prism_xz(front ^ face, -1, gd) ^ outer)
        back = wavy_lines((0, H / 2), -60, 13.0, 13, 160, 0.9, 26, gw, seed=5)
        cuts.append(prism_xz(back ^ face, D - gd, D + 1) ^ outer)
        side_face = CS.square([D - 2 * p["corner"] - 2, H - 2.4]).translate([p["corner"] + 1, 1.2])
        for sgn, seed in ((-1, 7), (1, 9)):
            pat = wavy_lines((D / 2, H / 2), -63, 13.0, 11, 140, 0.9, 26, gw, seed=seed) ^ side_face
            x0, x1 = (-a - 1, -a + gd) if sgn < 0 else (a - gd, a + 1)
            cuts.append(prism_yz(pat, x0, x1) ^ outer)
        return M.batch_boolean(cuts, m3d.OpType.Add)

    def grain_lid(self, body: M, xs, ys) -> M:
        p = self.p
        a, D = self.a, p["D"]
        gw, gd = p["groove_w"], p["groove_depth"]
        cuts = []
        # Top: grain running side to side, like boards across the lid.
        top_skin = body - heightfield(xs, ys, lambda X, Y: self.lid_z(X, Y) - gd, z0=-1.0)
        top = wavy_lines((0, D / 2), 0, 9.0, 9, 150, 0.8, 30, gw, seed=11) ^ CS.square([2 * a - 3, D - 3]).translate([-a + 1.5, 1.5])
        cuts.append(prism_xy(top, -1, 100) ^ top_skin)
        face = CS.square([2 * a - 2.0, 60]).translate([-a + 1.0, 1.2])
        for y0, y1, seed in ((-1, gd, 13), (D - gd, D + 1, 15)):
            pat = wavy_lines((0, 15), -65, 13.0, 13, 160, 0.9, 26, gw, seed=seed) ^ face
            cuts.append(prism_xz(pat, y0, y1) ^ body)
        side_face = CS.square([D - 2 * p["corner"] - 2, 60]).translate([p["corner"] + 1, 1.2])
        for sgn, seed in ((-1, 17), (1, 19)):
            pat = wavy_lines((D / 2, 15), -63, 13.0, 11, 140, 0.9, 26, gw, seed=seed) ^ side_face
            x0, x1 = (-a - 1, -a + gd) if sgn < 0 else (a - gd, a + 1)
            cuts.append(prism_yz(pat, x0, x1) ^ body)
        return M.batch_boolean(cuts, m3d.OpType.Add)

    # ---------- gem ----------

    def gem(self, slack: float = 0.0) -> M:
        """Printed flat on its back: the plug (with a small chamfer against elephant foot), a lip that stops
        at the face it sits in, and a cut-gem top."""
        p = self.p
        h = heart(p["heart_w"])
        body = h.offset(-slack, m3d.JoinType.Round, circular_segments=SEG) if slack else h
        plug = (body.offset(-0.3, m3d.JoinType.Round).extrude(0.4) + body.extrude(p["plug"] - 0.4).translate([0, 0, 0.4]))
        lip = h.offset(1.0, m3d.JoinType.Round, circular_segments=SEG).extrude(0.8).translate([0, 0, p["plug"]])
        crown = h.offset(1.0, m3d.JoinType.Round, circular_segments=SEG).extrude(3.2, scale_top=(0.55, 0.55))
        return plug + lip + crown.translate([0, 0, p["plug"] + 0.8])

    def lid_opened(self, lid: M, deg: float) -> M:
        ya, za = self.axis
        return lid.translate([0, -ya, -za]).rotate([-deg, 0, 0]).translate([0, ya, za])


def drop_specks(s: M) -> M:
    """Grooves grazing a steep edge can leave a speck of zero size; anything under 1 mm3 goes."""
    parts = [q for q in s.decompose() if q.volume() > 1.0]
    return M.batch_boolean(parts, m3d.OpType.Add) if len(parts) > 1 else parts[0]


def check_opening(ch: Chest, base: M, lid: M) -> tuple[float, list[str]]:
    """The widest the lid opens before touching the base (2-degree steps), and any problems."""
    problems = []
    if (lid ^ base).volume() > 0.5:
        problems.append(f"lid and base overlap when closed ({(lid ^ base).volume():.1f} mm3)")
    stop = None
    for deg in range(2, 182, 2):
        v = (ch.lid_opened(lid, deg) ^ base).volume()
        if v > 0.5:
            stop = deg
            break
    return (stop or 180), problems


def main() -> None:
    ap = argparse.ArgumentParser(description="Allen's daughter's treasure chest")
    ap.add_argument("--out", default=str(ROOT / "output" / "treasure-chest"))
    ap.add_argument("--width", type=float, default=120.0, help="outside width, mm (the rest follows)")
    ap.add_argument("--gems-each", type=int, default=2,
                    help="gems of each fit on the gem plate (2: one for the lock and one for the top heart)")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    p = dict(P)
    k = args.width / P["W"]
    for key in ("W", "D", "H", "h0", "ha", "plank_x", "plank_w"):
        p[key] = P[key] * k
    ch = Chest(p)
    base, lid, gem, gem2 = (drop_specks(s) for s in (ch.base(), ch.lid(), ch.gem(), ch.gem(slack=0.1)))
    stop, problems = check_opening(ch, base, lid)
    for s in (base, lid, gem):
        assert s.status() == m3d.Error.NoError and len(s.decompose()) == 1, "each part must be one solid"
    print(f"base {base.bounding_box()}, lid {lid.bounding_box()}")
    print(f"volumes: base {base.volume() / 1000:.0f} cm3, lid {lid.volume() / 1000:.0f} cm3, gem {gem.volume() / 1000:.1f} cm3")
    print(f"lid opens to about {stop} degrees")
    for pr in problems:
        print("PROBLEM:", pr)
    np.save(out / "_dims.npy", np.array([stop]))
    tip = tipping(ch, base, lid, stop)
    print(f"open, the chest's balance point is {tip:.0f} mm in front of the back edge of its bottom (above 0: it stays put)")
    if tip < 5:
        print("PROBLEM: the open chest could tip backward")
    write_files(ch, base, lid, gem, gem2, stop, out, args.gems_each)


def centroid(s: M) -> np.ndarray:
    mesh = s.to_mesh()
    v = np.asarray(mesh.vert_properties)[:, :3].astype(float)
    t = v[np.asarray(mesh.tri_verts)]
    vol = np.einsum("ij,ij->i", t[:, 0], np.cross(t[:, 1], t[:, 2])) / 6.0
    return (vol[:, None] * t.sum(axis=1) / 4.0).sum(axis=0) / vol.sum()


def tipping(ch: Chest, base: M, lid: M, deg: float) -> float:
    """How far in front of the back edge of the bottom the open chest's balance point is (mm), weighing each
    part by its walls (2 mm of shell) and 15% infill, roughly as Bambu Studio prints them."""
    def weight(s):
        shell = min(s.volume(), s.surface_area() * 2.0)
        return shell + 0.15 * (s.volume() - shell)
    opened = ch.lid_opened(lid, deg)
    wb, wl = weight(base), weight(opened)
    cy = (centroid(base)[1] * wb + centroid(opened)[1] * wl) / (wb + wl)
    return ch.p["D"] + ch.p["rail"] - cy        # from the back edge of the foot rail


def write_files(ch: Chest, base: M, lid: M, gem: M, gem2: M, stop: float, out: Path, each: int = 2) -> None:
    from charm_maker.bambu3mf import write_bambu_3mf
    from charm_maker.preview import render_shaded

    p = ch.p
    WOOD, DARK, RED = (176, 122, 72), (120, 80, 45), (214, 40, 70)
    ya, za = ch.axis
    # Plate 1: base upright, lid rim-down beside it (one filament).
    bb = base.bounding_box()
    lid_flat = lid.translate([0, 0, -p["H"]])
    lb = lid_flat.bounding_box()
    gap = 12.0
    depth = (bb[4] - bb[1]) + gap + (lb[4] - lb[1])
    y_start = 128 - depth / 2
    base_on = base.translate([128, y_start - bb[1], 0])
    lid_on = lid_flat.translate([128, y_start + (bb[4] - bb[1]) + gap - lb[1], 0])
    write_bambu_3mf([("chest-base", [("chest-base", base_on, 1, WOOD)]),
                     ("chest-lid", [("chest-lid", lid_on, 1, WOOD)])],
                    out / "treasure-chest.3mf", plate_name="treasure-chest")
    # Plate 2: the heart gems (one to use, one spare).
    g = gem.bounding_box()
    gw = g[3] - g[0]
    # Each heart hole (the lock A and the setting on top) takes the same gem; `each` of each fit, so both holes
    # can hold a gem at once whichever fit works (Allen, 2026-11-21, printing the chest: "can we make a gem to
    # fit that too?"). Snug ones in the front row, looser ones behind.
    gh = g[4] - g[1]
    gems = []
    for row, (name, solid) in enumerate((("heart-gem", gem), ("heart-gem-looser", gem2))):
        for i in range(each):
            x = 128 + (i - (each - 1) / 2) * gw * 1.5
            y = 128 + (row - 0.5) * gh * 1.5
            gems.append((name + (f"-{i + 1}" if each > 1 else ""), solid.translate([x - (g[0] + g[3]) / 2, y - (g[1] + g[4]) / 2, 0])))
    write_bambu_3mf([(n, [(n, s, 1, RED)]) for n, s in gems], out / "treasure-chest-gems.3mf", plate_name="treasure-chest-gems")
    # Pictures: closed with the gem in the lock, open with the gem on top, and the gem.
    lock_gem = gem.rotate([90, 0, 0]).translate([0, -p["plate_t"] + p["plug"], ch.heart_center_z()])
    top_gem = gem.rotate([90, 0, 0]).translate([0, p["plug"], ch.setting_center_z()])
    render_shaded({"base": base, "lid": lid, "gem": lock_gem}, out / "chest-closed.png", view=(20.0, -28.0),
                  px_per_mm=5.0, labels=False, colors={"base": WOOD, "lid": WOOD, "gem": RED})
    render_shaded({"base": base, "lid": lid, "gem": lock_gem}, out / "chest-front.png", view=(12.0, -14.0),
                  px_per_mm=5.0, labels=False, colors={"base": WOOD, "lid": WOOD, "gem": RED})
    opened = min(stop - 4, 100)
    render_shaded({"base": base, "lid": ch.lid_opened(lid, opened), "gem": ch.lid_opened(top_gem, opened)},
                  out / "chest-open.png", view=(32.0, -28.0), px_per_mm=4.0, labels=False,
                  colors={"base": WOOD, "lid": WOOD, "gem": RED})
    render_shaded({"base": base, "lid": lid, "gem": lock_gem, "gem2": top_gem}, out / "chest-two-gems.png", view=(20.0, -28.0),
                  px_per_mm=5.0, labels=False, colors={"base": WOOD, "lid": WOOD, "gem": RED, "gem2": RED})
    render_shaded({"base": base, "lid": lid}, out / "chest-back.png", view=(20.0, 152.0), px_per_mm=5.0, labels=False,
                  colors={"base": WOOD, "lid": WOOD})
    render_shaded({"gem": gem.rotate([90, 0, 0])}, out / "gem.png", view=(15.0, -20.0), px_per_mm=12.0, labels=False,
                  colors={"gem": RED})
    write_notes(ch, stop, out)


def write_notes(ch: Chest, stop: float, out: Path) -> None:
    p = ch.p
    w, g = p["k_w"], p["k_gap"]
    pin = 3 * w + 2 * g - 1.5
    tall = p["H"] + p["ha"] + 11
    (out / "PRINT_NOTES.md").write_text(f"""# Treasure chest: print notes

Her design: a wooden base with planks (C), a domed wooden lid (D) with the planks over the top, a short lock
plate (A) where lid and base meet, and a heart gem (B) that locks the lid in A or sits in the setting on top.

Size: {p['W']:.0f} mm wide, {p['D']:.0f} mm deep, about {tall:.0f} mm tall to the top of the heart. The box holds about
{(p['W'] - 2 * p['wall']) * (p['D'] - 2 * p['wall']) * (p['H'] - p['wall']) / 1000:.0f} ml.

## Plate 1: `treasure-chest.3mf` (the box and the lid)

- One filament: brown, or a wood PLA if you have one. Any AMS slot.
- Layer height **0.20 mm** (it is big; 0.12 mm would take much longer). Supports **off**: it is drawn to print
  without any. Default infill (15%) is fine; the lid is partly solid inside.
- The lid prints open side down, beside the box, as placed. Don't flip it or press **Arrange**.
- Rough guess: 5 to 7 hours and about 230 g of filament. Bambu Studio shows the real time after **Slice plate**.

## Plate 2: `treasure-chest-gems.3mf` (heart gems)

- One filament for the gems: red or pink (on its own plate so the chest needs no color changes).
- Layer height 0.12 mm, supports off. About 25 minutes.
- Both heart holes, the lock (A) on the front and the heart on top of the lid, take the same gem, so a gem can sit
  in each at once.
- Front row `heart-gem-1`, `heart-gem-2`: snug. Back row `heart-gem-looser-1`, `-2`: 0.1 mm smaller all around.
  Try a snug one first; if it is too hard to push in or pull out, use the looser ones. (The snug fit uses the gap
  that grips your clicker's switch, but a gem this shape has not been printed yet.)

## Putting it together

1. Hinge pins: cut two pieces of 1.75 mm filament, each about {pin:.0f} mm long.
2. Close the lid on the box. At the back, push one piece into each hinge from the middle of the chest's back,
   toward the side, until it stops (the outer end of each hinge is closed).
3. Trim it flush and put a small drop of glue on the open end so it can't slide out.
4. The lid opens to about {stop:.0f} degrees and stays open. The low ledge along the back of the bottom keeps the
   open chest from tipping backward.
5. Lock: close the lid and push the gem into the heart-shaped hole on the front plate (A). To open, pull the gem
   out by its top and keep it in the heart setting on top of the lid.
""")


if __name__ == "__main__":
    main()
