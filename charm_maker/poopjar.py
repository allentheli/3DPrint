"""Poop containers: see-through mesh bodies with a twist-off lid, for kids to fill with
printer poop (purge waste) and take home.

Kinds: a plain jar (round or hex), a rubber duck (mesh duck body, solid duck head that
twists off), a teddy bear (mesh jar, bear head lid) and a heart (mesh jar, puffy heart
lid). All print with no supports:
- mesh holes are diamonds, so every hole has a 45 degree roof;
- every outside slope that faces down is 45 degrees or steeper;
- the thread is an oval outline twisted one turn per lead: a smooth two-start helix
  with gentle flanks that closes in about one turn;
- heads print sitting on their neck opening, so the socket has a 45 degree cone ceiling;
- eyes, beak, muzzle and nose are flush color inlays (separate parts), never bumps.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

import manifold3d as m3d
import numpy as np
from shapely.geometry import Point, Polygon

from .geom import to_cross_section

KINDS = ("jar-round", "jar-hex", "duck", "bear", "heart", "star", "cloud")
OUTLINE_KINDS = ("heart", "star", "cloud")
SHAPES = ("round", "hex")          # kept for the plain jar


# ---------------------------------------------------------------------------
# Small building blocks
# ---------------------------------------------------------------------------

def _cyl(r: float, z0: float, z1: float, n: int = 192, cx: float = 0.0, cy: float = 0.0) -> m3d.Manifold:
    return m3d.Manifold.cylinder(z1 - z0, r, r, n).translate([cx, cy, z0])


def _cone(r0: float, r1: float, z0: float, z1: float, cx: float = 0.0, cy: float = 0.0, n: int = 192) -> m3d.Manifold:
    return m3d.Manifold.cylinder(z1 - z0, r0, r1, n).translate([cx, cy, z0])


def _sphere(r: float, c, n: int = 96) -> m3d.Manifold:
    return m3d.Manifold.sphere(r, n).translate(list(c))


def _slab(poly: Polygon, z: float, t: float = 0.01) -> m3d.Manifold:
    return m3d.Manifold.extrude(to_cross_section(poly), t).translate([0.0, 0.0, z])


def _oval(radius: float, amp: float, n: int = 240) -> m3d.CrossSection:
    t = np.linspace(0.0, 2 * math.pi, n, endpoint=False)
    r = radius + amp * np.cos(2 * t)
    return m3d.CrossSection([np.c_[r * np.cos(t), r * np.sin(t)]])


def helix(radius: float, amp: float, lead: float, z0: float, z_start: float, z_end: float,
          cx: float = 0.0, cy: float = 0.0, d_theta_deg: float = 2.0, dz: float = 0.4) -> m3d.Manifold:
    """Thread solid between z_start and z_end: everything inside r(theta, z) =
    radius + amp * cos(2 * (theta - phi(z))), with phi(z) = 360 * (z - z0) / lead.

    Two crests (a two-start thread) climbing counterclockwise as z rises: a normal
    right-hand thread, so lids tighten clockwise and loosen counterclockwise. Built as an
    even grid of small facets that follow the helix, so its flanks stay as gentle as the
    real surface (the steepest is about 41 degrees from vertical). Phase-locked to z0, so
    a jar and a lid built separately share the same helix."""
    nt = int(round(360.0 / d_theta_deg))
    nz = max(2, int(math.ceil((z_end - z_start) / dz)) + 1)
    th = np.linspace(0.0, 2 * math.pi, nt, endpoint=False)
    zs = np.linspace(z_start, z_end, nz)
    T, Z = np.meshgrid(th, zs)                                     # [nz, nt]
    phi = 2 * math.pi * (Z - z0) / lead
    R = radius + amp * np.cos(2 * (T - phi))
    side = np.c_[(cx + R * np.cos(T)).ravel(), (cy + R * np.sin(T)).ravel(), Z.ravel()]
    bottom_c = len(side)
    top_c = bottom_c + 1
    verts = np.vstack([side, [[cx, cy, z_start], [cx, cy, z_end]]])
    tris = []
    for k in range(nz - 1):
        for i in range(nt):
            a = k * nt + i
            b = k * nt + (i + 1) % nt
            c = (k + 1) * nt + (i + 1) % nt
            d = (k + 1) * nt + i
            tris.append((a, b, c))
            tris.append((a, c, d))
    for i in range(nt):
        tris.append((bottom_c, (i + 1) % nt, i))                         # bottom cap, facing down
        tris.append((top_c, (nz - 1) * nt + i, (nz - 1) * nt + (i + 1) % nt))   # top cap, facing up
    mesh = m3d.Mesh(vert_properties=np.asarray(verts, np.float32), tri_verts=np.asarray(tris, np.uint32))
    solid = m3d.Manifold(mesh)
    if solid.status() != m3d.Error.NoError:
        raise RuntimeError(f"thread mesh is not a valid solid: {solid.status()}")
    return solid


def _diamond_prism(size: float, depth: float) -> m3d.Manifold:
    """Diamond hole shape in the (tangent, height) plane, pushed through the wall along +x
    from x = -(depth - 1) to x = 1."""
    from .products import _xsection_along_x

    d = size / 2.0
    return _xsection_along_x(Polygon([(0, -d), (d, 0), (0, d), (-d, 0)]), depth, -(depth - 1.0))


def _rows(c: dict, z_lo: float, z_hi: float) -> list[tuple[float, int]]:
    pitch = c["hole"] + c["strut"] * math.sqrt(2)
    rows, z, k = [], z_lo + c["hole"] / 2, 0
    while z + c["hole"] / 2 <= z_hi + 1e-6:
        rows.append((z, k % 2))
        z += pitch / 2
        k += 1
    return rows


def _mesh_on_outline(c: dict, outline: Polygon, z_lo: float, z_hi: float) -> list[m3d.Manifold]:
    """Diamond holes through a vertical wall that follows a smooth convex outline."""
    pitch = c["hole"] + c["strut"] * math.sqrt(2)
    ring = outline.exterior
    L = ring.length
    n = max(6, int(L // pitch))
    proto = _diamond_prism(c["hole"], c["wall"] + 2.0)
    holes = []

    def turning(s0):
        """Angle (degrees) between the wall directions 2.5 mm either side of s0."""
        p0, p1, p2 = ring.interpolate((s0 - 2.5) % L), ring.interpolate(s0), ring.interpolate((s0 + 2.5) % L)
        a1 = math.atan2(p1.y - p0.y, p1.x - p0.x)
        a2 = math.atan2(p2.y - p1.y, p2.x - p1.x)
        return abs(math.degrees((a2 - a1 + math.pi) % (2 * math.pi) - math.pi))

    for z, parity in _rows(c, z_lo, z_hi):
        for j in range(n):
            s = (j + 0.5 * parity) / n * L
            if turning(s) > 35.0:
                continue                                          # a sharp corner: keep it solid
            p = ring.interpolate(s)
            a = ring.interpolate((s + 0.5) % L)
            b = ring.interpolate((s - 0.5) % L)
            tx, ty = a.x - b.x, a.y - b.y
            nx, ny = ty, -tx                                   # outward for a CCW ring
            if Polygon(ring).exterior.is_ccw is False:
                nx, ny = -nx, -ny
            ang = math.degrees(math.atan2(ny, nx))
            holes.append(proto.rotate([0.0, 0.0, ang]).translate([p.x, p.y, z]))
    return holes


def _roof_holes(c: dict, region, z_lo: float, z_hi: float) -> list[m3d.Manifold]:
    """Straight-down diamond holes through a sloped roof or shoulder. Their sides are
    vertical, so they print with no supports, and kids can see in from above too."""
    pitch = c["hole"] + c["strut"] * math.sqrt(2)
    if region.is_empty:
        return []
    d = c["hole"] / 2.0
    proto = Polygon([(0, -d), (d, 0), (0, d), (-d, 0)])
    minx, miny, maxx, maxy = region.bounds
    holes = []
    row = 0
    y = miny + d
    while y <= maxy - d:
        x = minx + d + (pitch / 2 if row % 2 else 0.0)
        while x <= maxx - d:
            cell = Polygon([(x + px, y + py) for px, py in proto.exterior.coords])
            if region.contains(cell):
                holes.append(m3d.Manifold.extrude(to_cross_section(cell), z_hi - z_lo).translate([0.0, 0.0, z_lo]))
            x += pitch
        y += pitch / 2
        row += 1
    return holes


def _neck_ridge(c: dict, Rn: float, band_z: float, H: float, cx: float = 0.0) -> m3d.Manifold:
    """Outside thread on the neck, starting with a 45 degree ramp so nothing overhangs."""
    amp, lead = c["thread_amplitude"], c["thread_lead"]
    ridge = helix(Rn + amp, amp, lead, band_z, band_z, H - 0.6, cx)
    ramp = _cone(Rn - 1.0, Rn + 2 * amp + 1.0, band_z, band_z + 2 * amp + 2.0, cx) + _cyl(Rn + 2 * amp + 1.0, band_z + 2 * amp + 2.0, H + 1.0, cx=cx)
    return ridge ^ ramp


def _socket(c: dict, Rn: float, band_z: float, H: float, cx: float = 0.0, cone_ceiling: bool = True) -> m3d.Manifold:
    """The inside of a lid: thread grooves, room for the neck, and (for lids printed on
    their opening) a 45 degree cone ceiling."""
    amp, lead, clear = c["thread_amplitude"], c["thread_lead"], c["thread_clearance"]
    lid_bottom = band_z + 0.5
    s = helix(Rn + amp + clear, amp, lead, band_z, lid_bottom - 1.0, H, cx) + _cyl(Rn + clear, lid_bottom - 1.0, H, cx=cx)
    if cone_ceiling:
        r = Rn + 2 * amp + clear
        s = s + _cone(r, 0.0, H - 0.01, H + r, cx)
    return s


def _lid_collar_radius(c: dict, Rn: float) -> float:
    return Rn + 2 * c["thread_amplitude"] + c["thread_clearance"] + c["lid_wall"]


# ---------------------------------------------------------------------------
# Bodies
# ---------------------------------------------------------------------------

@dataclass
class Body:
    solid: m3d.Manifold
    cavity: m3d.Manifold
    Rn: float          # neck outer radius
    cx: float          # neck center x
    band_z: float      # thread band start
    H: float           # rim height
    holes: int


def body_round(cfg: dict, size: str) -> Body:
    c = cfg["poop_jar"]
    D, H = float(c["sizes"][size]["diameter"]), float(c["sizes"][size]["height"])
    Rn, wall, floor = D / 2.0, c["wall"], c["floor"]
    band_z = H - c["thread_height"]
    solid = _cyl(Rn, 0.0, H)
    cavity = _cyl(Rn - wall, floor, H + 1.0)
    holes = _mesh_on_outline(c, Point(0, 0).buffer(Rn, quad_segs=64), c["bottom_band"], band_z - c["top_band"])
    solid = solid + _neck_ridge(c, Rn, band_z, H) - cavity
    solid = solid - m3d.Manifold.compose(holes)
    return Body(solid, cavity, Rn, 0.0, band_z, H, len(holes))


def body_hex(cfg: dict, size: str) -> Body:
    c = cfg["poop_jar"]
    D, H = float(c["sizes"][size]["diameter"]), float(c["sizes"][size]["height"])
    wall, floor = c["wall"], c["floor"]
    a = D / 2.0
    rc = a / math.cos(math.pi / 6)
    Rn = a - 3.0
    band_z = H - c["thread_height"]
    rc_in = rc - wall / math.cos(math.pi / 6)
    shoulder_h = max(4.0, (rc_in - (Rn - wall)) * c["shoulder_slope"])
    top = band_z - shoulder_h
    hexp = lambda af: Polygon([((af / 2) / math.cos(math.pi / 6) * math.cos(math.radians(60 * k)),   # noqa: E731
                                (af / 2) / math.cos(math.pi / 6) * math.sin(math.radians(60 * k))) for k in range(6)])
    outer, inner = hexp(D), hexp(D - 2 * wall)
    solid = (m3d.Manifold.extrude(to_cross_section(outer), top)
             + m3d.Manifold.batch_hull([_slab(outer, top - 0.01), _cyl(Rn, band_z, band_z + 0.01)])
             + _cyl(Rn, band_z, H))
    cavity = (m3d.Manifold.extrude(to_cross_section(inner), top - floor).translate([0, 0, floor])
              + m3d.Manifold.batch_hull([_slab(inner, top - 0.01), _cyl(Rn - wall, band_z, band_z + 0.01)])
              + _cyl(Rn - wall, band_z - 0.01, H + 1.0))
    pitch = c["hole"] + c["strut"] * math.sqrt(2)
    side = 2 * a * math.tan(math.pi / 6)
    cols = max(1, int((side - 3.0 - c["hole"]) // pitch) + 1)
    proto = _diamond_prism(c["hole"], wall + 2.0)
    holes = []
    for f in range(6):
        normal = 30.0 + 60.0 * f
        for z, parity in _rows(c, c["bottom_band"], top - c["top_band"]):
            k = cols - parity
            for i in range(k):
                u = (-(k - 1) / 2 + i) * pitch
                holes.append(proto.translate([a, u, z]).rotate([0.0, 0.0, normal]))
    roof = outer.buffer(-(wall + 1.5)).difference(Point(0, 0).buffer(Rn + 2.5))
    holes += _roof_holes(c, roof, top - 1.0, band_z - 0.5)
    solid = solid + _neck_ridge(c, Rn, band_z, H) - cavity
    solid = solid - m3d.Manifold.compose(holes)
    return Body(solid, cavity, Rn, 0.0, band_z, H, len(holes))


def body_duck(cfg: dict, size: str) -> Body:
    """An oval duck body: a 45 degree foot, a straight mesh belly, a 45 degree back that
    rises to a round neck set toward the front, and a tail that sweeps up at the back."""
    c = cfg["poop_jar"]
    k = cfg["poop_critters"]["duck"]["scale"][size]
    ax, ay = 32.0 * k, 25.0 * k                         # belly half-length, half-width
    foot = 5.0 * k                                      # 45 degree foot: inset == height
    belly_top = foot + 24.0 * k
    Rn = 14.0 * k
    cx = 7.0 * k                                        # neck toward the front (+x)
    wall, floor = c["wall"], c["floor"]
    belly = _ellipse(ax, ay)
    far = max(Point(x, y).distance(Point(cx, 0)) for x, y in belly.exterior.coords) - Rn
    band_z = belly_top + far * c["shoulder_slope"] + 1.0
    H = band_z + c["thread_height"]
    outer = m3d.Manifold.batch_hull([_slab(belly.buffer(-foot), 0.0), _slab(belly, foot - 0.01),
                                      _slab(belly, belly_top), _cyl(Rn, band_z, band_z + 0.01, cx=cx)])
    tail = m3d.Manifold.batch_hull([_sphere(4.0 * k, (-ax + 4.0 * k, 0.0, belly_top + 2.0 * k), 48),
                                    _sphere(2.2 * k, (-ax - 3.0 * k, 0.0, belly_top + 13.0 * k), 48),
                                    _slab(belly.buffer(-1.0).intersection(Polygon([(-ax - 1, -6 * k), (-ax + 10 * k, -6 * k),
                                                                                    (-ax + 10 * k, 6 * k), (-ax - 1, 6 * k)])),
                                          belly_top - 1.0)])
    solid = outer + tail + _cyl(Rn, band_z, H, cx=cx)
    w2 = wall * math.sqrt(2)
    cavity = (m3d.Manifold.batch_hull([_slab(belly.buffer(-foot - w2 + floor), floor), _slab(belly.buffer(-wall), foot + w2),
                                        _slab(belly.buffer(-wall), belly_top - w2 * 0.4),
                                        _cyl(Rn - wall, band_z - w2, band_z - w2 + 0.01, cx=cx)])
              + _cyl(Rn - wall, band_z - w2, H + 1.0, cx=cx))
    holes = _mesh_on_outline(c, belly, foot + c["bottom_band"] * 0.5, belly_top - c["top_band"])
    roof = (belly.buffer(-(wall + 1.5)).difference(Point(cx, 0).buffer(Rn + 2.5))
            .difference(Polygon([(-ax - 5, -ay), (-ax + 14.0 * k, -ay), (-ax + 14.0 * k, ay), (-ax - 5, ay)])))
    holes += _roof_holes(c, roof, belly_top - 1.0, band_z - 0.5)
    solid = solid + _neck_ridge(c, Rn, band_z, H, cx) - cavity
    solid = solid - m3d.Manifold.compose(holes)
    return Body(solid, cavity, Rn, cx, band_z, H, len(holes))


def body_outline(cfg: dict, size: str, shape: str) -> Body:
    """A jar in the shape of an outline (heart, star, cloud): straight mesh walls, and a
    roof that is a 45 degree cone rising to a round screw neck, so the outside and the
    inside ceiling both print with no supports."""
    import shapely
    from shapely import affinity

    from .cards import outline_shape

    c = cfg["poop_jar"]
    dims = c["sizes"][size]
    W = float(dims["diameter"]) * cfg["poop_critters"]["outline_scale"]
    wall, floor = c["wall"], c["floor"]
    outline = affinity.scale(outline_shape(shape), W, W, origin=(0, 0))
    pole = shapely.maximum_inscribed_circle(outline, tolerance=0.1)
    cx, cy = pole.coords[0]
    inscribed = float(pole.length)
    outline = affinity.translate(outline, -cx, -cy)          # neck on the z axis
    Rn = min(float(dims["diameter"]) / 2.0 * 0.6, inscribed - wall - 1.0)
    reach = max(math.hypot(x, y) for x, y in outline.exterior.coords)
    wall_top_min = c["bottom_band"] + 18.0 + c["top_band"]  # room for a few rows of holes
    band_z = max(float(dims["height"]) - c["thread_height"], wall_top_min + (reach - Rn))
    H = band_z + c["thread_height"]
    cone_h = band_z + Rn
    outer = m3d.Manifold.extrude(to_cross_section(outline), band_z) ^ m3d.Manifold.cylinder(cone_h, cone_h, 0.0, 256)
    inner_outline = outline.buffer(-wall, join_style="mitre")
    w2 = wall * math.sqrt(2)
    cavity = ((m3d.Manifold.extrude(to_cross_section(inner_outline), band_z).translate([0, 0, floor])
               ^ m3d.Manifold.cylinder(cone_h - w2, cone_h - w2, 0.0, 256))
              + _cyl(Rn - wall, band_z - (w2 - wall) - 0.5, H + 1.0))
    solid = outer + _cyl(Rn, band_z - 0.01, H)
    wall_top = band_z - (reach - Rn)
    holes = _mesh_on_outline(c, outline, c["bottom_band"], wall_top - c["top_band"])
    roof = outline.buffer(-(wall + 1.5)).difference(Point(0, 0).buffer(Rn + 2.5))
    holes += _roof_holes(c, roof, wall_top - 1.0, band_z - 0.5)
    solid = solid + _neck_ridge(c, Rn, band_z, H) - cavity
    solid = solid - m3d.Manifold.compose(holes)
    return Body(solid, cavity, Rn, 0.0, band_z, H, len(holes))


def _ellipse(ax: float, ay: float, n: int = 160) -> Polygon:
    t = np.linspace(0, 2 * math.pi, n, endpoint=False)
    return Polygon(np.c_[ax * np.cos(t), ay * np.sin(t)])


# ---------------------------------------------------------------------------
# Lids and heads (built in their closed position on the body)
# ---------------------------------------------------------------------------

def cap_plain(cfg: dict, b: Body) -> tuple[dict, bool]:
    """A round screw lid with grip ribs. Prints upside down (flat top on the bed)."""
    c = cfg["poop_jar"]
    RL = _lid_collar_radius(c, b.Rn)
    lid_bottom, lid_top = b.band_z + 0.5, b.H + c["lid_top"]
    lid = _cyl(RL, lid_bottom, lid_top, cx=b.cx)
    ribs = [_cyl(0.9, lid_bottom + 1.0, lid_top, 24).translate([RL, 0.0, 0.0]).rotate([0, 0, 360.0 * k / c["lid_ribs"]])
            for k in range(c["lid_ribs"])]
    lid = lid + m3d.Manifold.compose(ribs).translate([b.cx, 0.0, 0.0])
    lid = lid - _socket(c, b.Rn, b.band_z, b.H, b.cx, cone_ceiling=False)
    ch = 0.8
    lid = lid - (_cyl(RL + 3.0, lid_top - ch, lid_top + 1.0, cx=b.cx) - _cone(RL + 0.9 + ch, RL - ch, lid_top - ch - 0.9, lid_top + 1.0, b.cx))
    return {"lid": (lid, (236, 72, 153))}, True


def _head_on_collar(c: dict, b: Body, R: float, rise: float = 0.0):
    """A head sphere sitting on the lid collar with a 45 degree underside (hull of the
    collar ring and the sphere), centered over the neck. Returns (solid, center)."""
    RL = _lid_collar_radius(c, b.Rn)
    z0 = b.band_z + 0.5
    zc = max(z0 + R * 0.6, z0 + math.sqrt(2) * R - RL + 2.0) + rise
    center = (b.cx, 0.0, zc)
    head = m3d.Manifold.batch_hull([_cyl(RL, z0, z0 + 2.0, cx=b.cx), _sphere(R, center)])
    # Flat bottom at the lid's edge: it sits on the bed when printing and clears the body.
    return head.trim_by_plane([0.0, 0.0, 1.0], z0), center, RL


def _inlay(solid: m3d.Manifold, center, r: float) -> m3d.Manifold:
    """A flush color patch: the part of the solid inside a small sphere at its surface."""
    return solid ^ _sphere(r, center, 48)


def _surface_point(center, R: float, az_deg: float, el_deg: float, inset: float = 0.0):
    az, el = math.radians(az_deg), math.radians(el_deg)
    rr = R - inset
    return (center[0] + rr * math.cos(el) * math.cos(az), center[1] + rr * math.cos(el) * math.sin(az),
            center[2] + rr * math.sin(el))


def cap_duck(cfg: dict, b: Body) -> tuple[dict, bool]:
    c = cfg["poop_jar"]
    R = b.Rn * 1.35
    head, ctr, RL = _head_on_collar(c, b, R, rise=2.0)
    # Beak: side profile with a 45 degree underside, pushed through the head front.
    from .products import _xsection_along_x  # noqa: F401  (keeps imports local)
    x0 = ctr[0] + R * 0.55
    zb = ctr[2] - R * 0.35
    L = R * 0.75
    prof = Polygon([(x0, zb), (x0 + L, zb + L), (x0 + L + 1.5, zb + L + 1.5), (x0 + L - 1.0, zb + L + 4.5),
                    (x0, zb + R * 0.55)]).buffer(1.2, join_style="round").buffer(-0.6)
    beak2d = m3d.Manifold.extrude(to_cross_section(prof), R * 0.62).translate([0, 0, -R * 0.31])
    beak = beak2d.rotate([90.0, 0.0, 0.0])                # profile (x, z), width along y
    eyes = [_inlay(head, _surface_point(ctr, R, s * 38.0, 22.0), R * 0.16) for s in (-1, 1)]
    head = head + beak
    head = head - _socket(c, b.Rn, b.band_z, b.H, b.cx)
    eyes = [e ^ head for e in eyes]
    beak_part = beak - _socket(c, b.Rn, b.band_z, b.H, b.cx)
    head_part = head - beak_part - m3d.Manifold.compose(eyes)
    return {"head": (head_part, (252, 205, 40)), "beak": (beak_part ^ head, (247, 127, 0)),
            "eyes": (m3d.Manifold.compose(eyes), (25, 25, 30))}, False


def cap_bear(cfg: dict, b: Body) -> tuple[dict, bool]:
    c = cfg["poop_jar"]
    R = b.Rn * 1.18
    head, ctr, RL = _head_on_collar(c, b, R, rise=1.0)
    ears = []
    for s in (-1, 1):
        ec = _surface_point(ctr, R, s * 90.0, 52.0, inset=R * 0.12)
        ears.append(m3d.Manifold.batch_hull([_sphere(R * 0.30, ec, 48), _sphere(R * 0.30, _surface_point(ctr, R, s * 90.0, 30.0, inset=R * 0.45), 48)]))
    head = head + ears[0] + ears[1]
    head = head - _socket(c, b.Rn, b.band_z, b.H, b.cx)
    muzzle = _inlay(head, _surface_point(ctr, R, 0.0, -8.0, inset=-R * 0.05), R * 0.42)
    nose = _inlay(head, _surface_point(ctr, R, 0.0, 2.0), R * 0.12)
    eyes = [_inlay(head, _surface_point(ctr, R, s * 30.0, 22.0), R * 0.10) for s in (-1, 1)]
    dark = nose + eyes[0] + eyes[1]
    muzzle = muzzle - dark
    head_part = head - muzzle - dark
    return {"head": (head_part, (150, 95, 55)), "muzzle": (muzzle, (225, 190, 140)),
            "eyes and nose": (dark, (25, 25, 30))}, False


def cap_heart(cfg: dict, b: Body) -> tuple[dict, bool]:
    """A puffy heart standing on the lid collar."""
    from .cards import outline_shape
    from .relief import DistanceField, heightfield, profile

    c = cfg["poop_jar"]
    RL = _lid_collar_radius(c, b.Rn)
    z0 = b.band_z + 0.5
    W = RL * 2.5
    heart = outline_shape("heart")
    from shapely import affinity
    heart = affinity.scale(heart, W, W, origin=(0, 0))
    half = 5.0
    puff = 6.0
    df = DistanceField(heart)
    top = lambda xy: half + puff * profile(df(xy) / 7.0)          # noqa: E731
    pillow = heightfield(heart, lambda xy: -top(xy), top, 0.6)
    pillow = pillow.rotate([90.0, 0.0, 0.0])                         # heart plane -> (x, z)
    lo = np.asarray(pillow.bounding_box())
    collar_top = b.H + 3.0
    pillow = pillow.translate([b.cx, 0.0, collar_top - 6.0 - lo[2]])
    collar = _cyl(RL, z0, collar_top, cx=b.cx)
    cap = collar + pillow
    cap = cap - _socket(c, b.Rn, b.band_z, b.H, b.cx)
    return {"heart": (cap, (236, 72, 153))}, False


CAPS = {"plain": cap_plain, "duck": cap_duck, "bear": cap_bear, "heart": cap_heart}


# ---------------------------------------------------------------------------
# Containers
# ---------------------------------------------------------------------------

@dataclass
class Container:
    kind: str
    size: str
    body: Body
    cap: dict                      # part name -> (solid in closed position, rgb)
    cap_flip: bool                 # True: print the lid upside down; False: on its opening
    info: dict = field(default_factory=dict)

    @property
    def name(self) -> str:
        return f"poop-{self.kind}-{self.size}"

    @property
    def jar(self) -> m3d.Manifold:
        return self.body.solid

    @property
    def lid(self) -> m3d.Manifold:
        return _union([s for s, _ in self.cap.values()])

    def cap_for_printing(self) -> dict:
        out = {}
        if self.cap_flip:
            parts = {n: s.rotate([180.0, 0.0, 0.0]) for n, (s, _) in self.cap.items()}
        else:
            parts = {n: s for n, (s, _) in self.cap.items()}
        z = min(np.asarray(p.bounding_box())[2] for p in parts.values())
        for n, s in parts.items():
            out[n] = (s.translate([0.0, 0.0, -z]), self.cap[n][1])
        return out


def _union(solids):
    u = solids[0]
    for s in solids[1:]:
        u = u + s
    return u


def build_container(cfg: dict, kind: str = "duck", size: str = "medium") -> Container:
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}")
    if kind == "jar-hex":
        body, cap = body_hex(cfg, size), "plain"
    elif kind == "duck":
        body, cap = body_duck(cfg, size), "duck"
    elif kind in OUTLINE_KINDS:
        body, cap = body_outline(cfg, size, kind), "plain"
    else:
        body, cap = body_round(cfg, size), {"jar-round": "plain", "bear": "bear"}[kind]
    parts, flip = CAPS[cap](cfg, body)
    vol = body.cavity.trim_by_plane([0.0, 0.0, -1.0], -body.H).volume()
    bb = np.asarray(body.solid.bounding_box())
    info = {"holes": body.holes, "hole_size": cfg["poop_jar"]["hole"], "opening_mm": round(2 * (body.Rn - cfg["poop_jar"]["wall"]), 1),
            "volume_ml": round(vol / 1000.0, 1), "body_mm": [round(v, 1) for v in (bb[3] - bb[0], bb[4] - bb[1], bb[5] - bb[2])]}
    return Container(kind, size, body, parts, flip, info)


# Back-compat with the first jar API.
def build_jar(cfg: dict, shape: str = "round", size: str = "medium") -> Container:
    return build_container(cfg, f"jar-{shape}", size)


def unscrew_overlap(cfg: dict, con: "Container", steps: int = 12, direction: int = 1) -> float:
    """Worst overlap (mm³) between lid and body while unscrewing one turn. direction 1 is
    counterclockwise seen from above, which is how a right-hand thread loosens."""
    lead = cfg["poop_jar"]["thread_lead"]
    cx = con.body.cx
    lid = con.lid
    worst = 0.0
    for k in range(steps + 1):
        a = direction * 360.0 * k / steps
        moved = lid.translate([-cx, 0.0, 0.0]).rotate([0.0, 0.0, a]).translate([cx, 0.0, lead * k / steps])
        worst = max(worst, (moved ^ con.jar).volume())
    return worst


def overhang_area(solid: m3d.Manifold, max_angle_deg: float = 45.0, bed_tol: float = 0.05) -> float:
    """Area (mm²) of downward faces steeper than max_angle from vertical, not on the bed."""
    from .geom import to_trimesh

    tm = to_trimesh(solid)
    n = tm.face_normals
    limit = -math.cos(math.radians(max_angle_deg)) - 0.02
    zmin = tm.vertices[:, 2].min()
    on_bed = np.all(np.abs(tm.vertices[tm.faces][:, :, 2] - zmin) < bed_tol, axis=1)
    bad = (n[:, 2] < limit) & ~on_bed
    return float(tm.area_faces[bad].sum())


def poop_blobs(con: Container, n: int = 26, seed: int = 4) -> dict:
    """Fake printer poop inside the body, for the preview picture only."""
    rng = np.random.default_rng(seed)
    colors = [(236, 72, 153), (29, 78, 216), (252, 191, 73), (42, 157, 143), (214, 40, 40), (124, 58, 237), (247, 127, 0)]
    cav = con.body.cavity
    lo, hi = np.asarray(cav.bounding_box())[:3], np.asarray(cav.bounding_box())[3:]
    out, tries = {}, 0
    while len(out) < n and tries < 2000:
        tries += 1
        p = rng.uniform(lo + 3.0, hi - 3.0)
        p[2] = rng.uniform(lo[2] + 2.0, lo[2] + (con.body.band_z - lo[2]) * 0.8)
        s = rng.uniform(3.0, 5.0)
        blob = m3d.Manifold.sphere(1.0, 20).scale([s * rng.uniform(0.8, 1.4), s * rng.uniform(0.6, 1.0), s * rng.uniform(0.5, 0.9)])
        blob = blob.rotate([0, 0, float(rng.uniform(0, 360))]).translate(list(p))
        if (blob - cav).volume() > 0.01:
            continue
        out[f"poop {len(out)}"] = (blob, colors[len(out) % len(colors)])
    return out


def estimate_minutes(cfg: dict, con: Container) -> float:
    c = cfg["poop_jar"]
    vol = con.jar.volume() + con.lid.volume()
    return 4.0 + vol / c["estimate_flow_mm3_per_s"] / 60.0 * c["estimate_mesh_factor"]


def write_containers(cfg: dict, out_dir: Path, kinds=KINDS, sizes=("medium",)) -> list[dict]:
    from .bambu3mf import write_bambu_3mf
    from .export import write_plate
    from .preview import render_shaded

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for kind in kinds:
        for size in sizes:
            con = build_container(cfg, kind, size)
            d = out_dir / con.name
            d.mkdir(exist_ok=True)
            jb = np.asarray(con.jar.bounding_box())
            jar_p = con.jar.translate([-jb[0] + 8.0, -jb[1] + 8.0, -jb[2]])
            cap_p = con.cap_for_printing()
            cb = np.asarray(_union([s for s, _ in cap_p.values()]).bounding_box())
            dx = (jb[3] - jb[0]) + 8.0 + 10.0 - cb[0]
            dy = -cb[1] + 8.0
            cap_p = {n: (s.translate([dx, dy, 0.0]), rgb) for n, (s, rgb) in cap_p.items()}
            objects = [("body", [("body", jar_p, 1, (240, 240, 240))])]
            objects.append(("lid", [(n, s, i + 2, rgb) for i, (n, (s, rgb)) in enumerate(cap_p.items())]))
            write_bambu_3mf(objects, d / f"{con.name}.3mf")
            write_plate({"body": jar_p, **{n: s for n, (s, _) in cap_p.items()}}, d, f"{con.name}-plain")
            scene = {"body": (con.jar, (238, 238, 232)), **con.cap, **poop_blobs(con)}
            render_shaded({k: v[0] for k, v in scene.items()}, d / "preview-filled.png", view=(15.0, 35.0),
                          px_per_mm=8, labels=False, colors={k: v[1] for k, v in scene.items()})
            plate_scene = {"body": (jar_p, (238, 238, 232)), **cap_p}
            render_shaded({k: v[0] for k, v in plate_scene.items()}, d / "preview-plate.png", view=(35.0, 20.0),
                          px_per_mm=5, labels=False, colors={k: v[1] for k, v in plate_scene.items()})
            minutes = estimate_minutes(cfg, con)
            colors = ", ".join(cap_p)
            (d / "PRINT_NOTES.md").write_text("\n".join([
                f"# Poop container: {kind} ({size})",
                "",
                f"- Body about {con.info['body_mm'][0]:.0f} x {con.info['body_mm'][1]:.0f} x {con.info['body_mm'][2]:.0f} mm, holds about {con.info['volume_ml']:.0f} ml.",
                f"- {con.info['holes']} diamond holes, {con.info['hole_size']} mm corner to corner: the poop shows but stays in.",
                f"- The opening is {con.info['opening_mm']:.0f} mm across. The lid closes in about one turn.",
                "- Body prints upright. " + ("The lid prints upside down." if con.cap_flip else
                                             "The head prints standing on its opening (that is why the socket has a pointed ceiling).")
                + " No supports. Layer height 0.20 mm.",
                f"- Lid parts with their own filament: {colors}. The body is one object: pick any filament; a light one shows the poop colors best.",
                "- Print one first and try the lid. It should twist shut in about one turn and stay on when shaken. "
                "Too tight or too loose: tell Claude (one setting).",
                "- At the party: fill, twist shut, check it holds before it goes home. The pieces inside are small parts.",
                "",
                f"My rough estimate is {minutes:.0f} minutes. Bambu Studio's number is the real one.",
                "",
            ]), encoding="utf-8")
            results.append({"container": con, "dir": d, "minutes": minutes})
    return results
