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

    p = sub.add_parser("stand", help="build just the figure stand")
    p.add_argument("--out", default="output/stand", help="output folder")
    p.set_defaults(func=cmd_stand)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
