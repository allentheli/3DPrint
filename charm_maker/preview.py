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
                  light=(-0.4, -0.5, 0.75), labels: bool = True, colors: dict | None = None) -> Path:
    """Orthographic shaded render with a depth buffer. `view` = (elevation, azimuth) degrees."""
    elev, azim = (math.radians(v) for v in view)
    rz = np.array([[math.cos(azim), -math.sin(azim), 0], [math.sin(azim), math.cos(azim), 0], [0, 0, 1]])
    rx = np.array([[1, 0, 0], [0, math.cos(elev), -math.sin(elev)], [0, math.sin(elev), math.cos(elev)]])
    rot = rx @ rz
    L = np.asarray(light, dtype=float)
    L /= np.linalg.norm(L)
    tris = []
    for name, solid in solids.items():
        mesh = to_trimesh(solid)
        v = mesh.vertices @ rot.T
        n = mesh.face_normals @ rot.T
        tris.append((v[mesh.faces], n, name, (colors or {}).get(name, (235, 200, 120))))
    all_v = np.concatenate([t[0].reshape(-1, 3) for t in tris])
    lo, hi = all_v.min(axis=0), all_v.max(axis=0)
    pad = 10
    w = int((hi[0] - lo[0]) * px_per_mm) + 2 * pad
    h = int((hi[2] - lo[2]) * px_per_mm) + 2 * pad
    # Screen: x right, rotated z up, rotated y is depth (viewer looks along -y, so smaller y is nearer).
    color = np.full((h, w, 3), (245, 245, 240), np.uint8)
    depth = np.full((h, w), np.inf)
    for v, n, name, rgb in tris:
        sx = pad + (v[:, :, 0] - lo[0]) * px_per_mm
        sy = h - pad - (v[:, :, 2] - lo[2]) * px_per_mm
        sd = v[:, :, 1]
        facing = n[:, 1] <= 0.0
        shade = 0.45 + 0.75 * np.clip(n @ L, 0.0, 1.0)
        for i in np.flatnonzero(facing):
            _raster_triangle(color, depth, sx[i], sy[i], sd[i], tuple(int(min(255, c * shade[i])) for c in rgb))
    img = Image.fromarray(color)
    if labels:
        draw = ImageDraw.Draw(img)
        font = _font(max(10, int(px_per_mm * 3)))
        for v, n, name, _ in tris:
            top = v.reshape(-1, 3)
            x = pad + (top[:, 0].mean() - lo[0]) * px_per_mm
            y = h - pad - (top[:, 2].max() - lo[2]) * px_per_mm - 4
            draw.text((x, y), name, fill=(20, 20, 20), font=font, anchor="ms")
    img.save(path)
    return path


def _raster_triangle(color, depth, xs, ys, ds, rgb):
    """Fill one screen triangle into the color/depth buffers (nearer = smaller depth)."""
    h, w = depth.shape
    x0, x1 = int(max(0, np.floor(xs.min()))), int(min(w - 1, np.ceil(xs.max())))
    y0, y1 = int(max(0, np.floor(ys.min()))), int(min(h - 1, np.ceil(ys.max())))
    if x1 < x0 or y1 < y0:
        return
    (ax, ay), (bx, by), (cx, cy) = (xs[0], ys[0]), (xs[1], ys[1]), (xs[2], ys[2])
    det = (bx - ax) * (cy - ay) - (cx - ax) * (by - ay)
    if abs(det) < 1e-9:
        return
    gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
    l1 = ((bx - gx) * (cy - gy) - (cx - gx) * (by - gy)) / det
    l2 = ((cx - gx) * (ay - gy) - (ax - gx) * (cy - gy)) / det
    l3 = 1.0 - l1 - l2
    eps = -1e-6
    inside = (l1 >= eps) & (l2 >= eps) & (l3 >= eps)
    if not inside.any():
        return
    d = l1 * ds[0] + l2 * ds[1] + l3 * ds[2]
    sub_depth = depth[y0:y1 + 1, x0:x1 + 1]
    upd = inside & (d < sub_depth)
    sub_depth[upd] = d[upd]
    color[y0:y1 + 1, x0:x1 + 1][upd] = rgb


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
        for part in getattr(c.outline, "geoms", [c.outline]):     # a flexi joint coupon is two pieces
            ext = [(X(ox + x), Y(oy + y)) for x, y in part.exterior.coords]
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
    # Stand footprint (not on a plate that reprints one group).
    if "stand" in plate.placed:
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


def render_plate_map(cfg: dict, plate, path: Path, *, px_per_mm: float = 4.0) -> Path:
    """Who's who: the plate from above with each piece's name on it, so pieces can be
    handed out straight off the bed. The front of the printer is at the bottom."""
    W, H = cfg["printer"]["bed_size"]
    pad, top = 30, 70
    img = Image.new("RGB", (int(W * px_per_mm) + 2 * pad, int(H * px_per_mm) + 2 * pad + top), "white")
    draw = ImageDraw.Draw(img)

    def P(x, y):
        return (pad + x * px_per_mm, top + pad + (H - y) * px_per_mm)

    draw.rectangle([P(0, H), P(W, 0)], outline=(150, 150, 150), width=2)
    draw.text((pad, 18), f"Plate {plate.number} from above: who's who (front of the printer at the bottom)",
              fill=(0, 0, 0), font=_font(26))
    font = _font(max(14, int(px_per_mm * 4.5)))
    taken: list[tuple[float, float, float, float]] = []

    def free(b):
        return not any(b[0] < t[2] and t[0] < b[2] and b[1] < t[3] and t[1] < b[3] for t in taken)

    for pp in plate.pieces:
        u = None
        for solid in pp.solids().values():
            u = solid if u is None else u + solid
        for ring in u.project().to_polygons():
            r = np.asarray(ring, dtype=np.float64)
            if len(r) < 3 or abs(np.dot(r[:, 0], np.roll(r[:, 1], 1)) - np.dot(r[:, 1], np.roll(r[:, 0], 1))) < 4.0:
                continue                                   # specks from inside the solid, not an edge
            draw.polygon([P(x, y) for x, y in r], outline=(60, 60, 60), width=2)
        x0, y0, _, x1, y1, _ = (float(v) for v in u.bounding_box())
        cx, _ = P((x0 + x1) / 2, 0)
        _, y_mid = P(0, (y0 + y1) / 2)
        _, y_top = P(0, y1)
        _, y_bot = P(0, y0)
        # On the piece if there's room, else just above it, else just below, stepping
        # further out until the label is clear of the others.
        spots = [y_mid] + [v for k in range(4) for v in (y_top - 14 - 30 * k, y_bot + 14 + 30 * k)]
        for cy in spots:
            box = draw.textbbox((cx, cy), pp.piece.name, font=font, anchor="mm")
            box = (box[0] - 4, box[1] - 3, box[2] + 4, box[3] + 3)
            if free(box):
                break
        taken.append(box)
        if cy != y_mid:
            draw.line([cx, cy, cx, y_mid], fill=(150, 150, 150), width=1)
        draw.rectangle(list(box), fill=(255, 255, 255), outline=(200, 200, 200))
        draw.text((cx, cy), pp.piece.name, fill=(0, 0, 0), font=font, anchor="mm")
    img.save(path)
    return path


# ---------------------------------------------------------------------------
# Design previews
# ---------------------------------------------------------------------------

def _region_mask(size, geom, origin, px_per_mm, h_px):
    """Rasterize a (Multi)Polygon into an L-mode mask (255 inside)."""
    mask = Image.new("L", size, 0)
    d = ImageDraw.Draw(mask)
    geoms = geom.geoms if hasattr(geom, "geoms") else [geom]
    for poly in geoms:
        if poly.is_empty:
            continue
        ext = [((x - origin[0]) * px_per_mm, h_px - (y - origin[1]) * px_per_mm) for x, y in poly.exterior.coords]
        d.polygon(ext, fill=255)
        for ring in poly.interiors:
            pts = [((x - origin[0]) * px_per_mm, h_px - (y - origin[1]) * px_per_mm) for x, y in ring.coords]
            d.polygon(pts, fill=0)
    return mask


def _draw_piece_face(piece, assignments, px_per_mm: float, pad_mm: float = 2.0,
                     mark_dots: bool = False) -> Image.Image:
    d = piece.design
    minx, miny, maxx, maxy = d.outline.bounds
    origin = (minx - pad_mm, miny - pad_mm)
    w = int((maxx - minx + 2 * pad_mm) * px_per_mm) + 1
    h = int((maxy - miny + 2 * pad_mm) * px_per_mm) + 1
    img = Image.new("RGB", (w, h), (255, 255, 255))
    base_rgb = assignments[piece.base_part].rgb
    outline_mask = _region_mask((w, h), d.outline, origin, px_per_mm, h)
    img.paste(Image.new("RGB", (w, h), base_rgb), mask=outline_mask)
    for ink in d.inks:
        part = f"{d.name} {ink.name}"
        rgb = assignments[part].rgb if part in assignments else ink.rgb
        img.paste(Image.new("RGB", (w, h), rgb), mask=_region_mask((w, h), ink.geometry, origin, px_per_mm, h))
    # Outline edge and attachment hints.
    draw = ImageDraw.Draw(img)
    ext = [((x - origin[0]) * px_per_mm, h - (y - origin[1]) * px_per_mm) for x, y in d.outline.exterior.coords]
    draw.line(ext + ext[:1], fill=(90, 90, 90), width=max(1, int(0.15 * px_per_mm)))
    if mark_dots:   # small dots kept as eyes: easy to spot if one is really a speck
        for x, y in getattr(d, "dots", []):
            _dashed_circle(draw, (x - origin[0]) * px_per_mm, h - (y - origin[1]) * px_per_mm,
                           1.1 * px_per_mm, (40, 110, 230), max(1, int(0.12 * px_per_mm)))
    att = piece.attachment
    if att.get("kind") == "clip_pocket":
        cx, cy = att["center"]
        r = att["diameter"] / 2 * px_per_mm
        x, y = (cx - origin[0]) * px_per_mm, h - (cy - origin[1]) * px_per_mm
        _dashed_circle(draw, x, y, r, (200, 40, 40), max(1, int(0.2 * px_per_mm)))
    elif att.get("kind") == "clicker_case":
        s = att["switch_hole"] / 2
        corners = [(-s, -s), (s, -s), (s, s), (-s, s), (-s, -s)]
        draw.line([((x - origin[0]) * px_per_mm, h - (y - origin[1]) * px_per_mm) for x, y in corners],
                  fill=(200, 40, 40), width=max(1, int(0.2 * px_per_mm)))
        hx, hy = att["hole_center"]          # the ring hole runs left to right: a dashed channel
        rr, half = att["hole_diameter"] / 2, att["post_length"] / 2 + 1.0
        for yy in (hy - rr, hy + rr):
            py = h - (yy - origin[1]) * px_per_mm
            n = max(2, int(2 * half / 0.6))
            for i in range(0, n, 2):
                xa, xb = hx - half + 2 * half * i / n, hx - half + 2 * half * min(i + 1, n) / n
                draw.line([((xa - origin[0]) * px_per_mm, py), ((xb - origin[0]) * px_per_mm, py)],
                          fill=(200, 40, 40), width=max(1, int(0.15 * px_per_mm)))
    elif att.get("kind") == "stem_socket":
        cx, cy = att["center"]
        r = att["post_diameter"] / 2 * px_per_mm
        x, y = (cx - origin[0]) * px_per_mm, h - (cy - origin[1]) * px_per_mm
        _dashed_circle(draw, x, y, r, (200, 40, 40), max(1, int(0.2 * px_per_mm)))
    elif att.get("kind") == "side_loop":
        # The hole runs left to right inside the loop: show it as a dashed channel.
        cx, cy = att["center"]
        r = att["hole_diameter"] / 2
        x0, x1 = cx - att["length"] / 2, cx + att["length"] / 2
        width = max(1, int(0.15 * px_per_mm))
        for yy in (cy - r, cy + r):
            py = h - (yy - origin[1]) * px_per_mm
            steps = max(2, int((x1 - x0) / 0.6))
            for i in range(0, steps, 2):
                xa = x0 + (x1 - x0) * i / steps
                xb = x0 + (x1 - x0) * min(i + 1, steps) / steps
                draw.line([((xa - origin[0]) * px_per_mm, py), ((xb - origin[0]) * px_per_mm, py)],
                          fill=(200, 40, 40), width=width)
    return img


def _dashed_circle(draw, x, y, r, color, width, dashes=24):
    for i in range(dashes):
        a0 = 360 * i / dashes
        a1 = a0 + 360 / dashes * 0.55
        draw.arc([x - r, y - r, x + r, y + r], a0, a1, fill=color, width=width)


def render_design_preview(cfg: dict, piece, assignments: dict, path: Path, *, palette_ready: bool,
                          slot_labels: dict | None = None, render_path: Path | None = None) -> Path:
    """Actual size (at preview dpi) and zoomed views, swatches, the name crop and the fix list."""
    pv = cfg["preview"]
    dpi, zoom = pv["dpi"], pv["zoom"]
    ppm = dpi / 25.4
    d = piece.design
    actual = _draw_piece_face(piece, assignments, ppm)
    big = _draw_piece_face(piece, assignments, ppm * zoom, mark_dots=True)
    # Cap the zoomed view so the sheet stays reasonable.
    max_big = 1400
    if max(big.size) > max_big:
        f = max_big / max(big.size)
        big = big.resize((int(big.size[0] * f), int(big.size[1] * f)), Image.LANCZOS)
    font = _font(28)
    small = _font(22)
    pad = 24
    text_w = 620
    width = pad + actual.size[0] + pad + big.size[0] + pad + text_w + pad
    height = max(actual.size[1], big.size[1]) + 2 * pad + 60
    style_word = {"flat": "flat, prints face-down", "puffy": "puffy, prints face-up",
                  "outlined": "raised outline, prints face-up",
                  "puffy-outlined": "puffy + raised outline, prints face-up",
                  "figurine": "figurine front, flat back, prints face-up",
                  "case": "clicker case, prints upright"}.get(getattr(piece, "style", "flat"), "")
    if getattr(piece, "supports", False):
        style_word = f"round figurine, back {piece.attachment.get('back')}, prints lying on its back with supports"
    lines = [f"{d.name}: {cfg['products'][d.product]['label']}" + (f" (card {d.card})" if d.card else ""),
             f"size {piece.size()[0]:.1f} x {piece.size()[1]:.1f} mm, {piece.thickness} mm thick",
             f"style: {style_word}", ""]
    lines.append("Colors:")
    swatches = []
    for part, f in assignments.items():
        short = part[len(d.name) + 1:]
        if slot_labels and part in slot_labels:
            slot = slot_labels[part]
        else:
            slot = f"slot {f.slot}" if f.slot else "slot: assign in Bambu Studio"
        swatches.append((f.rgb, f"{short} -> {f.name} ({slot})"))
    att = piece.attachment
    if att.get("kind") == "clip_pocket":
        lines_att = [f"Clip pad pocket {att['diameter']} mm (dashed), {att['wall']:.1f} mm wall"]
    elif att.get("kind") == "ring_tab":
        lines_att = ([f"Small tab on top: {att['hole_diameter']} mm hole front to back for a jump ring, "
                      f"{att['wall']:g} mm of plastic around it"] if att.get("ring") == "jump ring"
                     else [f"Ring tab at the {att['position']}, {att['hole_diameter']} mm hole"])
    elif att.get("kind") == "side_loop":
        lines_att = [f"Loop on top: {att['hole_diameter']} mm hole running left to right (dashed), "
                     f"{att['height']:.1f} mm tall on the back"]
    elif att.get("kind") == "flat_back":
        lines_att = [f"Flat back: glue the magnet on, about {cfg['hardware']['magnet_height_above_bottom']:.0f} mm "
                     "above the bottom to line up with the stand"]
    elif att.get("kind") == "stem_socket":
        lines_att = [f"Keycap post {att['post_diameter']} mm (dashed) with a cross socket, stem fit {att['clearance']} mm; "
                     f"clears the switch by {att['travel_clearance']:.1f} mm when pressed"]
    elif att.get("kind") == "clicker_case":
        lines_att = [f"Clicker case: {att['switch_hole']} mm switch hole; ring hole {att['hole_diameter']} mm running "
                     f"left to right at half height (dashed); {att['height']:.1f} mm tall"]
    else:
        lines_att = []
    fixes = ["Fixes made:"] + [f"- {x}" for x in d.fixes]
    warns = (["Check:"] + [f"- {x}" for x in d.warnings]) if d.warnings else []
    name_img = None
    if d.name_image is not None and d.name_image.size:
        name_img = Image.fromarray(d.name_image[:, :, ::-1])
        f = min(1.0, (text_w - 10) / name_img.size[0])
        name_img = name_img.resize((int(name_img.size[0] * f), int(name_img.size[1] * f)), Image.LANCZOS)
    n_text = sum(len(_wrap(l, small, text_w - 10)) for l in lines_att + fixes + warns) + 2
    n_text += sum(len(_wrap(l, small, text_w - 46)) for _, l in swatches)
    shot = None
    if render_path is not None and Path(render_path).exists():
        shot = Image.open(render_path).convert("RGB")
        f = min(1.0, (text_w - 10) / shot.size[0], 380 / shot.size[1])
        shot = shot.resize((max(1, int(shot.size[0] * f)), max(1, int(shot.size[1] * f))), Image.LANCZOS)
    text_h = 40 * len(lines) + 4 * len(swatches) + 30 * n_text + (name_img.size[1] + 40 if name_img else 0) + 40
    text_h += shot.size[1] + 40 if shot else 0
    height = max(height, text_h + 2 * pad)
    sheet = Image.new("RGB", (int(width), int(height)), (255, 255, 255))
    sheet.paste(actual, (pad, pad + 40))
    sheet.paste(big, (pad + actual.size[0] + pad, pad + 40))
    draw = ImageDraw.Draw(sheet)
    draw.text((pad, pad), f"actual size at {dpi} dpi", fill=(0, 0, 0), font=small)
    draw.text((pad + actual.size[0] + pad, pad), f"{zoom}x zoom", fill=(0, 0, 0), font=small)
    x = pad + actual.size[0] + pad + big.size[0] + pad
    y = pad
    for i, line in enumerate(lines):
        draw.text((x, y), line, fill=(0, 0, 0), font=font if i == 0 else small)
        y += 40 if i == 0 else 30
    for rgb, label in swatches:
        draw.rectangle([x, y, x + 26, y + 26], fill=rgb, outline=(0, 0, 0))
        for i, part_line in enumerate(_wrap(label, small, text_w - 46)):
            draw.text((x + 36, y), part_line, fill=(0, 0, 0), font=small)
            y += 30
        y += 4
    if not palette_ready:
        draw.text((x, y), "(no loaded slots in config: generic palette)", fill=(160, 60, 60), font=small)
        y += 30
    y += 10
    for line in lines_att + [""] + fixes + [""] + warns:
        for part_line in _wrap(line, small, text_w - 10):
            draw.text((x, y), part_line, fill=(0, 0, 0) if not line.startswith("Check") else (160, 60, 60), font=small)
            y += 30
    if name_img is not None:
        draw.text((x, y), "Name on the card:", fill=(0, 0, 0), font=small)
        y += 32
        sheet.paste(name_img, (x, y))
        draw.rectangle([x, y, x + name_img.size[0], y + name_img.size[1]], outline=(120, 120, 120))
        y += name_img.size[1] + 12
    if shot is not None:
        draw.text((x, y), "3D view of the front:", fill=(0, 0, 0), font=small)
        y += 32
        sheet.paste(shot, (x, y))
    sheet.save(path, dpi=(dpi, dpi))
    return path


def _wrap(text: str, font, max_w: int) -> list[str]:
    words = text.split(" ")
    lines, cur = [], ""
    for wd in words:
        trial = (cur + " " + wd).strip()
        if font.getlength(trial) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = "  " + wd
    if cur:
        lines.append(cur)
    return lines or [""]


def render_contact_sheet(previews: list[Path], path: Path, *, title: str = "", cell_w: int = 900) -> Path:
    imgs = [Image.open(p) for p in previews]
    if not imgs:
        raise ValueError("nothing to put on the contact sheet")
    cols = 2 if len(imgs) > 1 else 1
    thumbs = []
    for im in imgs:
        f = cell_w / im.size[0]
        thumbs.append(im.resize((cell_w, int(im.size[1] * f)), Image.LANCZOS))
    rows = (len(thumbs) + cols - 1) // cols
    row_h = [max(t.size[1] for t in thumbs[r * cols:(r + 1) * cols]) for r in range(rows)]
    pad = 20
    W = cols * (cell_w + pad) + pad
    H = sum(row_h) + rows * pad + pad + 60
    sheet = Image.new("RGB", (W, H), (240, 240, 240))
    draw = ImageDraw.Draw(sheet)
    draw.text((pad, pad), f"Contact sheet: {title} ({len(imgs)} designs)", fill=(0, 0, 0), font=_font(34))
    y = pad + 60
    for r in range(rows):
        for c in range(cols):
            i = r * cols + c
            if i >= len(thumbs):
                break
            sheet.paste(thumbs[i], (pad + c * (cell_w + pad), y))
        y += row_h[r] + pad
    sheet.save(path)
    return path
