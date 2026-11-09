# Charm Maker

Turns a photo of a hand drawing into a ready-to-print file for a Bambu Lab printer
with AMS. Kids and adults draw on printed design cards, Allen photographs the cards, and
the tool makes flat, flush, multi-color pieces: hair clip charms, keychains, necklace
pendants, magnet figures, and earrings for adults (clicker keychains are next). Every
color in a drawing becomes its own part; spools are assigned in Bambu Studio.

The full specification is in `docs/charm-maker-spec.md`. The everyday runbook for a
Claude Code session is in `CLAUDE.md`.

## Status

| Milestone | What | Status |
| --- | --- | --- |
| 0 | Fit-test plate and config | Built. Waiting for Allen's fit results. |
| 1 | Cards, hair clips, keychains | Built. Waiting for a real card scan and a test print. |
| 2 | Party batch, all flat products | Built: hair clip, keychain, pendant, earrings, magnet figure. Waiting for a real scan and a test print. |
| 3 | Clicker keychain | Not started |
| 4 | Adults: PNG/SVG input, text mode | Not started (earrings and pendants are built) |
| 5 | Magnet figures and the stand | Figures built (flat back), stand built |

## Setup

Python 3.11 or newer.

```bash
pip install -r requirements.txt
```

## Commands

Optional: tell the tool which spool is in which AMS slot, so parts start on the right
spools (you can always change them in Bambu Studio):

```bash
python -m charm_maker load 1 "White PLA" --color "#F2F2F2"
```

```bash
python -m charm_maker slots
```

Print the cards (US Letter, print at "Actual size", not "Fit to page"). This writes
blank cards for every product, half-drawn cards (cloud, heart, cat, star, bow) and, if
slots are loaded, the optional marker calibration card into `output/cards/`:

```bash
python -m charm_maker cards
```

Optional: read a scanned calibration card for sharper color matching:

```bash
python -m charm_maker calibrate scans/calibration.pdf
```

Optional: build the filament chip plate for a printer tour:

```bash
python -m charm_maker chips
```

Turn photos or scans of filled-in cards into plates:

```bash
python -m charm_maker run photos/ --out output/party-1
```

`photos/` can hold JPEG, PNG, HEIC or PDF scans (the iPhone Notes scanner makes PDFs).
The cards tell the tool which product each drawing is. For a drawing on plain paper add
`--product keychain` (or `hair_clip`). Options: `--no-border` / `--border`,
`--tab top-left` for the keychain ring position, `--map "key-03 pink=Magenta"` to override
a filament. Output: `plates/plate-N.3mf`, `designs/<card>-preview.png`, `contact-sheet.png`,
`PRINT_NOTES.md`.

Shapes: add `--style puffy`, `--style outlined` (raised outline) or `--style puffy-outlined`
for the whole run, or per card like `--style clip-03=puffy`. Flat is the default.

The run never stops to ask about colors. Each color is a separate named part; parts
start on the nearest loaded spool when slots are set. `--ask-colors` turns on a strict
mode that stops with `QUESTION.md` for colors that aren't loaded.

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

## Opening a plate in Bambu Studio

1. **File > Import > Import 3MF/STL/STEP/SVG/OBJ/AMF...** and pick `plates/plate-1.3mf`.
   If asked, choose **Load geometry only**. Each charm should appear as one object with
   its color parts listed under it, with filament numbers already set per part.
2. If the parts show up without colors, click a part in the object list on the right
   and pick its filament number from the dropdown. `PRINT_NOTES.md` says which number
   is which color. If `plate-1.3mf` will not open at all, import `plate-1-plain.3mf`
   instead: every color is a separate object there; select all parts of one charm,
   right-click, **Assemble**, then set the filaments.
3. Layer height 0.12 mm, no supports. The design face is on the bed, so a smooth plate
   gives a glossy face and a textured plate a matte one.

Neither Bambu Studio behavior has been tested yet; the README will be updated after
the first real import.

## Files

- `config.yaml`: every product size, tolerance, hardware size and the filament list.
- `charm_maker/`: the code. `relief.py` builds puffy and raised-outline shapes,
  `palette.py` holds the loaded slots and color matching,
  `calibrate.py` reads the calibration card, `chips.py` builds the chip plate,
  `cards.py` makes the card PDFs and defines the card layouts,
  `reader.py` finds the markers and straightens photos, `inks.py` separates black and colors,
  `shape.py` applies the print fixes, `products.py` adds pockets and tabs and builds the solids,
  `plates.py` packs plates, `bambu3mf.py` writes the multi-part 3MF, `pipeline.py` ties it
  together, `fittest.py` builds the fit plate, `stand.py` the figure stand.
- `tests/`: automated geometry checks (watertight, one part, sizes, pocket walls).
- `docs/`: the spec and the fit-test guide.
- `DECISIONS.md`, `CHANGELOG.md`.

## Privacy

Photos and outputs never go into git (`photos/`, `input/`, `output/`, images and
print files are ignored). Nothing is sent over the network while processing, and
nothing is sent to the printer.
