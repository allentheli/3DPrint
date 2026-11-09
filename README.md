# Charm Maker

Turns a photo of a hand drawing into a ready-to-print file for a Bambu Lab printer
with AMS. Kids draw on printed design cards, Allen photographs the cards, and the
tool makes flat, flush, multi-color charms: hair clip charms, keychains, clicker
keychains, magnet figures, earrings and pendants.

The full specification is in `docs/charm-maker-spec.md`. The everyday runbook for a
Claude Code session is in `CLAUDE.md`.

## Status

| Milestone | What | Status |
| --- | --- | --- |
| 0 | Fit-test plate and config | Built. Waiting for Allen's fit results. |
| 1 | Cards, hair clips, keychains | Not started |
| 2 | Party batch | Not started |
| 3 | Clicker keychain | Not started |
| 4 | Adults: earrings, pendants, PNG/SVG, text | Not started |
| 5 | Magnet figures and the stand | Stand built (fit test). Figures not started |

## Setup

Python 3.11 or newer.

```bash
pip install -r requirements.txt
```

## Commands

Build the milestone 0 fit-test plate (3MF, STLs, previews, printed guide):

```bash
python -m charm_maker fit-test
```

Everything lands in `output/fit-test/`. Open `fit-test.3mf` in Bambu Studio with
**File > Import**. Read `output/fit-test/fit-test-guide.pdf` (or `docs/FIT_TEST.md`)
for the numbered steps.

Record which pieces fit (one number per group, any order):

```bash
python -m charm_maker fit-results 2 5 8 11 14 17
```

This writes the tested sizes into `config.yaml` and marks them `tested: true`.

Run the geometry tests:

```bash
python -m pytest
```

## Files

- `config.yaml`: every product size, tolerance, hardware size and the filament list.
- `charm_maker/`: the code. `fittest.py` builds the fit plate, `stand.py` the figure stand,
  `geom.py` the shared 2D/3D helpers, `export.py` writes 3MF and STL, `preview.py` draws pictures.
- `tests/`: automated geometry checks (watertight, one part, sizes, pocket walls).
- `docs/`: the spec and the fit-test guide.
- `DECISIONS.md`, `CHANGELOG.md`.

## Privacy

Photos and outputs never go into git (`photos/`, `input/`, `output/`, images and
print files are ignored). Nothing is sent over the network while processing, and
nothing is sent to the printer.
