"""Flexis (Allen, 2026-11-13): a kid's drawing as a flat toy cut into strips that wiggle,
linked by T-shaped tabs, printed already linked. The cuts keep the face whole."""

import manifold3d as m3d
import numpy as np
import pytest
from PIL import ImageDraw

from charm_maker.cards import card_layout
from charm_maker.pipeline import run_batch
from tests.synthetic import BLACK, PINK, YELLOW, card_image, draw_blob_card, photograph


def _ghost_card(cfg, out_dir, number=1, eyes_y=25.0):
    """A tall ghost-like shape with two round eyes and a smile, on a flexi card."""
    img, lay, ppm, P = card_image(cfg, "flexi", number, out_dir)
    bx, by, bw, bh = lay.box
    cx, cy = bx + bw / 2, by + bh / 2
    d = ImageDraw.Draw(img)
    w, h = 50, 70
    d.rounded_rectangle([P(cx - w, cy + h), P(cx + w, cy - h)], radius=int(45 * ppm), fill=YELLOW,
                        outline=BLACK, width=int(4.5 * ppm))
    for s in (-1, 1):
        d.ellipse([P(cx + s * 18 - 6, cy + eyes_y + 6), P(cx + s * 18 + 6, cy + eyes_y - 6)], fill=BLACK)
    d.arc([P(cx - 20, cy + 10), P(cx + 20, cy - 12)], 20, 160, fill=BLACK, width=int(4 * ppm))
    return photograph(img, out_dir / f"flexi-{number}.jpg", seed=number)


def _strips(piece):
    whole = m3d.Manifold.batch_boolean(list(piece.parts.values()), m3d.OpType.Add)
    return sorted([b for b in whole.decompose() if b.volume() > 1.0], key=lambda b: -b.bounding_box()[4])


@pytest.fixture(scope="module")
def ghost(cfg, tmp_path_factory):
    tmp = tmp_path_factory.mktemp("flexi")
    photos = tmp / "photos"
    photos.mkdir()
    _ghost_card(cfg, photos)
    res = run_batch(cfg, sorted(photos.glob("*.jpg")), tmp / "out")
    assert not res.problems, res.problems
    return res.pieces[0], res


def test_a_flexi_card_becomes_linked_strips(cfg, ghost):
    piece, res = ghost
    assert piece.design.product == "flexi"
    w, h = piece.size()
    # Drawn 100 x 140 card mm: a third of that, made 1.5 times bigger, plus the border.
    assert h == pytest.approx(140 / 3 * 1.5 + 2 * cfg["process"]["border"], abs=2.0)
    n = piece.attachment["strips"]
    assert 4 <= n <= 7
    assert len(_strips(piece)) == n
    assert any(f.startswith(f"cut into {n} strips") for f in piece.design.fixes)
    assert res.files["plates"], "it goes on a plate like the other flat pieces"


def test_the_strips_slide_but_hold_together(cfg, ghost):
    piece, _ = ghost
    st = cfg["products"]["flexi"]["strips"]
    gap = cfg["fit"]["flexi_strip_gap"]["value"]
    strips = _strips(piece)
    for up, low in zip(strips, strips[1:]):
        def hit(dx, dy):
            return (up.translate([dx, dy, 0]) ^ low).volume() > 1e-3
        assert not hit(0, 0), "printed apart"
        assert not hit(st["slide"] + gap - 0.1, 0) and not hit(-(st["slide"] + gap - 0.1), 0)
        pull = next(d for d in np.arange(0, 3.0, 0.05) if hit(0, d))
        assert pull <= gap + 0.15, "a T-joint holds the strips together"


def test_the_cuts_keep_the_eyes_whole(cfg, ghost):
    piece, _ = ghost
    assert any("clear of the eyes" in f for f in piece.design.fixes)
    cut = piece.attachment["cut"]
    for x, y in piece.design.dots:
        assert cut.distance(__import__("shapely").geometry.Point(x, y)) > 2.0


def test_any_card_can_be_made_a_flexi(cfg, tmp_path):
    photos = tmp_path / "photos"
    photos.mkdir()
    draw_blob_card(cfg, photos, "keychain", 3, BLACK, PINK)
    res = run_batch(cfg, sorted(photos.glob("*.jpg")), tmp_path / "out", products={"key-03": "flexi"})
    piece = res.pieces[0]
    assert piece.design.product == "flexi"
    assert any("made into a flexi" in f for f in piece.design.fixes)
    assert len(_strips(piece)) == piece.attachment["strips"] >= 3


def test_an_unknown_product_is_refused(cfg, tmp_path):
    with pytest.raises(ValueError, match="no such product"):
        run_batch(cfg, [], tmp_path / "out", products={"key-03": "spaceship"})


def test_the_flexi_card_has_no_shape_boxes(cfg):
    lay = card_layout(cfg, "flexi", 1)
    assert "shape_boxes" not in lay.zones and "tidy_box" in lay.zones
