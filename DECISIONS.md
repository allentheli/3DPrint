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

## Milestone 2

- Loaded slots live in `config.yaml` under `loaded:` and are written by `python -m charm_maker load`; each entry carries its own spool color, so the owned list is only needed for swap suggestions.
- Changing the spool in a slot clears that slot's marker calibration; putting the same spool back keeps it.
- Ink is matched with a hue-weighted Lab distance (lightness x0.3, chroma x0.5): streaky or pale marker fill changes lightness and chroma, a different marker changes hue. Measured on synthetic photos: yellow fill 1.6 from its calibrated marker, orange 41.
- Off-palette threshold 25 with calibration. Patches under 3 mm² and thin fringes (0.3 mm opening) are camera noise and go to the nearest loaded slot; anything bigger is its own flagged part.
- Spool colors alone cannot separate close markers (orange is 22.8 from a golden-yellow spool, the yellow marker 18.6), so a kid batch with uncalibrated loaded markers stops and asks once: scan the card, or go ahead (`--uncalibrated-ok`).
- The question is answered on the command line (`--off-palette nearest|swap`, `--map`, `--uncalibrated-ok`); a run with an open question writes previews and `QUESTION.md` but no plates.
- Swap plates are grouped by the spools they need and printed after the plates without swaps. Swap slots: empty slots first, then loaded slots the plate does not use, highest first, never the white base.
- Swap suggestions come only from Allen's real spool list, never the placeholder palette.
- Calibration card boxes sit at fixed spots per slot (box k is slot k), so a card printed before a swap still reads correctly.
- A calibration card in the same folder as drawings is read first and applied to that batch.
- Half-drawn cards are numbers 11 to 20 (five shapes, two each), so they never share a file name with blank cards 01 to 10; outlines are 4.5 mm on the card (1.5 mm printed), drawn as black ink.
- Kid card rule pictures: a small printer with four spools, one fat stroke, a filled circle. Adult cards keep the old marker rules until milestone 4.
- Parts are named after the color word in the spool's name ("Yellow PLA" gives "yellow"), because a golden-yellow hex code reads as orange.
- Chips: 26 x 18 x 1.2 mm tags, slot number cut 0.6 mm into the top, 15 mm apart for By object printing, layer 0.2 mm. My rough estimate is 14 minutes for four chips (5 min start-up, 8 mm³/s, 1.5 min per swap); Bambu Studio's estimate decides.
- The chip 3MF does not set Print sequence itself (a partial Bambu project settings file could break the import); `CHIPS.md` gives the click path instead.

## Simplified (after milestone 2)

Allen's calls:

- The goal is one consistent drawing-to-print-file path for every product; extras come second.
- Every product is for anyone, except earrings (adults). Cards are the same for kids and adults; the border is on by default for everyone.
- Pendant and earring holes run left to right, parallel to the face, so the chain or hook goes straight through and the piece faces forward. No jump ring.
- Color: the file keeps each color as a separate named part; Allen assigns spools in Bambu Studio. The run never stops to ask about colors.
- Magnet figures have a flat back; the magnet is glued on. No pocket.

My choices while building it:

- Colors are found per drawing (Lab clustering, hue-weighted, merge distance 20): streaky fill stays one color, orange next to yellow stays two. Up to 3 ink colors plus the white base; a 4th merges into its nearest with a note.
- Loaded slots stay as an optional head start: each part starts on the nearest loaded spool, and the preview notes when two parts start on the same spool or a color matches no spool well.
- The calibration card, strict mode (`--ask-colors`), swap plates and filament chips stay in the code but off the main path, so they can come back.
- Side loop: a flat-bottomed post with a round top, hole as a flat-topped teardrop (support-free face-down), front flush with the face, taller than the charm on the back (earring 4.0 mm, pendant 5.9 mm). Walls 1.0 mm (earring) and 1.2 mm (pendant); lengths 4.5 and 7 mm.
- Loops sit above the drawing's balance point (outline centroid), not its highest bump, because a hanging piece turns until its weight is under the hole. The post reaches down into a dip (heart) and the hole clears anything within 3 mm either side.
- The color face is cut after the loop is added, so the loop never covers the colors (checked: 15 mm² of overlap the other way round on a test shape, 0 now).
- Fit test: jump-ring holes and magnet pockets are replaced by sideways earring loops (1.8, 2.0, 2.3 mm) and necklace loops (3.0, 3.5, 4.0 mm), built with the same loop code as the products. Order: clip 1-3, keyring 4-6, earring 7-9, switch 10-12, stem 13-15, necklace 16-18.
- Earrings: one box on the card, two copies named `ear-NN-1` and `ear-NN-2`; `pair_mode: mirrored` mirrors the second; `style: stud` drops the loop.
- Magnet figures keep 3.2 mm thickness for stiffness; print notes say to glue the magnet about 12 mm above the bottom to line up with the stand.
- Half-drawn cards are made for every product except earrings.
- Keychain ring tabs still go on the highest point (unchanged); only hanging loops use the balance point.

## Shape styles

Allen's calls: shaped pieces as an option, puffy and a raised outline, and hair clips and earrings may be shaped too.

- Four styles for every product: flat (default), puffy, outlined, puffy-outlined; chosen per run or per card.
- Puffy height = base + puff x quarter-circle profile of the distance to the outline (full height 4 mm in from the edge), from a 0.05 mm distance raster sampled on a 0.4 mm mesh.
- Base and puff per product: hair clip 1.2 + 1.2, keychain 2.4 + 2.0 (the ring tab stays strong), pendant 1.8 + 1.8, earrings 1.0 + 1.0 (light), magnet figure 2.0 + 2.0.
- The raised outline is the darkest ink if its lightness is under 50 (black normally); 0.6 mm tall with 0.5 mm rounded shoulders. If no ink is that dark, nothing is raised and the preview says so.
- Each shaped piece is one solid split into colors (the colors are cut out of the whole), so neighbouring parts share exact surfaces: one body, zero overlap. The ridge is its own solid over the outline ink, so it does not leak onto neighbours.
- Shaped pieces print face-up; the back is flat. The clip pocket stays on the back and is bridged; loops keep their flat bottom on the bed.
- Found and fixed while building this: flat pieces were not mirrored, so their faces would have read backwards once turned over. Flat pieces are now built mirrored; 3D previews turn pieces over like a page.
- Previews now include a 3D view of the front.

## Lessons from real drawings

Six real kids' drawings (Meta Animated Drawings examples, MIT) were placed on cards and run. What broke and what changed:

- A faint thin pink pen and a faint light-blue pen were not found at all. Ink now also includes faint lines that are clearly colored (chroma over 10 and 18 Lab units from paper); gray marks that are only a little darker than paper (shadows, pencil) still are not ink. The soft edge next to a line counts as ink.
- The 3x3 noise cleanup erased lines 1 to 2 pixels wide. It is now a removal of isolated blobs under 6 pixels.
- Guide-colored pixels are removed only within 2 mm of where guides are printed, so a light-blue pen elsewhere in the box survives.
- Thin short marks (a smile, an eye line) were deleted as specks. A speck must now be both under 1 mm² and under 1.5 mm long.
- Crayon left white stripes; paper gaps narrower than 0.5 mm inside one color are filled, and the preview says so.
- Small dark eyes were lost three ways: the seed search stopped at 12 candidate colors (now 40); the 3-color cap merged the smallest color instead of the two most alike; and merged pixels went to the wrong partner. All fixed. The cap now compares colors by their strongest pixels on full color difference.
- The hue-weighted color distance ignored big lightness differences (dark brown vs pale peach scored 17.7). Lightness now counts at 30% for the first 15 units (streaky fill of one marker) and fully beyond (now 43.6). Separations that matter are unchanged: orange/yellow 42.7, blue/purple 27.0, black/dark blue 22.0.
- Pale inks started on white and vanished. An ink's color is now taken from its strongest pixels, and inks never start on a white spool. Dark dull inks start on black or gray by lightness; clearly colored inks start on the colored filament with the closest hue.
- Color words know brown and black, so eyes are named "brown" instead of "orange".

## Poop containers and screw tops

Allen's calls: kids fill the containers themselves; small see-through holes; a lid that opens and closes; character shapes (duck with a twist-off solid head, teddy bear, heart and more); "like Sebo3D's voronoi duck, but with a screw on top".

- Mesh holes are 4 mm diamonds (corner to corner) with 1.4 mm struts: 45 degree roofs, about 44% open, small enough to keep purge blobs in. Straight-down diamond holes also go through sloped roofs and shoulders (vertical sides, no supports).
- The thread is two-start, right-hand (clockwise closes), 10 mm lead (one turn), 1.4 mm deep, 0.4 mm radial clearance. Built as an even helical grid, not a twisted extrusion: the twisted extrusion's thin facets read as 64-90 degree overhangs; the grid's steepest flank is about 41 degrees.
- Lids that print on their opening (heads) get a 45 degree cone ceiling in the socket; the plain lid prints upside down with a chamfered top edge and grip ribs that run to the bed.
- Thread ridges start with a 45 degree ramp, so the ridge bottom never overhangs.
- Heart, star and cloud are outline jars: straight mesh walls and a roof that is a 45 degree cone up to the neck (outside and inside ceiling both print). They reuse the half-drawn card outlines. They work, but most of the roof is solid; a converted lattice model looks better.
- Heads (bear, duck) are a sphere on the lid collar with a 45 degree underside; eyes, nose, beak and muzzle are flush color inlays, so nothing sticks out underneath.
- Every container is checked: one watertight body, no overlap closed, no overlap while unscrewing a full turn counterclockwise (and an overlap clockwise, so the handedness is right), no faces steeper than 45 degrees except about 10 mm² on the bear's ears.
- Screw top for downloaded models: the head is the shell with most of its volume above the cut; the neck axis is the head's centroid 2 mm above the cut; the socket radius leaves 1 mm of head outside it over the whole thread height; the body keeps the lower head as a solid neck, gets a filling hole bored straight down, and loses any material the turning head (beak included) would sweep through, plus 1 mm. Overlapping shells are unioned into one body.
- Sebo3D's duck: cut at 50 mm (the lattice wraps the neck up to 54 mm; the head is 33 mm across at 50 mm and wider above). Opening 20 mm, 777 mm³ of lattice cleared near the head, unscrews cleanly. The head keeps the original's own overhangs (beak), so it still needs tree supports like the original. The original's mid-print pause is no longer needed.
- Converted downloaded models are never committed and are only for Allen's own printing.

## Test drive

- Six blank cards cover every product a kid can make except the clicker, including a name in letters (thin strokes, the hardest kid case). Allen does not want pre-set shapes, so half-drawn cards are out of the pack and only made with `cards --half-drawn`.
- The corner markers stay: they straighten the photo, set the exact scale and identify the card. Without them Allen would name each card's product and the size would be a guess.
- The pack is one PDF (parent page first) so it prints in one go.

## Figurines

Allen's calls: supports are fine; the back is blank or a mirror of the front; then: keep the back flat by default, because magnets and hair clips need a flat back anyway.

- Flat back is the default: the figurine front on the card's product, at the card's size, with its attachment, through the same face-up builder as puffy (base slab per product from `relief.products`, then the dome). No supports, normal charm plates.
- The flat-back dome is the same rise as the round figurine's front, scaled down as a whole when it passes the product's cap (`figurine.flat_back_max_dome`): hair clip 5, earrings 4, pendant 6, keychain 8, magnet figure 10 mm. Scaling keeps it round; clipping would flatten the top.
- A figurine base option on a flat back is ignored with a warning.
- Plates and notes split on "needs supports" (round backs only), not on the figurine style.
- A fifth style, figurine, for any card. Thickness from the drawing's local width: each point takes the radius R of the largest inscribed circle covering it, and the half-thickness at distance d from the edge is roundness x sqrt(d(2R - d)) + 0.8 mm edge (roundness 0.75), so every part has a round cross-section of its own width.
- Round backs: the longest side is scaled to 60 mm (`figurine.size`), whatever the card's product size.
- Round backs drop the card's attachment: no ring, clip or loop, and the finishing step is pulling off supports.
- Round backs: blank, or mirror, which puts the same colors on the back as a mirror image (seen from behind, they line up with the front).
- Colors go 0.6 mm deep from the surface into the body (`process.color_face_depth`, as on flat pieces); the rest is the base color.
- Bottom cut flat at 8% of the height (at least 2 mm) by default; disc base with a radius of 35% of the figure's width, 3 mm thick, plain base color; or none.
- Prints lying on its back (front up), tree supports, 0.16 mm layers, figurines on their own plates so charm plates keep supports off.
- No AI image-to-3D (Meshy, TripoSR): drawings would leave the machine, and the result would not be faithful to the drawing.
- Ink outlines are made disjoint after tracing, in ink order (black first): the earlier ink keeps a shared border. Pixel masks were already disjoint; the 0.15 mm closing in the tracer made neighbours overlap.

## Test drive 1

- Scanned PDF pages render at the embedded photo's resolution (the photo covering most of the page), capped at 8000 px; drawn (vector) pages still render at 300 dpi.
- Marker retry: if any card found has fewer than 4 markers, detect again with the longest side at 4000, 2500 and 1600 px; per corner the sharpest copy wins; corners are scaled back to full-size pixels.
- Lost-mark warning: a blob printing in a color farther than the merge distance (20) from its own, with chroma 20 or more, surviving a 0.25 card-mm opening (fringe does not) and at least 1 card mm². Colors merged by the color limit are skipped (they have their own note). The mark is not grown to a printable size: at 0.6 mm inside a 1 mm outline it would be covered by the thickened lines anyway.
- Fine pen drawings on hair clips (25 mm) lose detail to the 1.0 mm minimum line width: lines get about 2.5x thicker, whiskers merge, small gaps fill. Asked Allen whether to try thinner minimum lines or bigger pieces; nothing changed until he answers.

## Test drive 2

- Speck length is the long side of the mark's rotated bounding rectangle (minAreaRect), not the upright box, so slanted whiskers keep their full length. Area and the 1.5 mm length limit are unchanged.
- At keychain size (45 mm) her fine-pen face mostly survives; the outlined nose (0.3 mm² inside) fills in and one eye touches the mouth line once lines are 1.0 mm wide. Same open question as test drive 1.
- Allen's call: keep the 1.0 mm minimum line width and hair clip size as they are for now (option A), even though fine pen detail merges on 25 mm hair clips.
- Allen said each upload took too long. The tool runs in seconds (one card 4 s, eight cards 20 s); the time went to fixing bugs before handing over, the 2.5 minute test suite and, in a fresh session, a 4 minute package install. Runbook now: hand over first and fix after, tests only after code changes, one PDF for all cards; and a setup script installs the packages when a session starts.

