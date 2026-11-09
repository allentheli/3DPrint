# Changelog

## Shape styles (2026-11-09)

- New styles for every product: puffy, outlined (raised dark outline) and puffy-outlined, per run or per card with `--style`. Flat stays the default.
- Fix: flat pieces are now built mirrored. They print face-down, so without this the face read backwards when turned over.
- Previews show the style and a 3D view of the front; print notes explain face-up printing.
- 30 new tests: every style on every product is one watertight body with no overlapping parts, colors on top, the outline raised by 0.6 mm, the clip pocket and sideways loops still correct, flat faces reading right when turned over.

## Simplified, plus pendant, earrings and magnet figures (2026-11-09)

- Every distinct ink color becomes its own named part; the run never stops to ask about colors. Loaded slots, if set, give each part a starting spool. Calibration card, strict mode (`--ask-colors`), swap plates and chips are optional.
- Necklace pendants and earrings: a loop on top with the hole running left to right, above the balance point, flush with the face, support-free. Earrings come as a pair (identical or mirrored) or as studs.
- Magnet figures: flat back for a glued-on magnet.
- Products are for everyone (earrings for adults); one set of cards for all.
- Fit test: sideways earring and necklace loops replace the jump-ring holes and magnet pockets.
- 11 new tests, including that loop holes run left to right, never front to back, sit over the balance point and leave the face colors clear.

## Milestone 2: party batch and loaded palette (2026-11-09)

- Loaded AMS slots in `config.yaml`, with `load` and `slots` commands; spool swaps in plain words become one command.
- Kid cards now say "Use the colors in the printer" (printer picture), "Big and bold" and "Color it in".
- Half-drawn cards: cloud, heart, cat, star and bow outlines printed in black, two of each per product, read as part of the design.
- Marker calibration card: one box per loaded filament; scans are read by `calibrate` or straight from a batch folder, and the marker colors are saved into config.
- Kid ink is matched to the calibrated markers. Colors that aren't loaded become flagged parts and one question per batch (nearest loaded color, or own plate with a spool swap); nothing is merged silently. A batch also asks once if the calibration card hasn't been scanned.
- Swap plates with take-out and put-back steps in the print notes, printed after the plates without swaps.
- Filament chip plate (`chips`): one tag per loaded spool with its slot number cut in, notes for Print sequence By object.
- 15 new tests, including a calibration scan plus eight cards in one request becoming one plate with only the loaded spools.

## Milestone 1: cards, hair clips and keychains (2026-11-09)

- `python -m charm_maker cards` writes the design-card PDF (hair clip and keychain cards, 10 each) with ArUco markers, light guides, kid-facing pictures, a name line and a 50 mm check ruler.
- `python -m charm_maker run` turns photos, HEIC files or PDF scans of filled-in cards into packed plates: marker reading and straightening, lighting flattening, guide removal, black plus one color separation, speck removal, hole filling, thin-line thickening, die-cut border, bridges, corner rounding, clip pocket or ring tab, flush 0.6 mm color face, Bambu-style multi-part 3MF plus a plain 3MF and STLs, per-design previews at actual size and 4x, a contact sheet, print notes and a JSON summary per design.
- Drawings on plain paper work with `--product`; filament overrides with `--map`.
- 21 new tests, including an end-to-end run on synthetic warped card photos that checks the scale (a 60 mm ring on the card becomes 20 mm), guide removal next to yellow, logged fixes, watertight single-piece solids, pocket and hole walls, plate limits and file structure.

## Milestone 0: fit test (2026-11-09)

- `config.yaml` with every product, hardware size, fit-critical value (with `tested` flags) and an empty filament list.
- `python -m charm_maker fit-test` builds an 18-coupon single-color fit plate plus one figure stand: 3MF with named objects, one STL per piece, a merged STL, a shaded preview, an actual-size plan view, stand views and a printable guide (Markdown and PDF).
- `python -m charm_maker fit-results` writes Allen's results into `config.yaml`.
- Figure stand builder (`charm_maker/stand.py`) with the teardrop washer recess.
- 12 automated tests: watertight single-part solids, sizes, pocket and hole diameters, wall thickness, stand recess volume, plate layout, config writing.
