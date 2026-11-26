# Charm Maker: runbook for Claude Code sessions

Read `docs/charm-maker-spec.md` once if you have not. Allen owns this project and does
not write code: do the work, run it, and explain in plain words with numbered steps and
exact button names. Ask at most one question at a time, only when the answer changes what
you build. Never say something works unless you ran it. Say what you could not test.

## Hard rules (short form)

- Stay faithful to the drawing. No redrawing, no AI image generation.
- Flat pieces by default (face-down, colors flush, built mirrored); puffy and outlined
  styles on request (face-up); figurines on request (rounded 3D front, flat back by default).
  One solid part per design.
- Every output ships with a preview and a list of fixes.
- Drawings stay private: no network calls while processing, never commit photos or outputs
  (`.gitignore` covers `photos/`, `input/`, `output/`, images, 3MF and STL), never print.
- Fit-critical numbers come from `config.yaml` `fit:` and are set only from test prints.
  Each has a `tested` flag. Warn Allen before using an untested value for real pieces.

## Where things stand (update this when it changes)

Every product builds; nothing is printed and measured yet. Waiting on Allen:

- **Fit test** (`output/fit-test`, printed 2026-11-10). Recorded on 2026-11-11: clip pocket
  piece 1 = 11.2 mm, keyring hole piece 4 = 4.5 mm, switch hole piece 10 = 13.9 mm, keycap
  socket piece 13 = 0.10 mm (all four the tightest candidate, so if any feels loose in real
  pieces, add tighter candidates), necklace loop piece 17 = 3.5 mm. 2026-11-14: earring
  jump-ring hole piece 9 = 1.8 mm (Allen printed the earring test plate). Every fit group is
  now tested except the creatures' flexi joint gap (pieces 19-22).
- **Printed and good (2026-11-11):** the cup-style clicker (printed with the full-height ring
  post; the short 45-degree tab is newer and not printed yet) and Alison's pendant with the
  rejoined yellow straw. The kids love the figurine shape ("super puffy"); keep all shapes.
  **2026-11-13:** the shark duck flexi (Bambu's joint, 3 strips): "it works well"; a fridge
  magnet (glued magnet): works; filling a line drawing's areas with Bambu Studio's fill tool:
  works as long as the areas are enclosed.
  **2026-11-14:** the thumbs-up earrings (face-down, 10 x 17 mm, gaps 0.6-1.5 mm): Bambu Studio's
  default **Classic** wall generator left holes in the narrow gaps on the face; **Arachne** fixed most of
  them (his bee charm too). A print with **Elephant foot compensation** 0 and a 0.42 mm **Initial layer**
  line together came out worse (seams between every first-layer line, even in the wide border: likely the
  thinner line), so keep both at the defaults. The print notes say this. The same earring 1.25 times bigger
  (gaps 1.0-1.9 mm) was not better: wider gaps just get two lines with a dark seam between them, and the
  wide border shows seams too, so the first-layer lines are not fusing; it is not the drawing's size.
  Allen (2026-11-14): keep flat pieces face-down with Arachne, "prob doesnt need to be perfect, its just for a
  kid party". A face-up test plate exists (`output/earring-faceup-test`, one thumbs-up flipped); a flat
  face-up option is parked unless he asks after the party.
- **Poop containers: parked (Allen, 2026-11-13).** His printed duck, filled, showed too little
  poop through the 4 mm diamonds; the windows were made much bigger (see Poop containers), then
  he found one on MakerWorld that can work and parked ours for the future. Don't work on them
  unless he asks; the duck-head turn fix and the bigger windows are not printed.
- **Prints to try (as of 2026-11-14):** a figurine clicker (separate glued post, new) and the short
  sloped ring tab.
- **Flexi, two separate things (Allen, 2026-11-13; spec section 5):**
  - **Flexi (built 2026-11-13; the shark duck printed and works well):** a product of its own with its own card, like the
    keychain (Allen: not a tick box). The kid's drawing becomes a flat toy 80 mm long (drawn
    at the usual card scale, made 1.5 times bigger; a smaller drawing is made bigger to 80 mm BEFORE the print fixes, so a tiny face keeps its shape; colors
    are still read at the card's own scale), 7 mm thick, cut into strips at least 9 mm
    tall, printed flat and already linked. The joint is Bambu MakerLab's Flexi joint, copied size
    for size from Lawk3t's Pusheen Cat Flexi Toy (CC0) that Allen uploaded ("lets do the joint
    like this"): strips 1.5 mm apart, a 5.4 mm tab from the strip above in a 7.0 mm notch of the
    strip below, a 2.8 mm pin across the notch through a round tunnel in the tab, 0.47 mm all
    around. It holds in every direction and slides 0.8 mm along the pin. Proven, so no fit test
    (Allen: don't test or reinvent joints). Cuts keep the face whole: never through a kept dot, a
    small round mark or a small closed mark (ring eyes, teeth); cut heights are chosen together,
    with fewer strips if that is what it takes (only feature crossings count toward that, not plain ink, so
    colored-in drawings keep their strips), and a cut that would leave a loose bit is refused. If a cut
    still lands on a face, rerun that card with `--keep-whole flexi-01=0-40` (no cuts in the top 40%). Also
    check arms and wings in the preview: a cut across the tip of an arm leaves the tip on the next strip
    (Areen's bunny, printed 2026-11-15: "the tip of it was free flowing and the left over part is sharp");
    move the cut past the arms with `--keep-whole` (her bunny: `30-68`, 2 strips, arms whole). Allen
    preferred 3 strips with the arm moved down: on a copy of the card image the arm was shifted 150 px
    (about 4.5 mm on the flexi) and its two lines rejoined to the body line; only with his say-so. Moving
    the clipped tip to the other strip was tried and dropped (the tip above the cut is a ~1.3 mm sliver). Any card can be made a flexi with
    `--as key-02=flexi`; the shark duck (keychain-3, key-02) gives 3 strips, 4 joints, 49 x 65 mm
    (the joint is too big to fit between its eyes and teeth, so the head is one strip, like the
    Pusheen's). The flexi card is in the normal card set (`cards`; alone: `cards --products
    flexi`): the biggest drawing box, no shape boxes, and a real render of a sample flexi cat with
    "Your drawing becomes a wiggly flexi! Draw it big and tall." Ready for kids (2026-11-13).
  - **Flexi creatures (no drawing):** kids design their own creature by picking a head, body,
    legs, tail and colors; faces come with the heads (a few ready-made expressions). Round on
    both sides, flat belly, the common ring joint (a ring around an upright pin, like his shark
    and MontoyaMaker's kitten; gaps 0.39-0.65 mm). Allen's rules: legs big, each pair wholly on
    one piece; bumping while bending is fine, but pieces must not touch as printed; supports
    are fine where needed ("On build plate only", so they stay out of the joints). Built:
    `creature` (heads cat, bear, bunny, fish; bodies short, regular, long; paws or none; tails
    cat, fin, none; checks) and `creature-library` (code in `creature.py`). Parts may be borrowed from free downloads Allen
    picks (cut at a solid spot, given our joint end; never in git; Creative Commons preferred,
    MakerWorld's Standard license is personal printing only). I cannot reach MakerWorld,
    Printables, Thingiverse or Etsy. Painting a drawn face (`creature --face`) works but is not
    used by the card. The first cat is on Allen's printer; the ring-joint test plate
    (`fit-test --only flexi_joint_gap`, pieces 19-22) waits on his number. Next: ready-made
    faces and the creature card.
- **Laminated reusable cards (2026-11-13):** Allen will try one laminated card with dry-erase
  markers (draw, scan, wipe, draw, scan) to check glare and ghost marks. After his scans: card
  wording, a glare check, and duplicate names past `-z` (`--no-pencil` exists now, for ghost marks).
- **Open question for Allen:** his switch's length from the plate ledge to the pin tips (to
  trim the clicker by about 1.5 mm).
- **Party: 2026-11-14 or 15, 5:30-8 pm** (Allen, 2026-11-13: "get what we have ready"; creatures keep
  developing after). Plan: printer tour, then cards (keychain for dad, necklace for mom, then 1-3 for
  themselves), dinner while printing, done before they go home. Scan and upload the gift cards
  first so printing starts early; reply fast with plates, maps and notes. Party cards: `cards --count 1 --products hair_clip keychain pendant magnet_figure clicker
  flexi earrings --out output/party-cards`. Rehearsal on every real scan so far: 23 pieces, 4
  plates, about a minute, no problems. Number of kids not set. AMS slots are left empty on purpose: Allen
  changes spools at will and assigns colors in Bambu Studio.
- **Treasure chest (2026-11-17, Allen's daughter's own design, not a card):** `python tools/treasure_chest.py
  [--width 120]` writes `output/treasure-chest/`: box + lid on one plate (0.20 mm, no supports, about 230 g), four
  heart gems on another (two snug, two 0.1 mm looser: the gem fit is untested; both heart holes take the same gem,
  so one can sit in the lock and one on top, Allen 2026-11-21). Her labels: C wooden base, planks with
  round holes, D domed lid, A short lock plate, B heart gem that fits in A; read as a heart that locks the lid
  across the seam and otherwise sits in a setting on top. Hinge: printed knuckles with 1.75 mm filament pins,
  stops at about 96 degrees; a back foot rail keeps the open chest from tipping. Allen started printing the chest
  on 2026-11-21 (so its holes are fixed now).
- **Second treasure box (2026-11-22, the other daughter's drawing; Allen: "Don't need to be faithful ... make it
  nicer", the first chest "took a while to print"):** `python tools/treasure_box.py` writes `output/treasure-box-2/`:
  100 x 74 x 94 mm, flat tray lid (about half the plastic of the first chest, whose domed lid was mostly solid),
  her bread cat, two heart-pad paw prints and smiling star with feet raised on the lid top in the box color (Allen:
  "not colored but raised"; the lid prints right side up with 2 thin 0.9 mm dividers inside so its top bridges only ~31 mm, Allen's pick over
  supports;
  `top_style: color` in the script gives the inlaid, upside-down version), puppy hearts, lattice heart, stars and small paws raised in the box
  color on the fronts, an ice cream gem as the lock across the seam (snug + looser), the same filament-pin hinge.
  Light blue box, pink ice cream on its own plate (Allen). No sharp edges (Allen, 2026-11-22): hinge knuckles with
  rounded outlines and bevelled sides, the block behind the lock rounded, rim inner edges bevelled. 2026-11-23: the
  box printed fine; the lid came loose from the plate overnight (spaghetti): it stood on a thin rim (about 560 mm2,
  less after the inner bevel). Now a 45-degree foot inside the lid's rim (about 1,600 mm2 on the plate) plus a brim
  in Bambu Studio (Others, Brim type: Outer and inner brim). Fallback if it still lifts: print the lid upside down
  (top on the plate) with the pictures colored (`top_style: color`) or cut in. Colored front pictures (glued-in pieces) not built. Not printed.
- **Turkey crown (2026-11-25, Allen: "funny but fancy Thanksgiving turkey crown" for a yearly photo):**
  `python tools/turkey_crown.py` writes `output/turkey-crown/`: "King of the Feast", two flat 1.6 mm pieces
  (front 230 x 91 mm, back 170 x 26 mm) that bend round the head, joined at the sides by two hair ties over red
  mushroom buttons (fits kids and grown-ups). Gold crown, raised border and pearls, red domed jewels, faceted
  orange gem; a cartoon turkey medallion (banded tail fan, googly eyes, wattle, its own tiny crown); drumstick, pie,
  pumpkin and corn on the points; GOBBLE GOBBLE on the back. Face-up, colors only in the raised layers (gold,
  brown, orange, red in slots 1-4; about 18 color changes, roughly 2 h, 40 g). Not printed yet.
- **Imperial turkey crown (2026-11-25, from a MakerWorld photo Allen sent as inspiration; our own design):**
  `python tools/turkey_crown_3d.py` writes `output/turkey-crown-3d/`: one piece printed standing, 177 x 177 x 188 mm,
  open band 167 mm inside (sits on top of the head), pearl rows, domed jewels, scrolls, crossed-drumstick crests,
  turkey-feather fleurs, maple leaves, pearl-tipped spikes, four beaded gothic arches (never past 50 degrees from
  upright, so no supports) to an orb, a turkey on a flat platform on top (brown in slot 2: one color change). Brim
  recommended (tall piece on a thin ring). Roughly 5 h, 120 g. Not printed yet.
- **Turkey trophy crown (2026-11-25, Allen's two MakerWorld downloads, Standard Digital File License, never in git;
  he picked this over our own crowns):** `python -I tools/turkey_trophy_crown.py <Crown01.3mf> <turkey_ams.3mf>`
  (`photos/crown-model/`, `photos/turkey-model/`) writes `output/turkey-trophy-crown/`: the low-poly crown, the turkey
  (x1.2) cut flat at the belly with its whole tail fan wrapped round the crown's front (following the crown's
  curve and flare, 1.5 mm into it) under the front point, like a trophy mount (Allen: no plaque needed, "the
  turkey tail fan is important"); 10 low-poly gems in the big bottom triangles. One color, parts crown /
  turkey-trophy / gems for him to color. No supports (beak tip ~3 mm2 in the air). 2026-11-25 later: sits on top of the
  head as is (43 cm round inside; Allen: "as is is fine"); two 5 mm teardrop holes low on the band, opposite, just
  behind the sides (98.6 and 278.6 degrees, between gems) for a chin elastic; the turkey fused in (solid filled in
  behind its whole outline, 12.6 cm3 into the wall, trimmed flush with the crown's real inside), so the parts are now
  crown-with-turkey (one solid) and gems. Allen's Bambu Studio screenshot (from below) still showed a gap behind the
  butt and the lowest tail feathers (they sit in front of the fan's back): the turkey's back half is now pushed
  straight back into the crown (swept 16 mm), head, neck and chest untouched. Not printed yet.
- **Turkey royal scepter (2026-11-25, to go with the trophy crown):** Allen's download, Fran Gaur's SPQR Roman scepter
  (`photos/scepter-models/SPQR_A1mini_0.16.3mf`, Standard Digital File License, never in git), with our own turkey in the
  eagle's place: `python -I tools/turkey_scepter.py <SPQR .3mf>` writes `output/turkey-scepter/mockup.glb` (scepter stacked
  as screwed together, thunderbolts in the plaque's side slots). The turkey: fan 235 mm wide like the eagle's wings (bands,
  gold band, gold pearls), bronze scalloped breast, barred wings, red head with snood and wattle, googly eyes looking
  different ways, a crooked gold crown; flat back, relief like the eagle. No legs (Allen: a weak spot): the body sits on
  a round gold base, its toes peeking out onto it. Allen circled the SPQR plaque and thunderbolts: "make the circular base
  larger and replace the circled red part", so the top piece is cut just above the column's top ring and a 10 cm base sits
  there (45-degree flare from the column, beaded lip and rim, 18 ruby/sapphire/emerald jewels). "Make the tip of each of
  the turkey feather tails into gems too": each back-row feather ends in a jewel in a gold setting (mirrored colors;
  the pearls are gone). "Make the gems like gem shaped hexagonal": every jewel is a hexagonal cut gem (girdle, star facets,
  flat table) in a hexagonal gold setting, the feather-tip ones a little longer along the feather. Allen: the scepter
  need not match the file exactly. Whole scepter about 60 cm, fan 22 cm wide.
  **Print files (2026-11-25, Allen: one color, the kids color it with acrylic markers; "print it in parts if you must";
  "mindful of the time"):** `turkey-scepter-1-turkey.3mf` (the turkey on its back: everything in front of the fan has a
  tapered wall back to the flat back, so no supports; a 24 x 12 x 10 mm tab under the belly; the toes moved onto the
  turkey) and `turkey-scepter-2-shaft.3mf` (the base fused to the top of the column, upside down on the base's flat top,
  plus the original middle and bottom ball as the file prints them). The tab is glued into a slot in the base top
  (0.25 mm gap, untested; pointed slot end, no bridge). 0.24mm Draft, 10% infill, no supports, outer brim on plate 2.
  My rough estimate: 4 h + 7 h (Bambu Studio's is the real one); leaving out the middle saves about 1.5 h (46 cm long).
  Double-checked before printing (Allen: "we only got one shot"): files reloaded closed (the fan is built without color
  bands for the print, which had left 46 non-manifold edges; one edge in the designer's own middle piece remains), no
  spot over air at 45 degrees, one first-layer patch per piece (rim beads moved in: they were 72 loose dots), tab gap
  0.25 mm, screws mesh with no overlap (stack offset corrected 0.1 mm), and the screw holes of the middle and bottom ball
  got a 45-degree roof (flat 18 mm ceilings sat 0.3 mm past the peg tip). Plate 2: 3 walls, 15% infill (the designer's).
  Then Allen: "the turkey only look good straight on especially that thing on its beak" (the walls back to the flat
  back made the snood a fin and the eyes tubes from the side). Now only the neck and head have walls (hidden in the
  fan); eyes, beak, wattle, snood and crown are real 3D. The snood runs from the forehead along the beak, over its tip,
  and rests on the wattle. Still no supports: the eyes start inside the head; overhang specks total about 77 mm2
  (largest 9 mm2, under the crown). Not printed yet.
- **Golden Drumstick trophy (2026-11-26, Allen picked it from my Thanksgiving photo-prop ideas):** `python tools/golden_drumstick.py`
  writes `output/golden-drumstick/mockup.glb`: two-tier walnut base, gold plaque "GOLDEN DRUMSTICK / BIGGEST EATER 2026"
  (raised letters, shrunk to fit), round gold pedestal, a giant gold drumstick the cartoon way (meat down, bone up at
  18 degrees; standing on the bone with the knob down looked wrong), a three-tooth bite out of its right side (paler
  inside), the scepter turkey's crown on the knob, gold laurel branches rooted on the base. 110 x 72 x 176 mm. Mock-up
  sent; no print files yet. Then Allen: "give me a 2nd version ... I want multiple awards/trophies, one is champion of
  potatoes among others": `python tools/thanksgiving_trophies.py [--only ...]` writes one GLB per award and
  `awards-lineup.png` to `output/thanksgiving-trophies/`, all on the same base (`golden_drumstick.base()`): drumstick
  (version 1), drumstick-2 (two-handled cup with two crossed drumsticks and a red "#1"), potatoes (CHAMPION OF
  POTATOES / MOST MASHED: mashed-potato volcano, gravy crater and drips, butter pat, gold fork stuck in it), pie (PIE
  MASTER / LAST SLICE: pumpkin slice, crimped crust, whipped-cream swirl), gravy (GRAVY BOAT CAPTAIN / MOST GRAVY: boat
  on a saucer with a mast, sail and flag), food-coma (FOOD COMA CHAMPION / FIRST ASLEEP: roast turkey on a platter,
  "Zzz" thought bubble). Then Allen: "maybe others are just trophies with different words? ... and we can still have
  the golden drumstick": the default run is now the Golden Drumstick (version 1) plus six word awards, all the same
  trophy cup (`trophy_cup`: shaped to print standing with no supports, nothing past 45 degrees, angular handles,
  shallow dish on top, red "#1") with only the plaque changed (`WORD_AWARDS`, or `--words "TITLE|LINE 2" ...`):
  CHAMPION OF POTATOES / MOST MASHED, PIE MASTER / LAST SLICE, GRAVY BOAT CAPTAIN / MOST GRAVY, FOOD COMA CHAMPION /
  FIRST ASLEEP, LEFTOVER LEGEND / SECONDS AND THIRDS, CORNIEST JOKE / BEST WORST JOKE (all "2026"). The food toppers
  stay available with `--only potatoes pie gravy food-coma drumstick-2`. Rough estimate about 3 h each at full size
  (the solid base is most of it), about 2 h at 80%. Mock-ups only; no print files yet.
- **Cup awards (2026-11-26, Allen: "we can use this, and we can edit the text"):** BK-Projects' "Trophy Cup with Easy
  Customizable Text Plate" (`photos/cup-trophy/CupBambu.3mf`, MakerWorld Standard Digital File License, never in git):
  gold cup on a brown base with a 1.1 mm recess front and back for a separate 45 x 17.5 x 2 mm plate (glued).
  `python -I tools/cup_awards.py <CupBambu.3mf> [--awards "LINE 1|LINE 2" ...]` writes `output/cup-awards/`:
  `award-plates.3mf` (the designer's plate as is, our raised text 0.6 mm, Inter Bold with rounded corners, up to 4.8 mm,
  shrunk to fit 40.5 mm; gold slot 1, text slot 2), `award-plates.png` (numbered), `mockup.glb`. Allen's texts: I ATE /
  - 2026, THANKSGIVING CHAMPION, LEFTOVER LEGEND ("is good LOL"); potato fan options TOP TATER, SPUD STUD, MASHED POTATO
  MVP, CHAMPION OF POTATOES; more: STRETCHY PANTS AWARD, MOST STUFFED, GRAVY BOSS, PIE MASTER, FOOD COMA CHAMPION,
  TURKEY WHISPERER, SECONDS AND THIRDS CLUB, PROFESSIONAL NAPPER, WORLD'S BEST DISHWASHER. Allen: "I like the year on
  them 2026": every plate without a year gets a small third line `--year 2026` (titles 3.9 mm, year 3.0 mm). Cups print from his file
  (about 2 h each, my guess). Arachne for the thin letters. Not printed yet.
- **Medals (2026-11-26, Allen: the cups take "a long time to print, especially 5 of them"; "medals can be good, but I
  dont have ribbons"):** `python tools/medals.py [--awards ...] [--year 2026]` writes `output/medals/`: 60 mm gold
  medals, 3 mm, raised rim and laurel, the award (same texts as the cup plates) and 2026 in raised letters (slot 2), a
  top tab with a 13 x 3.6 mm slot for kitchen twine, yarn, a shoelace or gift-wrap ribbon; 9 per plate
  (`medals-1.3mf`, `medals-2.3mf`), `medals.txt`, `medals-picture.png`. About 20 min each (my guess). Then Allen: "lets
  try medals, and I want it to have a somewhat 3D turkey on top that doesnt stuck out too much": 68 mm now, a low-relief
  turkey in the upper half (two rows of fan feathers, body, wings, head, googly eyes with dark pupil caps sunk 0.1 mm
  into the eyes, beak, wattle, a tapered little crown with balls on its points; at most about 3 mm off the face), the
  words under it (`text_y`), laurel lower down; 6 per plate (`medals-1..3.3mf`), `medal-closeup.png`. Files closed (0
  odd edges), nothing over air; about 25 min each (my guess). Allen's picks (2026-11-26), `output/medals-picked/`, 5 per
  plate: LEFTOVER LEGEND, MOST SAUCED (was SPUD STUD; cranberry sauce for kids, tipsy for adults), MOST STUFFED, WEIRD UNCLE (was GRAVY BOSS), PIE MASTER | CLEAN PLATE CLUB, WISHBONE WINNER, GOBBLE
  GOBBLE GURU, DESSERT FIRST CLUB, MOST THANKFUL (all with 2026). Not printed yet.
- **Coloring guide (2026-11-26, Allen: kids color the scepter and the crown with acrylic markers; crown printed
  yellow, scepter turkey white, its stick and base yellow):** `output/coloring-guide/coloring-guide.pdf` (Letter,
  landscape, 2 pages: big renders, a close-up, and a swatch list of which color goes where). Scepter: our mock-up
  colors, with "gold" shown as yellow marker. Crown: the trophy crown rebuilt (`turkey_trophy_crown.build`, cut 17,
  scale 1.2) and the turkey colored from the downloaded model's own Bambu paint (`paint_color` per triangle, decoded:
  unpainted = filament 1 brown, then orange, red, white), carried through the same shift/scale/wrap and matched to the
  final faces within 0.8 mm (1.6 mm colored filler behind the fan); the 12 tip balls (icosahedra, faces of ~20 mm2) and
  10 band gems in red/blue/green (Allen: "I want the crown top the circular stuff at the tips to be colored"). Built
  with one-off scripts in the session scratchpad and the three.js renderer there (not in git).
- **Star tree topper (2026-11-22, Allen: "Give me a star with names"):** `python tools/star_topper.py Allen Emma
  Madison Alison [--size 176]` writes `output/star-topper/`: a chunky gold star, face-up, one name raised on each
  side arm (top left, top right, bottom left, bottom right, in the order given; Inter Bold, one size, as big as fits:
  11 mm), a raised heart in the middle, a raised border; raised parts are separate parts (one color change). A cone
  mount (tree tips 9-26 mm) prints standing beside it; the star's tab is glued into its slot. Not printed yet.
- Uploaded scans and downloaded models are not in git (private). A new session that needs
  them asks Allen to upload again (the duck model: `screw-top ... --cut 50`).

## Setup in a fresh session

The cloud environment's setup script may already have installed the packages; if
`python -c "import manifold3d, cv2, pymupdf"` works, skip the install (a clean one takes
about 4 minutes).

```bash
pip install -r requirements.txt
```

Run `python -m pytest -q` (about 2.5 minutes) only after changing code, never before
processing an upload.

## Speed: Allen waits on every upload

The tool itself takes about 4 seconds per run plus 2.5 seconds per card (30 cards: about
a minute and a half). Allen's wait is everything else, so on an upload:

1. Run it, show the contact sheet, hand over the plates and print notes. That is the reply.
2. If you spot a bug, say so in one line and fix it after the handover, unless it makes a
   piece wrong to print (then hold that card only and hand over the rest).
3. Ask him to scan all cards into one Notes PDF (one page per card) and upload once.

## When Allen uploads photos or images

Put the uploads in a folder (not in git), then read the kids' names first (a few seconds):

```bash
python -m charm_maker names <folder or files> --out output/<batch-name>
```

Look at `output/<batch-name>/names.png` (each card's handwritten name line) and run with
the names you read, so every piece is named after its kid (`keychain-jack`, `clip-mia`;
a second one is `keychain-jack-2`; a blank or unreadable name keeps the card number):

```bash
python -m charm_maker run <folder or files> --out output/<batch-name> --names key-01=Jack clip-02=Mia
```

1. Run the pipeline on all of them. Do not ask which product if the cards say it.
   For a drawing without card markers, pass `--product <key>` (keys are in `config.yaml`).
2. Show the contact sheet. In plain words, list the fixes and anything you were unsure of,
   including any name you could not read (the contact sheet shows the handwriting beside it).
3. Ask only if a card is unreadable. Do not ask about colors: every distinct ink color is
   its own named part in the 3MF (never merged, up to `max_ink_colors` 8), and Allen assigns
   spools in Bambu Studio. If loaded slots are in config, parts start on the nearest loaded
   spool as a head start. One exception (Allen, 2026-11-11): when a drawing has more colors
   than the AMS has slots (the `check:` line "more than the 4 AMS slots"), hand the rest over
   and ask him which colors should share a spool for that piece.
4. Hand over the plate files (as downloads in a cloud session) and say, for each plate,
   which filament goes in which AMS slot, the layer height and the plate type.
5. Remind him of finishing steps only when they apply: glue (clip pads, stud posts, magnets
   on the flat back of figures, the separate post into a shaped clicker keycap), split rings
   (keychains), a 4 mm jump ring then the hook (earrings), the chain straight through the loop
   (pendants), switch insertion (clickers).

When Allen says he swapped a spool ("pink is in slot 3 now"): run
`python -m charm_maker load 3 "Pink PLA"` (add `--color "#RRGGBB"` for a spool not in
`filaments:`; `load 3 empty` for an empty slot) and commit `config.yaml`, because cloud
sessions start fresh and the slots only survive in git.

Products that build today, for anyone: hair clip, keychain, necklace pendant, magnet
figure (a fridge magnet: flat back, glued magnet; Allen, 2026-11-13: no stand, so the card has no
"stand here" line; only the stand was ever printed, in the fit test), clicker keychain, flexi (the drawing in wiggly strips), and earrings for adults (one drawing makes a
mirror-image pair, a small top tab with a front-to-back hole for Allen's 4 mm jump rings, or `style: stud` for a flat back). A drawing without card markers needs
`--product`.

Clicker (Allen's switch: MX-style blue clicky, photo 2026-11-10): clickers are always flat (Allen,
2026-11-15: "The clicker should all be flat"; `products.clicker.always_style: flat`: the clicker card has no shape boxes, a shape ticked on
an older clicker card is not read, a command-line `--style` for that card still wins). Each clicker card gives two
pieces. The keycap `click-NN` is the drawing as a flat charm with a 5.5 mm post and cross socket
on the back, filled out behind to at least the switch's 15.6 mm square, printed face-down with
the charms. A shaped keycap (puffy, raised lines, figurine: only with `--style` for that card)
prints face-up, so its post is a third piece `click-NN-post` (prints standing, socket up) that
Allen glues into a round dent in the keycap's back. The case `click-NN-case` is a cup (Allen, after the first print on
2026-11-11: the switch showed and the keycap floated over a gap): the switch snaps into a plate
at the bottom of an opening shaped like the keycap, the keycap sits in that opening (0.6 mm
clearance, face 1.5 mm above the rim) and presses down into it, so nothing of the switch shows.
Below the plate a hollow for the switch body and pins and a floor with a push-out hole; a short
ring tab (about 9.5 mm tall, Allen: not the whole height) halfway up the side, its hole running
left to right (the ring hangs beside the case, so it sits flat on a table). About 25 mm tall plus
the keycap (the switch needs that height); printed upright on the same plate as the charms (Allen,
2026-11-14; at their 0.12 mm, slower than the 0.2 mm it gets on its own plate with `--separate-plates`) in one
filament, no supports: the tab's underside slopes back to the wall at 45 degrees (Allen: with
tree supports on, Bambu Studio also filled the hollow inside the case; `ring_tab_supports: true`
gives the tab a flat underside on supports instead). The clicker card has a "cover the square" guide (16 mm keycap) in a 40 mm drawing box
(Allen: a minimum, but a large maximum); a smaller drawing is scaled up to 16 mm across (never
past 40 mm), with a note (Allen, 2026-11-12: kids don't think in sizes, hair clips shrink
anyway). "Keep its size, more border" is `products.clicker.small_drawing: border` (a config copy). Clicker cards printed before 2026-11-10's 40 mm box must be reprinted
(their drawing box is smaller). The keycap post sits at the drawing's
balance point, or as near it as fits. Both use
the fit-test values (`switch_cutout`, `stem_socket_clearance`, `keyring_hole_diameter`). The
case preview shows the clicker assembled. `glue_on_fallback: true` under `products.clicker`
makes a plain charm to glue onto a store-bought blank keycap instead.

Coloring is optional (Allen, 2026-11-13): the cards say "Draw big and bold", "Close the lines",
"Color it in, or we will" (`cards.kids_color: optional`; `yes` brings back "Use the colors in the
printer ... Color it in", `no` says "Use a black marker"). A colored drawing works as always (every
color its own part). A line drawing comes out as its lines plus white areas, and Allen fills the
areas in Bambu Studio with the color-painting fill tool (no separate parts needed: the lines keep
the fill in). Flat pieces print face-down, so he paints them from the bottom view. Tried
2026-11-13: it works as long as the areas are enclosed (hence "Close the lines" on the cards).

Card tick boxes: under the name line, every card except the clicker and the flexi (clickers are always flat since
2026-11-15: their card says "Your drawing becomes a button that clicks!" instead) shows the five shapes, each
with a real render of a sample heart, and a tick box: Flat, Puffy, Raised lines, Puffy + lines,
Figurine. A "neat lines" box beside the name turns on tidy. The run reads the ticks itself and
says so in the fixes ("shape ticked on the card: Puffy"); no tick means flat; two ticks use the
stronger mark with a `check:` line. Cards printed before the boxes still read (no ticks).

Shape styles from the command line: `--style puffy` (or `outlined`, `puffy-outlined`, `flat`)
for every card in a run, or per card with `--style clip-03=puffy`; repeat the flag for several
cards. Order: a style named for that card, then the card's tick, then a style for every card,
then flat. "Make card 3 puffy with a raised outline" is `--style clip-03=puffy-outlined`.
A second copy of a card number in one batch is named `-b` (`clip-01-b`); per-card flags
(`--style`, `--tidy`, `--figurine-back`, `--figurine-base`, `--names`, `--map`, `--no-dots`, `--scale`) take that exact
card name too, even when the piece is named after the kid. To let
Allen try the styles on one print, give each charm a different style (two per style).
Flat pieces are built mirrored on purpose (they print face-down); shaped ones are not.

Tidy: the card's "neat lines" box, `--tidy` for every card, or `--tidy clip-03` for one (repeat for more). "Tidy card 3"
or "make them all tidy" means this. It redraws the outline color's strokes at one even
thickness with smooth edges; dots, blobs and colored-in areas keep their shape, other colors
only get smooth edges. Off by default; it works with any shape style. Never an AI redraw.

Eyes and small dots (Allen, 2026-11-12): small round dots are kept (eyes, wing dots), stay round,
and a pair of eyes is made the same shape and size; they are circled in blue on the preview and
listed in the fixes. A pencil speck looks exactly like a dot, so if a drawing gets dots it does not
have (test drive 4's rainbow has no face), run again with `--no-dots <card>` (repeat for more, or
`--no-dots` for all). Decided by shape and position only, never by how dark the ink is.
Pencil drafts (Allen, 2026-11-14: kids may draft in pencil and erase before the marker): pencil is read on
purpose (test drive 4 was drawn in pencil). A well-erased line is too faint to read; one still clearly
visible after erasing reads as a line and prints. Look for stray lines on the contact sheet; if a card has
one, run again with `--no-pencil <card>` (repeat for more, or `--no-pencil` for all): only the marker is read.
Separate marks drawn around the drawing get joined to it with base-color bridges ("N separate pieces
joined"); when Allen says they are nothing (Areen's cat clicker, 2026-11-15), run again with
`--drop-strays <card>`: only the biggest piece is kept, with everything inside its outline.
Very light pencil (Avery's giraffe, 2026-11-15) comes back as broken dashes: `--light-pencil <card>` reads
it whole (`reader.light_ink_value_max` 0.80 instead of 0.60 for that card).
Several uploads together (Allen at the party, 2026-11-15: "I'll need all of them together, can split into a
few different plates, and give me the ETAs"): copy the PDFs into one folder, run `names` on it (the cards
renumber: key-01, key-01-b, ...), redo every per-card fix under the new card names, and use
`--separate-plates`: flat pieces, flexis and clicker cases each get plates of their own, so the quick flat
pieces come off first; give each plate's rough time.
A drawing too small for its details (the butterfly's 4 mm face: its U-shaped smile filled in at the
1 mm line width) can be made bigger: `--scale fig-01=1.5` (before the print fixes, so lines and
gaps grow too; `--scale 1.5` for every card). Allen said yes to 1.5 for that butterfly. Colors are read at the
drawn size (read 3.9 times bigger, a pen line split into a black middle and a gray edge: Alison's dog, 2026-11-15).
Several drawings on one card, each its own piece (Alison, 2026-11-15: "Make each drawing into individual key
chains"): `python tools/split_card.py <card.pdf> photos/<batch>/cards` writes one card copy per drawing (the
others painted over in paper color; eyes, mouths and nearby loose marks stay with their drawing) and prints a
`--scale` for each copy that makes it about 40 mm (`--target`); then `names` and `run` on that folder with
those scales. Her eight doodles were 10-18 mm at the card's scale and became 40-52 mm keychains, one plate.
Ring eyes and little closed shapes (a beak, a small heart) keep the white inside them, widened
to 0.4 mm where she drew a hairline (the bird hair clip, 2026-11-12), so they no longer print as
black blobs; the fixes say "small hole(s) inside little closed marks kept".

Figurines: `--style figurine` (or `--style fig-02=figurine`) rounds the drawing's front like a
balloon, thick where the drawing is wide. By default the back stays **flat**, so it is still the
card's product at the card's size (clip pad, glued magnet, ring tab, loop all work) and it prints
back-down with no supports, on the normal plates. The dome is capped per product
(`figurine.flat_back_max_dome`, e.g. 5 mm on hair clips). A round back makes a standalone 60 mm
figure instead (the card's ring, clip or loop is dropped): `--figurine-back fig-02=blank` (plain
back, for characters) or `=mirror` (front colors on the back too). Round-back figures stand on a
flat-cut bottom; `--figurine-base fig-02=disc` adds a round stand, `none` keeps it round. They
go on their own plates with tree supports on and 0.16 mm layers (never with the charms and cases:
supports on a shared plate also filled the hollow in Allen's clicker case).

Optional extras, only when Allen asks: the marker calibration card (`calibrate`), strict
color checking (`run --ask-colors`, which stops with `QUESTION.md` and exit code 2), swap
plates (`--off-palette swap`), and the filament chip plate (`chips`).

## Commands that exist today

| Task | Command |
| --- | --- |
| Record a spool in a slot | `python -m charm_maker load <slot> "<spool>" [--color "#RRGGBB"]` |
| Show slots and calibration | `python -m charm_maker slots` |
| Print the cards | `python -m charm_maker cards` (blank cards, plus calibration if slots are loaded; `--half-drawn` adds pre-set outlines, which Allen said he does not need) |
| One card of each type | `python -m charm_maker cards --count 1 --out output/cards-one-each` (7 pages; Allen can print a page as often as he likes: repeats read as `key-01`, `key-01-b`, and pieces are named after the kid anyway) |
| Read a calibration scan | `python -m charm_maker calibrate <scan>` |
| Chip plate (printer tour) | `python -m charm_maker chips` (writes `output/chips/`) |
| Kids' names first | `python -m charm_maker names photos/ --out output/<batch>` (writes `names.png`) |
| Photos to plates | `python -m charm_maker run photos/ --out output/<batch> [--names key-01=Jack ...]` |
| Ignore an erased pencil draft | add `--no-pencil key-03` to `run` (repeat for more cards; alone, every card) |
| Leave out stray marks around a drawing | add `--drop-strays click-01-c` to `run`: only the main drawing (everything inside its outline stays) |
| One piece bigger than drawn | add `--scale fig-01=1.5` to `run` (any factor from 0.25 to 4; repeat for more cards) |
| Each drawing on a card its own piece | `python tools/split_card.py <card> photos/<batch>/cards` (prints the `--scale` flags) |
| Clicker cases on their own plate | add `--separate-plates` to `run` (the default puts the cases with the charms, as many plates as the bed needs; `printer.one_plate` in config; round-back figurines always get their own plate) |
| Quick plate (when Allen asks) | add `--quick key-03 ear-01` to `run`: those cards also on a quick plate; the run lists what to delete from the kids' plates |
| A plate per kid | add `--per-kid` to `run` (default: everything on one plate) |
| Just some pieces | add `--only mia key-03` to `run`: only those kids (by the name read) or cards |
| Build the fit-test plate | `python -m charm_maker fit-test` (writes `output/fit-test/`) |
| Flexi joint test plate | `python -m charm_maker fit-test --only flexi_joint_gap --out output/fit-test-flexi` (pieces 19-22) |
| Make a card into another product | add `--as key-02=flexi` to `run` (repeat for more cards) |
| Keep a flexi's face whole | add `--keep-whole flexi-01=0-40` to `run`: no cuts in that band (percent from the top) |
| A flexi creature from the parts | `python -m charm_maker creature --head cat --body regular --legs paws --tail cat --name mia` |
| Picture of every creature part | `python -m charm_maker creature-library` (writes `output/creature-library/`) |
| Reprint one fit-test group | `python -m charm_maker fit-test --only earring_hole_diameter --out output/fit-test-earrings` |
| Record fit results | `python -m charm_maker fit-results <piece numbers>` |
| Build only the stand | `python -m charm_maker stand` |
| Test-drive pack | `python -m charm_maker test-drive` |
| Poop containers | `python -m charm_maker poop-containers [--kinds ...] [--sizes ...]` |
| Screw top for a downloaded model | `python -m charm_maker screw-top <model> --cut <mm> [--scale 1.15]` |
| Tests | `python -m pytest -q` |

## When Allen reports fit-test results

He will say something like "clip 2, keyring 5, earring 8, switch 11, stem 14, necklace 17".
Run `python -m charm_maker fit-results 2 5 8 11 14 17`, show him the changed lines of
`config.yaml`, commit, and move to the next milestone. If a group had no fit, add new
candidates to that group's `candidates` in `config.yaml`, rebuild the plate, and send only
the new coupons (one small plate).

Piece numbers map to groups in config order: 1-3 clip pocket, 4-6 keyring hole,
7-9 earring jump-ring hole (small top tab, front to back), 10-12 switch housing (cutout in the lid), 13-15 stem socket,
16-18 necklace loop (sideways hole), 19-22 flexi joint gap (a block with a swinging arm; he may say "joint 20").

## Reading the results

- `contact-sheet.png`: every design, actual size and zoomed, with its fixes. Show this first.
- `designs/<card>-preview.png`: the same per design, plus the name crop from the card.
- `designs/<card>.json`: sizes, filament per part, fixes and warnings, for your own checks.
- `PRINT_NOTES.md`: filament per AMS slot for each plate, layer height, plate type, finishing.
- `plates/<kids-and-pieces>.3mf` and `...-map.png`: everything from an upload on one plate, clicker cases
  included (Allen, 2026-11-15 at the party: "I need everything on one plate, its becoming too many files
  for me to keep track"; a second plate only when the bed is full), named after the kids and what they
  made: `alison-clicker-earrings_madison-necklace.3mf` (past about 80 letters `_and-3-more`). Bambu Studio
  shows the same name on the plate. Round-back figurines get a `-figurines` plate (supports);
  `--separate-plates` gives clicker cases a `-clicker-cases` plate; `--per-kid` gives each kid a plate
  (his 2026-11-14 wish, since replaced). Two plates in one run never share a name (`-2`). The
  map is who's who, each piece's name where it sits on the plate (send it with the plate; it stops
  matching if Allen presses Arrange).
- **Quick plate, only when Allen asks** ("when I ask give the quick one for each on a separate plate and
  tell me which one I need to take out from the main plate"). Never pick for him: kids choose when
  times are close ("if they r close, I will give kids the choice"). When he names the pieces, run the
  same upload again with `--quick <cards>` (cards from the quickest-first list) to a new folder: the
  main plate comes out the same as before and a `quick_<kids-and-pieces>.3mf` plate is added; send
  only the quick plate and its map, and pass on the run's "take these out" lines (which piece to delete
  from the main plate in Bambu Studio, so nothing prints twice).
- Rough print times (Allen, 2026-11-14: "estimate the time ... which each kid's print would be the
  fastest"): the run prints "quickest first", each kid's pieces with rough minutes of printing (a
  clicker counts with its case, earrings as a pair), and each plate's rough total and color changes;
  `PRINT_NOTES.md` has both. The model (`printtime.py`, `print_time:` in config) counts plastic, a
  floor per layer and AMS color changes (1.5 min each), so flat one-color pieces are quickest and
  multicolor figurines and puffy pieces slowest. It ranks well; the minutes are a guess (Allen,
  2026-11-14: "an estimate in terms of time will be fine", so no calibration needed; tune `print_time`
  only if he gives Bambu Studio's time for a plate). Long ones read "1 h 10 min". Pieces within 5 minutes (or a quarter)
  of a kid's quickest are marked "close: let Jack pick".
- `names.png`: from the `names` step, each card's name line.
- `QUESTION.md`: only in strict mode (`--ask-colors`), written instead of plates.
- Any `check:` line in the run output means something Allen should look at: an untested fit
  value, a color that starts on a spool that doesn't really match, two colors starting on
  the same spool, more than 3 ink colors, fewer than 4 markers found, a renamed duplicate, a
  drawn color too small to print as its own color (it prints in its neighbor's color).

Filament overrides in plain words ("card 3's pink should be Magenta") become
`--map "clip-03 pink=Magenta"`; run again. Names are matched against the loaded spools
first, then `filaments:` (the spools Allen owns). A spool that isn't loaded means a swap
plate, and the print notes say what goes in and out of which slot.

## Handing files over

In a cloud session, send every `output/.../plates/*.3mf` (not the `-plain` copies), the plate maps,
the contact sheet and `PRINT_NOTES.md` with the file tool, and name each plate in the reply (a clicker's
case is on the same plate as the charms unless `--separate-plates`). For the printer tour, send `output/chips/filament-chips.3mf` and `CHIPS.md`. Tell Allen: Bambu Studio, **File > Import > Import 3MF/STL/STEP/SVG/OBJ/AMF...**,
pick the file, choose **Load geometry only** if asked.

## Test drive

`python -m charm_maker test-drive` writes `output/test-drive/test-drive-pack.pdf`: a parent
page (print at Actual size, markers, what to draw on each card, how to scan with iPhone
Notes, what to look for) and six blank cards: hair clip 01 and 02, keychain 01 and 02,
magnet figure 01, necklace pendant 01. When Allen uploads
the scan and says "test drive", run it like any batch (with `--style` for any shapes she picked:
the parent page offers flat, puffy, raised outline and figurine), show the contact sheet, and ask
what his daughter liked and what looked wrong. Note which problems are real-world ones to
fix (and add a regression test in `tests/test_real_world.py`).

## Poop containers (party favors, parked 2026-11-13)

See-through containers kids fill with printer poop and twist shut. Everything prints with
no supports and the lid closes in one turn (right-hand thread: clockwise to close). Head lids
(duck, bear, heart) stop facing front: a sloped crown on the jar's rim meets the lid's ceiling
there, and the collar sits just above the body (Allen's first duck turned about 45 degrees past
front, 2026-11-12). The downloaded-model screw top stops the same way: the head sits 0.1 mm over
the flat cut.

```bash
python -m charm_maker poop-containers --kinds jar-round bear heart --sizes medium
```

Windows (Allen, 2026-11-13, after filling his printed duck: the 4 mm diamond holes hid the
poop): tall windows 8 mm wide with 1.8 mm bars and pointed 45-degree tops (no supports), a solid
ring between rows on tall walls, and 10 mm diamond windows straight down through roofs. 40 to 75%
more window than before; `poop_jar.windows: diamonds` brings the old mesh back. The duck's
belly is taller for bigger windows; its sloped back stays mostly solid (little room there).

Kinds: `jar-round`, `jar-hex`, `bear` (bear-head lid), `duck`, `heart`, `star`, `cloud`.
Sizes: `small`, `medium`, `tall`. Each folder has the 3MF (body + lid parts), a preview
with fake poop inside, the print layout and `PRINT_NOTES.md`. The thread clearance
(`poop_jar.thread_clearance`, 0.4 mm) is untested: have Allen print one and try the lid.

To give a downloaded "poop eater" (lattice body, solid head, filled by a print pause) a
twist-off head:

```bash
python -m charm_maker screw-top path/to/model.3mf --cut 50 --name duck
```

`--cut` is the height to split the head off. Pick it from horizontal slices: above where the
lattice wraps the neck and where the head is wide enough for the socket; the tool refuses a
cut that leaves an opening under 18 mm and warns if the head would touch the body while
unscrewing. Downloaded models keep their license: the output is for Allen's own printing.
Never commit it. Sebo3D's duck (MakerWorld, Standard Digital File License) worked at
`--cut 50`: 20 mm opening; its head still needs the original's tree supports for the beak.

## Checking against real drawings

Synthetic test cards are clean; real ones are not. `tools/try_real_drawings.py` places
six real kids' drawings (Meta's Animated Drawings examples, MIT license) onto design cards,
fakes phone photos and leaves them for a normal run. Use it after changing ink, color or
shape code, and look at the contact sheet:

```bash
GIT_LFS_SKIP_SMUDGE=1 git clone --depth 1 https://github.com/facebookresearch/animateddrawings /tmp/ad
python tools/try_real_drawings.py /tmp/ad output/real-drawings
python -m charm_maker run output/real-drawings/cards --out output/real-drawings/out
```

Expected: purple figure in purple; candy corn with black eyes, orange and yellow; girl
with eyes and smile in black; pig outline in pink; garlic in blue with a red tongue; bug
in blue, whole (its faint body outline is found since pencil detection). Never commit the outputs.

## Housekeeping

- Record every choice the spec did not settle as one line in `DECISIONS.md`.
- Add to `CHANGELOG.md` at the end of each milestone.
- Commit on the branch the session is given (it was `claude/jolly-keller-ifv0pq`), and open a
  pull request to `main` for Allen to merge; he merges with one button. Never push to `main`.
