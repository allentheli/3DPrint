"""Shapes that are not flat: puffy pillows and raised outlines.

Built straight from the drawing, nothing redrawn: the puff height at a point comes
from how far that point is from the outline, and the raised ridge follows the
drawing's own dark outline. These pieces print face-up, colors on top, back on the bed.
"""

from __future__ import annotations

import cv2
import manifold3d as m3d
import numpy as np
from shapely.ops import unary_union

from .geom import cylinder, extrude
from .palette import rgb_to_lab

STYLES = ("flat", "puffy", "outlined", "puffy-outlined")


def profile(x: np.ndarray) -> np.ndarray:
    """Quarter-circle rise: 0 at the edge, 1 from x = 1 inward. Rounded, never sharp."""
    x = np.clip(x, 0.0, 1.0)
    return np.sqrt(np.clip(1.0 - (1.0 - x) ** 2, 0.0, 1.0))


class DistanceField:
    """Distance (mm) from any point inside a shape to its nearest edge, sampled from a
    fine raster so it is fast for many mesh vertices at once."""

    def __init__(self, geom, res: float = 0.05, pad: float = 1.0):
        minx, miny, maxx, maxy = geom.bounds
        self.x0, self.y1, self.res = minx - pad, maxy + pad, res
        w = int(np.ceil((maxx - minx + 2 * pad) / res)) + 1
        h = int(np.ceil((maxy - miny + 2 * pad) / res)) + 1
        mask = np.zeros((h, w), np.uint8)
        for poly in getattr(geom, "geoms", [geom]):
            if poly.is_empty:
                continue
            cv2.fillPoly(mask, [self._px(poly.exterior.coords)], 1)
            for ring in poly.interiors:
                cv2.fillPoly(mask, [self._px(ring.coords)], 0)
        self.field = cv2.distanceTransform(mask, cv2.DIST_L2, 5).astype(np.float32) * res

    def _px(self, coords):
        a = np.asarray(coords, dtype=np.float64)
        return np.round(np.c_[(a[:, 0] - self.x0) / self.res, (self.y1 - a[:, 1]) / self.res]).astype(np.int32)

    def __call__(self, xy: np.ndarray) -> np.ndarray:
        """Bilinear sample; zero outside the raster."""
        h, w = self.field.shape
        px = (xy[:, 0] - self.x0) / self.res
        py = (self.y1 - xy[:, 1]) / self.res
        x0 = np.clip(np.floor(px).astype(np.int64), 0, w - 2)
        y0 = np.clip(np.floor(py).astype(np.int64), 0, h - 2)
        fx = np.clip(px - x0, 0.0, 1.0)
        fy = np.clip(py - y0, 0.0, 1.0)
        f = self.field
        top = f[y0, x0] * (1 - fx) + f[y0, x0 + 1] * fx
        bot = f[y0 + 1, x0] * (1 - fx) + f[y0 + 1, x0 + 1] * fx
        return np.clip((top * (1 - fy) + bot * fy).astype(np.float64), 0.0, None)


def heightfield(region, bottom, top, sample: float) -> m3d.Manifold:
    """A solid over a 2D region whose bottom and top follow two height functions."""
    solid = extrude(region, 1.0).refine_to_length(sample)

    def warp(v):
        v = np.array(v, dtype=np.float64)
        b = bottom(v[:, :2])
        t = np.maximum(top(v[:, :2]), b + 0.05)
        v[:, 2] = b + v[:, 2] * (t - b)
        return v

    return solid.warp_batch(warp)


def outline_ink(cfg: dict, design):
    """The ink that draws the outline: black if there is one, else the darkest ink, as
    long as it is dark enough to read as an outline."""
    if not design.inks:
        return None
    darkest = min(design.inks, key=lambda i: rgb_to_lab(i.rgb)[0])
    if rgb_to_lab(darkest.rgb)[0] > cfg["relief"]["outline_max_lightness"]:
        return None
    return darkest


def build_relief_parts(cfg: dict, design, attachment: str | None, info: dict, style: str):
    """Parts for a face-up piece. Returns (parts, base_name, height, notes)."""
    if style not in STYLES or style == "flat":
        raise ValueError(f"unknown relief style {style!r}")
    rc = cfg["relief"]
    prod_r = rc["products"].get(design.product, {"base": 1.6, "puff": 1.6})
    face = cfg["process"]["color_face_depth"]
    puffy = style.startswith("puffy")
    outlined = style.endswith("outlined")
    base_t = prod_r["base"] if puffy else cfg["products"][design.product]["thickness"]
    puff = prod_r["puff"] if puffy else 0.0
    sample = rc["sample"]
    notes = []

    d_out = DistanceField(design.outline)

    def surface(xy):
        return base_t + puff * profile(d_out(xy) / rc["edge_round"])

    def under_face(xy):
        return surface(xy) - face

    ridge_ink = outline_ink(cfg, design) if outlined else None
    if outlined and ridge_ink is None:
        notes.append("no dark outline found, so nothing was raised")
    ridge = None
    if ridge_ink is not None:
        d_ink = DistanceField(ridge_ink.geometry)

        def ridge(xy):
            return rc["outline_raise"] * profile(d_ink(xy) / rc["outline_round"])

    # One solid for the whole drawing, then the colors are cut out of it, so every
    # surface two parts share is the same geometry and they meet exactly. The ridge is
    # its own heightfield over the outline ink only, so it never leaks onto neighbors.
    zero = lambda xy: np.zeros(len(xy))                    # noqa: E731
    whole = heightfield(design.outline, zero, surface, sample)
    if ridge is not None:
        whole = whole + heightfield(ridge_ink.geometry, under_face, lambda xy: surface(xy) + ridge(xy), sample)
    lift = rc["outline_raise"] + 20.0
    parts: dict[str, m3d.Manifold] = {}
    prisms = []
    for ink in design.inks:
        prism = heightfield(ink.geometry, under_face, lambda xy: surface(xy) + lift, sample)
        prisms.append(prism)
        parts[f"{design.name} {ink.name}"] = whole ^ prism
    base = whole
    if attachment == "side_loop":
        base = (base + info["solid"]) - info["hole_solid"]
    for prism in prisms:
        base = base - prism            # also keeps the loop post off the colors
    if attachment == "clip_pocket":
        cx, cy = info["center"]
        base = base - cylinder(info["diameter"], info["depth"] + 1.0, cx, cy, -1.0)
    parts = {f"{design.name} base": base, **parts}
    height = max(p.bounding_box()[5] for p in parts.values())
    label = {"puffy": "puffy", "outlined": "raised outline", "puffy-outlined": "puffy with a raised outline"}[style]
    notes.insert(0, f"{label}: prints face-up, colors on top" + (f", {ridge_ink.name} outline raised {rc['outline_raise']} mm"
                                                                  if ridge_ink is not None else ""))
    return parts, f"{design.name} base", height, notes
