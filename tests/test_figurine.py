"""Figurines: a drawing inflated into a rounded 3D figure. Flat back by default (the
card's product still works, no supports); round backs (blank or mirror) make a standalone
figure that prints on supports."""

import pytest
from shapely.geometry import Point, box

from charm_maker.geom import count_bodies, to_trimesh
from charm_maker.pipeline import run_batch
from charm_maker.products import build_piece
from charm_maker.shape import Design, InkRegion, _as_multi
from tests.synthetic import BLACK, PINK, YELLOW, draw_blob_card


def _design(product="keychain"):
    """A body with two legs, eyes near the top and orange feet."""
    body = Point(0, 10).buffer(10).union(box(-8, -10, -3, 2)).union(box(3, -10, 8, 2))
    feet = _as_multi(box(-8, -10, 8, -6).intersection(body))
    eyes = _as_multi(Point(-3, 12).buffer(1.5).union(Point(3, 12).buffer(1.5)))
    return Design("t", product, body, [InkRegion("black", (20, 20, 20), eyes), InkRegion("orange", (240, 120, 30), feet)])


def _union(piece):
    u = None
    for s in piece.parts.values():
        u = s if u is None else u + s
    return u


@pytest.mark.parametrize("back", ["blank", "mirror"])
@pytest.mark.parametrize("base", ["flat", "disc", "none"])
def test_figurine_is_one_sound_solid(cfg, back, base):
    p = build_piece(cfg, _design(), style="figurine", figurine_back=back, figurine_base=base)
    assert p.style == "figurine" and p.face_up and p.supports
    for s in p.parts.values():
        assert to_trimesh(s).is_watertight
    u = _union(p)
    assert count_bodies(u) == 1
    assert sum(s.volume() for s in p.parts.values()) == pytest.approx(u.volume(), abs=0.05), "parts must not overlap"
    assert u.bounding_box()[2] == pytest.approx(0.0, abs=1e-6), "lies on the bed"


def test_size_and_roundness(cfg):
    p = build_piece(cfg, _design(), style="figurine", figurine_back="blank", figurine_base="none")
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
    flat = build_piece(cfg, _design(), style="figurine", figurine_back="blank", figurine_base="flat")
    disc = build_piece(cfg, _design(), style="figurine", figurine_back="blank", figurine_base="disc")
    none = build_piece(cfg, _design(), style="figurine", figurine_back="blank", figurine_base="none")
    # Lying on its back, "down" for the standing figure is -y.
    lo_flat, lo_none = _union(flat).bounding_box()[1], _union(none).bounding_box()[1]
    assert lo_flat > lo_none + 1.0, "the bottom is cut flat"
    db = _union(disc).bounding_box()
    nb = _union(none).bounding_box()
    assert db[5] - db[2] > (nb[5] - nb[2]) * 0.9, "disc base is about as deep as the figure"
    assert disc.parts["t orange"].volume() == pytest.approx(flat.parts["t orange"].volume(), rel=0.02), "the disc stays plain"


def test_round_figurines_get_their_own_plate_and_notes(cfg, tmp_path):
    a = draw_blob_card(cfg, tmp_path, "hair_clip", 3, BLACK, YELLOW)
    b = draw_blob_card(cfg, tmp_path, "keychain", 4, BLACK, PINK)
    r = run_batch(cfg, [a, b], tmp_path / "out", styles={"key-04": "figurine"}, figurine_back={"key-04": "blank"})
    assert r.problems == []
    styles = {pp.piece.name: (pl.number, pp.piece.style) for pl in r.plates for pp in pl.pieces}
    assert styles["key-04"][1] == "figurine" and styles["clip-03"][1] == "flat"
    assert styles["key-04"][0] != styles["clip-03"][0], "figurines go on their own plate"
    notes = r.files["notes"].read_text()
    assert "Enable support" in notes and "tree(auto)" in notes
    assert "peel the tree supports" in notes
    assert "split ring" not in notes, "a figurine from a keychain card has no ring tab"


# --- Flat back (the default) -------------------------------------------------------


@pytest.mark.parametrize("product", ["hair_clip", "keychain", "pendant", "earrings", "magnet_figure"])
def test_flat_back_is_the_default_and_keeps_the_product(cfg, product):
    d = _design(product)
    w0, h0 = d.outline.bounds[2] - d.outline.bounds[0], d.outline.bounds[3] - d.outline.bounds[1]
    p = build_piece(cfg, d, style="figurine")
    assert p.style == "figurine" and p.face_up and not p.supports, "no supports: it lies on its flat back"
    for s in p.parts.values():
        assert to_trimesh(s).is_watertight
    u = _union(p)
    assert count_bodies(u) == 1
    assert sum(s.volume() for s in p.parts.values()) == pytest.approx(u.volume(), abs=0.05), "parts must not overlap"
    bb = u.bounding_box()
    assert bb[2] == pytest.approx(0.0, abs=1e-6)
    # The card's size is kept (not scaled to a 60 mm figure); a loop or tab may add a little.
    body = p.design.outline.bounds
    assert body[2] - body[0] == pytest.approx(w0, abs=12) and body[3] - body[1] < h0 + 15
    # Rounded front: taller than the same drawing puffy, but never above the product's cap.
    base = cfg["relief"]["products"][product]["base"]
    cap = cfg["figurine"]["flat_back_max_dome"][product]
    puffy = build_piece(cfg, _design(product), style="puffy")
    assert p.thickness > puffy.thickness
    assert p.thickness <= base + cap + 0.05
    # The colors are on the front only; the back is plain.
    face = cfg["process"]["color_face_depth"]
    for name, s in p.parts.items():
        if name != p.base_part:
            assert s.bounding_box()[2] >= base - face - 0.05, name


def test_flat_back_lies_flat_on_the_bed(cfg):
    p = build_piece(cfg, _design("magnet_figure"), style="figurine")
    footprint = _union(p).slice(0.05).area()
    assert footprint == pytest.approx(p.design.outline.area, rel=0.02), "the whole back touches the bed: glue the magnet anywhere"


def test_flat_back_keeps_the_clip_pocket_and_the_ring_hole(cfg):
    clip = build_piece(cfg, _design("hair_clip"), style="figurine")
    dia = clip.attachment["diameter"]
    back = _union(clip).slice(0.05).area()
    assert clip.design.outline.area - back == pytest.approx(3.14159 * (dia / 2) ** 2, rel=0.1), "clip pocket on the back"
    key = build_piece(cfg, _design("keychain"), style="figurine")
    hx, hy = key.attachment["hole"].centroid.coords[0]
    import manifold3d as m3d
    probe = m3d.Manifold.cylinder(40.0, 0.5, 0.5, 16).translate([hx, hy, -5.0])
    assert (_union(key) ^ probe).volume() == pytest.approx(0.0, abs=1e-6), "the split-ring hole goes right through"


def test_flat_back_figurines_share_plates_and_need_no_supports(cfg, tmp_path):
    a = draw_blob_card(cfg, tmp_path, "hair_clip", 3, BLACK, YELLOW)
    b = draw_blob_card(cfg, tmp_path, "keychain", 4, BLACK, PINK)
    r = run_batch(cfg, [a, b], tmp_path / "out", styles={"key-04": "figurine"})
    assert r.problems == []
    where = {pp.piece.name: pl.number for pl in r.plates for pp in pl.pieces}
    assert where["key-04"] == where["clip-03"], "same plate as the flat charms"
    notes = r.files["notes"].read_text()
    assert "Enable support" not in notes
    assert "split ring" in notes, "a flat-back keychain figurine is still a keychain"
    assert "Figurine fronts (key-04)" in notes


def test_a_base_option_on_a_flat_back_is_flagged(cfg):
    p = build_piece(cfg, _design("magnet_figure"), style="figurine", figurine_base="disc")
    assert not p.supports
    assert any("only for round-back" in w for w in p.design.warnings)

