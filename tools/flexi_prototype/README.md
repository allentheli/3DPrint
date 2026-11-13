# Flexi toy prototype (not part of the tool yet)

Scratch scripts from 2026-11-13 that built the first full flexi: a ready-made cat head with a
kid-style test face painted on, chest (front legs), torso, hips (back legs) and a tail, joined by
the standard ring joint (`charm_maker.fittest.flexi_joint`). Kept so the work survives a fresh
session; the real version goes into `charm_maker/` with a card, CLI and tests.

Run from the repository root, with a scratch folder for the in-between files (`W`):

```bash
python tools/flexi_prototype/proto_b.py $W cat     # head outline for the guide (cat-sil.npy)
python tools/flexi_prototype/faces.py $W            # test faces drawn on the guides
python tools/flexi_prototype/toy.py $W              # pieces, painted face, 3MF and renders
python tools/flexi_prototype/check.py $W            # each joint: swing, pull, lift
python tools/flexi_prototype/curl.py $W toy         # bend every joint in many combinations
```

Output goes to `output/flexi-concept/cat-flexi/` (not in git). `shapes.py` holds the ready-made
heads as blended shapes; `paint.py` and `render_bare.py` are the earlier head-only previews.
