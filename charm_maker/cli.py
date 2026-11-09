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


def cmd_cards(args: argparse.Namespace) -> int:
    from .cards import write_cards_pdf

    cfg = load_config(args.config)
    products = args.products or ["hair_clip", "keychain"]
    out = write_cards_pdf(cfg, products, Path(args.out), count=args.count)
    print(f"Cards written: {out} ({len(products)} product(s) x {args.count or cfg['cards']['copies_per_type']} cards)")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    from .pipeline import run_batch

    cfg = load_config(args.config)
    border = None if args.border is None else args.border
    result = run_batch(cfg, [Path(p) for p in args.inputs], Path(args.out), product_hint=args.product,
                       border=border, tab=args.tab, overrides=args.map or [], batch_name=Path(args.out).name)
    for piece in result.pieces:
        print(f"{piece.name}: {piece.design.product}, {piece.size()[0]:.1f} x {piece.size()[1]:.1f} mm")
        for fx in piece.design.fixes:
            print(f"    fix: {fx}")
        for w in piece.design.warnings:
            print(f"    check: {w}")
    for n, paths in result.files.get("plates", {}).items():
        print(f"plate {n}: {paths['3mf']}")
    if result.files.get("contact_sheet"):
        print(f"contact sheet: {result.files['contact_sheet']}")
        print(f"print notes: {result.files['notes']}")
    for p in result.problems:
        print(f"PROBLEM: {p}")
    return 0 if result.pieces else 1


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
    p.add_argument("--products", nargs="*", help="product keys from config (default: hair_clip keychain)")
    p.add_argument("--count", type=int, default=None, help="cards per product (default from config)")
    p.add_argument("--out", default="output/cards/cards.pdf")
    p.set_defaults(func=cmd_cards)

    p = sub.add_parser("run", help="turn photos of design cards into plates")
    p.add_argument("inputs", nargs="+", help="photo files, PDFs or a folder")
    p.add_argument("--out", default="output/batch", help="output folder")
    p.add_argument("--product", default=None, help="product for photos without card markers")
    p.add_argument("--border", dest="border", action="store_true", default=None, help="force the border on")
    p.add_argument("--no-border", dest="border", action="store_false", help="force the border off")
    p.add_argument("--tab", default=None, help="keychain tab position: top, top-left, top-right, left, right")
    p.add_argument("--map", action="append", help="filament override, e.g. 'clip-03 pink=Magenta'")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("stand", help="build just the figure stand")
    p.add_argument("--out", default="output/stand", help="output folder")
    p.set_defaults(func=cmd_stand)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
