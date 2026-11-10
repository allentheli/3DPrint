"""Figurines: a drawing inflated into a rounded 3D figure."""

import pytest
from shapely.geometry import Point, box

from charm_maker.geom import count_bodies, to_trimesh
from charm_maker.pipeline import run_batch
from charm_maker.products import build_piece
from charm_maker.shape import Design, InkRegion, _as_multi
from tests.synthetic import BLACK, PINK, YELLOW, draw_blob_card


def _design():
    """A body with two legs, eyes near the top and orange feet."""
    body = Point(0, 10).buffer(10).union(box(-8, -10, -3, 2)).union(box(3, -10, 8, 2))
    feet = _as_multi(box(-8, -10, 8, -6).intersection(body))
    eyes = _as_multi(Point(-3, 12).buffer(1.5).union(Point(3, 12).buffer(1.5)))
    return Design("t", "keychain", body, [InkRegion("black", (20, 20, 20), eyes), InkRegion("orange", (240, 120, 30), feet)])


def _union(piece):
    u = None
    for s in piece.parts.values():
        u = s if u is None else u + s
    return u


@pytest.mark.parametrize("back", ["blank", "mirror"])
@pytest.mark.parametrize("base", ["flat", "disc", "none"])
def test_figurine_is_one_sound_solid(cfg, back, base):
    p = build_piece(cfg, _design(), style="figurine", figurine_back=back, figurine_base=base)
    assert p.style == "figurine" and p.face_up
    for s in p.parts.values():
        assert to_trimesh(s).is_watertight
    u = _union(p)
    assert count_bodies(u) == 1
    assert sum(s.volume() for s in p.parts.values()) == pytest.approx(u.volume(), abs=0.05), "parts must not overlap"
    assert u.bounding_box()[2] == pytest.approx(0.0, abs=1e-6), "lies on the bed"


def test_size_and_roundness(cfg):
    p = build_piece(cfg, _design(), style="figurine", figurine_base="none")
    bb = _union(p).bounding_box()
    size = cfg["figurine"]["size"]
    assert max(bb[3] - bb[0], bb[4] - bb[1]) == pytest.approx(size, abs=0.5)
    # Inflated: the body (about 2/3 of the 60 mm height wide) is many mm thick, not a flat charm.
    assert bb[5] - bb[2] > 15.0


def test_back_blank_or_mirror(cfg):
    blank = build_piece(cfg, _design(), style="figurine", figurine_back="blank", figurine_base="none")
    mirror = build_piece(cfg, _design(), style="figurine", figurine_back="mirror", figurine_base="none")
    mid = _union(blank).bounding_box()[5] / 2
    eyes_b = blank.parts["t black"].bounding_box()
    eyes_m = mirror.parts["t black"].bounding_box()
    assert eyes_b[2] > mid, "blank back: the eyes are only on the front (top, as it lies)"
    assert eyes_m[2] < mid < eyes_m[5], "mirror: the eyes are on the back too"
    assert mirror.parts["t black"].volume() == pytest.approx(2 * blank.parts["t black"].volume(), rel=0.1)


def test_flat_bottom_and_disc(cfg):
    flat = build_piece(cfg, _design(), style="figurine", figurine_base="flat")
    disc = build_piece(cfg, _design(), style="figurine", figurine_base="disc")
    none = build_piece(cfg, _design(), style="figurine", figurine_base="none")
    # Lying on its back, "down" for the standing figure is -y.
    lo_flat, lo_none = _union(flat).bounding_box()[1], _union(none).bounding_box()[1]
    assert lo_flat > lo_none + 1.0, "the bottom is cut flat"
    db = _union(disc).bounding_box()
    nb = _union(none).bounding_box()
    assert db[5] - db[2] > (nb[5] - nb[2]) * 0.9, "disc base is about as deep as the figure"
    assert disc.parts["t orange"].volume() == pytest.approx(flat.parts["t orange"].volume(), rel=0.02), "the disc stays plain"


def test_figurines_get_their_own_plate_and_notes(cfg, tmp_path):
    a = draw_blob_card(cfg, tmp_path, "hair_clip", 3, BLACK, YELLOW)
    b = draw_blob_card(cfg, tmp_path, "keychain", 4, BLACK, PINK)
    r = run_batch(cfg, [a, b], tmp_path / "out", styles={"key-04": "figurine"})
    assert r.problems == []
    styles = {pp.piece.name: (pl.number, pp.piece.style) for pl in r.plates for pp in pl.pieces}
    assert styles["key-04"][1] == "figurine" and styles["clip-03"][1] == "flat"
    assert styles["key-04"][0] != styles["clip-03"][0], "figurines go on their own plate"
    notes = r.files["notes"].read_text()
    assert "Enable support" in notes and "tree(auto)" in notes
    assert "peel the tree supports" in notes
    assert "split ring" not in notes, "a figurine from a keychain card has no ring tab"

