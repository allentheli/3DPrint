"""The universal figure stand: a wide base, a ledge lip, and a tilted upright with
a washer recess on its back. Printed standing on its base, no supports."""

from __future__ import annotations

import math

import manifold3d as m3d
from shapely.geometry import box

from .geom import extrude, rounded_rect, teardrop, to_cross_section


def stand_parts(cfg: dict) -> dict[str, m3d.Manifold]:
    """The stand's pieces in their final positions, before booleans:
    base, upright (solid), lip, recess (to subtract)."""
    s = cfg["stand"]
    hw = cfg["hardware"]
    bw, bd, bt = s["base_width"], s["base_depth"], s["base_thickness"]
    uw, uh, ut = s["upright_width"], s["upright_height"], s["upright_thickness"]
    tilt = s["upright_tilt_deg"]

    # Base: X is width (left-right), Y is depth (front = -Y, back = +Y), Z up.
    base = extrude(rounded_rect(bw, bd, s["base_corner_radius"]), bt)

    # Upright in its own frame: X width, Y thickness (front face at y=0, back at y=ut),
    # Z height from z=-bt (buried in the base) to z=uh.
    washer_d = hw["washer_diameter"] + s["washer_recess_clearance"]
    recess_center_z = hw["magnet_height_above_bottom"]
    upright = _xz_extrude(box(-uw / 2, -bt, uw / 2, uh), ut)
    # The washer recess is a teardrop (45 degree roof) so it prints without supports.
    # It is cut from the back and may reach below the ledge into the base.
    recess = _xz_extrude(teardrop(washer_d, 0.0, recess_center_z), s["washer_recess_depth"] + 0.5)
    recess = recess.translate([0.0, s["front_wall"], 0.0])

    # Lean back: rotate about the front-bottom edge (the X axis through y=0, z=0),
    # then put the foot of the front face at the right depth on the base.
    foot_y = bd / 2 - s["upright_from_back_edge"] - ut * math.cos(math.radians(tilt))
    place = lambda m: m.rotate([-tilt, 0.0, 0.0]).translate([0.0, foot_y, bt])  # noqa: E731
    upright = place(upright)
    recess = place(recess)

    # Lip in front of the upright so the figure's bottom cannot slide forward.
    lip_y = foot_y - s["lip_gap"] - s["lip_thickness"] / 2
    lip = extrude(rounded_rect(uw, s["lip_thickness"], 0.5, 0.0, lip_y), s["lip_height"], bt)
    return {"base": base, "upright": upright, "lip": lip, "recess": recess}


def build_stand(cfg: dict) -> m3d.Manifold:
    p = stand_parts(cfg)
    stand = (p["base"] + p["upright"] + p["lip"]) - p["recess"]
    # Flatten anything buried below the bed.
    return stand.trim_by_plane([0.0, 0.0, 1.0], 0.0)


def _xz_extrude(shape, thickness: float) -> m3d.Manifold:
    """Extrude a shape drawn in (X, height) into a slab (X, Y=thickness, Z=height)."""
    solid = m3d.Manifold.extrude(to_cross_section(shape), thickness)
    # Rotate +90 about X: (x, y, z) -> (x, -z, y). Then mirror Y so thickness is +Y.
    return solid.rotate([90.0, 0.0, 0.0]).mirror([0.0, 1.0, 0.0])
