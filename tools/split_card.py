"""Split a card with several separate drawings into one card copy per drawing.

Alison's keychain card (2026-11-15) had eight little drawings and Allen asked for "each drawing
into individual key chains". Each copy keeps the card's markers and name line, with every other
drawing painted over in the paper's own color, so the copies run like normal cards (they read as
key-01, key-01-b, ...). A drawing keeps everything inside its outline (eyes, mouth) and loose
marks near it (whiskers) join the nearest drawing.

The drawings are small at the card's scale, so the script also prints a `--scale` for each copy
that makes it about TARGET mm on its long side (keychains are 35-55 mm).

    python tools/split_card.py photos/<batch>/card.pdf photos/<batch>/cards [--target 40] [--gap 1.5]

Card copies go in the output folder; small pictures of each drawing go in a `-thumbs` folder
beside it (so they are not read as cards). Both stay private (photos/ is not in git).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from charm_maker.config import load_config  # noqa: E402
from charm_maker.reader import load_image, read_card  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("card")
    ap.add_argument("out")
    ap.add_argument("--target", type=float, default=40.0, help="long side of each drawing, mm (default 40)")
    ap.add_argument("--gap", type=float, default=1.5, help="marks closer than this (card mm) are one drawing")
    a = ap.parse_args()
    out, thumbs = Path(a.out), Path(a.out + "-thumbs")
    out.mkdir(parents=True, exist_ok=True)
    thumbs.mkdir(parents=True, exist_ok=True)
    cfg = load_config(ROOT / "config.yaml")
    read = read_card(cfg, load_image(Path(a.card)))[0]
    if read.layout is None:
        sys.exit("no card markers found")
    page, ppm, lay = read.page, read.px_per_card_mm, read.layout
    card_scale = cfg["process"]["card_scale"]
    H = page.shape[0]
    bx, by, bw, bh = lay.box
    x0, x1 = int((bx + 2) * ppm), int((bx + bw - 2) * ppm)
    y0, y1 = int(H - (by + bh - 2) * ppm), int(H - (by + 2) * ppm)
    gray = cv2.cvtColor(page, cv2.COLOR_BGR2GRAY)
    ink = np.zeros(gray.shape, np.uint8)
    ink[y0:y1, x0:x1] = (gray[y0:y1, x0:x1] < 120).astype(np.uint8)
    ink = cv2.morphologyEx(ink, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    r = max(1, int(a.gap * ppm / 2))
    grown = cv2.dilate(ink, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1)))
    # Fill each closed outline, so eyes and mouths inside a face stay with it.
    ff = grown.copy()
    cv2.floodFill(ff, np.zeros((ff.shape[0] + 2, ff.shape[1] + 2), np.uint8), (0, 0), 2)
    n, lab, st, _ = cv2.connectedComponentsWithStats((ff != 2).astype(np.uint8))
    big = [i for i in range(1, n) if st[i, 4] > 300 * ppm * ppm]
    if not big:
        sys.exit("no drawing found in the box")
    dist = np.stack([cv2.distanceTransform((lab != i).astype(np.uint8), cv2.DIST_L2, 5) for i in big])
    labels = np.zeros(lab.shape, np.int32)
    for g, i in enumerate(big, 1):
        labels[lab == i] = g
    for j in range(1, n):
        if j in big:
            continue
        ys, xs = np.nonzero(lab == j)
        d = dist[:, ys, xs].min(axis=1)
        labels[lab == j] = int(d.argmin()) + 1
        print(f"  a loose mark ({st[j, 2] / ppm:.0f} x {st[j, 3] / ppm:.0f} card mm) joins the drawing "
              f"{d.min() / ppm:.1f} card mm away")
    # Paper behind the ink: mask anything darker than plain paper, fill it in from the paper around
    # it at 1 px per card mm, then blur; keeps the photo's light falloff (a median left gray smudges).
    soft = (gray < np.percentile(gray[y0:y1, x0:x1], 60) - 25).astype(np.uint8)
    soft = cv2.dilate(soft, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (int(3 * ppm) | 1, int(3 * ppm) | 1)))
    size = (max(1, int(page.shape[1] / ppm)), max(1, int(page.shape[0] / ppm)))
    small = cv2.resize(page, size, interpolation=cv2.INTER_AREA)
    small_mask = (cv2.resize(soft.astype(np.float32), size, interpolation=cv2.INTER_AREA) > 0).astype(np.uint8)
    small = cv2.inpaint(small, small_mask, 5, cv2.INPAINT_TELEA)
    paper = cv2.GaussianBlur(cv2.resize(small, (page.shape[1], page.shape[0])), (0, 0), 1.5 * ppm)
    region = np.zeros(gray.shape, bool)
    region[y0:y1, x0:x1] = True
    boxes = {}
    for g in range(1, len(big) + 1):
        ys, xs = np.nonzero(labels == g)
        boxes[g] = (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)
    # Reading order: rows top to bottom (25 card mm bands), then left to right.
    order = sorted(boxes, key=lambda g: (round((boxes[g][1] + boxes[g][3]) / 2 / (25 * ppm)),
                                         (boxes[g][0] + boxes[g][2]) / 2))
    scales = []
    for k, g in enumerate(order, 1):
        keep = cv2.dilate((labels == g).astype(np.uint8), np.ones((2 * r + 1, 2 * r + 1), np.uint8)).astype(bool)
        img = page.copy()
        blank = region & ~keep
        img[blank] = paper[blank]
        cv2.imwrite(str(out / f"drawing-{k}.png"), img)
        ax0, ay0, ax1, ay1 = boxes[g]
        cv2.imwrite(str(thumbs / f"drawing-{k}.png"), page[max(0, ay0 - 20):ay1 + 20, max(0, ax0 - 20):ax1 + 20])
        ys, xs = np.nonzero(ink.astype(bool) & keep)
        w, h = (xs.max() - xs.min() + 1) / ppm / card_scale, (ys.max() - ys.min() + 1) / ppm / card_scale
        f = round(min(4.0, max(0.25, a.target / max(w, h))), 2)
        scales.append(f)
        print(f"drawing-{k}: {w:.1f} x {h:.1f} mm at the card's scale; x{f:g} makes it about {a.target:g} mm")
    print(f"{len(order)} drawings in {out}")
    # Alone in a folder, the copies read in file order as key-01, key-01-b, key-01-c, ...
    names = [lay.stem] + [f"{lay.stem}-{chr(ord('b') + i)}" for i in range(len(order) - 1)]
    print("for `run` (check the names step reads them in this order):")
    print(" ".join(f"--scale {c}={f:g}" for c, f in zip(names, scales)))


if __name__ == "__main__":
    main()
