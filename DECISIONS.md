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

## Milestone 1

- Marker ids on a card encode corner, product type and card number (`corner*250 + type*30 + number`, 5x5 dictionary), so one marker alone identifies the card and all found marker corners feed one homography.
- Cards are one per US Letter page, 3x scale, 20 mm markers 10 mm from the page edges; the keychain box is 161 mm (max drawing 53.8 mm, the page is too short for 165 mm with the name line).
- File stems are `<type>-<number>` (clip-03, key-07) instead of a bare number, because numbers repeat across products. Duplicate stems in one batch get `-b`, `-c` suffixes and a warning.
- Guide color is light cyan #B9E4F5 (hue 197): far from yellow, and removed by hue plus low saturation. Verified only on synthetic photos so far; the first real scan with a yellow marker decides.
- The name line is cropped from the straightened photo and pasted into the preview; no OCR.
- Ink rule: a pixel is ink when it is dark (V < 0.60) or colorful (S > 0.40); black when also gray (S < 0.35, V < 0.55). Hues are clustered at 5 degree bins and merged within 30 degrees; extra colors beyond the card limit merge into the nearest kept one with a warning if they held at least 3% of the color pixels.
- A 1.5 mm band along the printed box edge is ignored as a backstop for the guide line; the rest of the guides go by color only, so ink crossing the circle is kept.
- Lighting is flattened per channel with a quadratic fit through paper tiles, so a fully filled shape is not mistaken for shadow.
- Color fringe where two inks meet (camera and JPEG) is removed by a 0.4 mm majority vote before specks are counted.
- Thin ink is thickened along its skeleton to exactly 1.0 mm; ragged edges of thick areas are left alone.
- Pieces farther apart than twice the border are joined by 2.5 mm strips between nearest points, logged as bridges.
- Vectorized masks get a 0.15 mm closing only; an opening shaved 0.09 mm off every shape.
- Clip pocket: center of the largest inscribed circle; border grows in 0.5 mm steps to 3 mm, then a full-thickness backer disc is unioned in (a back-only disc would print as an overhang face-down).
- Keychain tab: a 10 mm rounded tab at the highest point of the shape eroded by 2 mm (so thin spikes do not win), 1 mm overlap, 1 mm fillet; other positions rotate the shape, build at the top, rotate back.
- Multi-part 3MF follows the Bambu Studio project layout: one object per charm, components for parts, `Metadata/model_settings.config` with an `extruder` per part. A plain 3MF with named objects is written next to it as a fallback. Both untested in Bambu Studio until Allen opens one.
- Face-down build: the front face is at z=0 so the colors are flush with the bed; pockets open upward.
- Plates: shelf packing with 6 mm gaps and an 8 mm bed margin; pieces sorted by filament count then size, each plate limited to 4 filaments; generic-palette slots are numbered white, black, then the rest.
- Previews use a small software depth-buffer renderer on Pillow (no GPU in the cloud).

## Brief change: kids' palette is the loaded colors

Allen's calls, written into the brief:

- Kids draw only with markers matching the loaded spools; kid cards say "Use the colors in the printer" (printer picture), "Big and bold," "Color it in." The "black + 1 color" limit is gone.
- Config tracks which spool is in which AMS slot right now; Allen reports swaps in plain words and the session updates config.
- A marker calibration card has one box per loaded filament and is rescanned when spools or markers change; kid ink is matched to the calibrated marker colors instead of grouped by hue.
- A color that isn't loaded is asked about once per batch (nearest loaded color, or own plate with a spool swap), never merged silently. This replaces milestone 1's merge-with-a-check-line.
- Filament chips: one per loaded filament, a plate under about 15 minutes, printed live as the kids' printer tour.
- Shopping list: one broad-tip marker per loaded color, nothing else on the table.

My choices while writing it in:

- The white base spool gets no calibration box and no marker, because white is the paper.
- The chip plate uses Print sequence By object, so the AMS swaps once per chip instead of every layer; that is what keeps it near 15 minutes. Untested until it is sliced.
- Chips are single-filament tags with the slot number cut into the face, not raised, so kids can match a color to its slot.
- Config keeps the owned-spool list and the loaded slots separate, so a swap is a one-line change.
- The code still follows the old rules (card text, black + 1 color, merging); the change is scheduled into milestone 2.
