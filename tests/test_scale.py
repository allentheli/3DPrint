"""A piece made bigger or smaller than drawn (--scale fig-01=1.5): Allen's butterfly had a
4 mm face whose U-shaped smile filled in at the 1 mm line width; 1.5 times bigger it kept
its shape. The size is applied before the print fixes, so lines and gaps grow too."""

import pytest

from charm_maker.pipeline import run_batch
from tests.synthetic import BLACK, PINK, draw_blob_card


def test_one_card_made_bigger(cfg, tmp_path):
    photos = tmp_path / "photos"
    photos.mkdir()
    for n in (3, 4):
        draw_blob_card(cfg, photos, "magnet_figure", n, BLACK, PINK)
    res = run_batch(cfg, sorted(photos.glob("*.jpg")), tmp_path / "out", sizes={"fig-04": 1.5})
    got = {p.name: p for p in res.pieces}
    border = 2 * cfg["process"]["border"]
    plain, big = got["fig-03"].size()[0] - border, got["fig-04"].size()[0] - border
    assert big == pytest.approx(1.5 * plain, rel=0.05), "the drawing is 1.5 times as wide"
    assert "made 1.5 times the drawn size (asked for)" in got["fig-04"].design.fixes
    assert not any("times the drawn size" in f for f in got["fig-03"].design.fixes)


def test_a_silly_size_is_refused(cfg, tmp_path):
    with pytest.raises(ValueError, match="between 0.25 and 4"):
        run_batch(cfg, [], tmp_path / "out", sizes={"fig-01": 10})


def test_a_pen_line_stays_one_color_when_made_much_bigger(cfg, tmp_path):
    """Alison's dog keychain (2026-11-15): a small pen drawing made 3.9 times bigger split into a
    black middle and a gray edge, because its colors were read at the bigger size. Colors are
    read as drawn; only the fixes see it bigger."""
    from PIL import ImageDraw

    from tests.synthetic import card_image, photograph

    img, lay, ppm, P = card_image(cfg, "keychain", 7, tmp_path)
    bx, by, bw, bh = lay.box
    cx, cy, r = bx + bw * 0.3, by + bh * 0.7, 18.0          # a small face in one corner, card mm
    d = ImageDraw.Draw(img)
    d.ellipse([P(cx - r, cy + r), P(cx + r, cy - r)], outline=BLACK, width=max(2, int(1.6 * ppm)))
    for ex in (-6.0, 6.0):
        d.ellipse([P(cx + ex - 2, cy + 6), P(cx + ex + 2, cy + 2)], outline=BLACK, width=max(2, int(1.2 * ppm)))
    d.line([P(cx - 6, cy - 7), P(cx + 6, cy - 7)], fill=BLACK, width=max(2, int(1.4 * ppm)))
    photo = photograph(img, tmp_path / "key-07.jpg", seed=7)
    res = run_batch(cfg, [photo], tmp_path / "out", sizes={"key-07": 3.9})
    piece = res.pieces[0]
    inks = [n for n in piece.parts if not n.endswith(" base")]
    assert len(inks) == 1, f"one pen color, not a dark middle and a gray edge: {inks}"
