"""Write fit-test results into config.yaml, keeping comments intact."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from .config import load_config, read_config_text, write_config_text


def apply_fit_results(config_path, pieces: list[int]) -> list[str]:
    """`pieces` are coupon numbers that fit best. Each number belongs to exactly one
    fit group, so the order does not matter. Returns human-readable change lines."""
    cfg = load_config(config_path)
    groups = list(cfg["fit"].items())
    # Coupon numbering: groups in config order, candidates in order, starting at 1.
    number_map: dict[int, tuple[str, float]] = {}
    n = 0
    for key, spec in groups:
        for cand in spec["candidates"]:
            n += 1
            number_map[n] = (key, cand)
    text = read_config_text(config_path)
    changes = []
    seen: set[str] = set()
    for p in pieces:
        if p not in number_map:
            raise SystemExit(f"piece {p} is not on the fit-test plate (1 to {n})")
        key, value = number_map[p]
        if key in seen:
            raise SystemExit(f"piece {p} is in group {key}, which was already set in this call")
        seen.add(key)
        text = _set_fit_value(text, key, value)
        changes.append(f"{key}: value {value} (piece {p}), tested on {date.today().isoformat()}")
    write_config_text(text, config_path)
    return changes


def _set_fit_value(text: str, key: str, value: float) -> str:
    # Find the block "  <key>:\n    value: ...\n    tested: ..." and rewrite the two lines.
    pattern = re.compile(rf"(^  {re.escape(key)}:\n)((?:    .*\n)+)", re.M)
    m = pattern.search(text)
    if not m:
        raise SystemExit(f"could not find fit group {key} in config")
    block = m.group(2)
    block = re.sub(r"^    value: .*$", f"    value: {value}", block, count=1, flags=re.M)
    block = re.sub(r"^    tested: .*$", f"    tested: true   # {date.today().isoformat()}", block, count=1, flags=re.M)
    return text[: m.start(2)] + block + text[m.end(2):]
