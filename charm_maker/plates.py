"""Assign filaments, pack pieces onto plates, and write the files.

With loaded slots in config, every part prints in a loaded spool, so a batch
normally fits one plate. Designs that need a spool that isn't loaded (Allen chose
"swap") go on their own plate with spool-swap instructions."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import manifold3d as m3d

from .filaments import Filament, nearest_filament, nearest_ink_filament
from .geom import bounds
from .palette import Palette
from .products import Piece


@dataclass
class PlacedPiece:
    piece: Piece
    x: float
    y: float
    assignments: dict[str, Filament]      # part name -> filament

    def solids(self) -> dict[str, m3d.Manifold]:
        out = {}
        lo, _ = bounds(_union(self.piece.parts))
        for name, solid in self.piece.parts.items():
            out[name] = solid.translate([self.x - lo[0], self.y - lo[1], -lo[2]])
        return out


@dataclass
class Swap:
    slot: int
    take_out: Filament | None
    put_in: Filament


@dataclass
class Plate:
    number: int
    pieces: list[PlacedPiece] = field(default_factory=list)
    filaments: list[Filament] = field(default_factory=list)
    slot_map: dict[Filament, int] = field(default_factory=dict)
    swaps: list[Swap] = field(default_factory=list)
    shelf_x: float = 0.0
    shelf_y: float = 0.0
    shelf_h: float = 0.0

    @property
    def stem(self) -> str:
        """The plate's file name says what is on it (Allen, 2026-11-14: two files both called
        "plate" hid the clicker case): plate-2-clicker-cases, plate-1-charms."""
        groups = {pp.piece.group for pp in self.pieces}
        if groups == {"cases"}:
            kind = "clicker-cases"
        elif self.pieces and all(pp.piece.supports for pp in self.pieces):
            kind = "figurines"
        elif len(groups) > 1:
            kind = "everything"
        else:
            kind = "charms"
        return f"plate-{self.number}-{kind}"

    def slots(self) -> dict[Filament, int]:
        """Filament -> AMS slot. Loaded slots when known, else 1..N in order."""
        if self.slot_map:
            return {f: self.slot_map[f] for f in self.filaments}
        used, out = set(), {}
        for f in self.filaments:
            if f.slot and f.slot not in used:
                out[f] = f.slot
                used.add(f.slot)
        nxt = 1
        for f in self.filaments:
            if f in out:
                continue
            while nxt in used:
                nxt += 1
            out[f] = nxt
            used.add(nxt)
        return out


def _union(parts: dict[str, m3d.Manifold]) -> m3d.Manifold:
    solids = list(parts.values())
    u = solids[0]
    for s in solids[1:]:
        u = u + s
    return u


def not_loaded(name: str, rgb) -> Filament:
    return Filament(f"{name} (not loaded)", None, tuple(int(v) for v in rgb))


def assign_filaments(piece: Piece, palette: Palette, overrides: dict[tuple[str, str], str],
                     decision: str | None = None) -> dict[str, Filament]:
    """Part name -> filament. `decision` answers the off-palette question for the
    batch: "nearest" (print in the nearest loaded color) or "swap" (own plate)."""
    out: dict[str, Filament] = {}
    for part, rgb in piece.part_colors.items():
        short = part[len(piece.name) + 1:]
        ov = (overrides.get((piece.name, short)) or overrides.get((piece.design.card, short))
              or overrides.get(("*", short)))
        slot = piece.part_slots.get(part)
        off = piece.part_off_palette.get(part)
        if ov:
            f = palette.find(ov)
            if f is None:
                raise ValueError(f"no spool called {ov!r} (from the override for {part})")
        elif palette.ready and slot is not None and slot in palette.slots:
            f = palette.slots[slot].filament
        elif off is not None:
            if decision == "nearest":
                f = palette.slots[off["nearest_slot"]].filament
            elif decision == "swap":
                f = off.get("suggested") or Filament(f"{off['color']} spool (not in your list)", None,
                                                     tuple(int(v) for v in off["rgb"]))
            else:
                f = not_loaded(off["color"], off["rgb"])
        elif part == piece.base_part:
            f = nearest_filament(rgb, palette.loaded_filaments() if palette.ready else palette.owned)
        elif palette.ready:
            f = nearest_ink_filament(rgb, palette.loaded_filaments())
        else:
            f = nearest_ink_filament(rgb, palette.owned)
        out[part] = f
    return out


def unanswered_off_palette(piece: Piece, assignments: dict[str, Filament]) -> list[str]:
    return [p for p, f in assignments.items() if f.name.endswith("(not loaded)")]


def pack_plates(cfg: dict, pieces: list[Piece], palette: Palette,
                assignments: dict[str, dict[str, Filament]], *, one_plate: bool = False) -> list[Plate]:
    """Charms first (flat-back figurines and clicker keycaps included), then clicker cases
    (upright, thicker layers, one filament), then round-back figurines (they need supports
    and a different layer height), each group on plates of its own. With `one_plate`,
    everything shares a plate (as many as the bed needs, usually one), whatever the
    layer heights and however many colors: Allen sets the spools in Bambu Studio."""
    groups = [[p for p in pieces if not p.supports and p.group != "cases"],
              [p for p in pieces if p.group == "cases"],
              [p for p in pieces if p.supports]]
    if one_plate:
        groups = [list(pieces)]
    plates: list[Plate] = []
    for group in groups:
        if not group:
            continue
        more = _pack_group(cfg, group, palette, assignments, one_plate=one_plate)
        for pl in more:
            pl.number += len(plates)
        plates += more
    return plates


def _pack_group(cfg: dict, pieces: list[Piece], palette: Palette,
                assignments: dict[str, dict[str, Filament]], *, one_plate: bool = False) -> list[Plate]:
    items = [(p, assignments[p.name]) for p in pieces]
    if not palette.ready:
        return _pack_by_filament_sets(cfg, items, any_colors=one_plate)

    loaded = set(palette.loaded_filaments())
    groups: dict[frozenset, list] = {}
    for piece, assign in items:
        need = frozenset(f for f in assign.values() if f not in loaded)
        groups.setdefault(need, []).append((piece, assign))
    if one_plate and len(groups) > 1:
        groups = {frozenset().union(*groups): items}
    plates: list[Plate] = []
    for need in sorted(groups, key=lambda k: (len(k), sorted(f.name for f in k))):
        group = groups[need]
        slot_map = {s.filament: s.slot for s in palette.slots.values()}
        swaps: list[Swap] = []
        if need:
            used = {f for _, a in group for f in a.values()}
            free = _swap_slots(cfg, palette, used)
            if len(free) < len(need):
                names = ", ".join(p.name for p, _ in group)
                raise ValueError(f"{names} need {len(need)} spool swap(s) but only {len(free)} slot(s) can be swapped")
            for f, slot in zip(sorted(need, key=lambda f: f.name), free):
                out = palette.slots.get(slot)
                swaps.append(Swap(slot, out.filament if out else None, f))
                if out:
                    slot_map.pop(out.filament, None)
                slot_map[f] = slot
        group_plates = _shelf_pack(cfg, group, start=len(plates) + 1)
        for plate in group_plates:
            plate.slot_map = slot_map
            plate.swaps = swaps
            fs = {f for pp in plate.pieces for f in pp.assignments.values()}
            plate.filaments = sorted(fs, key=lambda f: slot_map[f])
        plates.extend(group_plates)
    return plates


def _swap_slots(cfg: dict, palette: Palette, used: set[Filament]) -> list[int]:
    """Slots that can take a different spool for a plate: empty ones first, then
    loaded ones the plate does not use (never the white base), highest first."""
    n = cfg["printer"]["ams_slots"]
    empty = [s for s in range(1, n + 1) if s not in palette.slots]
    spare = [s for s in sorted(palette.slots, reverse=True)
             if palette.slots[s].filament not in used and not palette.slots[s].is_white]
    return empty + spare


def _shelf_pack(cfg: dict, group: list, start: int) -> list[Plate]:
    pv = cfg["preview"]
    bed_w, bed_h = cfg["printer"]["bed_size"]
    margin, gap = pv["bed_margin"], pv["piece_gap"]
    usable_w, usable_h = bed_w - 2 * margin, bed_h - 2 * margin
    plates: list[Plate] = []
    for piece, assign in sorted(group, key=lambda t: -max(t[0].size())):
        w, h = piece.size()
        if w > usable_w or h > usable_h:
            raise ValueError(f"{piece.name} ({w:.0f} x {h:.0f} mm) does not fit on the plate")
        for plate in plates:
            if _try_place(plate, piece, assign, w, h, usable_w, usable_h, gap):
                break
        else:
            plate = Plate(start + len(plates))
            plates.append(plate)
            assert _try_place(plate, piece, assign, w, h, usable_w, usable_h, gap)
    for plate in plates:
        for pp in plate.pieces:
            pp.x += margin
            pp.y += margin
    return plates


def _pack_by_filament_sets(cfg: dict, items: list, *, any_colors: bool = False) -> list[Plate]:
    """Before loaded slots are set: group designs so no plate needs more than N filaments
    (unless `any_colors`: then only the bed size splits them)."""
    pv = cfg["preview"]
    bed_w, bed_h = cfg["printer"]["bed_size"]
    margin, gap = pv["bed_margin"], pv["piece_gap"]
    max_f = 10 ** 6 if any_colors else cfg["printer"]["max_filaments_per_plate"]
    usable_w, usable_h = bed_w - 2 * margin, bed_h - 2 * margin
    items = [(p, a, set(a.values())) for p, a in items]
    items.sort(key=lambda t: (-len(t[2]), -max(t[0].size())))
    plates: list[Plate] = []
    for piece, assign, fset in items:
        w, h = piece.size()
        if w > usable_w or h > usable_h:
            raise ValueError(f"{piece.name} ({w:.0f} x {h:.0f} mm) does not fit on the plate")
        placed = False
        for plate in plates:
            if len(set(plate.filaments) | fset) > max_f:
                continue
            if _try_place(plate, piece, assign, w, h, usable_w, usable_h, gap):
                placed = True
                break
        if not placed:
            plate = Plate(len(plates) + 1)
            plates.append(plate)
            assert _try_place(plate, piece, assign, w, h, usable_w, usable_h, gap)
        for f in fset:
            if f not in plate.filaments:
                plate.filaments.append(f)
    for plate in plates:
        plate.filaments.sort(key=lambda f: (0 if "white" in f.name.lower() else 1 if "black" in f.name.lower() else 2, f.name))
        for pp in plate.pieces:
            pp.x += margin
            pp.y += margin
    return plates


def _try_place(plate: Plate, piece: Piece, assign, w, h, usable_w, usable_h, gap) -> bool:
    """Simple shelf packing: rows from the bottom, left to right."""
    if plate.shelf_x + w > usable_w:
        new_y = plate.shelf_y + plate.shelf_h + gap
        if new_y + h > usable_h:
            return False
        plate.shelf_x, plate.shelf_y, plate.shelf_h = 0.0, new_y, 0.0
    if plate.shelf_y + h > usable_h:
        return False
    plate.pieces.append(PlacedPiece(piece, plate.shelf_x, plate.shelf_y, assign))
    plate.shelf_x += w + gap
    plate.shelf_h = max(plate.shelf_h, h)
    return True


def write_plates(cfg: dict, plates: list[Plate], out_dir: Path) -> dict[int, dict[str, Path]]:
    from .bambu3mf import write_bambu_3mf
    from .export import write_plate

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    result: dict[int, dict[str, Path]] = {}
    for plate in plates:
        stem = plate.stem
        slots = plate.slots()
        objects = []
        plain: dict[str, m3d.Manifold] = {}
        for pp in plate.pieces:
            solids = pp.solids()
            parts = []
            for name, solid in solids.items():
                f = pp.assignments[name]
                parts.append((name, solid, slots[f], f.rgb))
                plain[name] = solid
            objects.append((pp.piece.name, parts))
        paths = {"3mf": write_bambu_3mf(objects, out_dir / f"{stem}.3mf")}
        paths.update({f"plain-{k}": v for k, v in write_plate(plain, out_dir, f"{stem}-plain").items()})
        result[plate.number] = paths
    return result
