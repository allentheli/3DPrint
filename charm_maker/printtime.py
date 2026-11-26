"""Rough print times, not the slicer's (Allen, 2026-11-14: kids may make more than 3 pieces each;
print each kid's quickest ones before they go home, the rest after).

The model counts what takes time on small multicolor pieces: the plastic (at an effective
flow for fine layers), a floor per layer (small layers wait to cool), and the color changes
(every layer with several colors swaps filament, and a swap with its purge takes about a
minute and a half). It ranks pieces well; the minutes are a guess until Allen compares one
plate with Bambu Studio's number and the `print_time` settings are tuned to match.
"""

from __future__ import annotations

import math

from .plates import Plate

def layer_height(cfg: dict, plate: Plate | None = None) -> float:
    pr = cfg["printer"]
    if plate is not None and plate.kind == "clicker-cases":
        return pr["layer_height_cases"]
    if plate is not None and plate.kind == "figurines":
        return cfg["figurine"]["layer_height"]
    return pr["layer_height_charms"]


def estimate(cfg: dict, items: list[tuple[dict, dict]], layer_h: float, *, startup: bool = True) -> dict:
    """items: [(solids by part name, filament by part name)], each standing on the bed.
    Returns {"minutes", "changes", "layers"}."""
    t = cfg["print_time"]
    plastic, top = 0.0, 0.0
    spans: list[tuple[float, float, object]] = []
    for solids, filaments in items:
        if not solids:
            continue
        z0 = min(s.bounding_box()[2] for s in solids.values())
        for name, s in solids.items():
            bb = s.bounding_box()
            plastic += s.volume() * t["fill"]
            spans.append((bb[2] - z0, bb[5] - z0, filaments[name]))
            top = max(top, bb[5] - z0)
    layers = max(1, math.ceil(top / layer_h - 1e-6))
    changes, before = 0, set()
    for i in range(layers):
        z = (i + 0.5) * layer_h
        here = {f for a, b, f in spans if a <= z <= b}
        if not here:
            continue
        # Each extra color on a layer is a change; one more if the layer can't start with the
        # filament the last layer ended on.
        changes += len(here) - 1 + (0 if not before or (before & here) else 1)
        before = here
    printing = max(plastic / t["flow_mm3_per_s"], layers * t["min_layer_seconds"]) / 60.0
    minutes = printing + changes * t["change_minutes"] + (t["startup_minutes"] if startup else 0.0)
    return {"minutes": minutes, "changes": changes, "layers": layers}


def plate_estimate(cfg: dict, plate: Plate) -> dict:
    return estimate(cfg, [(pp.solids(), pp.assignments) for pp in plate.pieces], layer_height(cfg, plate))


def quickest(cfg: dict, pieces: list, assignments: dict) -> dict[str, list[dict]]:
    """Each kid's pieces, quickest first: {kid: [{"what", "card", "minutes", "pieces"}]}. A clicker
    counts with its case (and post); an earring pair as one. Times leave out the printer's
    start-up, which a plate pays once. Kids in name order, then cards with no name."""
    groups: dict[str, list] = {}
    for p in pieces:
        groups.setdefault(p.design.extras.get("card", p.name), []).append(p)
    out: dict[str, list[dict]] = {}
    for card, group in groups.items():
        kid, word = group[0].design.extras.get("who", (card, ""))
        word = word or cfg["products"][group[0].design.product].get("file_word", group[0].design.product)
        layer_h = cfg["figurine"]["layer_height"] if any(p.supports for p in group) else layer_height(cfg)
        est = estimate(cfg, [(p.parts, assignments[p.name]) for p in group], layer_h, startup=False)
        what = {"clicker": "clicker (with its case)", "earrings": "earrings (the pair)"}.get(word, word)
        out.setdefault(kid, []).append({"what": what, "card": card, "minutes": est["minutes"],
                                        "pieces": [p.name for p in group]})
    for items in out.values():
        items.sort(key=lambda it: it["minutes"])
        whats = [it["what"] for it in items]
        for it in items:                 # two of the same: say which card
            if whats.count(it["what"]) > 1:
                it["what"] += f" ({it['card']})"
    named = {k for k, v in out.items() if not any(k == it["card"] for it in v)}
    return dict(sorted(out.items(), key=lambda kv: (kv[0] not in named, kv[0])))


def duration(minutes: float) -> str:
    """12 min, 1 h 10 min: easy to plan a party evening by."""
    m = max(1, round(minutes))
    if m < 60:
        return f"{m} min"
    h, m = divmod(5 * round(m / 5), 60)     # long prints to the nearest 5 minutes
    return f"{h} h" + (f" {m} min" if m else "")


def close_to_quickest(items: list[dict]) -> list[dict]:
    """The pieces about as quick as a kid's quickest (within 5 minutes or a quarter): Allen,
    2026-11-14: "if they r close, I will give kids the choice", so no piece is picked for them."""
    if not items:
        return []
    first = items[0]["minutes"]
    return [it for it in items if it["minutes"] <= max(first + 5.0, first * 1.25)]


def quickest_lines(cfg: dict, table: dict[str, list[dict]]) -> list[str]:
    def m(it):
        return f"{it['what']} {duration(it['minutes'])}"

    lines = []
    for kid, items in table.items():
        named = any(it["card"] != kid for it in items)
        who = kid.replace("-", " ").title() if named else kid
        close = close_to_quickest(items)
        rest = items[len(close):]
        text = " or ".join(m(it) for it in close)
        if len(close) > 1:
            text += f" (close: let {who if named else 'them'} pick)"
        if rest:
            text += ", then " + ", ".join(m(it) for it in rest)
        lines.append(f"- **{who}:** {text}")
    return lines
