"""Choices ticked on the card: a shape (flat, puffy, raised lines, puffy + lines, figurine)
and "neat lines". The card shows a real render of each shape; the reader finds the ticks."""

import pymupdf
from PIL import ImageDraw

from charm_maker.cards import card_layout, write_cards_pdf
from charm_maker.options import SHAPES, read_options
from charm_maker.pipeline import run_batch
from charm_maker.reader import load_image, read_card
from tests.synthetic import BLACK, BLUE, PINK, card_image, photograph


def _card(cfg, tmp_path, number, *, ticks=(), fill=(), tidy=False, old_card=False):
    """A pink blob with a black outline on a keychain card; `ticks` get an X, `fill` are
    colored in. `old_card` paints over the option row like a card printed before it existed."""
    img, lay, ppm, P = card_image(cfg, "keychain", number, tmp_path)
    d = ImageDraw.Draw(img)
    bx, by, bw, bh = lay.box
    cx, cy, r = bx + bw / 2, by + bh / 2, bw * 0.3
    d.ellipse([P(cx - r, cy + r), P(cx + r, cy - r)], fill=PINK, outline=BLACK, width=int(4.5 * ppm))
    boxes = {k: (x, y, s) for k, x, y, s in lay.zones["shape_boxes"]}
    if old_card:
        x0 = boxes["flat"][0] - 2
        d.rectangle([P(x0, boxes["flat"][1] + 14), P(205, boxes["flat"][1] - 8)], fill=(255, 255, 255))
        x, y, s = boxes["puffy"]
        d.rectangle([P(x + 2, y + s - 2), P(x + s - 2, y + 2)], fill=(90, 90, 95))   # an old picture here
        x, y, s = lay.zones["tidy_box"]
        d.rectangle([P(x - 1, y + s + 1), P(x + s + 1, y - 1)], fill=(255, 255, 255))
    w = max(2, int(0.7 * ppm))
    for k in ticks:
        x, y, s = boxes[k]
        d.line([P(x + 1.5, y + 1.5), P(x + s - 1.5, y + s - 1.5)], fill=BLUE, width=w)
        d.line([P(x + 1.5, y + s - 1.5), P(x + s - 1.5, y + 1.5)], fill=BLUE, width=w)
    for k in fill:
        x, y, s = boxes[k]
        d.rectangle([P(x + 1.2, y + s - 1.2), P(x + s - 1.2, y + 1.2)], fill=BLACK)
    if tidy:
        x, y, s = lay.zones["tidy_box"]
        d.line([P(x + 1.5, y + 3.5), P(x + 3.5, y + 1.5), P(x + s - 1.2, y + s - 1.2)], fill=BLACK, width=w)
    return photograph(img, tmp_path / f"key-{number:02d}.jpg", seed=number)


def _options(cfg, path):
    reads = read_card(cfg, load_image(path))
    assert len(reads) == 1
    return read_options(cfg, reads[0])


def test_cards_show_the_choices(cfg, tmp_path):
    lay = card_layout(cfg, "keychain", 1)
    assert [k for k, *_ in lay.zones["shape_boxes"]] == [k for k, _ in SHAPES]
    text = pymupdf.open(str(write_cards_pdf(cfg, ["keychain", "clicker"], tmp_path / "c.pdf", numbers=[1])))
    key, click = (p.get_text() for p in text)
    for word in ["Pick a shape", "Flat", "Puffy", "Raised lines", "Puffy + lines", "Figurine", "neat lines"]:
        assert word in key
    assert sum(im[5] == "DeviceRGB" for im in text[0].get_images()) == len(SHAPES), "a real picture of each shape"
    # Clicker keys stay flat (the switch sits under them): no shape boxes, but neat lines still.
    assert "shape_boxes" not in card_layout(cfg, "clicker", 1).zones
    assert "Clicker keys stay flat" in click and "neat lines" in click and "Puffy" not in click


def test_reading_ticks(cfg, tmp_path):
    assert _options(cfg, _card(cfg, tmp_path, 3)) == {"style": None, "tidy": False, "notes": [], "warnings": []}
    o = _options(cfg, _card(cfg, tmp_path, 4, ticks=["puffy-outlined"], tidy=True))
    assert o["style"] == "puffy-outlined" and o["tidy"] and not o["warnings"]
    # Two ticked: the stronger mark (the colored-in box) wins, with a warning.
    o = _options(cfg, _card(cfg, tmp_path, 5, ticks=["puffy"], fill=["figurine"]))
    assert o["style"] == "figurine" and "more than one shape" in o["warnings"][0]


def test_old_cards_without_boxes_are_not_read_as_ticks(cfg, tmp_path):
    assert _options(cfg, _card(cfg, tmp_path, 6, old_card=True)) == {}


def test_card_choice_and_command_line(cfg, tmp_path):
    """A style named for this card beats the tick; the tick beats a style for all cards."""
    photos = tmp_path / "photos"
    photos.mkdir()
    for number, kw in [(3, {"ticks": ["puffy"]}), (4, {}), (5, {"ticks": ["puffy"]}), (6, {"tidy": True})]:
        (photos / f"key-{number:02d}.jpg").write_bytes(_card(cfg, tmp_path, number, **kw).read_bytes())
    res = run_batch(cfg, sorted(photos.iterdir()), tmp_path / "out", styles={"*": "outlined", "key-05": "flat"})
    got = {p.name: p for p in res.pieces}
    assert got["key-03"].style == "puffy"
    assert "shape ticked on the card: Puffy" in got["key-03"].design.fixes
    assert got["key-04"].style == "outlined"
    assert got["key-05"].style == "flat"
    assert any(f.startswith("tidy:") for f in got["key-06"].design.fixes)
    assert "neat lines ticked on the card" in got["key-06"].design.fixes
    assert not any(f.startswith("tidy:") for f in got["key-04"].design.fixes)
