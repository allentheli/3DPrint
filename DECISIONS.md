# Decisions

One line each, for choices the spec left open.

## Milestone 0

- Config is YAML (`config.yaml`) with comments, so Allen can read and edit it; fit values keep a `tested` flag and the `candidates` printed on the plate.
- Solids are built with manifold3d (booleans are guaranteed manifold) and 2D shapes with Shapely; trimesh writes the 3MF and STLs. No OpenCV needed before milestone 1.
- Fit coupons are rounded tags, 2 mm corners, with the feature in the lower square and a raised 0.4 mm number in the top strip, so pockets face up and numbers read without mirroring.
- Numbers use a built-in stroke font (digits drawn from line segments) so no font file is needed for labels.
- Clip pad pocket candidates 11.2, 11.5, 11.8 mm (spec). Keyring hole candidates 4.5, 5.0, 5.5 mm. Jump-ring hole 1.8, 2.0, 2.3 mm. Magnet pocket 10.2, 10.4, 10.6 mm. Switch cutout 13.9, 14.0, 14.1 mm (spec). Stem socket clearance 0.15, 0.25, 0.35 mm added to each arm width.
- MX stem modelled as a plus with 4.1 mm span, arms 1.17 mm (left-right) and 1.31 mm (front-back). To be checked against Allen's actual switch in milestone 3.
- Stem socket coupon: 8 mm boss, 4.5 mm tall, socket 4.0 mm deep with a closed floor, printed socket-up like the real keycap.
- Magnet pocket floor on the coupon is 1.3 mm (3.2 mm coupon minus 1.9 mm pocket), above the 1.2 mm minimum.
- Washer recess is a teardrop (45 degree roof) so the stand prints upright without supports.
- At the 12 mm standard magnet height a 25.4 mm washer reaches 0.7 mm below the ledge, so the recess also notches the base behind the upright rather than raising the magnet height.
- Stand: 44 x 34 mm base, 3 mm thick; upright 36 x 34 mm, 2.6 mm thick, tilted 10 degrees back, 8 mm from the back edge; 2.0 mm recess leaving a 0.6 mm front wall; 1.5 mm lip 4.5 mm in front of the upright.
- Printer bed size is set to 256 x 256 mm as a safe default until checked for the X2D.
- The fit guide is generated from config (Markdown and a PDF via ReportLab) so the printed sheet always matches the plate.
- Previews are drawn with a small software renderer on Pillow (no GPU in cloud sessions); the plan view is actual size at 300 dpi.
- Outputs are gitignored even for the fit test; the committed copy of the guide lives in `docs/FIT_TEST.md`.
