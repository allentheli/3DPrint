"""Photos in, plates out. Orchestrates reader -> inks -> fixes -> product -> plates."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

from .config import load_config
from .filaments import Filament, parse_overrides
from .inks import separate_colors, separate_inks
from .palette import Palette, color_distance, load_palette, spool_word
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


def design_from_read(cfg: dict, read: CardRead, *, product_hint: str | None, border: bool | None,
                     name: str, palette: Palette | None = None, tidy: bool = False,
                     keep_dots: bool = True, size: float = 1.0, product_override: str | None = None) -> Design:
    """`size` makes the piece that many times the drawn size (Allen, 2026-11-12: a bigger
    butterfly so its tiny face keeps its shape). It is applied before the print fixes, so
    her lines and the gaps between them grow too and the 1 mm minimum has room."""
    pr = cfg["process"]
    asked = size
    if border is None:
        border = pr["border_default"]
    if read.layout is not None:
        product = product_override or read.layout.product
        if product not in cfg["products"]:
            raise ValueError(f"unknown product {product!r}; products: {', '.join(cfg['products'])}")
        # Some products are bigger than their card box at the usual card scale (a flexi).
        size = asked * cfg["products"][product].get("drawing_scale", 1.0)
        scale = pr["card_scale"] / size
        px_per_mm = read.px_per_card_mm * scale        # real-size px per mm
        # Ignore a thin band along the printed box edge (the guide line lives there).
        ignore = _box_edge_band(cfg, read)
        zone = _guide_zone(cfg, read)
        inks = separate_colors(cfg, read.box_image, px_per_mm=px_per_mm, ignore=ignore, guide_zone=zone)
        grown = 1.0
        prod = cfg["products"][product]
        if prod.get("attachment") == "strips" and inks.layers:
            # A flexi drawn small grows to the flexi's size BEFORE the print fixes, like --scale, so
            # its lines, eyes and the paper between them grow too (2026-11-14: a small unicorn's face
            # melted into a black blob when it was fixed at its drawn size and enlarged after).
            union = np.zeros(inks.layers[0].mask.shape, bool)
            for layer in inks.layers:
                union |= layer.mask
            ys, xs = np.nonzero(union)
            if len(xs):
                long_mm = (max(xs.max() - xs.min(), ys.max() - ys.min()) + 1) / px_per_mm
                b = 2 * pr["border"] if border else 0.0
                target = float(prod["default_size"])
                if long_mm + b < target - 2.0:
                    # The colors stay as read at the card's own scale (read at the bigger size, a thin
                    # pen line splits into a dark middle and a gray edge); only the fixes see it bigger.
                    grown = (target - b) / long_mm
                    size *= grown
                    px_per_mm = read.px_per_card_mm * pr["card_scale"] / size
        design = fix_design(cfg, inks.layers, px_per_mm, border_on=border, name=name, product=product, tidy=tidy,
                            keep_dots=keep_dots)
        if grown != 1.0:
            design.fixes.append(f"drawn small: made {grown:.2f} times bigger, to the flexi's {prod['default_size']:g} mm, "
                                "before the print fixes, so the face keeps its shape")
        design.fixes[:0] = inks.fixes
        design.paper_rgb = inks.paper_rgb
        design.warnings.extend(inks.notes + read.notes)
        design.name_image = read.name_image
        if product != read.layout.product:
            design.fixes.append(f"made into a {cfg['products'][product]['label'].lower()} (asked for; drawn on a "
                                f"{cfg['products'][read.layout.product]['label'].lower()} card)")
        if size / grown != asked:
            design.fixes.append(f"made {size / grown / asked:g} times the drawn size (a {cfg['products'][product]['label'].lower()} "
                                "is bigger than its card box)")
        if asked != 1.0:
            design.fixes.append(f"made {asked:g} times the drawn size (asked for)")
        return design

    # Fallback: no markers. Use the whole image, scale the ink to the default size.
    product = product_override or product_hint
    assert product is not None
    scale = pr["card_scale"] / size
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
    size_mm = cfg["products"][product]["default_size"] * size
    target_ppm = cfg["reader"]["px_per_card_mm"] * scale
    resize = target_ppm * size_mm / longest_px
    pad = 10
    crop = small[max(ys.min() - pad, 0):ys.max() + pad, max(xs.min() - pad, 0):xs.max() + pad]
    crop = cv2.resize(crop, (int(crop.shape[1] * resize), int(crop.shape[0] * resize)), interpolation=cv2.INTER_CUBIC)
    inks = separate_colors(cfg, crop, px_per_mm=target_ppm)
    design = fix_design(cfg, inks.layers, target_ppm, border_on=border, name=name, product=product, tidy=tidy,
                        keep_dots=keep_dots)
    design.fixes[:0] = inks.fixes
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


def _guide_zone(cfg: dict, read: CardRead) -> np.ndarray:
    """Where guides are printed inside the crop (with a margin): the box label, the
    cover-the-circle ring and label, the ground line and its label. Guide-colored pixels
    elsewhere are drawing, not guide."""
    lay = read.layout
    ppm = read.px_per_card_mm
    ox, oy = read.box_origin_mm
    h, w = read.box_image.shape[:2]
    m = cfg["reader"]["guide_zone_margin"]
    zone = np.zeros((h, w), np.uint8)

    def px(x, y):
        return int(round((x - ox) * ppm)), int(round((oy - y) * ppm))

    def rect(x0, y0, x1, y1):
        cv2.rectangle(zone, px(x0 - m, y1 + m), px(x1 + m, y0 - m), 1, -1)

    bx, by, bw, bh = lay.box
    rect(bx + 1, by + bh - 7, bx + 40, by + bh - 1)                 # "draw inside the box"
    if "cover_circle" in lay.zones:
        cx, cy, d = lay.zones["cover_circle"]
        cv2.circle(zone, px(cx, cy), int(round(d / 2 * ppm)), 1, int(round(2 * m * ppm)) + 1)
        rect(cx - 14, cy - 4, cx + 14, cy + 1.5)                     # "cover the circle"
    if "cover_square" in lay.zones:
        cx, cy, side = lay.zones["cover_square"]
        a, b = px(cx - side / 2, cy + side / 2), px(cx + side / 2, cy - side / 2)
        cv2.rectangle(zone, a, b, 1, int(round(2 * m * ppm)) + 1)
        rect(cx - 14, cy - 4, cx + 14, cy + 1.5)                     # "cover the square"
    if "ground_line" in lay.zones:
        x0, y0, x1, y1 = lay.zones["ground_line"]
        rect(x0, y0, x1, y1)
        rect(x0 - 1, y0 - 6, x0 + 20, y0 - 1)                        # "stand here"
    for key in ("ring", "bail"):
        if key in lay.zones:
            cx, cy, d = lay.zones[key]
            rect(cx - d / 2, cy - d / 2, cx + d / 2 + 30, cy + d / 2)
    return zone.astype(bool)


def _rounded_rect_pts(x0, y0, x1, y1, r, n=8):
    pts = []
    for cx, cy, a0 in ((x1 - r, y0 + r, 270), (x1 - r, y1 - r, 0), (x0 + r, y1 - r, 90), (x0 + r, y0 + r, 180)):
        for i in range(n + 1):
            a = np.radians(a0 + 90 * i / n)
            pts.append((cx + r * np.cos(a), cy + r * np.sin(a)))
    return np.array(pts, np.int32).reshape(-1, 1, 2)


def run_batch(cfg: dict, inputs: list[Path], out_dir: Path, *, product_hint: str | None = None,
              border: bool | None = None, tab: str | None = None, overrides: list[str] | None = None,
              batch_name: str | None = None, off_palette: str | None = "nearest",
              config_path: Path | None = None, allow_uncalibrated: bool = True,
              styles: dict[str, str] | None = None, figurine_back: dict[str, str] | None = None,
              figurine_base: dict[str, str] | None = None, tidy: set[str] | None = None,
              names: dict[str, str] | None = None, one_plate: bool = False,
              no_dots: set[str] | None = None, sizes: dict[str, float] | None = None,
              products: dict[str, str] | None = None, keep_whole: dict[str, str] | None = None) -> BatchResult:
    """Photos in, plates out. Every distinct ink color is its own part; parts are
    pre-assigned to the nearest loaded spool as a head start, and Allen can change any
    of them in Bambu Studio. Strict mode (off_palette=None, allow_uncalibrated=False)
    stops and asks about colors that aren't loaded. Calibration cards are optional and
    applied first when present."""
    from .calibrate import measure_markers
    from .notes import write_print_notes, write_question
    from .palette import save_calibration
    from .preview import render_contact_sheet, render_design_preview, render_shaded

    if off_palette not in (None, "nearest", "swap"):
        raise ValueError("off_palette must be 'nearest' or 'swap'")
    from .relief import STYLES

    styles = dict(styles or {})
    for key, st in styles.items():
        if st not in STYLES:
            raise ValueError(f"unknown style {st!r} for {key}; use one of {', '.join(STYLES)}")

    def style_for(*cards: str, picked: str | None = None) -> str:
        """The exact name first (clip-01-b, a second copy of a card), then the card, then the
        shape ticked on the card itself, then the style for all cards."""
        named = next((styles[c] for c in cards if c in styles), None)
        return named or picked or styles.get("*") or cfg["relief"]["default_style"]

    figurine_back = dict(figurine_back or {})
    figurine_base = dict(figurine_base or {})

    def option_for(opts: dict, *cards: str):
        return next((opts[c] for c in (*cards, "*") if c in opts), None)

    tidy = set(tidy or ())
    no_dots = set(no_dots or ())
    products = dict(products or {})
    keep = {}
    for key, span in (keep_whole or {}).items():
        try:
            a, b = (float(v) for v in str(span).split("-"))
        except ValueError:
            raise ValueError(f"--keep-whole {key}={span}: use FROM-TO in percent from the top, e.g. 0-40") from None
        if not 0 <= a < b <= 100:
            raise ValueError(f"--keep-whole {key}={span}: use FROM-TO in percent from the top, e.g. 0-40")
        keep[key] = (a, b)
    for key, prod in products.items():
        if prod not in cfg["products"]:
            raise ValueError(f"--as {key}={prod}: no such product; use one of {', '.join(cfg['products'])}")
    sizes = {k: float(v) for k, v in (sizes or {}).items()}
    for key, k in sizes.items():
        if not 0.25 <= k <= 4.0:
            raise ValueError(f"--scale {key}={k:g}: use a factor between 0.25 and 4")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    designs_dir = out_dir / "designs"
    designs_dir.mkdir(exist_ok=True)
    ov = parse_overrides(overrides or [])
    problems: list[str] = []
    calibration_lines: list[str] = []

    # Pass 1: read every image.
    reads = _read_inputs(cfg, inputs, product_hint, problems)

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
    names = dict(names or {})
    kid_names: dict[str, int] = {}
    for (label, path, read), (name, base_name) in zip(drawings, _card_names(drawings)):
        try:
            from .options import read_options

            opts = read_options(cfg, read)                 # boxes the kid ticked on the card
            design = design_from_read(cfg, read, product_hint=product_hint, border=border, name=name, palette=palette,
                                      tidy=bool(tidy & {name, base_name, "*"}) or opts.get("tidy", False),
                                      keep_dots=not (no_dots & {name, base_name, "*"}),
                                      size=next((sizes[c] for c in (name, base_name, "*") if c in sizes), 1.0),
                                      product_override=next((products[c] for c in (name, base_name, "*")
                                                             if c in products), None))
            design.source = label
            span = next((keep[c] for c in (name, base_name, "*") if c in keep), None)
            if span:
                design.extras["keep_whole"] = span
                design.fixes.append(f"no cuts from {span[0]:g}% to {span[1]:g}% down the flexi (asked for, to keep the face whole)")
            design.fixes += opts.get("notes", [])
            design.warnings += opts.get("warnings", [])
            slots = cfg["printer"]["ams_slots"]
            if len(design.inks) + 1 > slots:
                design.warnings.append(f"{len(design.inks)} drawn colors plus the base: more than the {slots} AMS slots, "
                                       "so some must share a spool (every color is still its own part)")
            kid = kid_file_name(cfg, design.product, names.get(name, ""))
            if kid:
                # Named after the kid who drew it (keychain-jack); the card number stays as a note.
                kid_names[kid] = kid_names.get(kid, 0) + 1
                design.card, design.name = name, kid if kid_names[kid] == 1 else f"{kid}-{kid_names[kid]}"
            elif name != base_name:
                design.warnings.append(f"another {base_name} was already in this batch; renamed to {name}")
            new = []
            for copy_design in _copies(cfg, design):
                piece = build_piece(cfg, copy_design, tab_position=tab, style=style_for(name, base_name, picked=opts.get("style")),
                                    figurine_back=option_for(figurine_back, name, base_name),
                                    figurine_base=option_for(figurine_base, name, base_name))
                _check_piece(piece)
                _map_to_palette(cfg, piece, palette)
                _set_base_slot(cfg, piece, palette)
                new.append(piece)
                if piece.attachment.get("kind") == "stem_socket":       # a clicker: its case too
                    from .products import build_clicker_case, build_keycap_post

                    extra = [build_clicker_case(cfg, piece)]
                    if piece.attachment.get("separate_post"):          # a shaped keycap: its post apart
                        extra.insert(0, build_keycap_post(cfg, piece))
                    for more in extra:
                        _check_piece(more)
                        _map_to_palette(cfg, more, palette)
                        _set_base_slot(cfg, more, palette)
                        new.append(more)
        except Exception as e:  # noqa: BLE001
            problems.append(f"{label}: {e}")
            continue
        pieces.extend(new)

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
    uncalibrated = []
    if palette.ready and not allow_uncalibrated:
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
            plates = pack_plates(cfg, pieces, palette, assignments, one_plate=one_plate)
        except ValueError as e:
            problems.append(str(e))
        if plates:
            files["plates"] = write_plates(cfg, plates, out_dir / "plates")
            from .preview import render_plate_map

            for plate in plates:
                files["plates"][plate.number]["map"] = render_plate_map(
                    cfg, plate, out_dir / "plates" / f"{plate.stem}-map.png")
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
        colors = {n: a[n].rgb for n in piece.parts}
        # Turn the piece over (about the vertical axis, like turning a page) to see the
        # other side: the face of a face-down piece, the back of a face-up one.
        turned = {n: s.rotate([0.0, 180.0, 0.0]) for n, s in piece.parts.items()}
        front, back = (piece.parts, turned) if piece.face_up else (turned, piece.parts)
        render_shaded(back, d / f"{piece.name}-back.png", view=(40.0, 20.0), px_per_mm=12,
                      labels=False, colors=colors)
        if piece.group == "cases":
            # Show the clicker put together: case, the switch, and the keycap on top.
            keycap = next(p for p in pieces if p.name == piece.name[: -len("-case")])
            front, colors = _assembled_clicker(cfg, piece, keycap, assignments[keycap.name], colors)
        front_png = render_shaded(front, d / f"{piece.name}-front.png", view=(40.0, 20.0), px_per_mm=12,
                                  labels=False, colors=colors)
        p = render_design_preview(cfg, piece, a, d / f"{piece.name}-preview.png", palette_ready=palette.ready,
                                  slot_labels=slot_labels[piece.name], render_path=front_png)
        previews.append(p)
        (d / f"{piece.name}.json").write_text(json.dumps(_piece_summary(piece, a, slot_labels[piece.name]), indent=2))
    files["contact_sheet"] = render_contact_sheet(previews, out_dir / "contact-sheet.png", title=batch_name or out_dir.name)
    if plates:
        files["notes"] = write_print_notes(cfg, plates, out_dir / "PRINT_NOTES.md", palette=palette, problems=problems)
    return BatchResult(pieces, plates, files, palette.ready, problems, question, calibration_lines)


def _read_inputs(cfg: dict, inputs: list[Path], product_hint: str | None, problems: list[str]) -> list:
    """Every card in every photo, PDF page or folder: [(label, path, CardRead)]."""
    reads = []
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
    return reads


def _card_names(drawings: list) -> list[tuple[str, str]]:
    """(name, card) for each drawing, in order: the card (key-03), and key-03-b, key-03-c
    for more cards with the same number in one batch."""
    used: dict[str, int] = {}
    out = []
    for _, path, read in drawings:
        base = read.layout.stem if read.layout else _safe_stem(path.stem)
        used[base] = used.get(base, 0) + 1
        out.append((base if used[base] == 1 else f"{base}-{chr(ord('a') + used[base] - 1)}", base))
    return out


def kid_file_name(cfg: dict, product: str, kid: str) -> str:
    """keychain-jack from "Jack": the product's word and the name in plain letters.
    Empty when there is no usable name."""
    import re
    import unicodedata

    plain = unicodedata.normalize("NFKD", kid or "").encode("ascii", "ignore").decode().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", plain).strip("-")[:20].strip("-")
    if not slug:
        return ""
    return f"{cfg['products'][product].get('file_word', product)}-{slug}"


def read_names(cfg: dict, inputs: list[Path], out_dir: Path, *, product_hint: str | None = None):
    """The quick first step: every card's name line on one sheet (names.png), to read the
    names from before the real run. Returns ([(card, label)], sheet path, problems)."""
    from PIL import Image, ImageDraw

    from .preview import _font

    problems: list[str] = []
    reads = _read_inputs(cfg, inputs, product_hint, problems)
    drawings = [r for r in reads if not (r[2].layout is not None and r[2].layout.product == "calibration")]
    rows = []
    for (label, path, read), (name, _) in zip(drawings, _card_names(drawings)):
        crop = read.name_image
        img = Image.fromarray(crop[:, :, ::-1]) if crop is not None and crop.size else Image.new("RGB", (600, 80), "white")
        img = img.resize((900, max(1, int(img.height * 900 / img.width))), Image.LANCZOS)
        rows.append((name, label, img))
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    font = _font(30)
    h = 20 + sum(r[2].height + 30 for r in rows)
    sheet = Image.new("RGB", (1260, max(h, 60)), "white")
    d = ImageDraw.Draw(sheet)
    y = 20
    for name, label, img in rows:
        d.text((20, y + img.height // 2), name, fill=(0, 0, 0), font=font, anchor="lm")
        sheet.paste(img, (240, y))
        d.rectangle([240, y, 240 + img.width - 1, y + img.height - 1], outline=(200, 200, 200))
        y += img.height + 30
    path = out_dir / "names.png"
    sheet.save(path)
    return [(name, label) for name, label, _ in rows], path, problems


def _copies(cfg: dict, design: Design) -> list[Design]:
    """Earrings come as a pair: identical, or the second mirrored."""
    import copy

    from shapely import affinity

    prod = cfg["products"][design.product]
    n = int(prod.get("copies", 1))
    if n <= 1:
        return [design]
    base = design.name
    out = []
    for i in range(n):
        d = copy.deepcopy(design)
        d.name = f"{base}-{i + 1}"
        if i and prod.get("pair_mode") == "mirrored":
            d.outline = affinity.scale(d.outline, -1, 1, origin=(0, 0))
            for ink in d.inks:
                ink.geometry = affinity.scale(ink.geometry, -1, 1, origin=(0, 0))
            d.dots = [(-x, y) for x, y in d.dots]
            d.fixes.append("mirror image of the first one")
        out.append(d)
    out[0].fixes.append(f"made as a pair: {base}-1 and {base}-2")
    return out


def _map_to_palette(cfg: dict, piece: Piece, palette: Palette) -> None:
    """Head start only: give each color part the nearest loaded spool. Parts stay
    separate even when two land on the same spool, and the preview says so."""
    if not palette.ready:
        return
    pc = cfg["palette"]
    thr = pc["off_palette_distance"] if palette.calibrated else pc["off_palette_distance_uncalibrated"]
    inks = palette.ink_slots()
    if not inks:
        return
    seen: dict[int, str] = {}
    for part, rgb in piece.part_colors.items():
        if part == piece.base_part:
            continue
        best = min(inks, key=lambda s: color_distance(rgb, s.reference_rgb))
        dist = color_distance(rgb, best.reference_rgb)
        short = part[len(piece.name) + 1:]
        if dist > thr:
            area = sum(i.geometry.area for i in piece.design.inks if i.name == short)
            piece.part_off_palette[part] = {"color": short, "rgb": rgb, "nearest_slot": best.slot,
                                            "nearest_name": spool_word(best.filament),
                                            "distance": round(dist, 1), "area_mm2": round(area, 1),
                                            "suggested": palette.suggest_spool(rgb)}
            piece.part_slots[part] = None
            piece.design.warnings.append(f"{short} doesn't match a loaded spool; set to the nearest, "
                                         f"{best.filament.name} (slot {best.slot}). Change it in Bambu Studio if you like.")
        else:
            piece.part_slots[part] = best.slot
        target = piece.part_slots[part] or best.slot
        if target in seen and seen[target] != short:
            piece.design.warnings.append(f"{seen[target]} and {short} are separate parts but both start as "
                                         f"{best.filament.name}; change one in Bambu Studio if you like.")
        seen.setdefault(target, short)


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


def _assembled_clicker(cfg: dict, case: Piece, keycap: Piece, keycap_colors: dict, case_colors: dict):
    """The clicker as it will look: the case, a plain stand-in for the switch, and the
    keycap turned face-up on the stem at rest. For the preview only."""
    import manifold3d as m3d

    hw = cfg["hardware"]
    top = case.attachment["plate_z"]                    # the switch plate, at the bottom of the cup
    housing = m3d.Manifold.cube([hw["mx_cavity_size"], hw["mx_cavity_size"], hw["mx_housing_above_plate"]], True)
    housing = housing.translate([0.0, 0.0, top + hw["mx_housing_above_plate"] / 2])
    stem_h = hw["mx_stem_top_above_plate"] - hw["mx_housing_above_plate"]
    stem = m3d.Manifold.cube([4.0, 4.0, stem_h], True).translate([0.0, 0.0, top + hw["mx_housing_above_plate"] + stem_h / 2])
    att = keycap.attachment
    cx, cy = att["center"]
    rest = top + hw["mx_stem_top_above_plate"] - min(att["socket_depth"], hw["mx_stem_height"])  # post end
    lift = rest + keycap.thickness + att["post_height"]
    parts = {f"{case.name} switch": housing, f"{case.name} stem": stem}
    colors = {f"{case.name} switch": (205, 205, 210), f"{case.name} stem": (60, 120, 220)}
    for n, s in case.parts.items():
        parts[n], colors[n] = s, case_colors[n]
    if keycap.face_up:
        # A shaped keycap is built face-up; its separate post (here a plain stand-in) is glued
        # into the dent in its back.
        back = rest + att["post_height"]
        post = m3d.Manifold.cylinder(att["post_height"], att["post_diameter"] / 2, att["post_diameter"] / 2, 48)
        parts[f"{keycap.name} post"] = post.translate([0.0, 0.0, rest])
        colors[f"{keycap.name} post"] = (235, 235, 235)
        for n, s in keycap.parts.items():
            parts[n] = s.translate([-cx, -cy, back])
            colors[n] = keycap_colors[n].rgb
        return parts, colors
    for n, s in keycap.parts.items():
        parts[n] = s.rotate([0.0, 180.0, 0.0]).translate([-cx, -cy, lift])   # turned over, face up
        colors[n] = keycap_colors[n].rgb
    return parts, colors


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
    expected = piece.attachment.get("bodies", 1)          # a flexi: one per strip, linked by pin joints
    if count_bodies(union) != expected:
        raise ValueError("the piece is not one connected part" if expected == 1 else
                         f"the flexi came out in {count_bodies(union)} pieces, not its {expected} strips")


def _piece_summary(piece: Piece, assignments: dict[str, Filament], slot_labels: dict[str, str]) -> dict:
    d = piece.design
    w, h = piece.size()
    return {
        "name": d.name,
        "card": d.card or d.name,
        "product": d.product,
        "source": d.source,
        "size_mm": [round(w, 2), round(h, 2), piece.thickness],
        "style": piece.style,
        "prints": "face-up" if piece.face_up else "face-down (built mirrored)",
        "parts": {n: {"filament": f.name, "where": slot_labels.get(n, "")} for n, f in assignments.items()},
        "off_palette": {n: {k: v for k, v in i.items() if k != "suggested"} for n, i in piece.part_off_palette.items()},
        "attachment": {k: (list(v) if isinstance(v, tuple) else v) for k, v in piece.attachment.items()
                       if k not in ("hole", "solid", "hole_solid", "opening", "cut")},
        "fixes": d.fixes,
        "warnings": d.warnings,
    }
