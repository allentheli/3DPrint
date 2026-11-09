"""Run real kids' drawings through the whole card pipeline.

Uses the example drawings from Meta's Animated Drawings project (MIT license, collected
with consent): https://github.com/facebookresearch/AnimatedDrawings. Each drawing is
placed into a real design card's box, photographed (perspective, uneven light, blur,
JPEG), and then run like any upload. Nothing here is committed: outputs go to --out.

    GIT_LFS_SKIP_SMUDGE=1 git clone --depth 1 https://github.com/facebookresearch/animateddrawings /tmp/ad
    python tools/try_real_drawings.py /tmp/ad output/real-drawings
    python -m charm_maker run output/real-drawings/cards --out output/real-drawings/out

What each one tests: a bold purple marker (the easy case), crayon with paper showing
through and small dark eyes, a thin gray pen with a small face, a very faint thin pink
pen, a ballpoint plus red crayon under a hard shadow, and a faint light-blue pen.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from charm_maker.config import load_config          # noqa: E402
from charm_maker.inks import flatten_lighting        # noqa: E402
from tests.synthetic import card_image, photograph   # noqa: E402

# (image inside the Animated Drawings checkout, product, card number, crop as fractions)
JOBS = [
    ("examples/characters/char1/texture.png", "hair_clip", 4, None),
    ("examples/characters/char3/texture.png", "magnet_figure", 2, None),
    ("examples/characters/char2/texture.png", "pendant", 3, None),
    ("examples/characters/char6/image.png", "keychain", 5, None),
    ("examples/drawings/garlic.png", "keychain", 6, (0.17, 0.12, 0.80, 0.86)),
    ("examples/characters/char5/image.png", "magnet_figure", 7, (0.35, 0.31, 0.66, 0.73)),
]


def ink_bbox(rgb01: np.ndarray) -> tuple[int, int, int, int]:
    gray = rgb01.mean(axis=2)
    hsv = cv2.cvtColor(rgb01.astype(np.float32), cv2.COLOR_RGB2HSV)
    ink = (gray < 0.75) | (hsv[:, :, 1] > 0.2)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(ink.astype(np.uint8), connectivity=8)
    keep = [i for i in range(1, n) if stats[i, cv2.CC_STAT_AREA] > 30]
    ys, xs = np.nonzero(np.isin(labels, keep))
    return xs.min(), ys.min(), xs.max(), ys.max()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("source", help="Animated Drawings checkout")
    ap.add_argument("out", help="output folder (cards go in <out>/cards)")
    args = ap.parse_args()
    src, out = Path(args.source), Path(args.out) / "cards"
    out.mkdir(parents=True, exist_ok=True)
    cfg = load_config()
    for rel, product, number, crop_box in JOBS:
        im = Image.open(src / rel)
        if crop_box:
            w, h = im.size
            im = im.crop((int(crop_box[0] * w), int(crop_box[1] * h), int(crop_box[2] * w), int(crop_box[3] * h)))
        if im.mode == "RGBA":
            bg = Image.new("RGB", im.size, (235, 235, 230))
            bg.paste(im, mask=im.split()[3])
            im = bg
        flat = flatten_lighting(cv2.cvtColor(np.asarray(im.convert("RGB")), cv2.COLOR_RGB2BGR))
        x0, y0, x1, y1 = ink_bbox(flat)
        crop = flat[max(y0 - 6, 0):y1 + 6, max(x0 - 6, 0):x1 + 6]
        card, lay, ppm, P = card_image(cfg, product, number, out / "_pdf")
        bx, by, bw, bh = lay.box
        f = 0.82 * bw * ppm / max(crop.shape[:2])
        crop = cv2.resize(crop, (int(crop.shape[1] * f), int(crop.shape[0] * f)), interpolation=cv2.INTER_AREA)
        arr = np.asarray(card).astype(np.float32) / 255.0
        cx, cy = P(bx + bw / 2, by + bh / 2)
        ox, oy = int(cx - crop.shape[1] / 2), int(cy - crop.shape[0] / 2)
        arr[oy:oy + crop.shape[0], ox:ox + crop.shape[1]] *= crop          # ink darkens the card
        name = f"{product}-{number:02d}-{Path(rel).parent.name}.jpg"
        photograph(Image.fromarray((arr * 255).astype(np.uint8)), out / name, seed=number)
        print(f"{out / name}  <-  {rel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
