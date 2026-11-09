"""Command line entry point: python -m charm_maker <command>."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import load_config


def cmd_fit_test(args: argparse.Namespace) -> int:
    from .fittest import build_fit_plate, write_fit_test

    cfg = load_config(args.config)
    plate = build_fit_plate(cfg)
    paths = write_fit_test(cfg, plate, Path(args.out))
    print("Fit-test plate written:")
    for k, p in paths.items():
        print(f"  {k:12s} {p}")
    return 0


def cmd_fit_results(args: argparse.Namespace) -> int:
    from .fitresults import apply_fit_results

    changes = apply_fit_results(args.config, args.pieces)
    for line in changes:
        print(line)
    return 0


def cmd_stand(args: argparse.Namespace) -> int:
    from .export import write_plate
    from .stand import build_stand

    cfg = load_config(args.config)
    paths = write_plate({"stand": build_stand(cfg)}, Path(args.out), "stand")
    for k, p in paths.items():
        print(f"  {k:12s} {p}")
    return 0


def _config_path(args) -> Path:
    from .config import DEFAULT_CONFIG

    return Path(args.config) if args.config else DEFAULT_CONFIG


def cmd_cards(args: argparse.Namespace) -> int:
    from .cards import half_drawn_numbers, write_calibration_pdf, write_cards_pdf
    from .palette import load_palette

    cfg = load_config(args.config)
    products = args.products or ["hair_clip", "keychain", "pendant", "earrings", "magnet_figure"]
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    blank = write_cards_pdf(cfg, products, out / "design-cards.pdf", count=args.count)
    print(f"Blank cards: {blank} ({len(products)} product(s) x {args.count or cfg['cards']['copies_per_type']})")
    if args.half_drawn:
        kid_products = [p for p in products if not cfg["products"][p].get("adults_only")]
        half = write_cards_pdf(cfg, kid_products, out / "half-drawn-cards.pdf", numbers=half_drawn_numbers(cfg))
        print(f"Half-drawn cards: {half} ({', '.join(cfg['cards']['half_drawn_shapes'])}, "
              f"{cfg['cards']['half_drawn_copies']} of each for {', '.join(kid_products)})")
    palette = load_palette(cfg)
    if palette.ready:
        cal = write_calibration_pdf(cfg, palette, out / "calibration-card.pdf")
        print(f"Calibration card: {cal}")
    else:
        print("Calibration card: skipped, no loaded slots in config yet")
    return 0


def cmd_load(args: argparse.Namespace) -> int:
    from .palette import set_slot

    print(set_slot(_config_path(args), args.slot, args.spool, args.color))
    return cmd_slots(args)


def cmd_slots(args: argparse.Namespace) -> int:
    from .palette import load_palette

    palette = load_palette(load_config(args.config))
    if not palette.ready:
        print("No loaded slots yet.")
        return 0
    for slot, ls in sorted(palette.slots.items()):
        f = ls.filament
        if ls.is_white:
            cal = "white: the paper, no marker"
        elif ls.marker_rgb:
            cal = f"marker calibrated {ls.calibrated}"
        else:
            cal = "marker NOT calibrated yet"
        print(f"slot {slot}: {f.name} ({f.hex}), {cal}")
    return 0


def cmd_calibrate(args: argparse.Namespace) -> int:
    from .calibrate import measure_markers
    from .palette import save_calibration
    from .reader import load_image, read_card

    cfg = load_config(args.config)
    reads = [r for r in read_card(cfg, load_image(Path(args.scan))) if r.layout and r.layout.product == "calibration"]
    if not reads:
        print("No calibration card found in that image.")
        return 1
    markers, notes = measure_markers(cfg, reads[0])
    for n in notes:
        print(f"check: {n}")
    for line in save_calibration(_config_path(args), markers):
        print(line)
    return cmd_slots(args)


def cmd_chips(args: argparse.Namespace) -> int:
    from .chips import write_chips
    from .palette import load_palette

    cfg = load_config(args.config)
    paths = write_chips(cfg, load_palette(cfg), Path(args.out))
    for k, p in paths.items():
        if not k.startswith("plain-stl:"):
            print(f"  {k:12s} {p}")
    print(paths["notes"].read_text().split("My rough estimate")[1].split(".")[0].join(["My rough estimate", "."]))
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    from .pipeline import run_batch

    cfg = load_config(args.config)
    border = None if args.border is None else args.border
    styles: dict[str, str] = {}
    for spec in args.style or []:
        card, _, st = spec.rpartition("=")
        styles[card or "*"] = st
    result = run_batch(cfg, [Path(p) for p in args.inputs], Path(args.out), product_hint=args.product,
                       border=border, tab=args.tab, overrides=args.map or [], batch_name=Path(args.out).name,
                       off_palette=None if args.ask_colors else args.off_palette, config_path=_config_path(args),
                       allow_uncalibrated=not args.ask_colors, styles=styles)
    for line in result.calibration:
        print(f"calibration: {line}")
    for piece in result.pieces:
        print(f"{piece.name}: {piece.design.product}, {piece.style}, {piece.size()[0]:.1f} x {piece.size()[1]:.1f} mm")
        for fx in piece.design.fixes:
            print(f"    fix: {fx}")
        for w in piece.design.warnings:
            print(f"    check: {w}")
    for n, paths in result.files.get("plates", {}).items():
        print(f"plate {n}: {paths['3mf']}")
    if result.files.get("contact_sheet"):
        print(f"contact sheet: {result.files['contact_sheet']}")
    if result.files.get("notes"):
        print(f"print notes: {result.files['notes']}")
    for p in result.problems:
        print(f"PROBLEM: {p}")
    if result.question:
        print(f"QUESTION (no plates written yet): {result.files['question']}")
        print(result.question)
        return 2
    return 0 if result.pieces else 1


def cmd_test_drive(args: argparse.Namespace) -> int:
    from .testdrive import write_test_drive

    cfg = load_config(args.config)
    print(f"Test-drive pack: {write_test_drive(cfg, Path(args.out))}")
    return 0


def cmd_poop_containers(args: argparse.Namespace) -> int:
    from .poopjar import KINDS, write_containers

    cfg = load_config(args.config)
    kinds = args.kinds or list(KINDS)
    for r in write_containers(cfg, Path(args.out), kinds=kinds, sizes=args.sizes or ["medium"]):
        con = r["container"]
        print(f"{con.name}: {r['dir']}  (holes {con.info['holes']}, opening {con.info['opening_mm']:.0f} mm, "
              f"about {con.info['volume_ml']:.0f} ml, rough {r['minutes']:.0f} min)")
    return 0


def cmd_screw_top(args: argparse.Namespace) -> int:
    from .screwtop import add_screw_top, load_model, unscrew_check, write_screw_top

    cfg = load_config(args.config)
    model = load_model(Path(args.model), scale=args.scale)
    st = add_screw_top(cfg, model, args.cut)
    worst = unscrew_check(st, cfg["poop_jar"]["thread_lead"])
    if worst > 0.5:
        print(f"check: the head touches the body while unscrewing ({worst:.1f} mm³); try a higher --cut")
    name = args.name or Path(args.model).stem
    paths = write_screw_top(cfg, st, Path(args.out) / name, name)
    print(f"{name}: opening {st.info['opening_mm']:.0f} mm, cut at {st.cut_z} mm, cleared {st.info['cleared_mm3']:.0f} mm³ of body near the head")
    for k, p in paths.items():
        if not str(k).startswith("stl:"):
            print(f"  {k:16s} {p}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="charm_maker", description="Charm Maker")
    parser.add_argument("--config", default=None, help="path to config.yaml (default: repo config)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("fit-test", help="build the milestone 0 fit-test plate")
    p.add_argument("--out", default="output/fit-test", help="output folder")
    p.set_defaults(func=cmd_fit_test)

    p = sub.add_parser("fit-results", help="record which fit-test pieces fit, e.g. 2 5 8 11 14 17")
    p.add_argument("pieces", nargs="+", type=int, help="piece numbers that fit best, one per group")
    p.set_defaults(func=cmd_fit_results)

    p = sub.add_parser("cards", help="write the design-card PDF")
    p.add_argument("--products", nargs="*", help="product keys from config (default: every product that builds)")
    p.add_argument("--count", type=int, default=None, help="cards per product (default from config)")
    p.add_argument("--half-drawn", action="store_true", help="also make cards with a pre-printed outline to color in")
    p.add_argument("--out", default="output/cards", help="output folder")
    p.set_defaults(func=cmd_cards)

    p = sub.add_parser("load", help='record a spool in an AMS slot, e.g. load 3 "Pink PLA" --color "#EC4899"')
    p.add_argument("slot", type=int)
    p.add_argument("spool", help='spool name, or "empty"')
    p.add_argument("--color", default=None, help="hex color of the filament (needed for a new spool)")
    p.set_defaults(func=cmd_load)

    p = sub.add_parser("slots", help="show what is loaded and whether each marker is calibrated")
    p.set_defaults(func=cmd_slots)

    p = sub.add_parser("calibrate", help="read a scanned marker calibration card")
    p.add_argument("scan")
    p.set_defaults(func=cmd_calibrate)

    p = sub.add_parser("chips", help="build the filament chip plate (the printer tour)")
    p.add_argument("--out", default="output/chips")
    p.set_defaults(func=cmd_chips)

    p = sub.add_parser("run", help="turn photos of design cards into plates")
    p.add_argument("inputs", nargs="+", help="photo files, PDFs or a folder")
    p.add_argument("--out", default="output/batch", help="output folder")
    p.add_argument("--product", default=None, help="product for photos without card markers")
    p.add_argument("--border", dest="border", action="store_true", default=None, help="force the border on")
    p.add_argument("--no-border", dest="border", action="store_false", help="force the border off")
    p.add_argument("--tab", default=None, help="keychain tab position: top, top-left, top-right, left, right")
    p.add_argument("--map", action="append", help="filament override, e.g. 'clip-03 pink=Magenta'")
    p.add_argument("--off-palette", choices=["nearest", "swap"], default="nearest",
                   help="colors that don't match a loaded spool: nearest spool (default), or own plate with a swap")
    p.add_argument("--style", action="append",
                   help="flat (default), puffy, outlined or puffy-outlined; for every card, or one card: 'clip-03=puffy'")
    p.add_argument("--ask-colors", action="store_true",
                   help="strict mode: stop and ask about colors that aren't loaded and an unscanned calibration card")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("test-drive", help="a parent page and six cards to try the whole flow with one kid")
    p.add_argument("--out", default="output/test-drive/test-drive-pack.pdf")
    p.set_defaults(func=cmd_test_drive)

    p = sub.add_parser("poop-containers", help="see-through poop containers kids fill and twist shut")
    p.add_argument("--kinds", nargs="*", help="jar-round jar-hex duck bear heart star cloud (default: all)")
    p.add_argument("--sizes", nargs="*", help="small medium tall (default: medium)")
    p.add_argument("--out", default="output/poop-containers")
    p.set_defaults(func=cmd_poop_containers)

    p = sub.add_parser("screw-top", help="turn a downloaded poop-eater model's head into a twist-off lid")
    p.add_argument("model", help="3MF or STL file")
    p.add_argument("--cut", type=float, required=True, help="height (mm) to cut the head off at")
    p.add_argument("--scale", type=float, default=1.0)
    p.add_argument("--name", default=None)
    p.add_argument("--out", default="output/screw-top")
    p.set_defaults(func=cmd_screw_top)

    p = sub.add_parser("stand", help="build just the figure stand")
    p.add_argument("--out", default="output/stand", help="output folder")
    p.set_defaults(func=cmd_stand)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
