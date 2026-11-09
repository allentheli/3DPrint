"""Map ink colors to Allen's filaments (from config) and handle plain-word overrides."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

DEFAULT_FILAMENTS = [
    {"name": "White", "slot": None, "color": "#F2F2F2"},
    {"name": "Black", "slot": None, "color": "#1A1A1A"},
    {"name": "Red", "slot": None, "color": "#D62828"},
    {"name": "Orange", "slot": None, "color": "#F77F00"},
    {"name": "Yellow", "slot": None, "color": "#FCBF49"},
    {"name": "Green", "slot": None, "color": "#2A9D8F"},
    {"name": "Blue", "slot": None, "color": "#1D4ED8"},
    {"name": "Purple", "slot": None, "color": "#7C3AED"},
    {"name": "Pink", "slot": None, "color": "#EC4899"},
]


@dataclass(frozen=True)
class Filament:
    name: str
    slot: int | None
    rgb: tuple[int, int, int]

    @property
    def hex(self) -> str:
        return "#%02X%02X%02X" % self.rgb


def load_filaments(cfg: dict) -> tuple[list[Filament], bool]:
    """Returns (filaments, from_config). Falls back to a generic palette."""
    entries = cfg.get("filaments") or []
    from_config = bool(entries)
    if not entries:
        entries = DEFAULT_FILAMENTS
    out = []
    for e in entries:
        out.append(Filament(str(e["name"]), e.get("slot"), _hex_to_rgb(e["color"])))
    return out, from_config


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _srgb_to_lab(rgb: np.ndarray) -> np.ndarray:
    c = rgb.astype(np.float64) / 255.0
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    M = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = c @ M.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    L = 116 * f[..., 1] - 16
    a = 500 * (f[..., 0] - f[..., 1])
    b = 200 * (f[..., 1] - f[..., 2])
    return np.stack([L, a, b], axis=-1)


def nearest_filament(rgb: tuple[int, int, int], filaments: list[Filament]) -> Filament:
    lab = _srgb_to_lab(np.array(rgb))
    labs = _srgb_to_lab(np.array([f.rgb for f in filaments]))
    d = np.linalg.norm(labs - lab, axis=1)
    return filaments[int(np.argmin(d))]


def find_filament(name: str, filaments: list[Filament]) -> Filament:
    name_l = name.strip().lower()
    for f in filaments:
        if f.name.lower() == name_l:
            return f
    for f in filaments:
        if name_l in f.name.lower():
            return f
    raise ValueError(f"no filament called {name!r}; known: {[f.name for f in filaments]}")


def parse_overrides(specs: list[str]) -> dict[tuple[str, str], str]:
    """'clip-03 pink=Magenta' -> {('clip-03', 'pink'): 'Magenta'}. 'pink=Magenta' applies to all designs."""
    out: dict[tuple[str, str], str] = {}
    for spec in specs:
        if "=" not in spec:
            raise ValueError(f"override {spec!r} must look like 'card-03 pink=Magenta'")
        left, fil = spec.split("=", 1)
        words = left.split()
        if len(words) >= 2:
            out[(words[0], " ".join(words[1:]))] = fil.strip()
        else:
            out[("*", words[0])] = fil.strip()
    return out
