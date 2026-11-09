"""The loaded palette: which spool is in which AMS slot, and what its matching
marker looks like in a photo. Kids draw only with these colors."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import numpy as np
import yaml

from .config import load_config, read_config_text, write_config_text
from .filaments import DEFAULT_FILAMENTS, Filament, _hex_to_rgb, _srgb_to_lab

HUE_WORDS = [
    (0, "red"), (30, "orange"), (60, "orange"), (85, "yellow"), (100, "yellow"), (130, "lime"),
    (160, "green"), (200, "teal"), (230, "sky blue"), (280, "blue"), (310, "purple"),
    (340, "magenta"), (355, "pink"), (360, "red"),
]


@dataclass
class LoadedSlot:
    slot: int
    filament: Filament                       # slot is set on the filament
    marker_rgb: tuple[int, int, int] | None = None
    calibrated: str | None = None

    @property
    def is_white(self) -> bool:
        L, a, b = rgb_to_lab(self.filament.rgb)
        return L > 85 and np.hypot(a, b) < 12

    @property
    def reference_rgb(self) -> tuple[int, int, int]:
        """What this slot's ink looks like in a photo: the calibrated marker if known."""
        return self.marker_rgb or self.filament.rgb


@dataclass
class Palette:
    slots: dict[int, LoadedSlot]
    owned: list[Filament]
    owned_from_config: bool
    notes: list[str] = field(default_factory=list)

    @property
    def ready(self) -> bool:
        return bool(self.slots)

    @property
    def calibrated(self) -> bool:
        inks = self.ink_slots()
        return bool(inks) and all(s.marker_rgb for s in inks)

    def ink_slots(self) -> list[LoadedSlot]:
        """Loaded slots a kid can draw with (everything but white, which is the paper)."""
        return [s for _, s in sorted(self.slots.items()) if not s.is_white]

    def loaded_filaments(self) -> list[Filament]:
        return [s.filament for _, s in sorted(self.slots.items())]

    def base_slot(self, paper_rgb=(250, 250, 250)) -> LoadedSlot | None:
        whites = [s for s in self.slots.values() if s.is_white]
        if whites:
            return min(whites, key=lambda s: s.slot)
        if not self.slots:
            return None
        return min(self.slots.values(), key=lambda s: color_distance(s.filament.rgb, paper_rgb))

    def find(self, name: str) -> Filament | None:
        n = name.strip().lower()
        for pool in (self.loaded_filaments(), self.owned):
            for f in pool:
                if f.name.lower() == n:
                    return f
            for f in pool:
                if n in f.name.lower():
                    return f
        return None

    def suggest_spool(self, rgb, max_distance: float = 35.0) -> Filament | None:
        """Nearest owned spool that is not loaded, if it is close enough. Only spools from
        Allen's real list count, never the generic placeholder palette."""
        if not self.owned_from_config:
            return None
        loaded = {f.name for f in self.loaded_filaments()}
        cands = [f for f in self.owned if f.name not in loaded]
        if not cands:
            return None
        best = min(cands, key=lambda f: color_distance(f.rgb, rgb))
        return best if color_distance(best.rgb, rgb) <= max_distance else None


def rgb_to_lab(rgb) -> np.ndarray:
    return _srgb_to_lab(np.asarray(rgb, dtype=np.float64))


def color_distance(rgb1, rgb2, lw: float = 0.3, cw: float = 0.5) -> float:
    return float(lab_distance(rgb_to_lab(rgb1)[None, :], rgb_to_lab(rgb2), lw, cw)[0])


def lab_distance(lab: np.ndarray, ref_lab: np.ndarray, lw: float = 0.3, cw: float = 0.5) -> np.ndarray:
    """Distance that cares mostly about hue. Marker fill gets streaky and paler at the
    edges, which changes lightness and chroma; a different marker changes hue."""
    dL = lab[..., 0] - ref_lab[0]
    c1 = np.hypot(lab[..., 1], lab[..., 2])
    c2 = float(np.hypot(ref_lab[1], ref_lab[2]))
    dC = c1 - c2
    da = lab[..., 1] - ref_lab[1]
    db = lab[..., 2] - ref_lab[2]
    dH2 = np.maximum(da * da + db * db - dC * dC, 0.0)
    return np.sqrt((lw * dL) ** 2 + (cw * dC) ** 2 + dH2)


def color_word(rgb) -> str:
    L, a, b = rgb_to_lab(rgb)
    c = np.hypot(a, b)
    if c < 12:
        return "white" if L > 85 else "black" if L < 35 else "gray"
    h = (np.degrees(np.arctan2(b, a)) + 360.0) % 360.0
    # Lab hue angles: red ~40, orange ~60, yellow ~95, green ~135, blue ~290, purple ~310, pink ~350.
    table = [(25, "red"), (45, "red"), (62, "orange"), (75, "orange"), (100, "yellow"), (120, "lime"),
             (150, "green"), (195, "teal"), (240, "sky blue"), (290, "blue"), (315, "purple"),
             (335, "magenta"), (352, "pink"), (385, "red")]
    hh = h if h >= 15 else h + 360
    return min(table, key=lambda t: abs(t[0] - hh))[1]


NAME_WORDS = {
    "white": "white", "black": "black", "gray": "gray", "grey": "gray", "silver": "gray",
    "red": "red", "orange": "orange", "yellow": "yellow", "gold": "yellow", "lime": "lime",
    "green": "green", "mint": "green", "teal": "teal", "cyan": "sky blue", "sky": "sky blue",
    "blue": "blue", "navy": "blue", "purple": "purple", "violet": "purple", "lavender": "purple",
    "magenta": "magenta", "pink": "pink", "rose": "pink", "brown": "brown", "beige": "beige",
}


def spool_word(f: Filament) -> str:
    """Short color word for part names: from the spool's name if it says one, else from its color."""
    for token in re.findall(r"[a-z]+", f.name.lower()):
        if token in NAME_WORDS:
            return NAME_WORDS[token]
    return color_word(f.rgb)


def _parse_hex(h) -> tuple[int, int, int] | None:
    return _hex_to_rgb(str(h)) if h else None


def load_palette(cfg: dict) -> Palette:
    owned_entries = cfg.get("filaments") or []
    owned = [Filament(str(e["name"]), None, _hex_to_rgb(e["color"])) for e in owned_entries]
    from_config = bool(owned)
    if not owned:
        owned = [Filament(e["name"], None, _hex_to_rgb(e["color"])) for e in DEFAULT_FILAMENTS]
    slots: dict[int, LoadedSlot] = {}
    for key, entry in (cfg.get("loaded") or {}).items():
        if not entry:
            continue
        slot = int(key)
        f = Filament(str(entry["spool"]), slot, _hex_to_rgb(entry["color"]))
        slots[slot] = LoadedSlot(slot, f, _parse_hex(entry.get("marker")), entry.get("calibrated"))
    return Palette(slots, owned, from_config)


# ---------------------------------------------------------------------------
# Writing the `loaded:` block back into config.yaml (comments elsewhere survive)
# ---------------------------------------------------------------------------

def _format_loaded(loaded: dict[int, dict]) -> str:
    if not loaded:
        return "loaded: {}\n"
    lines = ["loaded:"]
    for slot in sorted(loaded):
        e = loaded[slot]
        parts = [f'spool: {yaml.safe_dump(e["spool"], default_style=chr(34)).strip()}', f'color: "{e["color"]}"']
        if e.get("marker"):
            parts.append(f'marker: "{e["marker"]}"')
        if e.get("calibrated"):
            parts.append(f'calibrated: "{e["calibrated"]}"')
        lines.append(f"  {slot}: {{{', '.join(parts)}}}")
    return "\n".join(lines) + "\n"


def write_loaded(config_path, loaded: dict[int, dict]) -> None:
    text = read_config_text(config_path)
    m = re.search(r"^loaded:.*\n(?:(?:[ \t]+.*)?\n)*?(?=^\S|\Z)", text, re.M)
    if not m:
        raise SystemExit("config.yaml has no `loaded:` section")
    block = m.group(0)
    # Keep trailing blank lines and comment-only lines (they belong to what follows).
    body_end = len(block)
    write_config_text(text[: m.start()] + _format_loaded(loaded) + text[m.start() + body_end:], config_path)


def _loaded_dict(cfg: dict) -> dict[int, dict]:
    return {int(k): dict(v) for k, v in (cfg.get("loaded") or {}).items() if v}


def to_hex(rgb) -> str:
    return "#%02X%02X%02X" % tuple(int(v) for v in rgb)


def set_slot(config_path, slot: int, spool: str, color: str | None = None) -> str:
    cfg = load_config(config_path)
    slots = cfg["printer"]["ams_slots"]
    if not 1 <= slot <= slots:
        raise SystemExit(f"slot must be 1 to {slots}")
    loaded = _loaded_dict(cfg)
    if spool.lower() in ("empty", "none", "-"):
        old = loaded.pop(slot, None)
        write_loaded(config_path, loaded)
        return f"slot {slot} is now empty" + (f" (was {old['spool']})" if old else "")
    if color is None:
        pal = load_palette(cfg)
        known = pal.find(spool)
        if known is None:
            raise SystemExit(f"no spool called {spool!r} in the spool list; add --color \"#RRGGBB\"")
        spool, color = known.name, to_hex(known.rgb)
    old = loaded.get(slot)
    loaded[slot] = {"spool": spool, "color": color.upper()}
    if old and old.get("spool") == spool and old.get("color", "").upper() == color.upper():
        # Same spool back in the same slot: keep its calibration.
        for k in ("marker", "calibrated"):
            if old.get(k):
                loaded[slot][k] = old[k]
    write_loaded(config_path, loaded)
    msg = f"slot {slot}: {spool} ({color.upper()})"
    if old and old.get("spool") != spool:
        msg += f", replacing {old['spool']}. Rescan the calibration card for this slot."
    return msg


def save_calibration(config_path, markers: dict[int, tuple[int, int, int]]) -> list[str]:
    cfg = load_config(config_path)
    loaded = _loaded_dict(cfg)
    today = date.today().isoformat()
    out = []
    for slot, rgb in sorted(markers.items()):
        if slot not in loaded:
            out.append(f"slot {slot}: box filled in, but nothing is loaded there; ignored")
            continue
        loaded[slot]["marker"] = to_hex(rgb)
        loaded[slot]["calibrated"] = today
        out.append(f"slot {slot} ({loaded[slot]['spool']}): marker {to_hex(rgb)}")
    write_loaded(config_path, loaded)
    return out
