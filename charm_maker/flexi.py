"""Flexi toys: a mix-and-match set of ready-made parts on one standard joint.

A toy is a head, a body of 2, 3 or 6 pieces, legs or none, and a tail or none. Neighbor pieces
meet at the same ring joint (`fittest.flexi_joint`, the one on the fit-test plate): the front
piece ends in a round end as wide as the body, with a pocket and an upright pin; the back piece
starts with a matching cup and a tongue ending in the ring around the pin. So any head fits any
body and any body any tail. The kid draws the face on a picture of the head (`face_guide`),
and the drawing is painted onto the head's surface, each color its own part.

Shapes are smooth blended solids (signed distances on a voxel grid, then marching cubes). Each
shape belongs to the pieces it may appear on, so legs are built onto their own piece only and
can never spill onto a neighbor (Allen, 2026-11-13: legs "cannot cross segments").
Coordinates: X forward (the head at +X), Y to the toy's left, Z up; the first joint at X = 0,
joint k at X = -k * piece_length.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import manifold3d as m3d
import numpy as np
from scipy import ndimage

from .fittest import flexi_joint
from .geom import extrude

HEADS = ("cat", "bear", "bunny", "fish")
BODIES = {"short": 2, "regular": 3, "long": 6}
LEGS = ("paws", "none")
TAILS = ("cat", "fin", "none")
FACE_VIEW = {"cat": "front", "bear": "front", "bunny": "front", "fish": "side"}
GUIDE_PPM = 40.0                 # face canvas pixels per mm of the real head


# --- Shapes as signed distances (mm, negative inside) ----------------------------------------

@dataclass
class Shape:
    fn: Callable                 # (X, Y, Z) -> distance
    lo: tuple                    # bounding box
    hi: tuple
    k: float = 0.0               # blend radius into what came before (0: a plain union)
    owners: tuple = ()           # the pieces it belongs to


def _ellipsoid_d(X, Y, Z, c, r, pitch=0.0):
    px, py, pz = X - c[0], Y - c[1], Z - c[2]
    if pitch:                    # tilt about Y: positive lifts the +X end
        a = math.radians(pitch)
        px, pz = px * math.cos(a) + pz * math.sin(a), -px * math.sin(a) + pz * math.cos(a)
    k0 = np.sqrt((px / r[0]) ** 2 + (py / r[1]) ** 2 + (pz / r[2]) ** 2)
    k1 = np.sqrt((px / r[0] ** 2) ** 2 + (py / r[1] ** 2) ** 2 + (pz / r[2] ** 2) ** 2) + 1e-9
    return k0 * (k0 - 1.0) / k1


def ellipsoid(c, r, k=0.0, pitch=0.0) -> Shape:
    e = (max(r[0], r[2]),) * 2 if pitch else (r[0], r[2])
    return Shape(lambda X, Y, Z: _ellipsoid_d(X, Y, Z, c, r, pitch),
                 (c[0] - e[0], c[1] - r[1], c[2] - e[1]), (c[0] + e[0], c[1] + r[1], c[2] + e[1]), k)


def cone(a, b, r0, r1=None, k=0.0, flat=1.0) -> Shape:
    """Rounded cone (a capsule when r1 is r0) from a to b; `flat` squashes it front to back."""
    r1 = r0 if r1 is None else r1
    A, B = np.array(a, np.float32), np.array(b, np.float32)
    ax = B - A
    L = float(np.linalg.norm(ax))
    ax = ax / L

    def fn(X, Y, Z):
        px, py, pz = X - A[0], Y - A[1], Z - A[2]
        t = np.clip(px * ax[0] + py * ax[1] + pz * ax[2], 0, L)
        qx, qy, qz = (px - t * ax[0]) / flat, py - t * ax[1], pz - t * ax[2]
        return np.sqrt(qx ** 2 + qy ** 2 + qz ** 2) - (r0 + (r1 - r0) * t / L)
    r = max(r0, r1)
    return Shape(fn, tuple(np.minimum(A, B) - r), tuple(np.maximum(A, B) + r), k)


def group(shapes: list[Shape], k=0.0) -> Shape:
    """Several shapes blended among themselves (each with its own k), used as one."""
    def fn(X, Y, Z):
        return _blend(shapes, X, Y, Z)
    lo = tuple(min(s.lo[i] for s in shapes) for i in range(3))
    hi = tuple(max(s.hi[i] for s in shapes) for i in range(3))
    return Shape(fn, lo, hi, k)


def smooth_union(a, b, k):
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0, 1)
    return b * (1 - h) + a * h - k * h * (1 - h)


def _blend(shapes, X, Y, Z):
    d = None
    for s in shapes:
        v = s.fn(X, Y, Z)
        d = v if d is None else (np.minimum(d, v) if s.k <= 0 else smooth_union(d, v, s.k))
    return d


def mirrored(make: Callable[[int], Shape], k=0.0) -> Shape:
    """A left and right pair (make(+1), make(-1)) as one shape."""
    return group([make(1), make(-1)], k)


# --- The parts --------------------------------------------------------------------------------

def head_shapes(name: str, zm: float) -> list[Shape]:
    """Ready-made heads, facing +X, the joint at X = 0. Every head has the same neck, which
    holds the joint's pocket and pin."""
    neck = ellipsoid((0.5, 0, zm), (8.0, 8.2, 7.4), k=3.0)
    if name in ("cat", "bear", "bunny"):
        skull = ellipsoid((10.5, 0, 10.5), (9.0, 10.5, 9.5))
        if name == "cat":
            muzzle = ellipsoid((16.5, 0, 7.5), (5.0, 6.8, 4.6), k=2.0)
            ears = mirrored(lambda s: cone((9.7, s * 5.8, 15.5), (9.1, s * 8.4, 23.5), 4.6, 0.9, flat=0.4), k=1.8)
        elif name == "bear":
            muzzle = ellipsoid((16.6, 0, 7.2), (5.4, 6.0, 4.5), k=2.0)
            ears = mirrored(lambda s: ellipsoid((9.6, s * 7.0, 18.6), (1.9, 3.5, 3.5)), k=1.5)
        else:
            muzzle = ellipsoid((16.2, 0, 7.6), (4.6, 6.0, 4.2), k=2.0)
            ears = mirrored(lambda s: cone((9.4, s * 3.8, 16.5), (8.6, s * 5.4, 30.5), 3.0, 2.0, flat=0.45), k=1.5)
        return [skull, muzzle, ears, neck]
    if name == "fish":
        return [ellipsoid((13.0, 0, 9.0), (13.0, 8.0, 8.5)),
                ellipsoid((22.0, 0, 6.8), (5.5, 4.4, 3.8), k=2.5),
                neck]
    raise ValueError(f"unknown head {name!r}; heads: {', '.join(HEADS)}")


def body_shapes(n: int, L: float, zm: float) -> list[list[Shape]]:
    """One rounded segment per body piece, blended into each other: chest, middles, hips."""
    out = []
    for i in range(n):
        xc = -(i + 0.5) * L
        if i == 0:
            s = ellipsoid((xc - 0.25, 0, zm), (9.5, 8.6, 8.0), k=3.0)
        elif i == n - 1:
            s = ellipsoid((xc, 0, zm), (9.5, 8.7, 8.0), k=3.0)
        else:
            s = ellipsoid((xc, 0, zm), (9.0, 8.3, 7.8), k=3.0)
        out.append([s])
    return out


def leg_shapes(kind: str, x_front: float, x_back: float) -> tuple[list[Shape], list[Shape]]:
    """Front legs (on the chest, behind the joint at x_front) and back legs (on the hips,
    behind the joint at x_back): chunky, sticking out sideways, paws resting on the bed."""
    if kind == "none":
        return [], []
    if kind != "paws":
        raise ValueError(f"unknown legs {kind!r}; legs: {', '.join(LEGS)}")
    r = 3.1
    xf = x_front - 9.9

    def front(s):
        return group([cone((xf - 2.5, s * 5.0, 7.0), (xf - 0.5, s * 13.2, 4.6), r),
                      ellipsoid((xf - 0.5, s * 14.6, 4.6), (3.9, 3.7, 3.0), k=1.0)])
    xh = x_back - 11.5

    def back(s):
        return group([ellipsoid((xh, s * 7.2, 7.0), (3.8, 3.6, 4.8)),
                      cone((xh, s * 8.0, 5.0), (xh + 0.3, s * 13.2, 4.6), r, k=1.2),
                      ellipsoid((xh + 0.3, s * 14.6, 4.6), (3.9, 3.7, 3.0), k=1.0)])
    return [mirrored(front, k=2.0)], [mirrored(back, k=2.0)]


def tail_shapes(kind: str, xt: float, zm: float, belly: float) -> list[Shape]:
    """Tails behind the joint at xt. Each starts with the same root, which holds the ring and also
    fills the round end of the piece in front (it nests in the tail's cup)."""
    if kind == "none":
        return []
    if kind == "cat":                          # a tapering tube lying on the bed, curving to one side
        out = [ellipsoid((xt - 6.5, 0, zm), (7.0, 7.0, 6.5), k=3.0)]
        for i in range(9):
            r = 3.8 - 0.2 * i
            out.append(ellipsoid((xt - 10 - 2.1 * i, 0.09 * i * i, belly + r * 0.75), (r, r, r), k=1.5))
        return out
    if kind == "fin":                          # a fish tail: a narrow stalk and an upright fin
        return [ellipsoid((xt - 6.5, 0, zm), (7.0, 7.0, 6.5), k=3.0),
                ellipsoid((xt - 13.0, 0, zm), (6.0, 3.4, 4.6), k=2.5),
                ellipsoid((xt - 20.5, 0, zm + 4.6), (7.5, 1.3, 2.8), pitch=-38, k=1.8),
                ellipsoid((xt - 20.5, 0, zm - 2.6), (7.5, 1.3, 2.8), pitch=38, k=1.8)]
    raise ValueError(f"unknown tail {kind!r}; tails: {', '.join(TAILS)}")


# --- Building a toy ---------------------------------------------------------------------------

@dataclass
class Toy:
    name: str
    parts: dict                                      # head, body, legs, tail choices
    pieces: dict = field(default_factory=dict)       # piece name -> solid, front to back
    paint: dict = field(default_factory=dict)        # "head black" -> solid
    colors: dict = field(default_factory=dict)       # part name -> rgb (preview and 3MF hint)
    joints: list = field(default_factory=list)       # joint X positions
    fixes: list = field(default_factory=list)
    checks: list = field(default_factory=list)
    info: dict = field(default_factory=dict)

    def all_parts(self) -> dict:
        return {**self.pieces, **self.paint}

    def size(self) -> tuple[float, float, float]:
        bb = np.array(m3d.Manifold.batch_boolean(list(self.all_parts().values()), m3d.OpType.Add).bounding_box())
        return tuple(float(v) for v in bb[3:] - bb[:3])


def piece_names(body: str, tail: str) -> list[str]:
    n = BODIES[body]
    middles = ["torso"] if n == 3 else [f"torso-{i}" for i in range(1, n - 1)]
    return ["head", "chest", *middles, "hips"] + ([] if tail == "none" else ["tail"])


def _standard(cfg: dict) -> dict:
    fx = cfg["flexi"]
    j = cfg["fit_test"]["flexi_joint"]
    gap = float(cfg["fit"]["flexi_joint_gap"]["value"])
    lobe_r = j["pin_radius"] + gap + j["ring_width"] + gap + j["cup_wall"]
    # The round end is as wide as the body, so turning never bumps where the pieces nest:
    # radius >= half-width / cos(half the swing), the swing being the joint's stop plus margin.
    rf = max(lobe_r + 1.5, fx["half_width"] / math.cos(math.radians((j["swing"] + 10) / 2)) - gap + 0.2)
    return {"zm": fx["joint_height"], "belly": fx["belly_cut"], "L": fx["piece_length"], "vox": fx["voxel"],
            "gap": gap, "rf": rf, "t": j["thickness"], "tested": bool(cfg["fit"]["flexi_joint_gap"].get("tested"))}


def _grid(lo, hi, vox):
    axes = [np.arange(a, b + vox / 2, vox, dtype=np.float32) for a, b in zip(lo, hi)]
    X, Y, Z = np.meshgrid(*axes, indexing="ij")
    return axes, X, Y, Z


def _solid(field_: np.ndarray, axes, vox: float) -> m3d.Manifold:
    """Marching cubes of a distance field (negative inside) into a solid."""
    from skimage import measure

    vol = np.pad(-field_, 2, constant_values=-1.0)
    if vol.max() <= 0:
        return m3d.Manifold()
    v, f, _, _ = measure.marching_cubes(vol, 0.0)
    v = (v - 2) * vox + np.array([a[0] for a in axes])
    return m3d.Manifold(m3d.Mesh(vert_properties=v.astype(np.float32), tri_verts=f[:, ::-1].astype(np.uint32)))


BIG = 400.0


def _keep_front(x: float, r: float) -> m3d.Manifold:
    """What the piece in front of a joint at x may have: x and forward, plus its round end."""
    return (m3d.Manifold.cylinder(80, r, r, 128).translate([x, 0, -20])
            + m3d.Manifold.cube([BIG, 2 * BIG, 80]).translate([x, -BIG, -20]))


def _keep_back(x: float, r: float, gap: float) -> m3d.Manifold:
    """What the piece behind a joint at x may have: x and back, less the cup around the round end."""
    return (m3d.Manifold.cube([BIG, 2 * BIG, 80]).translate([x - BIG, -BIG, -20])
            - m3d.Manifold.cylinder(80, r + gap, r + gap, 128).translate([x, 0, -20]))


def _clean(m: m3d.Manifold, min_volume: float = 0.01) -> m3d.Manifold:
    """Drop the empty slivers that cutting can leave behind."""
    parts = [p for p in m.decompose() if p.volume() > min_volume]
    return m3d.Manifold.batch_boolean(parts, m3d.OpType.Add) if len(parts) > 1 else (parts[0] if parts else m3d.Manifold())


def _overlaps(a, b) -> bool:
    A, B = a.bounding_box(), b.bounding_box()
    return all(A[i] <= B[i + 3] and B[i] <= A[i + 3] for i in range(3))


def build_toy(cfg: dict, head: str = "cat", body: str = "regular", legs: str = "paws", tail: str = "cat",
              face=None, name: str = "flexi", checks: bool = True) -> Toy:
    """Put a toy together from the library. `face` is the kid's face drawing (a BGR image of
    the face guide, drawn on), or None for a plain head."""
    if head not in HEADS:
        raise ValueError(f"unknown head {head!r}; heads: {', '.join(HEADS)}")
    if body not in BODIES:
        raise ValueError(f"unknown body {body!r}; bodies: {', '.join(BODIES)}")
    st = _standard(cfg)
    zm, L, vox, gap, rf, belly = st["zm"], st["L"], st["vox"], st["gap"], st["rf"], st["belly"]
    names = piece_names(body, tail)
    body_names = names[1:1 + BODIES[body]]
    joints = [-k * L for k in range(len(names) - 1)]
    toy = Toy(name, {"head": head, "body": body, "legs": legs, "tail": tail}, joints=joints)

    shapes: list[Shape] = []
    for s in head_shapes(head, zm):
        s.owners = ("head",)
        shapes.append(s)
    for seg in body_shapes(len(body_names), L, zm):
        for s in seg:
            s.owners = tuple(body_names)
            shapes.append(s)
    front_legs, back_legs = leg_shapes(legs, joints[0], joints[len(body_names) - 1])
    for s in front_legs:
        s.owners = (body_names[0],)
    for s in back_legs:
        s.owners = (body_names[-1],)
    shapes += front_legs + back_legs
    if tail != "none":
        # The tail's root also fills the hips' round end, which nests in the tail's cup.
        for i, s in enumerate(tail_shapes(tail, joints[-1], zm, belly)):
            s.owners = (body_names[-1], "tail") if i == 0 else ("tail",)
            shapes.append(s)
    extras = {body_names[0]: front_legs, body_names[-1]: back_legs}

    joint_parts = []
    for x in joints:
        jt = flexi_joint(cfg, gap, 0.0, 0.0, end_r=rf)
        place = lambda m: m.rotate([0, 0, 180]).translate([x, 0, zm - st["t"] / 2])   # noqa: E731
        joint_parts.append((place(jt["ring"]), place(jt["void"])))

    head_grid = None
    for i, pname in enumerate(names):
        mine = [s for s in shapes if pname in s.owners]
        x_front = joints[i - 1] if i > 0 else None
        x_back = joints[i] if i < len(joints) else None
        lo = [min(s.lo[a] for s in mine) - 1.5 for a in range(3)]
        hi = [max(s.hi[a] for s in mine) + 1.5 for a in range(3)]
        if x_front is not None:
            hi[0] = min(hi[0], x_front + 1.0)
        if x_back is not None:
            lo[0] = max(lo[0], x_back - rf - 1.0)
        lo[2] = belly - 1.0
        if pname == "head":                   # the same grid and field the face guide is drawn from
            axes, d = _head_only(cfg, head)
        else:
            axes, X, Y, Z = _grid(lo, hi, vox)
            d = np.maximum(_blend(mine, X, Y, Z), belly - Z)
        solid = _solid(d, axes, vox)
        region = None
        if x_front is not None:
            region = _keep_back(x_front, rf, gap)
        if x_back is not None:
            region = _keep_front(x_back, rf) if region is None else region ^ _keep_front(x_back, rf)
        piece = solid ^ region if region is not None else solid
        if extras.get(pname) and checks:
            plain = _solid(np.maximum(_blend([s for s in mine if s not in extras[pname]], X, Y, Z), belly - Z), axes, vox)
            lost = ((solid - plain) - piece).volume()
            if lost > 0.5:
                toy.checks.append(f"check: the legs on the {pname} reach past it; {lost:.1f} mm³ was cut off at its edge")
        if x_front is not None:
            piece = piece + joint_parts[i - 1][0]
        if x_back is not None:
            piece = piece - joint_parts[i][1]
        toy.pieces[pname] = _clean(piece)
        if pname == "head":
            head_grid = (axes, d)

    body_rgb = tuple(cfg["flexi"]["body_rgb"])
    toy.colors = {n: body_rgb for n in names}
    if face is not None:
        _paint_face(cfg, toy, face, head_grid)
    if checks:
        _check(cfg, toy, st)
    if not st["tested"]:
        toy.checks.append(f"check: the joint gap ({gap:.2f} mm) is not tested on your printer yet "
                          "(fit-test pieces 19-22)")
    toy.info = {"pieces": names, "joints_mm": [round(x, 2) for x in joints], "gap_mm": gap,
                "round_end_mm": round(rf, 2), "size_mm": [round(v, 1) for v in toy.size()], **toy.info}
    return toy


# --- The face -----------------------------------------------------------------------------------

def _head_only(cfg: dict, head: str):
    st = _standard(cfg)
    shapes = head_shapes(head, st["zm"])
    lo = [min(s.lo[a] for s in shapes) - 1.5 for a in range(3)]
    hi = [max(s.hi[a] for s in shapes) + 1.5 for a in range(3)]
    lo[0] = max(lo[0], -st["rf"] - 1.0)
    lo[2] = st["belly"] - 1.0
    axes, X, Y, Z = _grid(lo, hi, st["vox"])
    d = np.maximum(_blend(shapes, X, Y, Z), st["belly"] - Z)
    d = np.where((X < 0) & (X ** 2 + Y ** 2 > st["rf"] ** 2), np.maximum(d, 0.1), d)   # the round end
    return axes, d


def _canvas(axes, inside, view):
    """The face picture's frame in head mm: (u0, u1, v0, v1). Front: u = Y (the head's left
    is on the right, as you face it); side: u = X (the snout on the right)."""
    a = 1 if view == "front" else 0
    other = 0 if view == "front" else 1
    sil = inside.any(axis=other)                      # [u, z]
    us, vs = np.nonzero(sil)
    m = 1.5
    return (float(axes[a][us.min()] - m), float(axes[a][us.max()] + m),
            float(axes[2][vs.min()] - m), float(axes[2][vs.max()] + m)), sil


def face_guide(cfg: dict, head: str) -> tuple[np.ndarray, tuple]:
    """The picture the kid draws the face on: the head seen from the face's side, softly
    shaded in the card's light guide color (the reader removes it). Returns an RGB image at
    GUIDE_PPM pixels per mm of the head and the frame (u0, u1, v0, v1) in head mm."""
    import cv2

    view = FACE_VIEW[head]
    axes, d = _head_only(cfg, head)
    inside = d < 0
    frame, sil = _canvas(axes, inside, view)
    vox = cfg["flexi"]["voxel"]
    if view == "front":                               # height of the surface toward the viewer
        idx = np.arange(inside.shape[0]).reshape(-1, 1, 1)
        h = np.where(inside, idx, -1).max(axis=0).astype(np.float32) * vox      # [y, z]
        ua = axes[1]
    else:
        idx = np.arange(inside.shape[1]).reshape(1, -1, 1)
        h = np.where(inside, idx, -1).max(axis=1).astype(np.float32) * vox      # [x, z]
        ua = axes[0]
    h = ndimage.gaussian_filter(np.where(sil, h, h[sil].min() - 2), 1.2)
    gu, gv = np.gradient(h, vox)
    n = np.stack([-gu, -gv, np.ones_like(h)])
    n /= np.linalg.norm(n, axis=0)
    light = np.array([-0.45, 0.55, 0.70])
    shade = np.clip((n * light.reshape(3, 1, 1)).sum(0), 0, 1)
    u0, u1, v0, v1 = frame
    W, H = int(round((u1 - u0) * GUIDE_PPM)), int(round((v1 - v0) * GUIDE_PPM))
    za = axes[2]
    ci0, ci1 = int(round((u0 - ua[0]) / vox)), int(round((u1 - ua[0]) / vox))
    ri0, ri1 = int(round((za[-1] - v1) / vox)), int(round((za[-1] - v0) / vox))

    def up(a: np.ndarray, fill: float) -> np.ndarray:
        """[u, z] voxel picture -> the frame at GUIDE_PPM (rows z top down), smoothly scaled."""
        img = np.transpose(a)[::-1].astype(np.float32)
        img = np.pad(img, ((max(0, -ri0), max(0, ri1 - img.shape[0])), (max(0, -ci0), max(0, ci1 - img.shape[1]))),
                     constant_values=fill)
        img = img[max(0, ri0):max(0, ri0) + (ri1 - ri0), max(0, ci0):max(0, ci0) + (ci1 - ci0)]
        return cv2.resize(img, (W, H), interpolation=cv2.INTER_LINEAR)
    # A smooth outline (the voxels' stair steps blurred away) and a soft shading inside it.
    inside_up = cv2.GaussianBlur(up(sil.astype(np.float32), 0.0), (0, 0), GUIDE_PPM * 0.2) > 0.5
    shade_up = up(shade, 1.0)
    line_px = max(2, int(round(cfg["cards"]["guide_line_width"] / cfg["flexi"]["face_guide_scale"] * GUIDE_PPM)))
    rim = inside_up & ~ndimage.binary_erosion(inside_up, iterations=line_px)
    pale, mid, line = np.array([238, 248, 253.0]), np.array([170, 215, 235.0]), np.array([150, 205, 232.0])
    t = (1 - np.clip(shade_up, 0, 1))[..., None] * 0.85
    rgb = np.where(inside_up[..., None], pale * (1 - t) + mid * t, 255.0)
    rgb = np.where(rim[..., None], line, rgb)
    return rgb.clip(0, 255).astype(np.uint8), frame


def _paint_face(cfg: dict, toy: Toy, face, head_grid) -> None:
    """Paint the kid's drawing onto the head from the face's side: each ink color becomes its
    own part, a thin skin of the head's surface that faces that way and is seen first."""
    import cv2
    from shapely import affinity

    from .inks import separate_colors
    from .shape import fix_design

    head = toy.parts["head"]
    view = FACE_VIEW[head]
    axes, d = head_grid
    vox = cfg["flexi"]["voxel"]
    skin_mm = cfg["flexi"]["face_skin"]
    inside = d < 0
    piece = toy.pieces["head"]
    depth = ndimage.distance_transform_edt(inside).astype(np.float32) * vox
    inner = _solid(skin_mm - np.where(inside, ndimage.gaussian_filter(depth, 0.8), -1.0), axes, vox)
    skin = piece - inner
    g = np.gradient(ndimage.gaussian_filter(inside.astype(np.float32), 2.0))
    nx, ny, nz = -g[0], -g[1], -g[2]
    norm = np.sqrt(nx ** 2 + ny ** 2 + nz ** 2) + 1e-9
    reach = (skin_mm + 1.2) / vox

    def seen_from(axis, sign):
        idx = np.arange(inside.shape[axis]).reshape([-1 if a == axis else 1 for a in range(3)])
        if sign > 0:
            first = np.where(inside, idx, -1).max(axis=axis, keepdims=True)
            return inside & (idx >= first - reach)
        first = np.where(inside, idx, 10 ** 6).min(axis=axis, keepdims=True)
        return inside & (idx <= first + reach)
    if view == "front":
        zone = (nx / norm > 0.35) & seen_from(0, +1)
    else:
        zone = (np.abs(ny) / norm > 0.35) & (seen_from(1, +1) | seen_from(1, -1))
    zone = ndimage.binary_dilation(zone & (depth < skin_mm + 1.0), iterations=2)
    zone_solid = _solid(1.0 - 2.0 * ndimage.gaussian_filter(zone.astype(np.float32), 1.0), axes, vox)

    frame, _ = _canvas(axes, inside, view)
    u0, u1, v0, v1 = frame
    W, H = int(round((u1 - u0) * GUIDE_PPM)), int(round((v1 - v0) * GUIDE_PPM))
    img = cv2.resize(np.asarray(face), (W, H), interpolation=cv2.INTER_AREA)
    inks = separate_colors(cfg, img, px_per_mm=GUIDE_PPM, guide_zone=np.ones(img.shape[:2], bool))
    design = fix_design(cfg, inks.layers, GUIDE_PPM, border_on=False, name=f"{toy.name}-face", product="magnet_figure")
    if view == "front":
        to_prism = lambda g: extrude(g, 80, -40).transform([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0]])   # noqa: E731
    else:
        to_prism = lambda g: extrude(g, 80, -40).transform([[1, 0, 0, 0], [0, 0, 1, 0], [0, 1, 0, 0]])   # noqa: E731
    taken = m3d.Manifold()
    painted = []
    for ink in design.inks:
        part = (skin ^ zone_solid ^ to_prism(affinity.translate(ink.geometry, u0, v0))) - taken
        part = _clean(part)
        if part.volume() > 0.05:
            key = f"head {ink.name}"
            toy.paint[key] = part
            toy.colors[key] = tuple(int(c) for c in ink.rgb)
            taken = taken + part
            painted.append(ink.name)
    toy.pieces["head"] = _clean(piece - taken)
    # Charm-only fixes (joining pieces into one charm, its rounded outline) do not apply to a face.
    toy.fixes += [f"face: {f}" for f in design.fixes if "bridge" not in f and "corners rounded" not in f]
    toy.checks += [w if w.startswith("check:") else f"check: face: {w}" for w in design.warnings]
    toy.info["face_colors"] = painted
    if painted:
        toy.fixes.insert(0, f"face painted on the {head} head in {len(painted)} color(s): {', '.join(painted)}")
    else:
        toy.checks.append("check: no drawing found in the face picture; the head is plain")


# --- Checks -----------------------------------------------------------------------------------

def _turn(m: m3d.Manifold, x: float, a: float) -> m3d.Manifold:
    return m.translate([-x, 0, 0]).rotate([0, 0, a]).translate([x, 0, 0])


def joint_swing(front: m3d.Manifold, back: m3d.Manifold, x: float, limit: int = 60) -> tuple[int, int]:
    """How far the back piece turns each way about the joint at x before it touches the front
    piece (degrees, to `limit`)."""
    out = []
    for sign in (1, -1):
        free = 0
        for a in range(4, limit + 1, 4):
            if (_turn(back, x, sign * a) ^ front).volume() > 1e-3:
                break
            free = a
        for a in range(free + 1, min(free + 4, limit + 1)):
            if (_turn(back, x, sign * a) ^ front).volume() > 1e-3:
                break
            free = a
        out.append(free)
    return out[0], out[1]


def _check(cfg: dict, toy: Toy, st: dict) -> None:
    fx = cfg["flexi"]
    names = list(toy.pieces)
    for n, p in toy.pieces.items():
        paint = [s for k, s in toy.paint.items() if k.split()[0] == n]
        whole = m3d.Manifold.batch_boolean([p, *paint], m3d.OpType.Add) if paint else p
        k = sum(1 for c in whole.decompose() if c.volume() > 0.5)
        if k != 1:
            toy.checks.append(f"check: the {n} came out in {k} parts")
    near = fx["fuse_distance"]
    moves = [(near, 0, 0), (-near, 0, 0), (0, near, 0), (0, -near, 0), (0, 0, near), (0, 0, -near)]
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            A, B = toy.pieces[a], toy.pieces[b]
            if not _overlaps(A, B.translate([0, 0, 0])) and not any(_overlaps(A, B.translate(list(m))) for m in moves):
                continue
            if (A ^ B).volume() > 1e-3:
                toy.checks.append(f"check: the {a} and the {b} overlap as printed")
            elif any((A ^ B.translate(list(m))).volume() > 1e-3 for m in moves):
                toy.checks.append(f"check: the {a} and the {b} come within {near} mm of each other as printed "
                                  "and could fuse")
    swings = {}
    for k, x in enumerate(toy.joints):
        a, b = names[k], names[k + 1]
        left, right = joint_swing(toy.pieces[a], toy.pieces[b], x)
        swings[f"{a}-{b}"] = [left, right]
        if min(left, right) < fx["min_swing"]:
            toy.checks.append(f"check: the {a}-{b} joint turns only {min(left, right)} degrees one way "
                              f"before something bumps (less than {fx['min_swing']})")
    toy.info["swing_deg"] = swings


# --- Files ------------------------------------------------------------------------------------

def _posed(toy: Toy, angles: list[float]) -> dict:
    """Every joint turned by its angle, the pieces behind carried along."""
    order = list(toy.pieces)
    posed = toy.all_parts()
    axes2d = [np.array([x, 0.0]) for x in toy.joints]
    for k, ang in enumerate(angles[:len(toy.joints)]):
        cx, cy = axes2d[k]
        behind = set(order[k + 1:])
        for n in list(posed):
            if n.split()[0] in behind:
                posed[n] = posed[n].translate([-cx, -cy, 0]).rotate([0, 0, ang]).translate([cx, cy, 0])
        r = math.radians(ang)
        R = np.array([[math.cos(r), -math.sin(r)], [math.sin(r), math.cos(r)]])
        for j in range(k + 1, len(axes2d)):
            axes2d[j] = np.array([cx, cy]) + R @ (axes2d[j] - np.array([cx, cy]))
    return posed


def render_toy(toy: Toy, path: Path, px_per_mm: float = 7.0) -> Path:
    """Three views: from the front corner, from the side, and wiggled seen from above."""
    import tempfile

    from PIL import Image, ImageDraw

    from .preview import render_shaded

    wiggle = [22, -26, 26, -22, 20, -20, 18][:len(toy.joints)]
    views = [(toy.all_parts(), (25, -55)), (toy.all_parts(), (5, 0)), (_posed(toy, wiggle), (80, -90))]
    ims = []
    with tempfile.TemporaryDirectory() as tmp:
        for i, (parts, view) in enumerate(views):
            p = Path(tmp) / f"v{i}.png"
            render_shaded(parts, p, view=view, px_per_mm=px_per_mm, labels=False, colors=toy.colors)
            ims.append(Image.open(p).convert("RGB"))
    a, s, top = ims
    W = max(a.width, s.width) + top.width + 30
    H = max(a.height + s.height + 50, top.height + 40)
    sheet = Image.new("RGB", (W, H), (244, 244, 240))
    sheet.paste(a, (10, 40))
    sheet.paste(s, (10, 50 + a.height))
    sheet.paste(top, (W - top.width - 10, 30))
    d = ImageDraw.Draw(sheet)
    p = toy.parts
    d.text((10, 10), f"{toy.name}: {p['head']} head, {p['body']} body, legs: {p['legs']}, tail: {p['tail']}   "
               f"({' x '.join(f'{v:.0f}' for v in toy.size())} mm)", fill=(30, 30, 30))
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path)
    return path


def write_toy(cfg: dict, toy: Toy, out_dir: Path) -> dict:
    """The 3MF (one object, every piece and face color its own part, linked as printed), the
    preview, PRINT_NOTES.md and the toy's report (JSON)."""
    from .bambu3mf import write_bambu_3mf

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    parts = toy.all_parts()
    bb = np.array(m3d.Manifold.batch_boolean(list(parts.values()), m3d.OpType.Add).bounding_box())
    bw, bd = cfg["printer"]["bed_size"]
    shift = [-(bb[0] + bb[3]) / 2 + bw / 2, -(bb[1] + bb[4]) / 2 + bd / 2, -bb[2]]
    face = [n for n in toy.paint]
    slots = {n: 1 for n in toy.pieces}
    slots.update({n: 2 + i for i, n in enumerate(face)})
    entries = [(n, s.translate(shift), slots[n], toy.colors[n]) for n, s in parts.items()]
    paths = {"3mf": write_bambu_3mf([(toy.name, entries)], out_dir / f"{toy.name}.3mf")}
    paths["preview"] = render_toy(toy, out_dir / f"{toy.name}-preview.png")
    n_slots = cfg["printer"]["ams_slots"]
    lines = [f"# Print notes: {toy.name}", "",
             f"A flexi toy: {toy.parts['head']} head, {toy.parts['body']} body ({len(toy.pieces) - 1 - (toy.parts['tail'] != 'none')} "
             f"pieces), legs: {toy.parts['legs']}, tail: {toy.parts['tail']}. "
             f"{len(toy.pieces)} pieces linked by {len(toy.joints)} joints, printed already joined. "
             f"About {' x '.join(f'{v:.0f}' for v in toy.size())} mm.", "",
             "## Plate", "",
             f"- Import `{toy.name}.3mf` (**File > Import > Import 3MF/STL/STEP/SVG/OBJ/AMF...**, "
             "**Load geometry only** if asked). It is one object: keep its parts together, do not split it.",
             f"- Layer height: **{cfg['flexi']['layer_height']} mm**. Supports: off. It stands on its flat belly. "
             "Plate: either PEI plate.",
             "- If you ever turn supports on for a toy, also tick **On build plate only** (Support tab), so the "
             "slicer does not fill the gaps in the joints.", "",
             "| Slot | Parts |", "| --- | --- |", f"| 1 | the body: {', '.join(toy.pieces)} |"]
    for n in face:
        lines.append(f"| {slots[n]} | {n} |")
    if len(face) + 1 > n_slots:
        lines.append("")
        lines.append(f"- **{len(face) + 1} colors, {n_slots} AMS slots:** set some face colors to the same filament "
                     "in Bambu Studio.")
    lines += ["", "Any part can take any filament: pick them in Bambu Studio. Face colors change filament on many "
              "layers (the face stands upright), so they add swaps.", "",
              "## After printing", "", "- Gently wiggle each joint, one at a time, until it moves freely.", ""]
    if toy.fixes or toy.checks:
        lines += ["## Fixes and checks", ""] + [f"- {f}" for f in toy.fixes + toy.checks] + [""]
    paths["notes"] = out_dir / "PRINT_NOTES.md"
    paths["notes"].write_text("\n".join(lines))
    report = {"name": toy.name, "parts": toy.parts, "fixes": toy.fixes, "checks": toy.checks,
              "slots": slots, **toy.info}
    paths["report"] = out_dir / f"{toy.name}.json"
    paths["report"].write_text(json.dumps(report, indent=2))
    return paths


def write_guides(cfg: dict, out_dir: Path) -> list[Path]:
    """One face guide picture per head, saved to print at face_guide_scale times real size."""
    from PIL import Image

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    dpi = GUIDE_PPM / cfg["flexi"]["face_guide_scale"] * 25.4
    paths = []
    for h in HEADS:
        img, _ = face_guide(cfg, h)
        p = out_dir / f"{h}-face-guide.png"
        Image.fromarray(img).save(p, dpi=(dpi, dpi))
        paths.append(p)
    return paths


def write_library(cfg: dict, out_dir: Path) -> dict:
    """A picture of every part (each head on a short body, each body and legs, each tail) and
    the face guides."""
    from PIL import Image, ImageDraw

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = [("Heads", [dict(head=h, body="short", legs="paws", tail="none") for h in HEADS]),
            ("Bodies and legs", [dict(head="cat", body=b, legs=lg, tail="none")
                                 for b in BODIES for lg in LEGS if not (b == "long" and lg == "none")]),
            ("Tails", [dict(head="cat", body="short", legs="paws", tail=t) for t in TAILS])]
    import tempfile

    from .preview import render_shaded
    tiles = []
    with tempfile.TemporaryDirectory() as tmp:
        for title, combos in rows:
            row = []
            for c in combos:
                toy = build_toy(cfg, **c, name="part", checks=False)
                p = Path(tmp) / f"{len(tiles)}-{len(row)}.png"
                view = (25, 20) if title == "Tails" else (25, -50)         # tails from the side
                render_shaded(toy.all_parts(), p, view=view, px_per_mm=4.5, labels=False, colors=toy.colors)
                label = {"Heads": c["head"], "Tails": c["tail"]}.get(title, f"{c['body']}, legs: {c['legs']}")
                row.append((label, Image.open(p).convert("RGB")))
            tiles.append((title, row))
    W = max(sum(im.width + 20 for _, im in row) for _, row in tiles) + 20
    H = sum(max(im.height for _, im in row) + 60 for _, row in tiles) + 20
    sheet = Image.new("RGB", (W, H), (248, 248, 244))
    d = ImageDraw.Draw(sheet)
    y = 10
    for title, row in tiles:
        d.text((10, y), title, fill=(20, 20, 20))
        x = 10
        for label, im in row:
            sheet.paste(im, (x, y + 18))
            d.text((x, y + 22 + im.height), label, fill=(60, 60, 60))
            x += im.width + 20
        y += max(im.height for _, im in row) + 60
    lib = out_dir / "library.png"
    sheet.save(lib)
    return {"library": lib, "guides": write_guides(cfg, out_dir / "face-guides")}
