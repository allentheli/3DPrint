"""An imperial-style Thanksgiving crown, one piece, printed standing (Allen, 2026-11-25, from a photo of a gold
baroque crown on MakerWorld: "How bout using this as inspiration"). Our own design in that style, not a copy.

Fancy: a gold band with pearl rows, domed jewels and scrolls; four arches beaded with pearls rising to an orb.
Funny: a plump turkey stands on the orb where a cross would be; the four fleurs are turkey feathers; maple leaves
between them; crossed-drumstick crests on the band.

Sits on top of the head like a royal crown (open band, 167 mm inside), so it fits kids and grown-ups. Prints
upright in one piece with no supports: every slope is 40 degrees or steeper. The turkey starts on a flat
platform on the orb, so it can print brown with a single color change, or all gold.

    python tools/turkey_crown_3d.py [--out output/turkey-crown-3d]
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
from treasure_box import arc, ellipse, poly, smooth, stroke  # noqa: E402
from turkey_crown import bend, circle, union  # noqa: E402

M, CS = m3d.Manifold, m3d.CrossSection
R = m3d.JoinType.Round
SEG = 64

R_IN = 83.5          # inside radius of the band (167 mm across)
T_BAND = 2.6         # band wall
H_BAND = 32.0
RELIEF = 1.2
T_ARCH, W_ARCH = 3.6, 11.0          # the arches lean in on their own until they meet at the top
MAX_SLOPE = math.tan(math.radians(50))   # arches lean in at most 50 degrees from upright (40 from flat)
GOLD, BROWN = (232, 182, 40), (125, 75, 35)


def plate(cs: CS, phi_deg: float, thick: float = T_BAND, z0: float = 0.0) -> M:
    """A flat 2D shape (x along the band, y up) as a plate in the band's wall at angle phi, bent to the band."""
    return bend(cs.extrude(thick).translate([0, 0, z0]), R_IN, math.radians(phi_deg))


def relief(cs: CS, phi_deg: float, height: float = RELIEF) -> M:
    return plate(cs, phi_deg, height + 0.3, T_BAND - 0.3)


def dome(cs: CS, phi_deg: float, height: float, n: int = 6) -> M:
    out = None
    for i in range(n):
        u = (i + 1) / n
        layer = cs.offset(-3.0 * (1 - math.sqrt(max(0.0, 1 - u * u))), R, circular_segments=32)
        if layer.is_empty():
            break
        s = plate(layer, phi_deg, height / n + 0.02, T_BAND - 0.3 + height * i / n)
        out = s if out is None else out + s
    return out


# ---------- motifs (flat, mm) ----------

def feather(cx, cy, length, width, ang) -> tuple[CS, CS]:
    """A turkey feather (rounded tip) and its raised quill line, pointing up when ang = 0."""
    body = ellipse(0, length / 2, width / 2, length / 2)
    body = body + poly([(-width * 0.18, 0.0), (width * 0.18, 0.0), (0, -3.0)])
    quill = stroke([(0, -1.5), (0, length * 0.86)], 1.0)
    return body.rotate(ang).translate([cx, cy]), quill.rotate(ang).translate([cx, cy])


def fleur() -> tuple[CS, CS]:
    """Three turkey feathers fanned like a fleur-de-lis, bound by a collar."""
    base_y = H_BAND - 3.0
    shapes, lines = [], []
    for ang, length, width in ((0.0, 34.0, 11.0), (34.0, 25.0, 9.0), (-34.0, 25.0, 9.0)):
        b, q = feather(0.0, base_y + 4.0, length, width, ang)
        shapes.append(b)
        lines.append(q)
    collar = CS.square([20.0, 5.0]).translate([-10.0, base_y + 3.0])
    body = smooth(union(shapes), 0.6)
    band = (collar.offset(0.6, R) - collar) + CS.square([20, 1.0]).translate([-10, base_y + 5.0])
    return body + collar, union(lines + [band])


def maple(cx, cy, s) -> tuple[CS, CS]:
    """A maple leaf (about 24 x 24 mm at s = 1) and its raised veins."""
    # Right half from the top tip down: alternating lobe tips and notches (angle, radius); the left half mirrors it.
    lobes = [(62, 6.0), (40, 11.5), (12, 5.5), (-8, 10.0), (-35, 4.5), (-62, 5.0)]
    right = [(r * math.cos(math.radians(a)), r * math.sin(math.radians(a))) for a, r in lobes]
    left = [(-x, y) for x, y in reversed(right)]
    leaf = smooth(poly([(0.0, 13.0)] + right + [(0.9, -4.5), (-0.9, -4.5)] + left), 0.5)
    leaf = smooth(union([leaf, CS.square([1.8, 9.0]).translate([-0.9, -12.0])]), 0.3)    # the stem
    veins = union([stroke([(0, -4), (0, 11)], 0.9), stroke([(0, -1.5), (8.5, 7.0)], 0.9), stroke([(0, -1.5), (-8.5, 7.0)], 0.9),
                   stroke([(0, -3), (6.5, -1.5)], 0.8), stroke([(0, -3), (-6.5, -1.5)], 0.8)])
    return leaf.scale([s, s]).translate([cx, cy]), (veins ^ leaf.offset(-1.2, R)).scale([s, s]).translate([cx, cy])


def drumstick(len_: float) -> CS:
    meat = ellipse(0, len_ * 0.28, len_ * 0.22, len_ * 0.33)
    bone = stroke([(0, 0), (0, -len_ * 0.42)], len_ * 0.1)
    knobs = circle(-len_ * 0.07, -len_ * 0.47, len_ * 0.075) + circle(len_ * 0.07, -len_ * 0.47, len_ * 0.075)
    return smooth(meat + bone + knobs, 0.3)


def crossed_drumsticks() -> CS:
    d = drumstick(27.0)
    return d.rotate(180 + 38).translate([0, H_BAND / 2]) + d.rotate(180 - 38).translate([0, H_BAND / 2])


def scroll(cx, cy, mirror: float) -> CS:
    """A small C-scroll (filigree)."""
    s = arc(0, 0, 4.2, 30, 300, 1.2) + arc(2.0, -1.6, 1.8, 120, 400, 1.0)
    return s.scale([mirror, 1.0]).translate([cx, cy])


def pearls_row(y: float, x0: float, x1: float, step: float = 4.6, r: float = 1.35) -> CS:
    n = int((x1 - x0) / step)
    return union([circle(x0 + (k + 0.5) * (x1 - x0) / n, y, r) for k in range(n)])


# ---------- the crown ----------

def band() -> M:
    # The whole 2.6 mm wall stands on the plate (a tall piece on a thin ring: no bevel here; use a brim).
    return M.cylinder(H_BAND, R_IN + T_BAND, R_IN + T_BAND, 240) - M.cylinder(H_BAND + 2, R_IN, R_IN, 240).translate([0, 0, -1])


def arch_profile() -> np.ndarray:
    """Centre line (r, z) of a half arch: straight up from the band, then leaning in (never past 50 degrees
    from upright) to the hub."""
    r_c = R_IN + T_BAND / 2
    z0, z1 = H_BAND - 4.0, H_BAND + 4.0
    pts = [(r_c, z0), (r_c, z1)]
    r, z, dz = r_c, z1, 0.5
    ramp = 58.0                              # long ramp: a curved (gothic) arch, not a straight pole
    while r > 5.0:
        slope = MAX_SLOPE * min(1.0, (z - z1) / ramp)
        z += dz
        r -= slope * dz
        pts.append((max(r, 5.0), z))
    return np.array(pts)


def half_arch(phi_deg: float, prof: np.ndarray) -> tuple[M, float]:
    pts = [tuple(p) for p in prof[::4]] + [tuple(prof[-1])]
    cs = stroke(pts, T_ARCH)
    strip = cs.extrude(W_ARCH).translate([0, 0, -W_ARCH / 2]).rotate([90, 0, 0])
    rim_cs = stroke(pts, T_ARCH + 2.0) - stroke(pts, T_ARCH).offset(-0.01)
    rim_cs = rim_cs ^ stroke(pts, T_ARCH + 2.0)
    for side in (-1, 1):                     # raised edges along both sides of the arch
        rim = (stroke(pts, T_ARCH + 1.6)).extrude(1.4).translate([0, 0, side * (W_ARCH / 2 - 0.7) - 0.7]).rotate([90, 0, 0])
        strip = strip + rim
    # pearls along the outside of the arch
    beads = None
    d = np.cumsum(np.r_[0, np.hypot(*np.diff(prof, axis=0).T)])
    for s in np.arange(10.0, d[-1] - 12.0, 6.5):
        i = np.searchsorted(d, s)
        (r0, z0), (r1, z1_) = prof[max(i - 1, 0)], prof[min(i + 1, len(prof) - 1)]
        tx, tz = r1 - r0, z1_ - z0
        nrm = math.hypot(tx, tz)
        nx, nz = tz / nrm, -tx / nrm             # outward normal in the (r, z) plane
        rr, zz = prof[i]
        b = M.sphere(1.7, 24).translate([rr + nx * (T_ARCH / 2), 0, zz + nz * (T_ARCH / 2)])
        beads = b if beads is None else beads + b
    out = strip + beads
    return out.rotate([0, 0, phi_deg - 90.0]), prof[-1][1]


def turkey(z0: float) -> M:
    """A plump turkey facing front (-y), standing on a flat platform at z0."""
    body = M.sphere(1.0, 48).scale([9.0, 8.0, 10.0]).translate([0, 0, z0 + 10.0])
    skirt = M.cylinder(1.0, 5.5, 5.5, 48).translate([0, 0, z0])
    body = M.batch_hull([body, skirt])
    # Tail fan behind: a vertical plate, scalloped, 50 degrees each side of upright.
    fan_cs = None
    for k in range(7):
        a = math.radians(-50 + 100 * k / 6)
        f = ellipse(15.0 * math.sin(a), 15.0 * math.cos(a), 3.6, 6.0, -math.degrees(a))
        fan_cs = f if fan_cs is None else fan_cs + f
    wedge = poly([(0, 0), (12 * math.sin(math.radians(-50)), 12 * math.cos(math.radians(-50))),
                  (0, 13), (12 * math.sin(math.radians(50)), 12 * math.cos(math.radians(50)))])
    fan_cs = smooth(fan_cs + wedge, 0.4)
    fan = fan_cs.extrude(3.0).rotate([90, 0, 0]).translate([0, 6.5, z0 + 9.0])
    # Neck and head, leaning forward; beak, wattle along the neck, eyes.
    neck = M.batch_hull([M.sphere(4.0, 32).translate([0, -4.0, z0 + 16.0]), M.sphere(3.4, 32).translate([0, -6.5, z0 + 24.0])])
    head = M.sphere(4.6, 32).translate([0, -7.0, z0 + 26.5])
    beak = M.cylinder(3.0, 1.6, 0.2, 24).rotate([90, 0, 0]).translate([0, -11.0, z0 + 26.0])
    wattle = M.batch_hull([M.sphere(1.6, 24).translate([0, -10.4, z0 + 24.4]), M.sphere(1.3, 24).translate([0, -9.4, z0 + 21.0])])
    eyes = M.sphere(1.0, 16).translate([-2.3, -10.6, z0 + 27.8]) + M.sphere(1.0, 16).translate([2.3, -10.6, z0 + 27.8])
    wings = (M.sphere(1.0, 32).scale([2.6, 6.0, 6.5]).translate([-8.2, -0.5, z0 + 10.5])
             + M.sphere(1.0, 32).scale([2.6, 6.0, 6.5]).translate([8.2, -0.5, z0 + 10.5]))
    return body + fan + neck + head + beak + wattle + wings - eyes.translate([0, 0.6, 0])


def build() -> dict[str, M]:
    crown = band()
    pieces = []
    # Fleurs at front, left, back, right; maple leaves between.
    for phi in (0, 90, 180, 270):
        body, lines = fleur()
        pieces.append(plate(body, phi))
        pieces.append(relief(lines, phi, 1.0))
    for phi in (45, 135, 225, 315):
        leaf, veins = maple(0.0, H_BAND + 5.5, 1.3)
        pieces.append(plate(leaf, phi))
        pieces.append(relief(veins, phi, 0.9))
    for k in range(8):
        phi = 22.5 + 45.0 * k
        spike = poly([(-4.5, H_BAND - 3.0), (4.5, H_BAND - 3.0), (0.9, H_BAND + 13.0), (-0.9, H_BAND + 13.0)])
        pieces.append(plate(smooth(spike, 0.4), phi))
        ang = math.radians(phi)
        rr = R_IN + T_BAND / 2
        pieces.append(M.batch_hull([M.sphere(2.7, 32).translate([rr * math.sin(ang), -rr * math.cos(ang), H_BAND + 15.2]),
                                    M.sphere(0.9, 16).translate([rr * math.sin(ang), -rr * math.cos(ang), H_BAND + 11.4])]))
    # Band dressing: pearls top and bottom, jewels under the fleurs, crossed drumsticks under the leaves, scrolls.
    per = 2 * math.pi * R_IN / 8          # arc length between features
    for k in range(8):
        phi = 45.0 * k
        pieces.append(relief(pearls_row(H_BAND - 3.3, -per / 2, per / 2), phi, 1.0))
        pieces.append(relief(pearls_row(3.3, -per / 2, per / 2), phi, 1.0))
        if k % 2 == 0:
            pieces.append(dome(ellipse(0, H_BAND / 2, 6.5, 5.2), phi, 2.6))
            pieces.append(relief(ellipse(0, H_BAND / 2, 8.2, 6.9) - ellipse(0, H_BAND / 2, 7.0, 5.7), phi, 1.0))
        else:
            pieces.append(relief(crossed_drumsticks(), phi, 1.2))
        for side in (-1, 1):
            pieces.append(relief(scroll(side * per * 0.30, H_BAND / 2, side), phi, 0.9))
    for p in pieces:
        crown = crown + p
    prof = arch_profile()
    top = 0.0
    for phi in (0, 90, 180, 270):
        a, top = half_arch(phi, prof)
        crown = crown + a
    # Hub and orb (sphere over a 45-degree cone), with a band round its middle and a flat platform on top.
    # Hub where the arches meet: a cone underneath (it grows out of the arches, nothing in mid-air).
    hub = M.cylinder(8.0, 0.5, 6.0, 48).translate([0, 0, top - 14.0]) + M.cylinder(8.0, 6.0, 6.0, 48).translate([0, 0, top - 6.0])
    oc = top + 15.0
    orb = M.batch_hull([M.sphere(11.0, 64).translate([0, 0, oc]), M.cylinder(1.0, 5.0, 5.0, 48).translate([0, 0, top - 0.5])])
    belt = M.cylinder(3.0, 11.8, 11.8, 64).translate([0, 0, oc - 1.5]) - M.cylinder(5.0, 10.0, 10.0, 64).translate([0, 0, oc - 2.5])
    belt = M.batch_hull([belt, M.cylinder(0.1, 10.6, 10.6, 64).translate([0, 0, oc - 2.7])]) - M.cylinder(8, 9.5, 9.5, 64).translate([0, 0, oc - 4])
    plat_z = oc + 9.0
    orb = (orb + belt) ^ M.cylinder(plat_z, 30, 30, 8).translate([0, 0, 0.0])   # cut flat on top: the platform
    crown = crown + hub + orb
    keep = [c for c in crown.decompose() if c.volume() > 1.0]          # drop zero-size specks from the joins
    crown = keep[0] if len(keep) == 1 else M.batch_boolean(keep, m3d.OpType.Add)
    return {"crown": crown, "turkey": turkey(plat_z) - M.cylinder(plat_z, 40, 40, 8)}


def overhangs(s: M, limit_deg: float = 40.0) -> float:
    """Area (mm2) facing down flatter than `limit_deg` from flat, not on the bed."""
    mesh = s.to_mesh()
    v = np.asarray(mesh.vert_properties)[:, :3].astype(float)
    t = v[np.asarray(mesh.tri_verts)]
    n = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
    area = np.linalg.norm(n, axis=1) / 2
    nz = n[:, 2] / np.maximum(np.linalg.norm(n, axis=1), 1e-12)
    low = t[:, :, 2].max(axis=1) < 0.3
    bad = (nz < -math.cos(math.radians(limit_deg))) & ~low
    return float(area[bad].sum())


def main() -> None:
    ap = argparse.ArgumentParser(description="Imperial turkey crown")
    ap.add_argument("--out", default=str(ROOT / "output" / "turkey-crown-3d"))
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    parts = build()
    for k, s in parts.items():
        assert s.status() == m3d.Error.NoError and not s.is_empty(), k
    allp = parts["crown"] + parts["turkey"]
    bb = allp.bounding_box()
    print(f"crown {bb[3] - bb[0]:.0f} x {bb[4] - bb[1]:.0f} x {bb[5]:.0f} mm, inside {2 * R_IN:.0f} mm; "
          f"pieces {len(parts['crown'].decompose())} + {len(parts['turkey'].decompose())}; "
          f"plastic {allp.volume() / 1000:.0f} cm3")
    print(f"flatter-than-40-degree overhangs: crown {overhangs(parts['crown']):.0f} mm2, turkey {overhangs(parts['turkey']):.0f} mm2")
    write_files(parts, out)


def write_files(parts: dict, out: Path) -> None:
    from charm_maker.bambu3mf import write_bambu_3mf
    from charm_maker.preview import render_shaded

    on = {k: v.translate([128, 128, 0]) for k, v in parts.items()}
    write_bambu_3mf([("turkey-crown", [("crown", on["crown"], 1, GOLD), ("turkey", on["turkey"], 2, BROWN)])],
                    out / "turkey-crown-3d.3mf", plate_name="turkey-crown-3d")
    cols = {"crown": GOLD, "turkey": BROWN}
    render_shaded(parts, out / "crown-front.png", view=(12.0, -15.0), px_per_mm=4.0, labels=False, colors=cols)
    render_shaded(parts, out / "crown-gold.png", view=(12.0, -15.0), px_per_mm=4.0, labels=False,
                  colors={"crown": GOLD, "turkey": GOLD})
    render_shaded(parts, out / "crown-above.png", view=(45.0, 20.0), px_per_mm=4.0, labels=False, colors=cols)
    (out / "PRINT_NOTES.md").write_text("""# Imperial turkey crown: print notes

A gold crown in the style of the one you sent (our own design): pearl rows, jewels, scrolls and crossed-drumstick
crests on the band; turkey-feather fleurs, maple leaves and pearl-tipped spikes round the top; four beaded arches
to an orb; a turkey standing on the orb. One piece, about 18 cm tall; the open band (16.7 cm inside) sits on top
of the head like a royal crown, so it fits kids and grown-ups.

## Plate: `turkey-crown-3d.3mf`

- **Slot 1: gold** (silk gold looks best), **slot 2: brown** for the turkey. Only one color change: the turkey
  starts on a flat platform on the orb. For an all-gold crown, set the turkey to slot 1 too.
- Layer height **0.20 mm**, supports **off**: every slope is 40 degrees or steeper.
- **Brim on**: the crown is tall and stands on the thin ring of its band (your lid came loose that way). On the
  right, **Others** tab, **Brim type**: **Outer and inner brim**, **Brim width** 5 mm; peel it off after. Wash the
  plate with dish soap first.
- Don't press **Arrange**. Bambu Studio shows the real time after **Slice plate** (my rough guess: about 5 hours).
""")


if __name__ == "__main__":
    main()
