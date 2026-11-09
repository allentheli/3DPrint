"""PRINT_NOTES.md: what goes in which AMS slot, swaps, layer height, plate type, finishing."""

from __future__ import annotations

from pathlib import Path

from .palette import Palette
from .plates import Plate

FINISHING = {
    "hair_clip": "Hair clips: scuff the clip pad lightly, then glue the charm's pocket onto the pad with gel super glue or E6000. Let it cure fully before handing it out.",
    "keychain": "Keychains: open a 25 mm split ring and thread it through the tab hole.",
    "clicker": "Clickers: press the switch into the case from the top until it clicks, then push the keycap onto the stem.",
    "magnet_figure": "Magnet figures: glue a 10 x 2 mm magnet flat on the back with gel super glue, about 12 mm above the bottom edge so it lines up with the stand (two-part epoxy if it pops off). Let it cure fully.",
    "earrings": "Earrings: push the hook straight through the loop, left to right, so the earring faces forward. Stud style: glue a post pad on the flat back.",
    "pendant": "Pendants: thread the chain straight through the loop, left to right, so the pendant faces forward.",
}


def write_print_notes(cfg: dict, plates: list[Plate], path: Path, *, palette: Palette, problems: list[str]) -> Path:
    pr = cfg["printer"]
    lines = ["# Print notes", ""]
    if not palette.ready:
        lines += ["**No loaded slots in `config.yaml` yet.** Colors use a generic palette and slots are "
                  "numbered in order of use. Tell Claude which spool is in which slot.", ""]
    else:
        loaded = ", ".join(f"slot {s.slot} {s.filament.name}" for _, s in sorted(palette.slots.items()))
        lines += [f"Loaded right now: {loaded}.", ""]
        if not palette.calibrated:
            lines += ["The calibration card has not been scanned for every loaded marker yet, so ink was "
                      "matched to the spool colors. Scan it before the party for the best matching.", ""]
    products = set()
    for plate in plates:
        lines.append(f"## Plate {plate.number}: `plates/plate-{plate.number}.3mf`")
        lines.append("")
        if plate.swaps:
            lines.append("**Spool swap for this plate.** Print it after the plates without swaps.")
            lines.append("")
            for i, sw in enumerate(plate.swaps, 1):
                out = f"take {sw.take_out.name} out of slot {sw.slot} and put" if sw.take_out else f"put"
                lines.append(f"{i}. Before printing: {out} **{sw.put_in.name}** in slot {sw.slot}.")
            back = [sw for sw in plate.swaps if sw.take_out]
            if back:
                lines.append(f"{len(plate.swaps) + 1}. After printing: put "
                             + ", ".join(f"{sw.take_out.name} back in slot {sw.slot}" for sw in back)
                             + ", and tell Claude if you leave it swapped.")
            lines.append("")
        elif palette.ready:
            lines.append("No spool swaps: everything prints with the spools already loaded.")
            lines.append("")
        slots = plate.slots()
        lines.append("| AMS slot | Filament | Used by |")
        lines.append("| --- | --- | --- |")
        for f in sorted(plate.filaments, key=lambda f: slots[f]):
            users = sorted({pp.piece.name for pp in plate.pieces for ff in pp.assignments.values() if ff == f})
            lines.append(f"| {slots[f]} | {f.name} ({f.hex}) | {', '.join(users)} |")
        lines.append("")
        kinds = {pp.piece.design.product for pp in plate.pieces}
        products |= kinds
        layer = pr["layer_height_charms"]
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


def write_question(off: list[dict], path: Path, uncalibrated: list[str] | None = None) -> tuple[Path, str]:
    """The once-per-batch question: an unscanned calibration card, and colors that aren't loaded."""
    lines = ["# Question before printing", ""]
    if uncalibrated:
        lines += [
            "## The calibration card hasn't been scanned for: " + ", ".join(uncalibrated),
            "",
            "Without it, ink is matched to the spool colors, and close markers (an orange and a",
            "golden yellow, say) can't be told apart. A color that isn't loaded could slip into a",
            "loaded one without anyone noticing.",
            "",
            "- **scan**: fill in the calibration card, scan it, and run the batch again (best).",
            "- **go ahead**: use the spool colors this time. Check the contact sheet colors closely.",
            "",
        ]
    if off:
        rows = []
        for o in off:
            suggest = o["suggested"].name if o.get("suggested") else "none in your spool list"
            rows.append(f"| {o['card']} | {o['color']} | {o['area_mm2']} mm² | {o['nearest_name']} (slot {o['nearest_slot']}) | {suggest} |")
        lines += [
            "## Colors that aren't loaded",
            "",
            "These drawings use a color that isn't in the printer:",
            "",
            "| Card | Color | Area | Nearest loaded color | Matching spool you own |",
            "| --- | --- | --- | --- | --- |",
            *rows,
            "",
            "Answer once for the whole batch:",
            "",
            "- **nearest**: print them in the nearest loaded color. One plate, no swaps.",
            "- **swap**: print them on their own plate, with a spool swap for that plate.",
            "",
            "A different answer per card also works, for example \"card clip-03 orange as Pink PLA\".",
            "",
        ]
    text = "\n".join(lines)
    path.write_text(text, encoding="utf-8")
    return path, text
