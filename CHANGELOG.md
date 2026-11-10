# Changelog

## Test drive 3 (2026-11-10)

A brown house-like character with a yellow window on hair clip card 01.

- The yellow window (7.8 mm² at real size) printed brown. A marker's color spreads over many nearby shades; the yellow was spread over 156, none big enough to start a color. Shades clearly unlike every color already found (more than twice the merge distance) are now pooled with their neighbors. Shades of a pen already found are not, so the real garlic drawing's blue pen stays one color; the six real drawings and the first two scans come out unchanged.
- 1 new regression test.

## Test drive 2 (2026-11-10)

Second real scan: a loaf-shaped cat on keychain card 01.

- Short slanted strokes (whiskers 1.7 mm long) were removed as specks: the length was measured upright, so a stroke at 45 degrees looked 1.44 mm, under the 1.5 mm that protects thin strokes. Marks are now measured along their length. Round dots are still specks. On the real drawings this also keeps three dashes of the bug's faint outline.
- 1 new regression test.

## Test drive 1 (2026-11-10)

First real scan: a cat on hair clip card 01, scanned with iPhone Notes.

- Scanned PDFs are read at the photo's own resolution. iPhone Notes makes 27 x 36 inch pages, so the old fixed 300 dpi blew the photo up 4x (8196 x 10753 px) and two of the four corner markers were missed. Now 1966 x 2579 px, all four found, ten times faster.
- When a card is missing a corner marker, the reader looks again on smaller copies of the image (for 48 MP phone photos too).
- A drawn color too small to print as its own color (the cat's 0.6 mm pink tongue) used to print in its neighbor's color without a word. Now a `check:` line says so and where it went.
- 4 new regression tests in `tests/test_real_world.py`.

## Figurines (2026-11-10)

- New style `figurine` for any card: the drawing's front inflated like a balloon, thick where the drawing is wide. One solid split into the kid's color parts.
- Flat back by default: still the card's hair clip, magnet, keychain, pendant or earring, at the card's size, printed face-up with no supports. The rounded front is capped per product (5 mm on hair clips, up to 10 mm on magnets).
- Round backs for a standalone 60 mm figure (`--figurine-back blank` or `mirror`); bottom flat, disc stand or round (`--figurine-base`); per card or for the whole run. They go on their own plates; print notes turn tree supports on, use 0.16 mm layers and say to peel the supports off.
- Fixed while building this: a figurine from a keychain card no longer gets the split-ring finishing step.
- Fixed for every style: where two crayon colors interlock (the candy corn), the traced outline of one color closed over the other's thin teeth, so the two color parts overlapped by a fraction of a cubic millimetre. Earlier colors now keep the shared border; overlap on all six real drawings is now zero. Regression test in `tests/test_real_world.py`.
- The test-drive parent page now offers the shapes (flat, puffy, raised outline, figurine) and still fits on one page.
- 20 new tests: one sound body with no part overlap for every back and base and every product, flat back on the bed, clip pocket and ring hole kept, dome caps, colors only on the front, size, flat bottom and plain disc, plates and notes, interlocking colors.

## Test drive (2026-11-09)

- `test-drive`: a parent page and six blank cards (two hair clips, two keychains, a magnet figure, a necklace) for trying the whole flow with one kid. A test renders every card and reads it back.
- Half-drawn (pre-set outline) cards are now only made with `cards --half-drawn`.

## Poop containers (2026-11-09)

- `poop-containers`: see-through party favors kids fill with printer poop and twist shut: round and hex jars, a bear whose head is the lid, a duck, and heart, star and cloud jars. Diamond mesh, right-hand screw lid that closes in one turn, no supports.
- `screw-top`: turns a downloaded poop-eater model's head into a twist-off lid (cut, threaded neck, threaded socket with a cone ceiling, filling hole, clearance for the turning head). Done for Sebo3D's voronoi duck.
- 32 new tests: watertight single bodies, no overlap closed or while unscrewing, right-hand thread, no supports, see-through and fillable, screw top on a stand-in model.

## Real drawings (2026-11-09)

- Tested on six real kids' drawings (MIT-licensed examples) placed on cards: bold marker, crayon, thin gray pen, faint pink pen, ballpoint with a hard shadow, faint light-blue pen. Before: two found no ink, faces lost their smiles, crayon striped, eyes vanished, pale inks started on white. After: all six come out faithful.
- Ink detection finds faint colored pens, keeps 1-2 pixel lines, removes guide colors only near printed guides.
- Thin short marks are no longer specks; crayon gaps under 0.5 mm are filled.
- Color separation keeps small dark colors (eyes) under the 3-color cap; colors are judged by their strongest pixels; inks never start on white.
- `tools/try_real_drawings.py` repeats the check. 6 new regression tests rebuild each failure on synthetic cards.

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
