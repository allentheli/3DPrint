# Changelog

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
