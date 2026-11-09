# Changelog

## Milestone 0: fit test (2026-11-09)

- `config.yaml` with every product, hardware size, fit-critical value (with `tested` flags) and an empty filament list.
- `python -m charm_maker fit-test` builds an 18-coupon single-color fit plate plus one figure stand: 3MF with named objects, one STL per piece, a merged STL, a shaded preview, an actual-size plan view, stand views and a printable guide (Markdown and PDF).
- `python -m charm_maker fit-results` writes Allen's results into `config.yaml`.
- Figure stand builder (`charm_maker/stand.py`) with the teardrop washer recess.
- 12 automated tests: watertight single-part solids, sizes, pocket and hole diameters, wall thickness, stand recess volume, plate layout, config writing.
