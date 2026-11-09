# Charm Maker: runbook for Claude Code sessions

Read `docs/charm-maker-spec.md` once if you have not. Allen owns this project and does
not write code: do the work, run it, and explain in plain words with numbered steps and
exact button names. Ask at most one question at a time, only when the answer changes what
you build. Never say something works unless you ran it. Say what you could not test.

## Hard rules (short form)

- Stay faithful to the drawing. No redrawing, no AI image generation.
- Flat, flush, face-down pieces. One solid part per design.
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
3. Ask only if a card is unreadable, or once per batch if a drawing uses a color that isn't loaded:
   map it to the nearest loaded color, or print it on its own plate with a spool swap.
   Never merge colors silently. Also ask once if the calibration card hasn't been scanned
   for the loaded markers. The run does this for you: exit code 2, `QUESTION.md`, no plates.
   Relay the question in plain words, then run again with his answer:
   "nearest" is `--off-palette nearest`, "swap" is `--off-palette swap`, "go ahead" without
   a scan is `--uncalibrated-ok`, and a per-card answer is `--map "clip-03 orange=Pink PLA"`.
4. Hand over the plate files (as downloads in a cloud session) and say, for each plate,
   which filament goes in which AMS slot, the layer height and the plate type.
5. Remind him of finishing steps only when they apply: glue (clips, studs, magnets),
   rings (keychains, earrings, pendants), switch insertion (clickers).

When Allen says he swapped a spool ("pink is in slot 3 now"):

1. `python -m charm_maker load 3 "Pink PLA"` (add `--color "#RRGGBB"` for a spool not in
   `filaments:`; `load 3 empty` for an empty slot). This clears that slot's calibration.
2. `python -m charm_maker cards` and `python -m charm_maker chips`, and send him the new
   `calibration-card.pdf` and `filament-chips.3mf`.
3. Remind him to fill in and rescan the calibration card. Commit `config.yaml`: cloud
   sessions start fresh, so the loaded slots and calibration only survive in git.

When a calibration card scan arrives (alone or in a batch), the run reads it and saves the
marker colors into `config.yaml`. Run `python -m charm_maker slots` to show the result and
commit `config.yaml`.

Hair clips and keychains work today. Clicker, earrings, pendant and magnet figure
products are in config but their attachments are not built yet (milestones 3 to 5).
Until `loaded:` is filled in, kid ink is grouped by hue against a generic palette and
extra colors are merged with a `check:` line; tell Allen that and get his spools first.

## Commands that exist today

| Task | Command |
| --- | --- |
| Record a spool in a slot | `python -m charm_maker load <slot> "<spool>" [--color "#RRGGBB"]` |
| Show slots and calibration | `python -m charm_maker slots` |
| Print the cards | `python -m charm_maker cards` (blank, half-drawn and calibration PDFs in `output/cards/`) |
| Read a calibration scan | `python -m charm_maker calibrate <scan>` |
| Chip plate (printer tour) | `python -m charm_maker chips` (writes `output/chips/`) |
| Photos to plates | `python -m charm_maker run photos/ --out output/<batch>` |
| Build the fit-test plate | `python -m charm_maker fit-test` (writes `output/fit-test/`) |
| Record fit results | `python -m charm_maker fit-results <piece numbers>` |
| Build only the stand | `python -m charm_maker stand` |
| Tests | `python -m pytest -q` |

## When Allen reports fit-test results

He will say something like "clip 2, keyring 5, jump ring 8, magnet 11, switch 14, stem 17".
Run `python -m charm_maker fit-results 2 5 8 11 14 17`, show him the changed lines of
`config.yaml`, commit, and move to the next milestone. If a group had no fit, add new
candidates to that group's `candidates` in `config.yaml`, rebuild the plate, and send only
the new coupons (one small plate).

Piece numbers map to groups in config order: 1-3 clip pocket, 4-6 keyring hole,
7-9 jump-ring hole, 10-12 magnet pocket, 13-15 switch cutout, 16-18 stem socket.

## Reading the results

- `contact-sheet.png`: every design, actual size and zoomed, with its fixes. Show this first.
- `designs/<card>-preview.png`: the same per design, plus the name crop from the card.
- `designs/<card>.json`: sizes, filament per part, fixes and warnings, for your own checks.
- `PRINT_NOTES.md`: filament per AMS slot for each plate, layer height, plate type, finishing.
- `QUESTION.md`: written instead of plates when something needs Allen's answer first.
- Any `check:` line in the run output means something Allen should look at: an untested fit
  value, a color that isn't loaded, matching without calibration, fewer than 4 markers
  found, a renamed duplicate card.

Filament overrides in plain words ("card 3's pink should be Magenta") become
`--map "clip-03 pink=Magenta"`; run again. Names are matched against the loaded spools
first, then `filaments:` (the spools Allen owns). A spool that isn't loaded means a swap
plate, and the print notes say what goes in and out of which slot.

## Handing files over

In a cloud session, send `output/.../plates/*.3mf`, the contact sheet and `PRINT_NOTES.md`
with the file tool. For the printer tour, send `output/chips/filament-chips.3mf` and `CHIPS.md`. Tell Allen: Bambu Studio, **File > Import > Import 3MF/STL/STEP/SVG/OBJ/AMF...**,
pick the file, choose **Load geometry only** if asked.

## Housekeeping

- Record every choice the spec did not settle as one line in `DECISIONS.md`.
- Add to `CHANGELOG.md` at the end of each milestone.
- Commit on branch `claude/jolly-keller-ifv0pq` unless told otherwise.
