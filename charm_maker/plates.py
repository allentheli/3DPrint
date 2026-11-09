"""Pack pieces onto plates, limited by filaments per plate, and write the files."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import manifold3d as m3d

from .filaments import Filament, find_filament, nearest_filament
from .geom import bounds, move_to
from .products import Piece


@dataclass
class PartAssignment:
    part: str
    filament: Filament
    rgb: tuple[int, int, int]


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
class Plate:
    number: int
    pieces: list[PlacedPiece] = field(default_factory=list)
    filaments: list[Filament] = field(default_factory=list)
    shelf_x: float = 0.0
    shelf_y: float = 0.0
    shelf_h: float = 0.0

    def slots(self) -> dict[Filament, int]:
        """Filament -> AMS slot. Uses the config slot if given, else 1..N in order."""
        used = set()
        out = {}
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
            nxt += 1
        return out


def _union(parts: dict[str, m3d.Manifold]) -> m3d.Manifold:
    solids = list(parts.values())
    u = solids[0]
    for s in solids[1:]:
        u = u + s
    return u


def assign_filaments(piece: Piece, filaments: list[Filament], overrides: dict[tuple[str, str], str]) -> dict[str, Filament]:
    out: dict[str, Filament] = {}
    for part, rgb in piece.part_colors.items():
        short = part[len(piece.name) + 1:]
        key = (piece.name, short)
        if key in overrides:
            out[part] = find_filament(overrides[key], filaments)
        elif ("*", short) in overrides:
            out[part] = find_filament(overrides[("*", short)], filaments)
        else:
            out[part] = nearest_filament(rgb, filaments)
    return out


def pack_plates(cfg: dict, pieces: list[Piece], filaments: list[Filament],
                overrides: dict[tuple[str, str], str]) -> list[Plate]:
    pv = cfg["preview"]
    bed_w, bed_h = cfg["printer"]["bed_size"]
    margin, gap = pv["bed_margin"], pv["piece_gap"]
    max_f = cfg["printer"]["max_filaments_per_plate"]
    usable_w, usable_h = bed_w - 2 * margin, bed_h - 2 * margin

    items = []
    for p in pieces:
        a = assign_filaments(p, filaments, overrides)
        items.append((p, a, set(a.values())))
    # Big filament sets first, then by size, so shared-color pieces land together.
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
    # Shift everything by the bed margin, and list filaments in a stable order (white, black, rest).
    for plate in plates:
        plate.filaments.sort(key=lambda f: (0 if "white" in f.name.lower() else 1 if "black" in f.name.lower() else 2, f.name))
        for pp in plate.pieces:
            pp.x += margin
            pp.y += margin
    return plates


def _try_place(plate: Plate, piece: Piece, assign, w, h, usable_w, usable_h, gap) -> bool:
    """Simple shelf packing: rows from the bottom, left to right."""
    if plate.shelf_x + w > usable_w:
        # New shelf.
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
        stem = f"plate-{plate.number}"
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
        paths = {"3mf": write_bambu_3mf(objects, out_dir / f"{stem}.3mf", {slots[f]: f for f in plate.filaments})}
        paths.update({f"plain-{k}": v for k, v in write_plate(plain, out_dir, f"{stem}-plain").items()})
        result[plate.number] = paths
    return result
