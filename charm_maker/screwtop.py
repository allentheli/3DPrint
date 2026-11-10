"""Add a twist-off screw top to a downloaded "poop eater" model.

Many poop-eater models (a lattice body with a solid head, for example) are filled by
pausing the print. This tool cuts the model at a chosen height, turns the part above
(the head) into a lid with a threaded socket, and gives the body a matching threaded
neck and a filling hole. Kids can then fill it themselves and twist the head back on.

The thread is the same two-start helix as the poop jars: it closes in about one turn,
and the lid's socket has a 45 degree cone ceiling so the head still prints standing
on its cut face, with no supports. Anything of the body that would hit the head while
it turns (lattice hugging the neck) is cleared.

Downloaded models keep their own license: the output is for your own printing.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from functools import reduce
from pathlib import Path

import manifold3d as m3d
import numpy as np
import trimesh
from shapely.geometry import Point, Polygon

from .poopjar import _cyl, _lid_collar_radius, _neck_ridge, _socket, overhang_area


@dataclass
class ScrewTop:
    body: m3d.Manifold
    lid: m3d.Manifold              # in its closed position
    axis: tuple[float, float]
    cut_z: float
    neck_radius: float
    info: dict = field(default_factory=dict)

    def lid_for_printing(self) -> m3d.Manifold:
        """Standing on its cut face, as it printed in the original model."""
        return self.lid.translate([0.0, 0.0, -self.cut_z - 0.5])


HEAD_OVERHANG_OK = 5.0     # mm² of downward faces a twist-off head may have and still print without supports


def load_model(path: Path, scale: float = 1.0) -> m3d.Manifold:
    geo = trimesh.load(str(path))
    mesh = geo.to_geometry() if hasattr(geo, "to_geometry") else geo
    solid = m3d.Manifold(m3d.Mesh(vert_properties=np.asarray(mesh.vertices, np.float32),
                                  tri_verts=np.asarray(mesh.faces, np.uint32)))
    if solid.status() != m3d.Error.NoError or solid.is_empty():
        raise ValueError(f"{Path(path).name} is not a clean solid ({solid.status()})")
    if scale != 1.0:
        solid = solid.scale([scale, scale, scale])
    lo = np.asarray(solid.bounding_box())
    return solid.translate([-lo[0], -lo[1], -lo[2]])


def _region(solid: m3d.Manifold, z: float):
    polys = [Polygon(p) for p in solid.slice(float(z)).to_polygons() if len(p) > 2]
    if not polys:
        return None
    return reduce(lambda a, b: a.symmetric_difference(b), polys)


def _biggest(region):
    return max(getattr(region, "geoms", [region]), key=lambda g: g.area)


def add_screw_top(cfg: dict, model: m3d.Manifold, cut_z: float, *, min_opening: float = 18.0) -> ScrewTop:
    c = cfg["poop_jar"]
    Ht, wall = c["thread_height"], c["wall"]
    parts = model.decompose()
    # The lid part: the piece with most of its volume above the cut (the head).
    def above_share(p):
        v = p.volume()
        return p.trim_by_plane([0.0, 0.0, 1.0], cut_z).volume() / v if v > 0 else 0.0
    lid_part = max(parts, key=lambda p: (above_share(p) > 0.5, p.trim_by_plane([0.0, 0.0, 1.0], cut_z).volume()))
    others = [p for p in parts if p is not lid_part]

    # Neck axis: the head's cross-section a little above the cut.
    sec = _biggest(_region(lid_part, cut_z + 2.0))
    axis = (float(sec.centroid.x), float(sec.centroid.y))
    ax_pt = Point(axis)
    # The socket needs a full ring of plastic in the head from the cut to the thread top.
    inscribed = min(_biggest(_region(lid_part, z)).exterior.distance(ax_pt)
                    for z in np.linspace(cut_z + 0.6, cut_z + Ht + 0.5, 8))
    RL = inscribed - 1.0                      # leave at least 1 mm of the head outside the socket
    Rn = RL - (2 * c["thread_amplitude"] + c["thread_clearance"] + c["lid_wall"])
    opening = 2 * (Rn - wall)
    if opening < min_opening:
        raise ValueError(f"the head is only {2 * inscribed:.0f} mm across at {cut_z} mm: the opening would be "
                         f"{opening:.0f} mm. Cut higher, or scale the model up.")
    band_z, H = cut_z, cut_z + Ht
    cx, cy = axis

    def at_axis(m):
        return m.translate([cx, cy, 0.0])

    # Body: everything below the cut, plus non-lid parts above it, minus what a turning head would hit.
    lid_raw = lid_part.trim_by_plane([0.0, 0.0, 1.0], cut_z)
    sweep = _sweep(lid_raw, axis, cut_z - 0.6, clearance=1.0)
    pieces = [p.trim_by_plane([0.0, 0.0, -1.0], -cut_z) for p in parts]
    pieces += [p.trim_by_plane([0.0, 0.0, 1.0], cut_z) for p in others]
    # The model's shells overlap (struts poke into the head): join them into one solid.
    body = m3d.Manifold.batch_boolean([p for p in pieces if not p.is_empty()], m3d.OpType.Add)
    cleared = (body ^ sweep).volume()
    body = body - sweep
    # The threaded neck and the filling hole straight down through the old head base.
    lowest = float(np.asarray(lid_part.bounding_box())[2])
    neck = at_axis(_cyl(Rn, cut_z - 2.0, H) + _neck_ridge(c, Rn, band_z, H))
    bore = at_axis(_cyl(Rn - wall, lowest - 1.0, H + 1.0))
    body = (body + neck) - bore
    # Lid: the head above the cut, with a threaded socket and a 45 degree cone ceiling.
    lid = lid_raw - at_axis(_socket(c, Rn, band_z, H))
    lid = lid.trim_by_plane([0.0, 0.0, 1.0], cut_z + 0.5)
    info = {"axis": [round(cx, 1), round(cy, 1)], "cut_z": cut_z, "neck_radius": round(Rn, 2),
            "opening_mm": round(opening, 1), "lid_collar_radius": round(RL, 2),
            "head_inscribed_radius": round(inscribed, 2), "cleared_mm3": round(cleared, 1)}
    return ScrewTop(body, lid, axis, cut_z, Rn, info)


def _sweep(solid: m3d.Manifold, axis, z_from: float, clearance: float) -> m3d.Manifold:
    """The space a part sweeps when it turns about the axis: stacked discs of its
    widest reach at each height, plus clearance."""
    cx, cy = axis
    v = np.asarray(solid.to_mesh().vert_properties)[:, :3]
    r = np.hypot(v[:, 0] - cx, v[:, 1] - cy)
    z = v[:, 2]
    top = float(z.max())
    step = 0.5
    discs = []
    zz = z_from
    while zz < top + step:
        sel = (z >= zz - 1.0) & (z <= zz + step + 1.0)
        if sel.any():
            discs.append(_cyl(float(r[sel].max()) + clearance, zz, zz + step, 96, cx, cy))
        zz += step
    return m3d.Manifold.batch_boolean(discs, m3d.OpType.Add)


def unscrew_check(st: ScrewTop, lead: float, steps: int = 12, direction: int = 1) -> float:
    """Worst overlap (mm³) between the lid and the body while unscrewing one full turn.
    direction 1 is counterclockwise seen from above: how a right-hand thread loosens."""
    cx, cy = st.axis
    worst = 0.0
    for k in range(steps + 1):
        a = direction * 360.0 * k / steps
        moved = (st.lid.translate([-cx, -cy, 0.0]).rotate([0.0, 0.0, a]).translate([cx, cy, lead * k / steps]))
        worst = max(worst, (moved ^ st.body).volume())
    return worst


def write_screw_top(cfg: dict, st: ScrewTop, out_dir: Path, name: str) -> dict[str, Path]:
    from .bambu3mf import write_bambu_3mf
    from .export import write_plate
    from .preview import render_shaded

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    bb = np.asarray(st.body.bounding_box())
    body_p = st.body.translate([-bb[0] + 8.0, -bb[1] + 8.0, -bb[2]])
    lid_p = st.lid_for_printing()
    lb = np.asarray(lid_p.bounding_box())
    lid_p = lid_p.translate([(bb[3] - bb[0]) + 18.0 - lb[0], -lb[1] + 8.0, 0.0])
    paths = {"3mf": write_bambu_3mf([("body", [("body", body_p, 1, (240, 240, 240))]),
                                     ("head", [("head", lid_p, 2, (240, 240, 240))])], out_dir / f"{name}.3mf")}
    paths.update({f"plain-{k}": v for k, v in write_plate({"body": body_p, "head": lid_p}, out_dir, f"{name}-plain").items()})
    paths["preview-closed"] = render_shaded({"body": st.body, "head": st.lid}, out_dir / "preview-closed.png",
                                            view=(15.0, -60.0), px_per_mm=6, labels=False,
                                            colors={"body": (238, 238, 232), "head": (252, 205, 40)})
    paths["preview-plate"] = render_shaded({"body": body_p, "head": lid_p}, out_dir / "preview-plate.png",
                                           view=(30.0, -30.0), px_per_mm=4, labels=False,
                                           colors={"body": (238, 238, 232), "head": (252, 205, 40)})
    # A cutaway through the neck, to see the thread and the socket.
    cx, cy = st.axis
    cut = lambda m: m.trim_by_plane([1.0, 0.0, 0.0], cx).trim_by_plane([0.0, 0.0, -1.0], -(st.cut_z + 40.0))  # noqa: E731
    paths["preview-cutaway"] = render_shaded({"body": cut(st.body).trim_by_plane([0, 0, 1], st.cut_z - 25.0),
                                              "head": cut(st.lid)}, out_dir / "preview-cutaway.png",
                                             view=(0.0, 90.0), px_per_mm=8, labels=False,
                                             colors={"body": (200, 200, 195), "head": (252, 205, 40)})
    i = st.info
    # The socket and thread print without supports; the head's own shape may not (a
    # duck's beak hangs out over the bed). Measure it instead of promising.
    hangs = overhang_area(st.lid_for_printing())
    i["head_overhang_mm2"] = round(hangs, 1)
    if hangs > HEAD_OVERHANG_OK:
        head_line = ("- Print the head standing on its flat cut face. Its own shape (a beak, a chin) hangs out "
                     f"over the bed ({hangs:.0f} mm² steeper than 45 degrees), so turn supports **on** for the head, "
                     "as the original model does: in the Process panel open the **Support** tab, tick **Enable support**, "
                     "set **Type** to **tree(auto)**. The socket and thread inside need none.")
    else:
        head_line = "- Print the head standing on its flat cut face. No supports (the socket has a pointed ceiling)."
    (out_dir / "PRINT_NOTES.md").write_text("\n".join([
        f"# {name}: screw-top version",
        "",
        f"- The head is now a twist-off lid. The opening is {i['opening_mm']:.0f} mm across; the head closes in about one turn.",
        "- Print the body upright, like the original, but with no pause: kids fill it later.",
        head_line,
        "- Layer height 0.20 mm. Same settings as the original model otherwise.",
        "- Print one first and try the head: it should twist shut in about one turn and stay on when shaken. "
        "Too tight or too loose: tell Claude (one setting).",
        "- This is a modified copy of a downloaded model: keep it for your own printing, do not share or upload it.",
        "",
    ]), encoding="utf-8")
    return paths
