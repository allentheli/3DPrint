"""Photos in, plates out. Orchestrates reader -> inks -> fixes -> product -> plates."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

from .filaments import Filament, load_filaments, parse_overrides
from .inks import separate_inks
from .plates import Plate, pack_plates, write_plates
from .products import Piece, build_piece
from .reader import CardRead, load_image, pdf_page_count, read_card
from .shape import Design, fix_design

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".pdf", ".tif", ".tiff", ".bmp", ".webp"}


@dataclass
class BatchResult:
    pieces: list[Piece]
    plates: list[Plate]
    files: dict
    filaments_from_config: bool
    problems: list[str] = field(default_factory=list)


def collect_inputs(paths: list[Path]) -> list[Path]:
    out: list[Path] = []
    for p in paths:
        p = Path(p)
        if p.is_dir():
            out.extend(sorted(q for q in p.iterdir() if q.suffix.lower() in IMAGE_SUFFIXES))
        elif p.exists():
            out.append(p)
        else:
            raise FileNotFoundError(p)
    return out


def design_from_read(cfg: dict, read: CardRead, *, product_hint: str | None, border: bool | None,
                     name: str) -> Design:
    rd = cfg["reader"]
    pr = cfg["process"]
    scale = pr["card_scale"]
    if read.layout is not None:
        product = read.layout.product
        audience = cfg["products"][product]["audience"]
        max_colors = pr["kid_card_max_colors"] if audience == "kids" else pr["adult_card_max_colors"]
        px_per_mm = read.px_per_card_mm * scale        # real-size px per mm
        # Ignore a thin band along the printed box edge (the guide line lives there).
        ignore = _box_edge_band(cfg, read)
        inks = separate_inks(cfg, read.box_image, max_colors, ignore)
        if border is None:
            border = pr["border_default_kid_cards"] if audience == "kids" else pr["border_default_adult_cards"]
        design = fix_design(cfg, inks.layers, px_per_mm, border_on=border, name=name, product=product)
        design.paper_rgb = inks.paper_rgb
        design.warnings.extend(inks.notes + read.notes)
        design.name_image = read.name_image
        return design

    # Fallback: no markers. Use the whole image, scale the ink to the default size.
    product = product_hint
    assert product is not None
    audience = cfg["products"][product]["audience"]
    max_colors = pr["kid_card_max_colors"] if audience == "kids" else pr["adult_card_max_colors"]
    img = read.box_image
    h, w = img.shape[:2]
    f = min(1.0, 1600.0 / max(h, w))
    small = cv2.resize(img, (int(w * f), int(h * f)), interpolation=cv2.INTER_AREA) if f < 1 else img
    coarse = separate_inks(cfg, small, max_colors)
    union = np.zeros(small.shape[:2], bool)
    for layer in coarse.layers:
        union |= layer.mask
    union = cv2.morphologyEx(union.astype(np.uint8), cv2.MORPH_OPEN, np.ones((5, 5), np.uint8)).astype(bool)
    if not union.any():
        raise ValueError("no ink found in the image")
    ys, xs = np.nonzero(union)
    longest_px = max(xs.max() - xs.min(), ys.max() - ys.min()) + 1
    size_mm = cfg["products"][product]["default_size"]
    target_ppm = cfg["reader"]["px_per_card_mm"] * scale
    resize = target_ppm * size_mm / longest_px
    pad = 10
    crop = small[max(ys.min() - pad, 0):ys.max() + pad, max(xs.min() - pad, 0):xs.max() + pad]
    crop = cv2.resize(crop, (int(crop.shape[1] * resize), int(crop.shape[0] * resize)), interpolation=cv2.INTER_CUBIC)
    inks = separate_inks(cfg, crop, max_colors)
    if border is None:
        border = pr["border_default_kid_cards"] if audience == "kids" else pr["border_default_adult_cards"]
    design = fix_design(cfg, inks.layers, target_ppm, border_on=border, name=name, product=product)
    design.paper_rgb = inks.paper_rgb
    design.warnings.extend(inks.notes + read.notes)
    design.fixes.append(f"scaled so the longest side is {size_mm} mm (no card markers)")
    return design


def _box_edge_band(cfg: dict, read: CardRead) -> np.ndarray:
    lay = read.layout
    ppm = read.px_per_card_mm
    bx, by, bw, bh = lay.box
    ox, oy = read.box_origin_mm          # crop top-left in card mm (y up)
    band = cfg["reader"]["edge_band"]
    h, w = read.box_image.shape[:2]
    mask = np.zeros((h, w), np.uint8)
    # Rectangle corners of the box in crop pixels.
    x0, x1 = (bx - ox) * ppm, (bx + bw - ox) * ppm
    y0, y1 = (oy - (by + bh)) * ppm, (oy - by) * ppm
    r = 3 * ppm   # the box has 3 mm rounded corners
    pts = _rounded_rect_pts(x0, y0, x1, y1, r)
    cv2.polylines(mask, [pts], True, 1, thickness=max(1, int(round(2 * band * ppm))))
    # Also everything outside the box plus margin is not a drawing.
    outside = np.ones((h, w), np.uint8)
    cv2.fillPoly(outside, [_rounded_rect_pts(x0 - band * ppm, y0 - band * ppm, x1 + band * ppm, y1 + band * ppm, r)], 0)
    return (mask | outside).astype(bool)


def _rounded_rect_pts(x0, y0, x1, y1, r, n=8):
    pts = []
    for cx, cy, a0 in ((x1 - r, y0 + r, 270), (x1 - r, y1 - r, 0), (x0 + r, y1 - r, 90), (x0 + r, y0 + r, 180)):
        for i in range(n + 1):
            a = np.radians(a0 + 90 * i / n)
            pts.append((cx + r * np.cos(a), cy + r * np.sin(a)))
    return np.array(pts, np.int32).reshape(-1, 1, 2)


def run_batch(cfg: dict, inputs: list[Path], out_dir: Path, *, product_hint: str | None = None,
              border: bool | None = None, tab: str | None = None, overrides: list[str] | None = None,
              batch_name: str | None = None) -> BatchResult:
    from .preview import render_contact_sheet, render_design_preview, render_shaded
    from .notes import write_print_notes

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    designs_dir = out_dir / "designs"
    designs_dir.mkdir(exist_ok=True)
    filaments, from_config = load_filaments(cfg)
    ov = parse_overrides(overrides or [])
    pieces: list[Piece] = []
    problems: list[str] = []
    used_names: dict[str, int] = {}

    for path in collect_inputs(inputs):
        pages = pdf_page_count(path) if path.suffix.lower() == ".pdf" else 1
        for page in range(pages):
            label = f"{path.name}" + (f" page {page + 1}" if pages > 1 else "")
            try:
                image = load_image(path, page)
                reads = read_card(cfg, image, product_hint)
            except Exception as e:  # noqa: BLE001
                problems.append(f"{label}: {e}")
                continue
            for read in reads:
                base_name = read.layout.stem if read.layout else _safe_stem(path.stem)
                name = base_name
                if name in used_names:
                    used_names[name] += 1
                    name = f"{base_name}-{chr(ord('a') + used_names[base_name] - 1)}"
                else:
                    used_names[name] = 1
                try:
                    design = design_from_read(cfg, read, product_hint=product_hint, border=border, name=name)
                    design.source = label
                    if name != base_name:
                        design.warnings.append(f"another {base_name} was already in this batch; renamed to {name}")
                    piece = build_piece(cfg, design, tab_position=tab)
                    _check_piece(piece)
                except Exception as e:  # noqa: BLE001
                    problems.append(f"{label}: {e}")
                    continue
                pieces.append(piece)

    if not pieces:
        return BatchResult([], [], {}, from_config, problems)

    plates = pack_plates(cfg, pieces, filaments, ov)
    files = {"plates": write_plates(cfg, plates, out_dir / "plates")}
    assignments = {pp.piece.name: pp.assignments for plate in plates for pp in plate.pieces}
    previews = []
    for piece in pieces:
        d = designs_dir
        p = render_design_preview(cfg, piece, assignments[piece.name], d / f"{piece.name}-preview.png",
                                  from_config=from_config)
        previews.append(p)
        colors = {n: assignments[piece.name][n].rgb for n in piece.parts}
        render_shaded(piece.parts, d / f"{piece.name}-back.png", view=(40.0, 20.0), px_per_mm=12,
                      labels=False, colors=colors)
        face_up = {n: s.rotate([180.0, 0.0, 0.0]) for n, s in piece.parts.items()}
        render_shaded(face_up, d / f"{piece.name}-front.png", view=(40.0, 20.0), px_per_mm=12,
                      labels=False, colors=colors)
        (d / f"{piece.name}.json").write_text(json.dumps(_piece_summary(piece, assignments[piece.name]), indent=2))
    files["contact_sheet"] = render_contact_sheet(previews, out_dir / "contact-sheet.png", title=batch_name or out_dir.name)
    files["notes"] = write_print_notes(cfg, plates, out_dir / "PRINT_NOTES.md", from_config=from_config, problems=problems)
    return BatchResult(pieces, plates, files, from_config, problems)


def _safe_stem(s: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in s)[:40] or "drawing"


def _check_piece(piece: Piece) -> None:
    """Every part sound, and all parts together form one connected piece."""
    from .geom import count_bodies, to_trimesh

    union = None
    for name, solid in piece.parts.items():
        if solid.is_empty():
            raise ValueError(f"part {name} is empty")
        if not to_trimesh(solid).is_watertight:
            raise ValueError(f"part {name} is not watertight")
        union = solid if union is None else union + solid
    if count_bodies(union) != 1:
        raise ValueError("the piece is not one connected part")


def _piece_summary(piece: Piece, assignments: dict[str, Filament]) -> dict:
    d = piece.design
    w, h = piece.size()
    return {
        "name": d.name,
        "product": d.product,
        "source": d.source,
        "size_mm": [round(w, 2), round(h, 2), piece.thickness],
        "parts": {n: {"filament": f.name, "slot": f.slot} for n, f in assignments.items()},
        "attachment": {k: (list(v) if isinstance(v, tuple) else v) for k, v in piece.attachment.items() if k != "hole"},
        "fixes": d.fixes,
        "warnings": d.warnings,
    }
