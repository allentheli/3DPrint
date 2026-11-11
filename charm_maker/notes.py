"""PRINT_NOTES.md: what goes in which AMS slot, swaps, layer height, plate type, finishing."""

from __future__ import annotations

from pathlib import Path

from .palette import Palette
from .plates import Plate

FINISHING = {
    "hair_clip": "Hair clips: scuff the clip pad lightly, then glue the charm's pocket onto the pad with gel super glue or E6000. Let it cure fully before handing it out.",
    "keychain": "Keychains: open a 25 mm split ring and thread it through the tab hole.",
    "clicker": "Clickers: push the switch down into the cup until it clicks into the square hole at the bottom (it only fits one way up, any of four turns), then push the keycap's post onto the switch's cross stem: the keycap sits in the cup's opening, a little above the rim. Thread a 25 mm split ring through the hole in the post at the top of the case (it runs left to right). A pen through the hole in the case's floor pushes the switch back out.",
    "clicker_post": "Puffy and figurine clicker keycaps come with their post as a separate small piece: glue its flat end into the round dent in the middle of the keycap's back with gel super glue (socket end out), and let it cure before pushing it onto the switch.",
    "magnet_figure": "Magnet figures: glue a 10 x 2 mm magnet flat on the back with gel super glue, about 12 mm above the bottom edge so it lines up with the stand (two-part epoxy if it pops off). Let it cure fully.",
    "earrings": "Earrings: twist a 4 mm jump ring open sideways (don't pull it apart), slip it through the small hole at the top, hang the hook on it and twist it shut. If an earring faces sideways, turn the jump ring a quarter turn. Stud style: glue a post pad on the flat back.",
    "pendant": "Pendants: thread the chain straight through the loop, left to right, so the pendant faces forward.",
    "figurine": "Round-back figurines: let the plate cool, then peel the tree supports off the back with your fingers or flush cutters; sand any nubs. They have no ring, clip or loop: they are toys to stand up or hold.",
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
        lines.append(f"Who's who: `plates/plate-{plate.number}-map.png` shows each piece's name where it sits on the plate.")
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
        products |= {"figurine" if pp.piece.supports else pp.piece.design.product for pp in plate.pieces}
        products |= {"clicker_post" for pp in plate.pieces if pp.piece.attachment.get("kind") == "keycap_post"}
        cases = [pp.piece for pp in plate.pieces if pp.piece.group == "cases"]
        n_slots = cfg["printer"]["ams_slots"]
        if len(plate.filaments) > n_slots:
            lines.append(f"- **{len(plate.filaments)} colors, {n_slots} AMS slots:** before slicing, set some parts to the same "
                         "filament in Bambu Studio so the plate uses at most "
                         f"{n_slots}. The slot numbers above past {n_slots} are only labels.")
        if cases and len(cases) == len(plate.pieces):
            if any(c.attachment.get("needs_supports") for c in cases):
                lines.append(f"- Clicker cases ({', '.join(c.name for c in cases)}) print upright, the open cup on top. "
                             "Turn supports **on** for the ring tab on the side: in the Process panel open the **Support** "
                             "tab, tick **Enable support**, set **Type** to **tree(auto)**. Supports grow only under the tab; "
                             "snap them off after printing. (The switch plate inside needs none.)")
            else:
                lines.append(f"- Clicker cases ({', '.join(c.name for c in cases)}) print upright, the open cup on top. "
                             "Supports off: the switch plate inside hangs over the hollow under it by less than 1 mm.")
            lines.append(f"- Layer height: **{pr['layer_height_cases']} mm**. One filament for the whole plate, any color; "
                         "assign it to every part.")
            lines.append("- Pieces: " + ", ".join(f"{c.name} ({c.size()[0]:.0f} x {c.size()[1]:.0f} mm, "
                                                    f"{c.thickness:.0f} mm tall)" for c in cases))
            lines.append("")
            continue
        figs = [pp.piece.name for pp in plate.pieces if pp.piece.supports]
        if figs and len(figs) == len(plate.pieces):
            lines.append(f"- Figurines ({', '.join(figs)}): they lie on their backs with the front up. Turn supports **on**: "
                         "in the Process panel open the **Support** tab, tick **Enable support**, set **Type** to **tree(auto)**.")
            lines.append(f"- Layer height: **{cfg['figurine']['layer_height']} mm**. Plate: either PEI plate; "
                         "the back and the supports sit on it, and the colored front prints on top.")
            lines.append("- Pieces: " + ", ".join(f"{pp.piece.name} ({pp.piece.size()[0]:.0f} x {pp.piece.size()[1]:.0f} mm, "
                                                    f"{pp.piece.thickness:.0f} mm thick)" for pp in plate.pieces))
            lines.append("")
            continue
        layer = pr["layer_height_charms"]
        why = ([f"the round-back figurines ({', '.join(figs)})"] if figs else []) + \
              [f"the ring tab on {c.name}" for c in cases if c.attachment.get("needs_supports")]
        if why:
            lines.append(f"- Layer height: **{layer} mm** for the whole plate. Supports: **on**, for {' and '.join(why)}: "
                         "**Support** tab, tick **Enable support**, **Type** **tree(auto)**. The other pieces have "
                         "nothing to hold up, so they get none.")
        else:
            lines.append(f"- Layer height: **{layer} mm**. Supports: off.")
        if cases:
            lines.append(f"- Clicker cases ({', '.join(c.name for c in cases)}) stand upright on this plate, the open cup "
                         f"on top. At {layer} mm they just take longer than on their own plate "
                         f"({pr['layer_height_cases']} mm). Set each case to any one filament.")
        charms = [pp for pp in plate.pieces if pp.piece.group != "cases" and not pp.piece.supports]
        up = [pp.piece.name for pp in charms if pp.piece.face_up]
        down = [pp.piece.name for pp in charms if not pp.piece.face_up]
        if down:
            lines.append("- Flat pieces print face-down: smooth PEI gives a glossy face, textured PEI a matte, sparkly one.")
        if up:
            lines.append(f"- Shaped pieces ({', '.join(up)}) print face-up with the colors on top, flat back on the bed, "
                         "no supports. Their colors change over more layers than flat ones, so they print slower and purge more. "
                         "Keep 0.12 mm layers so the curves stay smooth.")
            tall = [pp.piece for pp in plate.pieces if pp.piece.style == "figurine"]
            if tall:
                top = max(pc.thickness for pc in tall)
                lines.append(f"- Figurine fronts ({', '.join(pc.name for pc in tall)}) stand up to {top:.0f} mm tall, so "
                             "their colors change over many layers: expect more filament changes and more printer poop.")
            if any(pp.piece.face_up and pp.piece.attachment.get("kind") == "clip_pocket" for pp in plate.pieces):
                lines.append("- On face-up hair clips the clip pocket is on the bed side; the printer bridges over it.")
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
