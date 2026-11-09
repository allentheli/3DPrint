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

## When Allen uploads photos or images (milestone 1 onward)

1. Run the pipeline on all of them. Do not ask which product if the cards say it.
2. Show the contact sheet. In plain words, list the fixes and anything you were unsure of.
3. Ask only if a card is unreadable or a color mapping is genuinely unclear.
4. Hand over the plate files (as downloads in a cloud session) and say, for each plate,
   which filament goes in which AMS slot, the layer height and the plate type.
5. Remind him of finishing steps only when they apply: glue (clips, studs, magnets),
   rings (keychains, earrings, pendants), switch insertion (clickers).

The pipeline is not built yet. Until milestone 1 lands, the commands are below.

## Commands that exist today

| Task | Command |
| --- | --- |
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

## Handing files over

In a cloud session, send `output/.../*.3mf`, the preview PNGs and the guide PDF with the
file tool. Tell Allen: Bambu Studio, **File > Import > Import 3MF/STL/STEP/SVG/OBJ/AMF...**,
pick the file, choose **Load geometry only** if asked.

## Housekeeping

- Record every choice the spec did not settle as one line in `DECISIONS.md`.
- Add to `CHANGELOG.md` at the end of each milestone.
- Commit on branch `claude/jolly-keller-ifv0pq` unless told otherwise.
