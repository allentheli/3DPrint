"""A downloaded crown with a turkey "trophy mount" on its front and gems on the band (Allen, 2026-11-25: "lets use
this crown model, but at the front put the bust of the turkey right upfront (think of the deer head mount on the
wall ...), ok to just in one color, I will color it myself, and put some gems on the crown").

Both models are Allen's downloads (MakerWorld, Standard Digital File License: personal printing only). They are
read from his files at run time; neither they nor the output go into git.

- The turkey (scaled up) is cut just above the widest part of its belly: legs and lower belly go, and the cut sits
  flat on the plate, so the bust prints standing the way the turkey was drawn to print.
- A rounded plaque with bevelled edges stands behind it, set into the crown's wall (never through to the inside);
  the turkey's own tail fan spreads round the plaque, like a hunter's fan mount.
- Low-poly gems sit in the big triangles of the band, matching the crown.
- Separate parts, one color: crown, turkey-trophy, gems; recolor any of them in Bambu Studio.

    python -I tools/turkey_trophy_crown.py <crown.3mf> <turkey.3mf> [--out output/turkey-trophy-crown]
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import manifold3d as m3d
import numpy as np
import trimesh

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

M, CS = m3d.Manifold, m3d.CrossSection
GOLD, BROWN, RED = (232, 182, 40), (125, 75, 35), (200, 30, 45)


def load(path: Path) -> M:
    geo = trimesh.load(str(path))
    mesh = geo.to_geometry() if hasattr(geo, "to_geometry") else geo
    solid = M(m3d.Mesh(vert_properties=np.asarray(mesh.vertices, np.float32), tri_verts=np.asarray(mesh.faces, np.uint32)))
    if solid.status() != m3d.Error.NoError or solid.is_empty():
        raise ValueError(f"{Path(path).name} is not a clean solid ({solid.status()})")
    return solid


def hollow(crown: M, cx: float, cy: float, band_top: float) -> M:
    """The inside of the band, exactly: the hull of its inner wall's outline at many heights (extended above and
    below), so whatever is cut with it ends flush with the inside of the crown."""
    pts = []
    for z in np.linspace(0.05, band_top - 0.2, 40):
        polys = [np.asarray(p) for p in crown.slice(float(z)).to_polygons()]
        inner = min(polys, key=lambda p: np.hypot(p[:, 0] - cx, p[:, 1] - cy).mean())
        for zz in ([z, -5.0] if z < 0.1 else [z, band_top + 60.0] if z > band_top - 0.3 else [z]):
            pts += [(x, y, zz) for x, y in inner]
    h = M.hull_points(np.array(pts))
    # 0.35 mm bigger than the inside, so a cut with it ends inside the wall, never on the crown's own surface.
    return h.translate([-cx, -cy, 0]).scale([1.005, 1.005, 1.0]).translate([cx, cy, 0])


def crown_axis(crown: M) -> tuple[float, float]:
    b = crown.bounding_box()
    return (b[0] + b[3]) / 2, (b[1] + b[4]) / 2


def inner_cone(crown: M, cx: float, cy: float, band_top: float, grow: float = -0.6) -> M:
    """The inside of the band (a cone through its inner wall, 0.6 mm in), so nothing pokes into the crown."""
    def inner_r(z):
        rs = []
        for p in crown.slice(z).to_polygons():
            p = np.asarray(p)
            rs.append(np.hypot(p[:, 0] - cx, p[:, 1] - cy).min())
        return min(rs)
    r0, r1 = inner_r(0.5), inner_r(band_top - 1.0)
    h = band_top - 1.5
    k = (r1 - r0) / h
    return M.cylinder(200.0, r0 + grow - k * 50.0, r0 + grow + k * 150.0, 180).translate([cx, cy, -50.0])


def front_radius(crown: M, cx: float, cy: float, top: float, half_angle: float = 28.0):
    """The crown's outer radius at the front (largest within +-half_angle of straight ahead), by height."""
    zs = np.arange(0.0, top + 1.0, 1.0)
    rs = []
    for z in zs:
        best = 0.0
        for p in crown.slice(float(max(z, 0.3))).to_polygons():
            p = np.asarray(p)
            ang = np.degrees(np.arctan2(p[:, 0] - cx, -(p[:, 1] - cy)))
            sel = np.abs(ang) < half_angle
            if sel.any():
                best = max(best, float(np.hypot(p[sel, 0] - cx, p[sel, 1] - cy).max()))
        rs.append(best if best > 0 else (rs[-1] if rs else 76.0))
    rs = np.maximum.accumulate(np.array(rs))          # never step back in: the fan sits in front of the flare
    return zs, rs


def trophy(crown: M, turkey: M, cx: float, cy: float, cut: float, scale: float) -> M:
    """The turkey cut flat at the belly (head, chest, wings and the whole tail fan), its fan wrapped round the
    crown's front, the bust sticking out in front: a hunter's mount without the plaque (Allen: "we dont
    necessary need a plaque, but the turkey tail fan is important")."""
    t = turkey.simplify(0.03)
    b = t.bounding_box()
    fan_back, body_mid = b[4], 131.0                                                  # turkey's own y: back of the fan, middle of the body
    t = t.translate([-(b[0] + b[3]) / 2, -b[4], -cut]).trim_by_plane([0, 0, 1], 0.0)   # fan's back at y = 0
    t = t.scale([scale, scale, scale])
    # Solid behind the turkey's whole outline, 8 mm back into the crown (the crown's faceted front leaves gaps
    # behind a flat fan): the turkey is fused to the crown all over, not just along its ridges (Allen: "I like for
    # it to be fused so its secure").
    sil = t.rotate([-90, 0, 0]).project().offset(-0.4, m3d.JoinType.Round, circular_segments=24)
    backfill = sil.extrude(8.0).rotate([90, 0, 0]).translate([0, 8.0, 0])
    # The tail's lowest feathers and the rear of the body sit in front of the fan's back, so fill from every part
    # of the turkey's back straight into the crown: the turkey pushed back on itself, 0.6 mm at a time, 16 mm
    # (Allen's screenshot, 2026-11-25: "fuse the tail and the butt to the crown completely").
    # Only the back half (rear of the body, the butt, the tail): the head, neck and chest stay as drawn.
    rear = t ^ M.cube([400, 400, 400]).translate([-200, -0.45 * (fan_back - body_mid) * scale - 6.0, -1])
    swept = M.batch_boolean([rear.translate([0, 0.6 * k, 0]) for k in range(27)], m3d.OpType.Add)
    t = (t + backfill + swept).refine_to_length(1.5)
    top = t.bounding_box()[5]
    zs, rs = front_radius(crown, cx, cy, top)
    embed = 1.5

    def wrap(v):
        v = np.asarray(v, float)
        R = np.interp(v[:, 2], zs, rs) - embed
        d = -v[:, 1]                                   # how far in front of the fan's back
        phi = v[:, 0] / R
        out = np.empty_like(v)
        out[:, 0] = cx + (R + d) * np.sin(phi)
        out[:, 1] = cy - (R + d) * np.cos(phi)
        out[:, 2] = v[:, 2]
        return out
    return t.warp_batch(wrap)


def band_facets(crown: M, cx: float, cy: float, band_top: float):
    mesh = crown.to_mesh()
    v = np.asarray(mesh.vert_properties)[:, :3].astype(float)
    tri = v[np.asarray(mesh.tri_verts)]
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    area = np.linalg.norm(n, axis=1) / 2
    n = n / np.maximum(np.linalg.norm(n, axis=1)[:, None], 1e-9)
    cen = tri.mean(axis=1)
    radial = np.stack([cen[:, 0] - cx, cen[:, 1] - cy], 1)
    rr = np.linalg.norm(radial, axis=1)
    out = (np.einsum("ij,ij->i", n[:, :2], radial / rr[:, None]) > 0.7)
    sel = out & (cen[:, 2] < band_top - 2) & (area > 120)
    facets = []
    for i in np.flatnonzero(sel):
        a, b_, c = tri[i]
        la, lb, lc = np.linalg.norm(b_ - c), np.linalg.norm(a - c), np.linalg.norm(a - b_)
        inc = (la * a + lb * b_ + lc * c) / (la + lb + lc)                          # incircle centre
        r_in = 2 * area[i] / (la + lb + lc)
        ang = math.degrees(math.atan2(cen[i, 0] - cx, -(cen[i, 1] - cy))) % 360
        facets.append(dict(center=inc, normal=n[i], r_in=r_in, angle=ang, z=cen[i, 2], area=area[i]))
    return facets


def gem(center, normal, size: float) -> M:
    """A low-poly gem (hexagonal, bevelled 45 degrees) sitting on a facet."""
    n = np.asarray(normal, float)
    up = np.array([0.0, 0.0, 1.0])
    u = np.cross(up, n)
    u /= np.linalg.norm(u)
    w = np.cross(n, u)
    pts = []
    rt, h = 0.55 * size, 0.45 * size
    for k in range(6):
        a = math.radians(30 + 60 * k)
        d = math.cos(a) * u + math.sin(a) * w
        pts.append(center - 0.6 * n + size * d)
        pts.append(center + h * n + rt * d)
    return M.hull_points(np.array(pts))


def elastic_holes(cx: float, cy: float, angles=(98.6, 278.6), z: float = 8.0, d: float = 5.0) -> M:
    """Round holes through the band (teardrop, point up, so the top prints without sagging)."""
    r = d / 2
    drop = CS.batch_hull([CS.circle(r, 48), CS.square([0.01, 0.01]).translate([-0.005, r * math.sqrt(2)])])
    out = None
    for a in angles:
        h = drop.extrude(40.0).translate([0, 0, -20.0])          # along local z
        h = h.rotate([90, 0, 0])                                  # now along -y..y, the drop in x-z
        h = h.translate([0, -70.0, z]).rotate([0, 0, a])          # out at radius ~70, turned to angle a
        h = h.translate([cx, cy, 0])
        out = h if out is None else out + h
    return out


def unsupported(s: M, step: float = 0.2, max_from_upright: float = 50.0) -> list:
    """Spots wider than 1.5 mm printed over thin air (beyond `max_from_upright` degrees)."""
    reach = step * math.tan(math.radians(max_from_upright))
    top = s.bounding_box()[5]
    z, prev, bad = step, s.slice(step / 2), []
    while z < top:
        cur = s.slice(z)
        un = cur - prev.offset(reach, m3d.JoinType.Round)
        if un.area() > 0.5:
            core = un.offset(-0.75, m3d.JoinType.Round)
            if not core.is_empty() and core.area() > 0.05:
                for p in core.decompose():
                    b = p.bounds()
                    bad.append((round(z, 1), round(p.area(), 1), [round(x, 1) for x in b]))
        prev, z = cur, z + step
    return bad


def build(crown_path: Path, turkey_path: Path, cut: float, scale: float):
    crown = load(crown_path)
    turkey = load(turkey_path)
    cx, cy = crown_axis(crown)
    band_top = 37.0
    tro = trophy(crown, turkey, cx, cy, cut, scale)
    tro = tro - inner_cone(crown, cx, cy, band_top)
    # One gem per section of the crown (the biggest triangle of the band in each 30 degrees), not on the turkey.
    best = {}
    for f in band_facets(crown, cx, cy, band_top):
        if min(abs(f["angle"]), abs(360 - f["angle"])) < 28 or f["r_in"] < 10.0:    # behind the turkey; small triangles
            continue
        sector = int(((f["angle"] + 15.0) % 360) // 30)
        if sector not in best or f["r_in"] > best[sector]["r_in"]:
            best[sector] = f
    gems = None
    for f in best.values():
        g = gem(f["center"], f["normal"], min(8.0, 0.75 * f["r_in"]))
        gems = g if gems is None else gems + g
    gems = gems - crown
    tro = tro - inner_cone(crown, cx, cy, band_top) - hollow(crown, cx, cy, band_top)
    overlap = (tro ^ crown).volume()
    # Two holes for a chin elastic: opposite each other, just behind the sides, low on the band, between gems.
    crown = crown - elastic_holes(cx, cy)
    tro = tro - elastic_holes(cx, cy)
    keep = [c for c in tro.decompose() if c.volume() > 1.0]          # zero-size slivers from trimming against the wall
    tro = keep[0] if len(keep) == 1 else M.batch_boolean(keep, m3d.OpType.Add)
    # Overlapping solids joined in one go (no face lies on another, so no slivers along the seam).
    fused = crown + tro
    keep = [c for c in fused.decompose() if c.volume() > 1.0]
    fused = keep[0] if len(keep) == 1 else M.batch_boolean(keep, m3d.OpType.Add)
    gems = gems - fused
    print(f"turkey sunk into the crown: {overlap / 1000:.1f} cm3 of overlap, now one solid ({len(fused.decompose())} piece)")
    return {"crown-with-turkey": fused, "gems": gems}, (cx, cy)


def main() -> None:
    ap = argparse.ArgumentParser(description="Crown with a turkey trophy mount and gems")
    ap.add_argument("crown")
    ap.add_argument("turkey")
    ap.add_argument("--out", default=str(ROOT / "output" / "turkey-trophy-crown"))
    ap.add_argument("--cut", type=float, default=17.0, help="height on the turkey (mm, before scaling) where the bust is cut")
    ap.add_argument("--scale", type=float, default=1.2, help="turkey size")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    parts, (cx, cy) = build(Path(args.crown), Path(args.turkey), args.cut, args.scale)
    whole = M.batch_boolean(list(parts.values()), m3d.OpType.Add)
    bb = whole.bounding_box()
    print(f"{bb[3] - bb[0]:.0f} x {bb[4] - bb[1]:.0f} x {bb[5]:.0f} mm; pieces: " +
          ", ".join(f"{k} {len(v.decompose())}" for k, v in parts.items()) +
          f"; whole {len(whole.decompose())}; plastic {whole.volume() / 1000:.0f} cm3")
    bad = unsupported(whole)
    print(f"{len(bad)} spots printing over thin air:", bad[:20])
    write_files(parts, cx, cy, out)


def write_files(parts: dict, cx: float, cy: float, out: Path) -> None:
    from charm_maker.bambu3mf import write_bambu_3mf
    from charm_maker.preview import render_shaded

    allb = M.batch_boolean(list(parts.values()), m3d.OpType.Add).bounding_box()
    dx, dy = 128 - (allb[0] + allb[3]) / 2, 128 - (allb[1] + allb[4]) / 2        # the whole thing centred on the plate
    on = {k: v.translate([dx, dy, 0]) for k, v in parts.items()}
    write_bambu_3mf([("turkey-trophy-crown", [(k, s, 1, GOLD) for k, s in on.items()])],
                    out / "turkey-trophy-crown.3mf", plate_name="turkey-trophy-crown")
    view_parts = {k: v.simplify(0.05) for k, v in parts.items()}
    (out / "PRINT_NOTES.md").write_text("""# Turkey trophy crown: print notes

Your downloaded crown ("Low-Poly Geometric Crown", Canary_3D_Print) with your downloaded turkey ("Thanksgiving day
Turkey", faffi) mounted on its front like a hunter's trophy: the turkey cut flat at the belly, its tail fan wrapped
round the crown's front, the head and chest sticking out under the front point. The turkey is fused into the crown
(solid plastic behind the whole fan, into the crown's wall): one piece. A gem in each big triangle at the bottom of
the band (10, in an even row). Two holes for a chin elastic. Both models are under MakerWorld's Standard Digital
File License: for your own printing only.

## Plate: `turkey-trophy-crown.3mf`

- Two parts, both slot 1: `crown-with-turkey` (one solid) and `gems`. To color the gems, click `gems` in the list on
  the left and pick another filament. To color the turkey, use the **Color painting** tool on it. Colors only change
  on the layers where they are (the bottom 45 mm).
- Layer height **0.20 mm**. Supports **off**: the crown printed without them, and the turkey's legs and lower belly
  (the part that needed supports) are cut away. The beak tip has a few square millimetres hanging in the air; it
  prints with at most a slightly droopy tip. For a perfect beak, turn supports on with **On build plate only**.
- Brim: **Outer brim only**, 5 mm.
- Don't press **Arrange**.

## Chin elastic

The crown sits on top of the head (43 cm round inside). Two 5 mm holes, low on the band just behind each side.
Thread hat elastic (round cord or thin flat elastic) through one hole from the outside, knot it inside, run it
under the chin, and knot it inside the other hole at a comfortable length.
""")

    render_shaded(view_parts, out / "crown-front.png", view=(10.0, -12.0), px_per_mm=4.0, labels=False,
                  colors={"crown-with-turkey": GOLD, "gems": GOLD})
    render_shaded(view_parts, out / "crown-colored-idea.png", view=(18.0, -30.0), px_per_mm=4.0, labels=False,
                  colors={"crown-with-turkey": GOLD, "gems": RED})
    render_shaded(view_parts, out / "crown-side.png", view=(8.0, -100.0), px_per_mm=4.0, labels=False,
                  colors={"crown-with-turkey": GOLD, "gems": RED})
    render_shaded(view_parts, out / "crown-inside.png", view=(55.0, 170.0), px_per_mm=4.0, labels=False,
                  colors={"crown-with-turkey": GOLD, "gems": RED})


if __name__ == "__main__":
    main()
