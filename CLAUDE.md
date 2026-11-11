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
  pieces, add tighter candidates), necklace loop piece 17 = 3.5 mm. Still waiting on the earring
  jump-ring hole only (pieces 7-9 changed on 2026-11-11; Allen tests with Madison's real
  earrings instead, 1.5 mm = piece 8: if the jump ring goes on and closes, record 8). Until
  then earrings say so in a `check:` line.
- **Prints to try (as of 2026-11-11):** Madison's one-plate batch (cup-style clicker with the
  short ring tab, no supports: check the keycap moves freely in the 0.6 mm gap; both
  earring pairs with the jump-ring test; the bubble tea clip with each color its own part),
  Alison's pendant (the 0.5 mm yellow straw strip), the shark and bird in the 3D shapes, and
  one poop container lid (thread clearance untested).
- **Open questions for Allen:** his switch's length from the plate ledge to the pin tips (to
  trim the clicker by about 1.5 mm); whether "every drawn color its own part, never merged"
  should be the default (he recolors in Bambu Studio anyway).
- **Party:** date and number of kids not set yet. AMS slots are left empty on purpose: Allen
  changes spools at will and assigns colors in Bambu Studio.
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
   its own named part in the 3MF, and Allen assigns spools in Bambu Studio. If loaded slots
   are in config, parts start on the nearest loaded spool as a head start.
4. Hand over the plate files (as downloads in a cloud session) and say, for each plate,
   which filament goes in which AMS slot, the layer height and the plate type.
5. Remind him of finishing steps only when they apply: glue (clip pads, stud posts, magnets
   on the flat back of figures), split rings (keychains), a 4 mm jump ring then the hook (earrings), the chain straight through
   the loop (pendants), switch insertion (clickers).

When Allen says he swapped a spool ("pink is in slot 3 now"): run
`python -m charm_maker load 3 "Pink PLA"` (add `--color "#RRGGBB"` for a spool not in
`filaments:`; `load 3 empty` for an empty slot) and commit `config.yaml`, because cloud
sessions start fresh and the slots only survive in git.

Products that build today, for anyone: hair clip, keychain, necklace pendant, magnet
figure (flat back, glued magnet), clicker keychain, and earrings for adults (one drawing makes a
mirror-image pair, a small top tab with a front-to-back hole for Allen's 4 mm jump rings, or `style: stud` for a flat back). A drawing without card markers needs
`--product`.

Clicker (Allen's switch: MX-style blue clicky, photo 2026-11-10): each clicker card gives two
pieces. The keycap `click-NN` is the drawing as a flat charm (always flat) with a 5.5 mm post
and cross socket on the back, filled out behind to at least the switch's 15.6 mm square, printed
face-down with the charms. The case `click-NN-case` is a cup (Allen, after the first print on
2026-11-11: the switch showed and the keycap floated over a gap): the switch snaps into a plate
at the bottom of an opening shaped like the keycap, the keycap sits in that opening (0.6 mm
clearance, face 1.5 mm above the rim) and presses down into it, so nothing of the switch shows.
Below the plate a hollow for the switch body and pins and a floor with a push-out hole; a short
ring tab (about 9.5 mm tall, Allen: not the whole height) halfway up the side, its hole running
left to right (the ring hangs beside the case, so it sits flat on a table). About 25 mm tall plus
the keycap (the switch needs that height); printed upright on its own plate at 0.2 mm in one
filament, no supports: the tab's underside slopes back to the wall at 45 degrees (Allen: with
tree supports on, Bambu Studio also filled the hollow inside the case; `ring_tab_supports: true`
gives the tab a flat underside on supports instead). The clicker card has a "cover the square" guide (16 mm keycap) in a 40 mm drawing box
(Allen: a minimum, but a large maximum); a smaller drawing is scaled up to 16 mm (never past
40 mm) with a note. Clicker cards printed before 2026-11-10's 40 mm box must be reprinted
(their drawing box is smaller). The keycap post sits at the drawing's
balance point, or as near it as fits. Both use
the fit-test values (`switch_cutout`, `stem_socket_clearance`, `keyring_hole_diameter`). The
case preview shows the clicker assembled. `glue_on_fallback: true` under `products.clicker`
makes a plain charm to glue onto a store-bought blank keycap instead.

Card tick boxes: under the name line, every card (except clicker) shows the five shapes, each
with a real render of a sample heart, and a tick box: Flat, Puffy, Raised lines, Puffy + lines,
Figurine. A "neat lines" box beside the name turns on tidy. The run reads the ticks itself and
says so in the fixes ("shape ticked on the card: Puffy"); no tick means flat; two ticks use the
stronger mark with a `check:` line. Cards printed before the boxes still read (no ticks).

Shape styles from the command line: `--style puffy` (or `outlined`, `puffy-outlined`, `flat`)
for every card in a run, or per card with `--style clip-03=puffy`; repeat the flag for several
cards. Order: a style named for that card, then the card's tick, then a style for every card,
then flat. "Make card 3 puffy with a raised outline" is `--style clip-03=puffy-outlined`.
A second copy of a card number in one batch is named `-b` (`clip-01-b`); per-card flags
(`--style`, `--tidy`, `--figurine-back`, `--figurine-base`, `--names`, `--map`) take that exact
card name too, even when the piece is named after the kid. To let
Allen try the styles on one print, give each charm a different style (two per style).
Flat pieces are built mirrored on purpose (they print face-down); shaped ones are not.

Tidy: the card's "neat lines" box, `--tidy` for every card, or `--tidy clip-03` for one (repeat for more). "Tidy card 3"
or "make them all tidy" means this. It redraws the outline color's strokes at one even
thickness with smooth edges; dots, blobs and colored-in areas keep their shape, other colors
only get smooth edges. Off by default; it works with any shape style. Never an AI redraw.

Figurines: `--style figurine` (or `--style fig-02=figurine`) rounds the drawing's front like a
balloon, thick where the drawing is wide. By default the back stays **flat**, so it is still the
card's product at the card's size (clip pad, glued magnet, ring tab, loop all work) and it prints
back-down with no supports, on the normal plates. The dome is capped per product
(`figurine.flat_back_max_dome`, e.g. 5 mm on hair clips). A round back makes a standalone 60 mm
figure instead (the card's ring, clip or loop is dropped): `--figurine-back fig-02=blank` (plain
back, for characters) or `=mirror` (front colors on the back too). Round-back figures stand on a
flat-cut bottom; `--figurine-base fig-02=disc` adds a round stand, `none` keeps it round. They
go on their own plates with tree supports on and 0.16 mm layers.

Optional extras, only when Allen asks: the marker calibration card (`calibrate`), strict
color checking (`run --ask-colors`, which stops with `QUESTION.md` and exit code 2), swap
plates (`--off-palette swap`), and the filament chip plate (`chips`).

## Commands that exist today

| Task | Command |
| --- | --- |
| Record a spool in a slot | `python -m charm_maker load <slot> "<spool>" [--color "#RRGGBB"]` |
| Show slots and calibration | `python -m charm_maker slots` |
| Print the cards | `python -m charm_maker cards` (blank cards, plus calibration if slots are loaded; `--half-drawn` adds pre-set outlines, which Allen said he does not need) |
| One card of each type | `python -m charm_maker cards --count 1 --out output/cards-one-each` (6 pages; Allen can print a page as often as he likes: repeats read as `key-01`, `key-01-b`, and pieces are named after the kid anyway) |
| Read a calibration scan | `python -m charm_maker calibrate <scan>` |
| Chip plate (printer tour) | `python -m charm_maker chips` (writes `output/chips/`) |
| Kids' names first | `python -m charm_maker names photos/ --out output/<batch>` (writes `names.png`) |
| Photos to plates | `python -m charm_maker run photos/ --out output/<batch> [--names key-01=Jack ...]` |
| Everything on one plate | add `--one-plate` to `run`: clicker cases and figurines join the charms in one 3MF at 0.12 mm, any number of colors (Allen sets spools in Bambu Studio) |
| Build the fit-test plate | `python -m charm_maker fit-test` (writes `output/fit-test/`) |
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
16-18 necklace loop (sideways hole).

## Reading the results

- `contact-sheet.png`: every design, actual size and zoomed, with its fixes. Show this first.
- `designs/<card>-preview.png`: the same per design, plus the name crop from the card.
- `designs/<card>.json`: sizes, filament per part, fixes and warnings, for your own checks.
- `PRINT_NOTES.md`: filament per AMS slot for each plate, layer height, plate type, finishing.
- `plates/plate-N-map.png`: who's who, each piece's name where it sits on the plate (send it
  with the plate; it stops matching if Allen presses Arrange in Bambu Studio).
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

In a cloud session, send `output/.../plates/*.3mf`, the plate maps, the contact sheet and `PRINT_NOTES.md`
with the file tool. For the printer tour, send `output/chips/filament-chips.3mf` and `CHIPS.md`. Tell Allen: Bambu Studio, **File > Import > Import 3MF/STL/STEP/SVG/OBJ/AMF...**,
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

## Poop containers (party favors)

See-through containers kids fill with printer poop and twist shut. Everything prints with
no supports and the lid closes in one turn (right-hand thread: clockwise to close).

```bash
python -m charm_maker poop-containers --kinds jar-round bear heart --sizes medium
```

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
