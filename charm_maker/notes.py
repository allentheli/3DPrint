"""PRINT_NOTES.md: what goes in which AMS slot, layer height, plate type, finishing."""

from __future__ import annotations

from pathlib import Path

from .plates import Plate

FINISHING = {
    "hair_clip": "Hair clips: scuff the clip pad lightly, then glue the charm's pocket onto the pad with gel super glue or E6000. Let it cure fully before handing it out.",
    "keychain": "Keychains: open a 25 mm split ring and thread it through the tab hole.",
    "clicker": "Clickers: press the switch into the case from the top until it clicks, then push the keycap onto the stem.",
    "magnet_figure": "Magnet figures: glue a 10 x 2 mm magnet into each pocket with gel super glue (two-part epoxy if any pop out).",
    "earrings": "Earrings: hook style gets a jump ring and hook; stud style gets a glue-on post pad.",
    "pendant": "Pendants: thread a jump ring or bail through the hole, then the chain or cord.",
}


def write_print_notes(cfg: dict, plates: list[Plate], path: Path, *, from_config: bool, problems: list[str]) -> Path:
    pr = cfg["printer"]
    lines = ["# Print notes", ""]
    if not from_config:
        lines += ["**Filament list is empty in `config.yaml`.** Colors below use a generic palette; "
                  "slots are numbered in order of use. Add your spools to `filaments:` to get real names and slots.", ""]
    products = set()
    for plate in plates:
        lines.append(f"## Plate {plate.number}: `plates/plate-{plate.number}.3mf`")
        lines.append("")
        slots = plate.slots()
        lines.append("| AMS slot | Filament | Used by |")
        lines.append("| --- | --- | --- |")
        for f in plate.filaments:
            users = sorted({pp.piece.name for pp in plate.pieces for part, ff in pp.assignments.items() if ff == f})
            lines.append(f"| {slots[f]} | {f.name} ({f.hex}) | {', '.join(users)} |")
        lines.append("")
        kinds = {pp.piece.design.product for pp in plate.pieces}
        products |= kinds
        layer = pr["layer_height_cases"] if kinds <= {"clicker_case", "stand"} else pr["layer_height_charms"]
        lines.append(f"- Layer height: **{layer} mm**. Supports: off.")
        lines.append("- Plate: smooth PEI for a glossy face, textured PEI for a matte, sparkly face. The design face is on the bed.")
        lines.append("- Pieces: " + ", ".join(f"{pp.piece.name} ({pp.piece.size()[0]:.0f} x {pp.piece.size()[1]:.0f} mm)" for pp in plate.pieces))
        lines.append("")
    lines.append("## After printing")
    lines.append("")
    for p in sorted(products):
        if p in FINISHING:
            lines.append(f"- {FINISHING[p]}")
    lines.append("")
    if problems:
        lines.append("## Problems")
        lines.append("")
        lines += [f"- {p}" for p in problems]
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
