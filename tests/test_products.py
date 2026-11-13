"""Every product from a drawing: the pendant's sideways loop, earrings with a small
jump-ring tab, earring pairs, magnet figures with a flat back, and colors kept as
separate parts."""

import pymupdf
import pytest
from shapely.geometry import Polygon

from charm_maker.cli import main
from charm_maker.config import load_config
from charm_maker.geom import count_bodies, to_trimesh
from charm_maker.pipeline import run_batch
from tests.synthetic import BLACK, BLUE, ORANGE, PINK, YELLOW, draw_blob_card
from tests.test_geometry import loop_hole_check


@pytest.fixture(scope="module")
def batch(cfg, tmp_path_factory):
    d = tmp_path_factory.mktemp("products")
    draw_blob_card(cfg, d, "pendant", 1, BLACK, PINK)
    draw_blob_card(cfg, d, "earrings", 1, BLACK, BLUE)
    draw_blob_card(cfg, d, "magnet_figure", 1, BLACK, YELLOW, extra=(ORANGE, 0, 0, 20))
    draw_blob_card(cfg, d, "hair_clip", 8, BLACK, YELLOW, extra=(ORANGE, 0, 0, 8))
    return run_batch(cfg, [d], d / "out")


def _piece(batch, name):
    return next(p for p in batch.pieces if p.name == name)


def _sound(piece):
    union = None
    for s in piece.parts.values():
        assert to_trimesh(s).is_watertight
        union = s if union is None else union + s
    assert count_bodies(union) == 1
    return union


def test_every_product_builds(batch):
    assert batch.problems == [] and batch.question is None
    assert sorted(p.name for p in batch.pieces) == ["clip-08", "ear-01-1", "ear-01-2", "fig-01", "pend-01"]
    for p in batch.pieces:
        _sound(p)
    assert batch.plates


@pytest.mark.parametrize("name", ["ear-01-1", "ear-01-2"])
def test_earrings_hang_from_a_jump_ring(cfg, batch, name):
    """Allen: a 4 mm jump ring goes through the earring, then the hook on the ring. The
    old sideways loop was a 4.5 mm tunnel a 4 mm ring could not get through and around.
    Now a small tab right above the balance point has a hole front to back, with so
    little plastic around it that the ring closes around it."""
    from shapely.geometry import Point
    from shapely.ops import unary_union

    p = _piece(batch, name)
    att, hw = p.attachment, cfg["hardware"]
    assert att["kind"] == "ring_tab" and att["ring"] == "jump ring"
    assert att["hole_diameter"] == cfg["fit"]["earring_hole_diameter"]["value"]
    # Through, front to back: no plastic at the hole's center on any layer.
    hx, hy = p.solid_xy(*att["hole_center"])
    for z in (0.2, p.thickness / 2, p.thickness - 0.2):
        face = [Polygon(q) for q in p.parts[p.base_part].slice(z).to_polygons()]
        covering = sum(q.contains(Point(hx, hy)) for q in face)
        assert covering % 2 == 0, f"plastic in the hole at z={z}"
    # The ring closes around the plastic beside the hole: wall by thickness fits inside it.
    inside = hw["jump_ring_diameter"] - 2 * 0.75                     # a typical 4 mm ring's wire
    assert (att["wall"] ** 2 + p.thickness ** 2) ** 0.5 < inside - 0.2
    # The tab's outer edge is only the wall away from the hole (the ring goes around there).
    top = p.design.outline.bounds[3]
    assert top - att["hole_center"][1] == pytest.approx(att["hole_diameter"] / 2 + att["wall"], abs=0.15)
    # It hangs straight: the hole is above the balance point.
    inks = unary_union([i.geometry for i in p.design.inks])
    assert att["hole_center"][0] == pytest.approx(p.design.outline.centroid.x, abs=1.0)
    assert att["hole_center"][0] == pytest.approx(inks.centroid.x, abs=1.0)
    assert _sound(p).bounding_box()[5] == pytest.approx(p.thickness, abs=0.01), "flat: nothing on the back"


@pytest.mark.parametrize("name,kind", [("pend-01", "necklace")])
def test_loops_run_left_to_right(cfg, batch, name, kind):
    p = _piece(batch, name)
    att = p.attachment
    assert att["kind"] == "side_loop" and att["loop"] == kind
    loop = cfg["hardware"][f"{kind}_loop"]
    x_c, y_c = att["center"]
    sx, sy = p.solid_xy(x_c, y_c)
    loop_hole_check(p.parts[p.base_part], sx, sy, att["hole_diameter"], loop["wall"], loop["length"])
    union = _sound(p)
    bb = union.bounding_box()
    assert bb[2] == pytest.approx(0.0, abs=1e-6), "front face flat on the bed"
    assert bb[5] == pytest.approx(att["height"], abs=0.01), "loop stands taller than the charm on the back"
    assert att["height"] > p.thickness
    # It hangs straight: the loop is above the balance point of the drawing.
    from shapely import affinity
    from shapely.ops import unary_union
    inks = unary_union([i.geometry for i in p.design.inks])
    assert x_c == pytest.approx(inks.centroid.x, abs=0.6)
    # The loop never covers the colors on the front face (in solid coordinates).
    if p.mirrored:
        inks = affinity.scale(inks, -1, 1, origin=(0, 0))
    from functools import reduce
    contours = [Polygon(q) for q in p.parts[p.base_part].slice(0.3).to_polygons()]
    face = reduce(lambda a, b: a.symmetric_difference(b), contours)   # even-odd: holes stay holes
    assert face.intersection(inks).area < 0.5


def test_earrings_are_a_matching_pair(cfg, batch):
    a, b = _piece(batch, "ear-01-1"), _piece(batch, "ear-01-2")
    assert a.size() == pytest.approx(b.size(), abs=1e-6)
    assert a.thickness == b.thickness == cfg["products"]["earrings"]["thickness"]
    assert any("pair" in f for f in a.design.fixes)


def test_mirrored_pair_and_stud_style(cfg, tmp_path):
    import copy

    c = copy.deepcopy(cfg)
    c["products"]["earrings"]["pair_mode"] = "mirrored"
    c["products"]["earrings"]["style"] = "stud"
    photo = draw_blob_card(c, tmp_path, "earrings", 2, BLACK, PINK, extra=(BLUE, 8, 0, 6))
    r = run_batch(c, [photo], tmp_path / "out")
    a, b = sorted(r.pieces, key=lambda p: p.name)
    assert a.attachment == {} and b.attachment == {}, "stud: no loop"
    assert a.parts[a.base_part].bounding_box()[5] == pytest.approx(c["products"]["earrings"]["thickness"])
    blue_a = next(i for i in a.design.inks if i.name == "blue").geometry.centroid.x
    blue_b = next(i for i in b.design.inks if i.name == "blue").geometry.centroid.x
    assert blue_a == pytest.approx(-blue_b, abs=0.3), "second earring is the mirror image"


def test_magnet_figure_has_a_flat_back(cfg, batch):
    p = _piece(batch, "fig-01")
    assert p.attachment == {"kind": "flat_back"}
    base = p.parts[p.base_part]
    t = cfg["products"]["magnet_figure"]["thickness"]
    assert base.bounding_box()[5] == pytest.approx(t)
    polys = [Polygon(q) for q in base.slice(t - 0.05).to_polygons()]
    assert len(polys) == 1, "nothing cut into the back"


def test_orange_and_yellow_stay_separate_parts(batch):
    for name in ("fig-01", "clip-08"):
        names = {n.split(" ", 1)[1] for n in _piece(batch, name).parts}
        assert {"yellow", "orange", "black", "base"} <= names, names


def test_cards_for_every_product(tmp_path):
    assert main(["cards", "--out", str(tmp_path), "--count", "1"]) == 0
    doc = pymupdf.open(str(tmp_path / "design-cards.pdf"))
    titles = [doc[i].get_text().split("\n")[0] for i in range(doc.page_count)]
    assert titles == ["Hair clip charm", "Keychain", "Necklace pendant", "Earrings (a pair)", "Magnet figure",
                      "Clicker keychain", "Flexi"]
    assert "wiggly flexi" in doc[6].get_text(), "the flexi card shows what the drawing becomes"
    for i in range(doc.page_count):
        assert "Use the colors in the printer" in doc[i].get_text()
    one = ["Draw just ONE earring" in doc[i].get_text() for i in range(doc.page_count)]
    assert one == [t.startswith("Earrings") for t in titles], "one drawing makes the pair: only the earring card says so"
    assert not (tmp_path / "half-drawn-cards.pdf").exists(), "pre-set shapes only when asked"
    assert main(["cards", "--out", str(tmp_path / "h"), "--count", "1", "--half-drawn"]) == 0
    half = pymupdf.open(str(tmp_path / "h" / "half-drawn-cards.pdf"))
    assert half.page_count == 60, "half-drawn cards for every product except earrings"
