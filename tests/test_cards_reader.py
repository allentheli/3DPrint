import numpy as np
import pytest

from charm_maker.cards import card_layout, decode_marker_id, marker_id
from charm_maker.reader import detect_cards, load_image, read_card
from tests.synthetic import card_image, draw_circle_card, photograph


def test_marker_ids_round_trip():
    seen = set()
    for corner in range(4):
        for type_id in range(8):
            for n in range(1, 31):
                mid = marker_id(corner, type_id, n)
                assert mid < 1000 and mid not in seen
                seen.add(mid)
                assert decode_marker_id(mid) == (corner, type_id, n)
    assert decode_marker_id(999) is None


def test_card_layout_is_three_times_real_size(cfg):
    for product in ("hair_clip", "keychain"):
        lay = card_layout(cfg, product, 1)
        size_max = cfg["products"][product]["size_max"]
        assert lay.scale == 3
        assert lay.box[2] <= size_max * 3 + 1e-6
        assert lay.box[2] >= size_max * 3 * 0.95
        for corner in ("TL", "TR", "BR", "BL"):
            x, y, s = lay.markers[corner]
            assert 0 <= x and x + s <= lay.page[0] and 0 <= y and y + s <= lay.page[1]


def test_markers_are_found_on_a_warped_photo(cfg, tmp_path):
    photo = draw_circle_card(cfg, tmp_path)
    img = load_image(photo)
    found = detect_cards(cfg, img)
    assert list(found) == [(cfg["cards"]["type_ids"]["hair_clip"], 2)]
    assert len(found[(0, 2)]) == 4
    reads = read_card(cfg, img)
    assert len(reads) == 1
    assert reads[0].layout.product == "hair_clip" and reads[0].layout.number == 2
    assert reads[0].name_image is not None and reads[0].name_image.size > 0


def test_straightened_page_has_the_right_scale(cfg, tmp_path):
    """After rectification the printed 50 mm check ruler must measure 50 mm."""
    photo = draw_circle_card(cfg, tmp_path)
    read = read_card(cfg, load_image(photo))[0]
    page = read.page
    ppm = read.px_per_card_mm
    lay = read.layout
    c = cfg["cards"]
    m, ms = c["margin"], c["marker_size"]
    rx, ry = m + ms + 10, m + 8                      # where the ruler is drawn
    y = int((lay.page[1] - ry) * ppm)
    x0, x1 = int((m + ms + 2) * ppm), int((lay.page[0] - m - ms - 2) * ppm)     # between the bottom markers
    rows = page[y - 1:y + 2, x0:x1, :].mean(axis=2).min(axis=0)
    dark = np.flatnonzero(rows < 128)
    assert dark.size
    measured = (dark.max() - dark.min()) / ppm
    assert measured == pytest.approx(50.0, abs=1.0)


def test_unwarped_scan_also_reads(cfg, tmp_path):
    img, lay, ppm, P = card_image(cfg, "keychain", 1, tmp_path)
    photo = photograph(img, tmp_path / "flat.jpg", warp=False)
    reads = read_card(cfg, load_image(photo))
    assert reads[0].layout.product == "keychain"


def test_no_markers_needs_a_product(cfg):
    blank = np.full((400, 400, 3), 255, np.uint8)
    with pytest.raises(ValueError):
        read_card(cfg, blank)
    reads = read_card(cfg, blank, product_hint="keychain")
    assert reads[0].layout is None
