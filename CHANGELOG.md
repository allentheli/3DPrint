# Changelog

## Flexi joint test (2026-11-13)

- First step toward flexi toys kids draw themselves, shark style (head, upper body, torso, lower body, tail): a joint test plate, pieces 19-22, one per gap (0.30 to 0.60 mm, centred on the gaps of the flexi shark Allen showed), 8 mm tall. Each is a block with an arm on a round knob, printed already joined, no supports. `fit-test --only flexi_joint_gap` builds it; report the best number like the other fit tests.
- The fit test's top view draws two-piece coupons.
- 1 new test, 2 updated.

## Eyes are kept, round and matching (2026-11-12)

- Small round dots (eyes, dots on a wing, boba pearls) are no longer removed as specks: the cat and the butterfly have their eyes back.
- Eyes stay round and apart: a line next to an eye gives way, and the gap-filling for crayon coloring no longer glues an eye, smile or nose to the line beside it. Marks drawn closer than 0.4 mm get a 0.4 mm gap so they print as two.
- A pair of eyes gets the same shape and size, each where it was drawn.
- Kept dots are circled in blue on the preview. A pencil speck looks just like a dot, so `--no-dots <card>` removes them for that drawing (test drive 4's rainbow).
- Clicker assembly note: the ring goes through the tab halfway up the side.
- `--scale fig-01=1.5` makes one piece bigger (or smaller) than drawn, before the print fixes. The butterfly at 1.5 times keeps its two eyes and J-shaped smile.
- Ring eyes and little closed shapes keep the white inside them (the bird's ring-in-a-ring eyes, its outlined beak and heart cheeks, the ice cream's oval sprinkles), widened to a printable 0.4 mm where she drew a hairline.
- Checked against every real scan so far (pen, marker and pencil). 6 new tests.

## Figurine clickers, every color its own part (2026-11-11)

- Clicker keycaps can be puffy, raised lines or figurine (the kids' favorite). A shaped keycap prints face-up, so its post is a separate small piece glued into a dent in the keycap's back; the print notes say so. The clicker card now has the shape tick boxes.
- Every drawn color stays its own part (up to 8); a drawing with more colors than the 4 AMS slots gets a check line, and Claude asks Allen which share a spool.
- Earring hole 1.8 mm (was 1.5), same 1 mm to the edge.
- A clicker drawing smaller than 16 mm is scaled up by default (Allen's call); a setting keeps its size and grows the border instead.
- Poop container heads (duck, bear, heart) and screw-top heads stop facing front when screwed shut (they could turn about 45 degrees past front). 2 new tests.
- The name picture reaches up to the drawing box, so tall handwriting is no longer cut off at the top.
- Allen's prints: the cup clicker and Alison's pendant came out well.
- 4 new tests, 2 updated.

## Clicker case is a cup (2026-11-11)

- After the first printed clicker (switch top showing, keycap floating over a gap), the case is now a cup: the switch sits inside it, the keycap sits in its drawing-shaped opening with 0.6 mm to spare and its face 1.5 mm above the rim, and presses down into it. Nothing of the switch or the gap shows. Same overall height (about 25 mm plus the keycap), now one solid shape.
- Clicker keycaps are filled out behind the drawing to the switch's 15.6 mm square, so they cover it.
- The clicker's ring post is now a short tab halfway up the side (9.5 mm tall instead of the case's whole height). Its underside slopes back to the wall at 45 degrees, so the case prints with no supports (Allen: supports also filled the inside of the case).
- The assembled preview shows the keycap in the cup. Print notes and assembly steps updated. 1 new test, 2 updated.

## Pieces named after the kid (2026-11-10)

- New quick first step, `names`: every card's handwritten name line on one sheet. Claude reads it and runs with `--names key-01=Jack`, and every file, Bambu Studio part, preview and print note says `keychain-jack` instead of `key-01` (a second one is `keychain-jack-2`). The card number stays in the preview and still works for every flag. A blank name keeps the card number.
- Each plate gets a who's-who map (`plate-N-map.png`): the plate from above with each kid's name on their piece.
- The card's name label is now a bold "Your name:".
- The earring card says "Draw just ONE earring. We print a mirror-image pair." under the title (the title "Earrings (a pair)" read like "draw two").
- Earring pairs are now mirror images by default (Allen's call): the second one is flipped left to right.
- The name picture now starts where the line starts, so it shows only the handwriting (it caught the end of the bigger "Your name:" label).
- First real scan with the new card (a pendant): the handwritten name and the Figurine tick were both read correctly.
- A thin strip of color between two lines (a straw colored in yellow) is kept: the lines thicken on the paper side instead of over it, plain and with neat lines. 2 new tests (fail on the old code).
- A color that thins out to a faint streak past a line is joined back into one piece along that streak, 0.5 mm wide so it prints (her straw is now one continuous yellow strip). A plain dark bar between two patches is never bridged. 2 new tests.
- Clicker fit results recorded: switch hole 13.9 mm, keycap socket 0.10 mm (tested 2026-11-11).
- Clip pocket 11.2 mm, keyring hole 4.5 mm and necklace loop 3.5 mm recorded from the fit test (2026-11-11). Only the earring hole is left.
- `run --one-plate` puts everything (clicker cases and figurines too) on one plate in one 3MF, with print notes for the mixed plate. Plate-map labels no longer overlap on small pieces. 1 new test.
- Earrings hang from a 4 mm jump ring (Allen's call): a small tab above the balance point with a 1.5 mm hole front to back and 1 mm of plastic around it, instead of the sideways loop a jump ring could not get around. Fit pieces 7-9 are the new tabs; `fit-test --only earring_hole_diameter` prints just those three. 3 new tests, 3 updated.
- 2 new tests.

## Kids pick the shape on the card (2026-11-10)

- Every card (except clicker) now shows the five shapes under the name line, each with a small 3D picture the tool renders itself from a sample heart: Flat, Puffy, Raised lines, Puffy + lines, Figurine. The kid ticks one; no tick means flat. A "neat lines" box beside the name turns on tidy.
- The run reads the ticks and says so in each design's fixes; two ticked shapes use the stronger mark and warn. A style named for one card on the command line still wins; a style for all cards does not override a tick.
- Older cards still read (no ticks); the drawing box and markers did not move. The three kid rules ("use the colors in the printer", "big and bold", "color it in") moved to a compact strip between the bottom markers.
- Clicker keycaps can now be 16 to 40 mm (were 16 to 22); the clicker card's drawing box grew to match, so clicker cards printed before must be reprinted.
- 4 new tests.

## Milestone 3: clicker keychain (2026-11-10)

- Each clicker card makes two pieces. The keycap is the drawing as a flat charm with a 5.5 mm round post and the cross socket for the MX stem on its back, under the drawing's middle (a backer disc if the drawing is too thin there); it prints face-down with the charms. Clicker keycaps are always flat (the post is on the back).
- The case is shaped like the drawing (Allen's call): its outline 1 mm bigger all round, smoothed, never smaller than the 18.8 mm box the switch needs. A 1.5 mm lid holds the switch hole right under the keycap's post; below it a 15.6 mm square hollow 9 mm deep for the switch body and pins, a floor with a push-out hole, and a ring tab at the top, flat on the bed. It prints upright on its own plate, 0.2 mm layers, one filament, no supports (the lid overhangs the hollow by under 1 mm).
- Pressed all the way down, the keycap clears the switch housing by 1.5 mm (housing taken at 7 mm above the plate, the high end of the published 6.6 to 7).
- The ring hangs from a post at the top that stands the case's full height, the hole running left to right at half height, so the ring never passes under the case and the clicker sits flat on a table (Allen's call). Teardrop hole, no supports.
- The clicker card has a "cover the square" guide the size of the smallest keycap (16 mm), so the keycap covers the switch (Allen's call). A drawing still smaller is scaled up to 16 mm (never past 22 mm), with a note; only its size changes. The keycap post sits at the drawing's balance point, or as near it as fits.
- Sizes come from the fit test (switch hole, stem fit, ring hole), with a check line while untested. The case preview shows the clicker assembled. The glue-on fallback (a plain charm for a store-bought blank keycap) is one setting.
- `cards` now prints clicker cards too.
- 10 new tests. Not printed yet.


## Screw-top notes measure the head (2026-11-10)

- The twist-off head's print notes always said "no supports", but a downloaded model's head can overhang on its own (Sebo3D's duck: the beak, 109 mm² steeper than 45 degrees). The notes now measure the head and, when it overhangs, say to turn tree supports on for the head, as the original does. 1 new test.


## Switch housings in the fit test (2026-11-10)

- Checked established clicker designs (popular MakerWorld clickers, a clicker generator, keyboard builders): no clicker-specific standard; all use the MX keyboard standard (14.0 mm square cutout, 1.5 mm plate, plate top 5 mm above the PCB) and a printed fit test. The switch holes (13.9 / 14.0 / 14.1) already bracket it; the keycap clearances are now 0.10 / 0.15 / 0.20 mm, centered on the common printed-clicker default of 0.15 in 0.05 mm steps (they were 0.15 / 0.25 / 0.35).

- Keycap posts (pieces 13 to 15) are now the real keycap size, 5.5 mm round, as Allen asked, so the fit found is the fit the clicker keycap gets. Only the arm thickness varies (1.32 / 1.42 / 1.52 mm and 1.46 / 1.56 / 1.66 mm); the cross length is a fixed 4.2 mm, which keeps about 0.5 mm of plastic at the cross tips (a 0.37 mm wall on piece 15 otherwise). The guide asks Allen to report a cracked post.

- Allen's switch (photo): MX-style blue clicky. Fit-test pieces 10 to 12 are now small closed housings like the clicker case, as he asked: a 1.5 mm lid with the square hole (13.9 / 14.0 / 14.1 mm), a 15.6 mm square hollow 9 mm deep for the switch body and pins, and a floor with a 6 mm push-out hole to move the switch between the three boxes. The lid overhangs the hollow by only 0.8 mm, so no supports.
- 1 new test; the size test knows the taller pieces.


## Trying the 3D styles (2026-11-10)

- A sampler plate of the eight test-drive charms, two in each style (puffy, raised outline, puffy with raised outline, figurine front), and a picture of every charm in every style.
- Per-card styles and figurine options take the exact name of a second copy of a card (`clip-01-b`), not only the card number.
- A one-color line drawing (pencil, a single colored pen) gets its lines raised by the raised-outline styles, whatever their shade; before, only an ink dark enough counted, so the pencil butterfly and rainbow got nothing raised. A one-color colored-in area still gets nothing raised.
- Shaped pendants and earrings: the loop rises above the charm, and cutting out the colors cut notches into it where ink reached under it (the rainbow's sun rays). The loop now stays whole and the hidden bit of color is trimmed, with a note.
- 4 new tests.

## Eyes stay eyes (2026-11-10)

- The brown house creature (test drive 3) lost its eyes: on a 22 mm hair clip its 0.5 mm eyes sat 0.3 mm above the mouth, and thickening every line to 1 mm merged eyes and mouth into one blob. Thickening now never merges separate marks: each keeps at least 0.4 mm from its neighbor (or the gap she drew, if smaller), even if it then stays a little thinner than 1 mm. Tidy's redraw follows the same rule, and smoothing never wipes out a tiny mark.
- Also keeps the hair clip cat's whiskers apart.
- 2 new regression tests (plain and tidy).

## Tidy (2026-11-10)

- New option `--tidy` (every card) or `--tidy <card>`: a clean, sticker-like version of the kid's own lines. The outline color's strokes are redrawn along their middle at one even thickness (her typical line width, 1.0 to 1.6 mm), with wobbly and grainy edges smoothed. Eyes, noses, filled areas and separate dots keep their shape; other colors only get smooth edges and fill up to the outline, including the thin white sliver kids leave between coloring and outline. No AI, nothing leaves the session. Off by default.
- Checked on all eight test-drive cards and the six real drawings.
- 5 new tests: even width, smoother edges, eyes and a short mouth survive, colors meet a thinner outline with no gap, off unless asked and per card from the command line.


## Test drive 4 (2026-11-10)

Five cards in one Notes scan: a bird pendant, a butterfly keychain, two dog magnets and a rainbow pendant.

- The butterfly and the rainbow were drawn in pencil and mostly lost: gray marks were not ink. A pencil line is now ink when it is a thin gray stroke clearly darker than the paper right around it (its core at least 20 Lab units darker, growing along its grainy edges down to 10). Broad shadows are not lines, and drawings showing through from the back of the page (7 at most) stay out.
- The gray rim right next to existing ink is left out, so ink lines don't thicken; a pencil stroke touching ink is judged by the rest of it.
- The faint body outline of the real bug drawing is now found too, so the bug comes out whole instead of in pieces. The other real drawings gain 1 to 5% line area; the earlier test-drive scans are unchanged.
- 1 new regression test.

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
