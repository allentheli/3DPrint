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
