"""Filament chips: one small tag per loaded filament, printed live as the kids'
printer tour. Each chip is one filament, with its slot number cut into the top.
Printed one object at a time, so the AMS swaps once per chip, not every layer."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import manifold3d as m3d

from .geom import extrude, move_to, rounded_rect
from .labels import label_shape
from .palette import Palette


@dataclass
class Chip:
    slot: int
    filament_name: str
    rgb: tuple[int, int, int]
    solid: m3d.Manifold


def build_chips(cfg: dict, palette: Palette) -> list[Chip]:
    if not palette.ready:
        raise ValueError("no loaded slots in config yet: tell Claude which spool is in which slot")
    c = cfg["chips"]
    w, l, t = c["width"], c["length"], c["thickness"]
    chips = []
    x = 0.0
    for slot, ls in sorted(palette.slots.items()):
        body = extrude(rounded_rect(w, l, c["corner_radius"], w / 2, l / 2), t)
        number = label_shape(str(slot), c["number_height"], c["number_stroke"], w / 2, l / 2)
        depth = c["number_depth"]
        body = body - extrude(number, depth + 1.0, t - depth)
        chips.append(Chip(slot, ls.filament.name, ls.filament.rgb, move_to(body, x, 0.0)))
        x += w + c["gap"]
    return chips


def estimate_minutes(cfg: dict, chips: list[Chip]) -> float:
    """A rough guess, not the slicer: start-up + plastic at an average flow + one AMS
    swap between chips (Print sequence: By object)."""
    c = cfg["chips"]
    volume = sum(ch.solid.volume() for ch in chips)
    printing = volume / c["estimate_flow_mm3_per_s"] / 60.0
    swaps = max(0, len(chips) - 1) * c["estimate_swap_minutes"]
    return c["estimate_startup_minutes"] + printing + swaps


def write_chips(cfg: dict, palette: Palette, out_dir: Path) -> dict[str, Path]:
    from .bambu3mf import write_bambu_3mf
    from .export import write_plate
    from .preview import render_shaded

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    chips = build_chips(cfg, palette)
    bed_w, _ = cfg["printer"]["bed_size"]
    margin = cfg["preview"]["bed_margin"]
    row_w = max(ch.solid.bounding_box()[3] for ch in chips)
    if row_w + 2 * margin > bed_w:
        raise ValueError("the chips do not fit in one row; reduce chips.gap or chips.width")
    placed = {f"chip slot {ch.slot}": ch.solid.translate([margin, margin, 0.0]) for ch in chips}
    objects = [(name, [(name, solid, ch.slot, ch.rgb)]) for (name, solid), ch in zip(placed.items(), chips)]
    paths = {"3mf": write_bambu_3mf(objects, out_dir / "filament-chips.3mf")}
    paths.update({f"plain-{k}": v for k, v in write_plate(placed, out_dir, "filament-chips-plain").items()})
    paths["preview"] = render_shaded(placed, out_dir / "filament-chips-preview.png", view=(45.0, -20.0),
                                     px_per_mm=8, labels=False,
                                     colors={n: ch.rgb for n, ch in zip(placed, chips)})
    minutes = estimate_minutes(cfg, chips)
    c = cfg["chips"]
    lines = [
        "# Filament chips: the printer tour",
        "",
        "One chip per loaded spool, with its slot number cut into the top. Print this live",
        "while the kids watch, before they design. Each kid can see that slot 3 is pink,",
        "and so on.",
        "",
        "| Chip | Slot | Spool |",
        "| --- | --- | --- |",
        *[f"| {i} | {ch.slot} | {ch.filament_name} |" for i, ch in enumerate(chips, 1)],
        "",
        "## Print it",
        "",
        "1. Bambu Studio: **File > Import > Import 3MF/STL/STEP/SVG/OBJ/AMF...**, pick `filament-chips.3mf`.",
        "   Choose **Load geometry only** if asked.",
        "2. Check each chip has its slot's filament. If not, click the chip in the object list and pick",
        "   its slot number in the filament dropdown.",
        "3. **Process > Others > Print sequence: By object.** This prints one chip at a time, so the AMS",
        "   changes filament once per chip instead of on every layer. It is what keeps the plate short.",
        f"4. **Layer height {c['layer_height']} mm.** Supports off.",
        "5. Click **Slice plate** and read the time estimate in the top right.",
        f"   It should be under about {c['budget_minutes']} minutes. If it is not, tell Claude and the chips get smaller.",
        "6. If Bambu Studio says the objects are too close for By object, click **Arrange** (the A key).",
        "",
        f"My rough estimate is {minutes:.0f} minutes, including start-up. It is a guess from the",
        "amount of plastic and the number of filament changes. Bambu Studio's number is the real one.",
        "",
    ]
    notes = out_dir / "CHIPS.md"
    notes.write_text("\n".join(lines), encoding="utf-8")
    paths["notes"] = notes
    return paths
