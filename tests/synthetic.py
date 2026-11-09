"""Build fake phone photos of filled-in design cards, for tests."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pymupdf
from PIL import Image, ImageDraw

from charm_maker.cards import card_layout, write_cards_pdf

BLACK = (25, 25, 30)
YELLOW = (245, 215, 40)
PINK = (240, 80, 140)


def card_image(cfg: dict, product: str, number: int, out_dir: Path, dpi: int = 150):
    """Render one blank card from the real PDF generator. Returns (PIL image, layout, px_per_mm, to_px)."""
    pdf = write_cards_pdf(cfg, [product], out_dir / f"cards-{product}.pdf", count=number)
    doc = pymupdf.open(str(pdf))
    pix = doc[number - 1].get_pixmap(dpi=dpi)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    lay = card_layout(cfg, product, number)
    ppm = dpi / 25.4
    H = lay.page[1]

    def to_px(x, y):
        return (x * ppm, (H - y) * ppm)

    return img, lay, ppm, to_px


def photograph(img: Image.Image, path: Path, *, warp: bool = True, seed: int = 1) -> Path:
    """Perspective, uneven light, blur, noise and JPEG, like a casual phone photo."""
    arr = np.asarray(img)
    h, w = arr.shape[:2]
    if warp:
        src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
        dst = np.float32([[60, 40], [w - 30, 70], [w - 80, h - 50], [20, h - 20]])
        M = cv2.getPerspectiveTransform(src, dst)
        arr = cv2.warpPerspective(arr, M, (w, h), borderValue=(120, 110, 100))
    yy, xx = np.mgrid[0:h, 0:w]
    light = (0.75 + 0.25 * xx / w) * (0.8 + 0.2 * (1 - yy / h))
    arr = np.clip(arr * light[..., None], 0, 255).astype(np.uint8)
    arr = cv2.GaussianBlur(arr, (3, 3), 0)
    noise = np.random.default_rng(seed).normal(0, 3, arr.shape)
    arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
    Image.fromarray(arr).save(path, quality=88)
    return path


def draw_circle_card(cfg: dict, out_dir: Path, *, product: str = "hair_clip", diameter_card_mm: float = 60.0,
                     fill=YELLOW, number: int = 2) -> Path:
    """A black ring of known outer diameter with a fill. Used to check the scale."""
    img, lay, ppm, P = card_image(cfg, product, number, out_dir)
    bx, by, bw, bh = lay.box
    cx, cy = bx + bw / 2, by + bh / 2
    r = diameter_card_mm / 2
    d = ImageDraw.Draw(img)
    d.ellipse([P(cx - r, cy + r), P(cx + r, cy - r)], fill=fill, outline=BLACK, width=int(4.5 * ppm))
    return photograph(img, out_dir / f"circle-{product}.jpg")


def draw_cat_card(cfg: dict, out_dir: Path, number: int = 3) -> Path:
    img, lay, ppm, P = card_image(cfg, "hair_clip", number, out_dir)
    bx, by, bw, bh = lay.box
    cx, cy = bx + bw / 2, by + bh / 2
    d = ImageDraw.Draw(img)
    r = 30
    d.ellipse([P(cx - r, cy + r), P(cx + r, cy - r)], fill=YELLOW, outline=BLACK, width=int(4.5 * ppm))
    for s in (-1, 1):
        d.polygon([P(cx + s * 12, cy + 26), P(cx + s * 30, cy + 48), P(cx + s * 30, cy + 20)], fill=YELLOW, outline=BLACK)
        d.line([P(cx + s * 12, cy + 26), P(cx + s * 30, cy + 48)], fill=BLACK, width=int(4.5 * ppm))
        d.line([P(cx + s * 30, cy + 48), P(cx + s * 30, cy + 20)], fill=BLACK, width=int(4.5 * ppm))
        d.ellipse([P(cx + s * 12 - 4, cy + 10), P(cx + s * 12 + 4, cy + 2)], fill=BLACK)
        d.line([P(cx + s * 20, cy - 5), P(cx + s * 52, cy + 2)], fill=BLACK, width=int(2.5 * ppm))     # 0.83 mm real
        d.line([P(cx + s * 20, cy - 10), P(cx + s * 52, cy - 18)], fill=BLACK, width=int(2.5 * ppm))
    d.line([P(cx - 8, cy - 14), P(cx + 8, cy - 14)], fill=BLACK, width=int(4 * ppm))
    d.ellipse([P(cx + 25, cy - 30), P(cx + 26.5, cy - 31.5)], fill=BLACK)      # speck, 0.2 mm² real
    d.ellipse([P(cx - 35, cy - 30), P(cx - 29, cy - 36)], fill=BLACK)          # separate 2 mm dot
    return photograph(img, out_dir / "cat.jpg")


def draw_small_star_card(cfg: dict, out_dir: Path, number: int = 4) -> Path:
    """A small yellow star that leaves the printed guide circle and its label visible."""
    img, lay, ppm, P = card_image(cfg, "hair_clip", number, out_dir)
    cx, cy, _ = lay.zones["cover_circle"]
    pts = []
    for i in range(10):
        a = np.pi / 2 + i * np.pi / 5
        rr = 14 if i % 2 == 0 else 6
        pts.append(P(cx + rr * np.cos(a) + 22, cy + rr * np.sin(a) + 20))
    d = ImageDraw.Draw(img)
    d.polygon(pts, fill=YELLOW)
    d.line(pts + pts[:1], fill=YELLOW, width=int(4 * ppm))
    return photograph(img, out_dir / "star.jpg")


def draw_heart_keychain(cfg: dict, out_dir: Path, number: int = 3) -> Path:
    img, lay, ppm, P = card_image(cfg, "keychain", number, out_dir)
    bx, by, bw, bh = lay.box
    cx, cy = bx + bw / 2, by + bh / 2
    pts = []
    for t in np.linspace(0, 2 * np.pi, 200):
        x = 16 * np.sin(t) ** 3
        y = 13 * np.cos(t) - 5 * np.cos(2 * t) - 2 * np.cos(3 * t) - np.cos(4 * t)
        pts.append(P(cx + x * 4.2, cy + y * 4.2 + 8))
    d = ImageDraw.Draw(img)
    d.polygon(pts, fill=PINK)
    d.line(pts + pts[:1], fill=BLACK, width=int(4.5 * ppm))
    return photograph(img, out_dir / "heart.jpg")
