"""2D and 3D geometry helpers shared by every product builder.

2D shapes are Shapely polygons in millimetres (X right, Y up, as seen on the
card). Solids are manifold3d Manifolds. Z is thickness, Z=0 is the print bed.
"""

from __future__ import annotations

import math

import manifold3d as m3d
import numpy as np
import trimesh
from shapely import affinity
from shapely.geometry import LineString, Point, Polygon, box
from shapely.geometry.polygon import orient
from shapely.ops import unary_union

CIRCLE_SEGMENTS = 96


def circle(diameter: float, cx: float = 0.0, cy: float = 0.0) -> Polygon:
    """A circle polygon with enough segments to print smooth."""
    return Point(cx, cy).buffer(diameter / 2.0, quad_segs=CIRCLE_SEGMENTS // 4)


def rounded_rect(width: float, height: float, radius: float, cx: float = 0.0, cy: float = 0.0) -> Polygon:
    """A rectangle with rounded corners, centred on (cx, cy)."""
    radius = max(0.0, min(radius, width / 2.0, height / 2.0))
    inner = box(cx - width / 2 + radius, cy - height / 2 + radius, cx + width / 2 - radius, cy + height / 2 - radius)
    if radius == 0:
        return inner
    return inner.buffer(radius, quad_segs=16)


def square(size: float, cx: float = 0.0, cy: float = 0.0) -> Polygon:
    return box(cx - size / 2, cy - size / 2, cx + size / 2, cy + size / 2)


def plus(span: float, arm_x: float, arm_y: float, cx: float = 0.0, cy: float = 0.0) -> Polygon:
    """A plus shape: a left-right bar of width `arm_x` and a front-back bar of width `arm_y`."""
    bar_lr = box(cx - span / 2, cy - arm_x / 2, cx + span / 2, cy + arm_x / 2)
    bar_fb = box(cx - arm_y / 2, cy - span / 2, cx + arm_y / 2, cy + span / 2)
    return unary_union([bar_lr, bar_fb])


def teardrop(diameter: float, cx: float = 0.0, cy: float = 0.0) -> Polygon:
    """A circle with a 45 degree pointed roof, so it prints as a vertical-wall
    recess without supports. The point is at +Y (up when printed upright)."""
    r = diameter / 2.0
    c = circle(diameter, cx, cy)
    k = r / math.sqrt(2.0)
    roof = Polygon([(cx - k, cy + k), (cx, cy + r * math.sqrt(2.0)), (cx + k, cy + k)])
    return unary_union([c, roof])


def stroke_polygon(points: list[tuple[float, float]], width: float) -> Polygon:
    return LineString(points).buffer(width / 2.0, quad_segs=8)


def to_cross_section(shape) -> m3d.CrossSection:
    """Convert a Shapely (Multi)Polygon to a manifold CrossSection."""
    geoms = list(shape.geoms) if hasattr(shape, "geoms") else [shape]
    contours = []
    for poly in geoms:
        if poly.is_empty:
            continue
        poly = orient(poly, 1.0)  # CCW exterior, CW holes
        contours.append(np.asarray(poly.exterior.coords[:-1], dtype=np.float64))
        for ring in poly.interiors:
            contours.append(np.asarray(ring.coords[:-1], dtype=np.float64))
    if not contours:
        return m3d.CrossSection()
    return m3d.CrossSection(contours, m3d.FillRule.Positive)


def extrude(shape, height: float, z0: float = 0.0) -> m3d.Manifold:
    """Extrude a Shapely shape from z0 up by `height`."""
    solid = m3d.Manifold.extrude(to_cross_section(shape), height)
    if z0:
        solid = solid.translate([0.0, 0.0, z0])
    return solid


def cylinder(diameter: float, height: float, cx: float = 0.0, cy: float = 0.0, z0: float = 0.0) -> m3d.Manifold:
    c = m3d.Manifold.cylinder(height, diameter / 2.0, diameter / 2.0, CIRCLE_SEGMENTS)
    return c.translate([cx, cy, z0])


def rotate_x(solid: m3d.Manifold, degrees: float) -> m3d.Manifold:
    return solid.rotate([degrees, 0.0, 0.0])


def to_trimesh(solid: m3d.Manifold) -> trimesh.Trimesh:
    mesh = solid.to_mesh()
    verts = np.asarray(mesh.vert_properties)[:, :3]
    faces = np.asarray(mesh.tri_verts)
    return trimesh.Trimesh(vertices=verts, faces=faces, process=False)


def bounds(solid: m3d.Manifold) -> tuple[np.ndarray, np.ndarray]:
    bb = np.asarray(solid.bounding_box(), dtype=np.float64)
    return bb[:3], bb[3:]


def size(solid: m3d.Manifold) -> np.ndarray:
    lo, hi = bounds(solid)
    return hi - lo


def move_to(solid: m3d.Manifold, x: float, y: float) -> m3d.Manifold:
    """Translate so the solid's bounding box min corner is at (x, y) and z min is 0."""
    lo, _ = bounds(solid)
    return solid.translate([x - lo[0], y - lo[1], -lo[2]])


def translate_shape(shape, dx: float, dy: float):
    return affinity.translate(shape, dx, dy)


def count_bodies(solid: m3d.Manifold, min_volume: float = 1e-3) -> int:
    """Connected parts with real volume. Booleans between touching parts can leave
    zero-volume shells, which are not pieces."""
    return sum(1 for part in solid.decompose() if abs(part.volume()) > min_volume)
