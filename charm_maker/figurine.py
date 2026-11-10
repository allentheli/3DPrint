"""Figurines: a drawing inflated into a rounded 3D figure, like a balloon or a plush toy.

No AI: the thickness at each point follows how wide the drawing is there. Each point
takes the radius of the largest circle inside the outline that covers it, so a wide body
becomes a fat round body and an arm becomes a round tube. The kid's colors sit on the
front; the back is blank (characters) or a mirror of the front (patterns). A figurine
prints lying on its back, front up, with tree supports underneath.
"""

from __future__ import annotations

import cv2
import manifold3d as m3d
import numpy as np
from shapely import affinity

from .relief import heightfield

FIELD_RES = 0.25          # mm per pixel for the thickness field


class _Field:
    """A raster over a shape with bilinear sampling (points in mm)."""

    def __init__(self, geom, pad: float = 2.0):
        minx, miny, maxx, maxy = geom.bounds
        self.x0, self.y1 = minx - pad, maxy + pad
        self.w = int(np.ceil((maxx - minx + 2 * pad) / FIELD_RES)) + 1
        self.h = int(np.ceil((maxy - miny + 2 * pad) / FIELD_RES)) + 1
        mask = np.zeros((self.h, self.w), np.uint8)
        for poly in getattr(geom, "geoms", [geom]):
            cv2.fillPoly(mask, [self._px(poly.exterior.coords)], 1)
            for ring in poly.interiors:
                cv2.fillPoly(mask, [self._px(ring.coords)], 0)
        self.dist = cv2.distanceTransform(mask, cv2.DIST_L2, 5).astype(np.float32)   # pixels

    def _px(self, coords):
        a = np.asarray(coords, dtype=np.float64)
        return np.round(np.c_[(a[:, 0] - self.x0) / FIELD_RES, (self.y1 - a[:, 1]) / FIELD_RES]).astype(np.int32)

    def sample(self, arr: np.ndarray, xy: np.ndarray) -> np.ndarray:
        px = (xy[:, 0] - self.x0) / FIELD_RES
        py = (self.y1 - xy[:, 1]) / FIELD_RES
        x0 = np.clip(np.floor(px).astype(int), 0, self.w - 2)
        y0 = np.clip(np.floor(py).astype(int), 0, self.h - 2)
        fx, fy = np.clip(px - x0, 0, 1), np.clip(py - y0, 0, 1)
        top = arr[y0, x0] * (1 - fx) + arr[y0, x0 + 1] * fx
        bot = arr[y0 + 1, x0] * (1 - fx) + arr[y0 + 1, x0 + 1] * fx
        return (top * (1 - fy) + bot * fy).astype(np.float64)


def local_radius(dist_px: np.ndarray) -> np.ndarray:
    """For each pixel, the radius (pixels) of the largest inscribed circle that covers it."""
    R = np.zeros_like(dist_px)
    for r in range(int(dist_px.max()), 0, -1):
        centers = (dist_px >= r).astype(np.uint8)
        if not centers.any():
            continue
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))
        covered = cv2.dilate(centers, k).astype(bool)
        R = np.where(covered & (R < r), r, R)
    return R


def scale_to_figurine(cfg: dict, design) -> float:
    """Scale the drawing so its longest side is the figurine size. Returns the factor."""
    size = cfg["figurine"]["size"]
    minx, miny, maxx, maxy = design.outline.bounds
    k = size / max(maxx - minx, maxy - miny)
    design.outline = affinity.scale(design.outline, k, k, origin=(0, 0))
    for ink in design.inks:
        ink.geometry = affinity.scale(ink.geometry, k, k, origin=(0, 0))
    return k


def build_figurine_parts(cfg: dict, design, back: str | None = None, base: str | None = None):
    """Parts for a figurine lying on its back (drawing in x/y, thickness along z, front up).
    Returns (parts {name: solid}, colors {name: rgb}, base part name, info)."""
    fc = cfg["figurine"]
    back = back or fc["back"]
    base = base or fc["base"]
    if back not in ("blank", "mirror"):
        raise ValueError("figurine back must be 'blank' or 'mirror'")
    if base not in ("flat", "disc", "none"):
        raise ValueError("figurine base must be 'flat', 'disc' or 'none'")
    face = cfg["process"]["color_face_depth"]
    sample = fc["sample"]

    f = _Field(design.outline)
    d = f.dist * FIELD_RES
    R = np.maximum(local_radius(f.dist) * FIELD_RES, d)
    half = fc["roundness"] * np.sqrt(np.clip(d * (2 * R - d), 0, None)) + fc["edge_half_thickness"]
    half = cv2.GaussianBlur(half.astype(np.float32), (0, 0), fc["smoothing_px"])

    def top(xy):
        return f.sample(half, xy)

    whole = heightfield(design.outline, lambda xy: -top(xy), top, sample)
    minx, miny, maxx, maxy = design.outline.bounds
    notes = []
    disc = None
    if base in ("flat", "disc"):
        cut = max(2.0, fc["flat_bottom"] * (maxy - miny))
        whole = whole.trim_by_plane([0.0, 1.0, 0.0], miny + cut)
        notes.append(f"bottom cut flat {cut:.1f} mm up so it stands")
        if base == "disc":
            foot = whole.trim_by_plane([0.0, -1.0, 0.0], -(miny + cut + 0.5))
            fb = np.asarray(foot.bounding_box())
            cx = (fb[0] + fb[3]) / 2 if not foot.is_empty() else (minx + maxx) / 2
            r = fc["disc_radius"] * (maxx - minx)
            disc = (m3d.Manifold.cylinder(fc["disc_thickness"], r, r, 96)
                    .rotate([-90.0, 0.0, 0.0]).translate([cx, miny + cut - fc["disc_thickness"] + 0.5, 0.0]))
            notes.append(f"round base {2 * r:.0f} mm across")

    colors = {}
    parts = {}
    prisms = []
    for ink in design.inks:
        front = heightfield(ink.geometry, lambda xy: top(xy) - face, lambda xy: top(xy) + 30.0, sample)
        prisms.append(front)
        region = front
        if back == "mirror":
            behind = heightfield(ink.geometry, lambda xy: -top(xy) - 30.0, lambda xy: -top(xy) + face, sample)
            prisms.append(behind)
            region = front + behind
        parts[f"{design.name} {ink.name}"] = whole ^ region
        colors[f"{design.name} {ink.name}"] = ink.rgb
    # The round base (if any) is added after the colors, so it stays plain.
    base_part = whole + disc if disc is not None else whole
    for p in prisms:
        base_part = base_part - p
    if disc is not None:
        base_part = base_part + (disc - whole)
    base_name = f"{design.name} base"
    parts = {base_name: base_part, **parts}
    colors = {base_name: design.paper_rgb, **colors}
    # Lie on the back, front up, on the bed.
    z0 = min(float(np.asarray(s.bounding_box())[2]) for s in parts.values())
    parts = {n: s.translate([0.0, 0.0, -z0]) for n, s in parts.items()}
    thick = 2 * float(half.max())
    notes.insert(0, f"figurine: inflated to {thick:.0f} mm at its thickest, back {back}; prints lying on its back with supports")
    info = {"kind": "figurine", "back": back, "base": base, "thickness": round(thick, 1)}
    return parts, colors, base_name, notes, info
