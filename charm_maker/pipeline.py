"""Photos in, plates out. Orchestrates reader -> inks -> fixes -> product -> plates."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

from .config import load_config
from .filaments import Filament, parse_overrides
from .inks import Reference, classify_to_palette, separate_inks
from .palette import Palette, load_palette, spool_word
from .plates import Plate, assign_filaments, pack_plates, unanswered_off_palette, write_plates
from .products import Piece, build_piece
from .reader import CardRead, load_image, pdf_page_count, read_card
from .shape import Design, fix_design

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".pdf", ".tif", ".tiff", ".bmp", ".webp"}


@dataclass
class BatchResult:
    pieces: list[Piece]
    plates: list[Plate]
    files: dict
    palette_ready: bool
    problems: list[str] = field(default_factory=list)
    question: str | None = None
    calibration: list[str] = field(default_factory=list)


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


def _references(palette: Palette) -> list[Reference]:
    return [Reference(s.slot, spool_word(s.filament), s.reference_rgb) for s in palette.ink_slots()]


def _inks_for(cfg: dict, palette: Palette, bgr: np.ndarray, audience: str, px_per_mm: float,
              ignore: np.ndarray | None = None):
    pr = cfg["process"]
    if audience == "kids" and palette.ready:
        return classify_to_palette(cfg, bgr, _references(palette), calibrated=palette.calibrated,
                                   px_per_mm=px_per_mm, ignore=ignore)
    max_colors = pr["kid_card_max_colors"] if audience == "kids" else pr["adult_card_max_colors"]
    res = separate_inks(cfg, bgr, max_colors, ignore)
    if audience == "kids":
        res.notes.append("no loaded slots in config yet: colors grouped by hue and matched to a generic palette")
    return res


def design_from_read(cfg: dict, read: CardRead, *, product_hint: str | None, border: bool | None,
                     name: str, palette: Palette | None = None) -> Design:
    palette = palette or load_palette(cfg)
    pr = cfg["process"]
    scale = pr["card_scale"]
    if read.layout is not None:
        product = read.layout.product
        audience = cfg["products"][product]["audience"]
        px_per_mm = read.px_per_card_mm * scale        # real-size px per mm
        # Ignore a thin band along the printed box edge (the guide line lives there).
        ignore = _box_edge_band(cfg, read)
        inks = _inks_for(cfg, palette, read.box_image, audience, px_per_mm, ignore)
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
    img = read.box_image
    h, w = img.shape[:2]
    f = min(1.0, 1600.0 / max(h, w))
    small = cv2.resize(img, (int(w * f), int(h * f)), interpolation=cv2.INTER_AREA) if f < 1 else img
    coarse = separate_inks(cfg, small, 3)
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
    inks = _inks_for(cfg, palette, crop, audience, target_ppm)
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
              batch_name: str | None = None, off_palette: str | None = None,
              config_path: Path | None = None, allow_uncalibrated: bool = False) -> BatchResult:
    """Photos in, plates out. Calibration cards in the batch are applied first.
    `off_palette` answers the once-per-batch question: "nearest" or "swap"."""
    from .calibrate import measure_markers
    from .notes import write_print_notes, write_question
    from .palette import save_calibration
    from .preview import render_contact_sheet, render_design_preview, render_shaded

    if off_palette not in (None, "nearest", "swap"):
        raise ValueError("off_palette must be 'nearest' or 'swap'")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    designs_dir = out_dir / "designs"
    designs_dir.mkdir(exist_ok=True)
    ov = parse_overrides(overrides or [])
    problems: list[str] = []
    calibration_lines: list[str] = []

    # Pass 1: read every image.
    reads: list[tuple[str, Path, CardRead]] = []
    for path in collect_inputs(inputs):
        pages = pdf_page_count(path) if path.suffix.lower() == ".pdf" else 1
        for page in range(pages):
            label = f"{path.name}" + (f" page {page + 1}" if pages > 1 else "")
            try:
                image = load_image(path, page)
                for read in read_card(cfg, image, product_hint):
                    reads.append((label, path, read))
            except Exception as e:  # noqa: BLE001
                problems.append(f"{label}: {e}")

    # Calibration cards first, so the drawings in the same batch use them.
    drawings = []
    for label, path, read in reads:
        if read.layout is not None and read.layout.product == "calibration":
            markers, notes = measure_markers(cfg, read)
            calibration_lines += [f"{label}: {n}" for n in notes]
            if config_path is not None:
                calibration_lines += save_calibration(config_path, markers)
                cfg = load_config(config_path)
            else:
                for slot, rgb in markers.items():
                    entry = (cfg.get("loaded") or {}).get(slot)
                    if entry:
                        entry["marker"] = "#%02X%02X%02X" % rgb
                        calibration_lines.append(f"slot {slot}: marker {entry['marker']} (not saved)")
        else:
            drawings.append((label, path, read))
    palette = load_palette(cfg)

    # Pass 2: drawings to pieces.
    pieces: list[Piece] = []
    used_names: dict[str, int] = {}
    for label, path, read in drawings:
        base_name = read.layout.stem if read.layout else _safe_stem(path.stem)
        name = base_name
        if name in used_names:
            used_names[name] += 1
            name = f"{base_name}-{chr(ord('a') + used_names[base_name] - 1)}"
        else:
            used_names[name] = 1
        try:
            design = design_from_read(cfg, read, product_hint=product_hint, border=border, name=name, palette=palette)
            design.source = label
            if name != base_name:
                design.warnings.append(f"another {base_name} was already in this batch; renamed to {name}")
            piece = build_piece(cfg, design, tab_position=tab)
            _check_piece(piece)
            _set_base_slot(cfg, piece, palette)
            for part, info in piece.part_off_palette.items():
                info["suggested"] = palette.suggest_spool(info["rgb"])
                piece.design.warnings.append(
                    f"{info['color']} is not loaded ({info['area_mm2']} mm²); nearest loaded is {info['nearest_name']} (slot {info['nearest_slot']})")
        except Exception as e:  # noqa: BLE001
            problems.append(f"{label}: {e}")
            continue
        pieces.append(piece)

    if not pieces:
        return BatchResult([], [], {}, palette.ready, problems, None, calibration_lines)

    assignments = {}
    for piece in pieces:
        try:
            assignments[piece.name] = assign_filaments(piece, palette, ov, off_palette)
        except ValueError as e:
            problems.append(f"{piece.name}: {e}")
    pieces = [p for p in pieces if p.name in assignments]

    files: dict = {}
    question = None
    unanswered = [(p, part) for p in pieces for part in unanswered_off_palette(p, assignments[p.name])]
    kids = any(cfg["products"][p.design.product]["audience"] == "kids" for p in pieces)
    uncalibrated = []
    if palette.ready and kids and not allow_uncalibrated:
        uncalibrated = [f"slot {s.slot} {s.filament.name}" for s in palette.ink_slots() if not s.marker_rgb]
    plates: list[Plate] = []
    slot_labels: dict[str, dict[str, str]] = {p.name: {} for p in pieces}
    if unanswered or uncalibrated:
        off = []
        for p, part in unanswered:
            info = dict(p.part_off_palette[part])
            info["card"] = p.name
            off.append(info)
            slot_labels[p.name][part] = "answer the question first"
        files["question"], question = write_question(off, out_dir / "QUESTION.md", uncalibrated)
    else:
        try:
            plates = pack_plates(cfg, pieces, palette, assignments)
        except ValueError as e:
            problems.append(str(e))
        if plates:
            files["plates"] = write_plates(cfg, plates, out_dir / "plates")
            for plate in plates:
                slots = plate.slots()
                for pp in plate.pieces:
                    for part, f in pp.assignments.items():
                        swap = any(sw.put_in == f for sw in plate.swaps)
                        slot_labels[pp.piece.name][part] = f"slot {slots[f]}, plate {plate.number}" + (" after a spool swap" if swap else "")

    previews = []
    for piece in pieces:
        d = designs_dir
        a = assignments[piece.name]
        p = render_design_preview(cfg, piece, a, d / f"{piece.name}-preview.png", palette_ready=palette.ready,
                                  slot_labels=slot_labels[piece.name])
        previews.append(p)
        colors = {n: a[n].rgb for n in piece.parts}
        render_shaded(piece.parts, d / f"{piece.name}-back.png", view=(40.0, 20.0), px_per_mm=12,
                      labels=False, colors=colors)
        face_up = {n: s.rotate([180.0, 0.0, 0.0]) for n, s in piece.parts.items()}
        render_shaded(face_up, d / f"{piece.name}-front.png", view=(40.0, 20.0), px_per_mm=12,
                      labels=False, colors=colors)
        (d / f"{piece.name}.json").write_text(json.dumps(_piece_summary(piece, a, slot_labels[piece.name]), indent=2))
    files["contact_sheet"] = render_contact_sheet(previews, out_dir / "contact-sheet.png", title=batch_name or out_dir.name)
    if plates:
        files["notes"] = write_print_notes(cfg, plates, out_dir / "PRINT_NOTES.md", palette=palette, problems=problems)
    return BatchResult(pieces, plates, files, palette.ready, problems, question, calibration_lines)


def _set_base_slot(cfg: dict, piece: Piece, palette: Palette) -> None:
    if not palette.ready:
        return
    if cfg["process"]["base_color"] == "kid_color":
        slots = [s for n, s in piece.part_slots.items() if s is not None and n != piece.base_part]
        if slots:
            piece.part_slots[piece.base_part] = slots[-1]
            return
    base = palette.base_slot(piece.design.paper_rgb)
    piece.part_slots[piece.base_part] = base.slot
    if not base.is_white:
        piece.design.warnings.append(f"no white spool loaded: the base prints in {base.filament.name} (slot {base.slot})")


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


def _piece_summary(piece: Piece, assignments: dict[str, Filament], slot_labels: dict[str, str]) -> dict:
    d = piece.design
    w, h = piece.size()
    return {
        "name": d.name,
        "product": d.product,
        "source": d.source,
        "size_mm": [round(w, 2), round(h, 2), piece.thickness],
        "parts": {n: {"filament": f.name, "where": slot_labels.get(n, "")} for n, f in assignments.items()},
        "off_palette": {n: {k: v for k, v in i.items() if k != "suggested"} for n, i in piece.part_off_palette.items()},
        "attachment": {k: (list(v) if isinstance(v, tuple) else v) for k, v in piece.attachment.items() if k != "hole"},
        "fixes": d.fixes,
        "warnings": d.warnings,
    }
