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

## Setup in a fresh session

```bash
pip install -r requirements.txt
python -m pytest -q
```

## When Allen uploads photos or images

Put the uploads in a folder (not in git), then:

```bash
python -m charm_maker run <folder or files> --out output/<batch-name>
```

1. Run the pipeline on all of them. Do not ask which product if the cards say it.
   For a drawing without card markers, pass `--product <key>` (keys are in `config.yaml`).
2. Show the contact sheet. In plain words, list the fixes and anything you were unsure of.
3. Ask only if a card is unreadable. Do not ask about colors: every distinct ink color is
   its own named part in the 3MF, and Allen assigns spools in Bambu Studio. If loaded slots
   are in config, parts start on the nearest loaded spool as a head start.
4. Hand over the plate files (as downloads in a cloud session) and say, for each plate,
   which filament goes in which AMS slot, the layer height and the plate type.
5. Remind him of finishing steps only when they apply: glue (clip pads, stud posts, magnets
   on the flat back of figures), split rings (keychains), the hook or chain straight through
   the loop (earrings, pendants), switch insertion (clickers).

When Allen says he swapped a spool ("pink is in slot 3 now"): run
`python -m charm_maker load 3 "Pink PLA"` (add `--color "#RRGGBB"` for a spool not in
`filaments:`; `load 3 empty` for an empty slot) and commit `config.yaml`, because cloud
sessions start fresh and the slots only survive in git.

Products that build today, for anyone: hair clip, keychain, necklace pendant, magnet
figure (flat back, glued magnet), and earrings for adults (a pair, top loop with a sideways
hole, or `style: stud` for a flat back). The clicker is not built yet: ask Allen for the
switch brand or a photo first. A drawing without card markers needs `--product`.

Shape styles: `--style puffy` (or `outlined`, `puffy-outlined`, `flat`) for every card in a
run, or per card with `--style clip-03=puffy`; repeat the flag for several cards. Flat is the
default. "Make card 3 puffy with a raised outline" is `--style clip-03=puffy-outlined`.
Flat pieces are built mirrored on purpose (they print face-down); shaped ones are not.

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
| Read a calibration scan | `python -m charm_maker calibrate <scan>` |
| Chip plate (printer tour) | `python -m charm_maker chips` (writes `output/chips/`) |
| Photos to plates | `python -m charm_maker run photos/ --out output/<batch>` |
| Build the fit-test plate | `python -m charm_maker fit-test` (writes `output/fit-test/`) |
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
7-9 earring loop (sideways hole), 10-12 switch cutout, 13-15 stem socket,
16-18 necklace loop (sideways hole).

## Reading the results

- `contact-sheet.png`: every design, actual size and zoomed, with its fixes. Show this first.
- `designs/<card>-preview.png`: the same per design, plus the name crop from the card.
- `designs/<card>.json`: sizes, filament per part, fixes and warnings, for your own checks.
- `PRINT_NOTES.md`: filament per AMS slot for each plate, layer height, plate type, finishing.
- `QUESTION.md`: only in strict mode (`--ask-colors`), written instead of plates.
- Any `check:` line in the run output means something Allen should look at: an untested fit
  value, a color that starts on a spool that doesn't really match, two colors starting on
  the same spool, more than 3 ink colors, fewer than 4 markers found, a renamed duplicate.

Filament overrides in plain words ("card 3's pink should be Magenta") become
`--map "clip-03 pink=Magenta"`; run again. Names are matched against the loaded spools
first, then `filaments:` (the spools Allen owns). A spool that isn't loaded means a swap
plate, and the print notes say what goes in and out of which slot.

## Handing files over

In a cloud session, send `output/.../plates/*.3mf`, the contact sheet and `PRINT_NOTES.md`
with the file tool. For the printer tour, send `output/chips/filament-chips.3mf` and `CHIPS.md`. Tell Allen: Bambu Studio, **File > Import > Import 3MF/STL/STEP/SVG/OBJ/AMF...**,
pick the file, choose **Load geometry only** if asked.

## Test drive

`python -m charm_maker test-drive` writes `output/test-drive/test-drive-pack.pdf`: a parent
page (print at Actual size, markers, what to draw on each card, how to scan with iPhone
Notes, what to look for) and six blank cards: hair clip 01 and 02, keychain 01 and 02,
magnet figure 01, necklace pendant 01. When Allen uploads
the scan and says "test drive", run it like any batch, show the contact sheet, and ask
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
in blue (its body outline is very faint and comes out in pieces). Never commit the outputs.

## Housekeeping

- Record every choice the spec did not settle as one line in `DECISIONS.md`.
- Add to `CHANGELOG.md` at the end of each milestone.
- Commit on branch `claude/jolly-keller-ifv0pq` unless told otherwise.
