"""Preview images. No GPU: a small software renderer on top of Pillow.

- render_shaded(): an orthographic shaded view of solids, for checking geometry.
- render_plan(): a top-down, actual-size (at a stated DPI) line drawing.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .geom import to_trimesh


def _font(size: int) -> ImageFont.ImageFont:
    for name in ("DejaVuSans-Bold.ttf", "DejaVuSans.ttf", "Arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def render_shaded(solids: dict, path: Path, *, view=(35.0, -30.0), px_per_mm: float = 6.0,
                  light=(-0.4, -0.5, 0.75), labels: bool = True) -> Path:
    """Orthographic shaded render. `view` = (elevation, azimuth) in degrees."""
    elev, azim = (math.radians(v) for v in view)
    # Rotation: azimuth about Z, then elevation about X.
    rz = np.array([[math.cos(azim), -math.sin(azim), 0], [math.sin(azim), math.cos(azim), 0], [0, 0, 1]])
    rx = np.array([[1, 0, 0], [0, math.cos(elev), -math.sin(elev)], [0, math.sin(elev), math.cos(elev)]])
    rot = rx @ rz
    tris = []
    for name, solid in solids.items():
        mesh = to_trimesh(solid)
        v = mesh.vertices @ rot.T
        f = mesh.faces
        n = mesh.face_normals @ rot.T
        tris.append((v[f], n, name, mesh.vertices[f]))
    all_v = np.concatenate([t[0].reshape(-1, 3) for t in tris])
    lo, hi = all_v.min(axis=0), all_v.max(axis=0)
    pad = 10
    w = int((hi[0] - lo[0]) * px_per_mm) + 2 * pad
    h = int((hi[2] - lo[2]) * px_per_mm) + 2 * pad
    # Screen: x -> right, z (after rotation) -> up, y -> depth.
    img = Image.new("RGB", (w, h), (245, 245, 240))
    draw = ImageDraw.Draw(img)
    L = np.asarray(light, dtype=float)
    L /= np.linalg.norm(L)
    faces = []
    for v, n, name, _ in tris:
        depth = v[:, :, 1].mean(axis=1)
        for i in np.argsort(-depth):  # far first
            if n[i][1] > 0.0:  # facing away from the viewer (viewer looks along -y)
                continue
            shade = 0.35 + 0.65 * max(0.0, float(np.dot(n[i], L)))
            faces.append((depth[i], v[i], shade))
    faces.sort(key=lambda t: -t[0])
    for _, tri, shade in faces:
        pts = [(pad + (p[0] - lo[0]) * px_per_mm, h - pad - (p[2] - lo[2]) * px_per_mm) for p in tri]
        c = int(80 + 170 * shade)
        draw.polygon(pts, fill=(c, int(c * 0.9), int(c * 0.6)))
    if labels:
        font = _font(max(10, int(px_per_mm * 3)))
        for v, n, name, _ in tris:
            top = v.reshape(-1, 3)
            x = pad + (top[:, 0].mean() - lo[0]) * px_per_mm
            y = h - pad - (top[:, 2].max() - lo[2]) * px_per_mm - 4
            draw.text((x, y), name, fill=(20, 20, 20), font=font, anchor="ms")
    img.save(path)
    return path


def render_plan(plate, path: Path, *, dpi: int = 300, title: str = "") -> Path:
    """Top-down line drawing of a FitPlate at actual size when printed at `dpi`."""
    from .fittest import FitPlate  # local import to avoid a cycle

    assert isinstance(plate, FitPlate)
    px = dpi / 25.4
    margin_mm = 10
    pw, ph = plate.plate_size
    w = int((pw + 2 * margin_mm) * px)
    h = int((ph + 2 * margin_mm + 12) * px)
    img = Image.new("RGB", (w, h), "white")
    draw = ImageDraw.Draw(img)
    font = _font(int(3.2 * px))
    small = _font(int(2.2 * px))

    def X(x_mm):
        return (margin_mm + x_mm) * px

    def Y(y_mm):
        return h - (margin_mm + y_mm) * px

    for c in plate.coupons:
        name = f"fit-{c.number:02d}"
        ox, oy = plate.positions[name]
        ext = [(X(ox + x), Y(oy + y)) for x, y in c.outline.exterior.coords]
        draw.polygon(ext, outline=(0, 0, 0), width=max(1, int(0.25 * px)))
        fx, fy = c.feature_center
        r = c.feature_size / 2
        bbox = [X(ox + fx - r), Y(oy + fy + r), X(ox + fx + r), Y(oy + fy - r)]
        if c.group == "switch_cutout":
            draw.rectangle(bbox, outline=(200, 0, 0), width=max(1, int(0.2 * px)))
        else:
            draw.ellipse(bbox, outline=(200, 0, 0), width=max(1, int(0.2 * px)))
        if c.group == "stem_socket_clearance":
            s = c.extras["span"] / 2
            draw.line([X(ox + fx - s), Y(oy + fy), X(ox + fx + s), Y(oy + fy)], fill=(200, 0, 0), width=2)
            draw.line([X(ox + fx), Y(oy + fy - s), X(ox + fx), Y(oy + fy + s)], fill=(200, 0, 0), width=2)
        w_mm = c.outline.bounds[2] - c.outline.bounds[0]
        l_mm = c.outline.bounds[3] - c.outline.bounds[1]
        draw.text((X(ox + w_mm / 2), Y(oy + w_mm + (l_mm - w_mm) / 2)), str(c.number),
                  fill=(0, 0, 0), font=font, anchor="mm")
        draw.text((X(ox + w_mm / 2), Y(oy - 0.5)), f"{c.candidate}", fill=(90, 90, 90), font=small, anchor="ma")
    # Stand footprint.
    sx, sy = plate.positions["stand"]
    from .geom import bounds

    lo, hi = bounds(plate.placed["stand"])
    draw.rectangle([X(lo[0]), Y(hi[1]), X(hi[0]), Y(lo[1])], outline=(0, 0, 0), width=max(1, int(0.25 * px)))
    draw.text((X((lo[0] + hi[0]) / 2), Y((lo[1] + hi[1]) / 2)), "stand\n(seen from above)",
              fill=(0, 0, 0), font=small, anchor="mm", align="center")
    # Title and 50 mm check ruler.
    draw.text((X(0), int(2 * px)), title or "Charm Maker fit-test plate", fill=(0, 0, 0), font=font, anchor="la")
    ry = int(7 * px)
    draw.line([X(0), ry, X(50), ry], fill=(0, 0, 0), width=max(1, int(0.3 * px)))
    for t in range(0, 51, 10):
        draw.line([X(t), ry - int(1.5 * px), X(t), ry + int(1.5 * px)], fill=(0, 0, 0), width=max(1, int(0.3 * px)))
    draw.text((X(52), ry), f"50 mm check ruler (print at 100%, {dpi} dpi)", fill=(0, 0, 0), font=small, anchor="lm")
    img.save(path, dpi=(dpi, dpi))
    return path
