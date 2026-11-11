"""Shape styles: flat (face-down, built mirrored), puffy, outlined, puffy-outlined
(face-up). Every style must be one sound solid with the colors on the front."""

import pytest
from shapely import affinity
from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union

from charm_maker.geom import count_bodies, to_trimesh
from charm_maker.pipeline import run_batch
from charm_maker.products import build_piece
from charm_maker.shape import Design, InkRegion, _as_multi
from tests.synthetic import BLACK, PINK, YELLOW, draw_blob_card
from tests.test_geometry import loop_hole_check

STYLES = ["flat", "puffy", "outlined", "puffy-outlined"]


def _letter_f():
    """An asymmetric drawing: a black F inside a pink disc, with a white border."""
    f = _as_multi(box(-4, -8, -1, 10).union(box(-4, 7, 6, 10)).union(box(-4, 0, 4, 3)))
    disc = Point(1, 1).buffer(13)
    pink = _as_multi(disc.difference(f.buffer(0.01)))
    outline = Polygon(disc.buffer(1.5).exterior)
    return outline, [InkRegion("black", (20, 20, 20), f), InkRegion("pink", (236, 72, 153), pink)]


def _build(cfg, product, style):
    outline, inks = _letter_f()
    return build_piece(cfg, Design("t", product, outline, inks), style=style)


def _union(piece):
    u = None
    for s in piece.parts.values():
        u = s if u is None else u + s
    return u


@pytest.mark.parametrize("product", ["hair_clip", "keychain", "pendant", "earrings", "magnet_figure"])
@pytest.mark.parametrize("style", STYLES)
def test_every_style_is_one_sound_solid(cfg, product, style):
    p = _build(cfg, product, style)
    for name, s in p.parts.items():
        assert to_trimesh(s).is_watertight, name
    u = _union(p)
    assert count_bodies(u) == 1
    assert sum(s.volume() for s in p.parts.values()) == pytest.approx(u.volume(), abs=0.05), "parts must not overlap"
    assert u.bounding_box()[2] == pytest.approx(0.0, abs=1e-6), "flat on the bed"
    assert p.face_up == (style != "flat")
    assert p.mirrored == (style == "flat")


def test_flat_faces_read_correctly_when_turned_over(cfg):
    """Face-down: the bed side is the face. Turned over like a page it must read like the
    drawing, so the solid is the mirror image of the drawing."""
    p = _build(cfg, "magnet_figure", "flat")
    black = p.parts["t black"]
    lo = black.bounding_box()
    f_minx, _, f_maxx, _ = p.design.inks[0].geometry.bounds
    assert lo[0] == pytest.approx(-f_maxx, abs=0.05) and lo[3] == pytest.approx(-f_minx, abs=0.05)
    turned = black.rotate([0.0, 180.0, 0.0]).bounding_box()
    assert turned[0] == pytest.approx(f_minx, abs=0.05) and turned[3] == pytest.approx(f_maxx, abs=0.05)


def test_face_up_styles_are_not_mirrored(cfg):
    p = _build(cfg, "magnet_figure", "puffy")
    bb = p.parts["t black"].bounding_box()
    f_minx, _, f_maxx, _ = p.design.inks[0].geometry.bounds
    assert bb[0] == pytest.approx(f_minx, abs=0.05) and bb[3] == pytest.approx(f_maxx, abs=0.05)


def test_puffy_rises_toward_the_middle(cfg):
    r = cfg["relief"]["products"]["magnet_figure"]
    p = _build(cfg, "magnet_figure", "puffy")
    top = max(s.bounding_box()[5] for s in p.parts.values())
    assert top == pytest.approx(r["base"] + r["puff"], abs=0.1)
    # Near the edge it is only a little taller than the base slab: the rounded profile
    # at 0.3 mm in, not the full puff.
    from charm_maker.relief import profile
    edge = p.parts["t base"].trim_by_plane([1.0, 0.0, 0.0], p.design.outline.bounds[2] - 0.3)
    expected = r["base"] + r["puff"] * float(profile(0.3 / cfg["relief"]["edge_round"]))
    assert edge.bounding_box()[5] == pytest.approx(expected, abs=0.1)
    assert edge.bounding_box()[5] < top - 1.0


def test_colors_sit_on_top(cfg):
    """Face-up: no base plastic above the color layer anywhere inside the inks."""
    face = cfg["process"]["color_face_depth"]
    for style in ("puffy", "outlined", "puffy-outlined"):
        p = _build(cfg, "magnet_figure", style)
        inks = unary_union([i.geometry for i in p.design.inks]).buffer(-0.3)
        from charm_maker.geom import extrude
        above = p.parts["t base"] ^ extrude(inks, 30.0, 0.0)
        top_of_base_in_inks = above.bounding_box()[5] if not above.is_empty() else 0.0
        top_of_inks = min(s.bounding_box()[5] for n, s in p.parts.items() if n != "t base")
        assert top_of_base_in_inks <= top_of_inks - face + 0.15, style


def test_outline_is_raised(cfg):
    raise_mm = cfg["relief"]["outline_raise"]
    for style, other in (("outlined", "flat"), ("puffy-outlined", "puffy")):
        p = _build(cfg, "magnet_figure", style)
        black = p.parts["t black"].bounding_box()[5]
        pink = p.parts["t pink"].bounding_box()[5]
        assert black - pink == pytest.approx(raise_mm, abs=0.15), style
        assert any("outline raised" in f for f in p.design.fixes)


def test_no_dark_outline_means_nothing_raised(cfg):
    outline = Polygon(Point(0, 0).buffer(12).exterior)
    p = build_piece(cfg, Design("t", "magnet_figure", outline, [InkRegion("yellow", (245, 215, 40), _as_multi(Point(0, 0).buffer(9)))]),
                    style="outlined")
    assert any("no dark outline" in f for f in p.design.fixes)



def test_a_one_color_line_drawing_gets_its_lines_raised(cfg):
    """Test drive 4: the butterfly and rainbow are light gray pencil, too light to count as
    a dark outline, so the raised-outline style raised nothing. In a one-color line drawing
    the only ink is the outline, whatever its shade."""
    ring = _as_multi(Point(0, 0).buffer(10).difference(Point(0, 0).buffer(9)))
    outline = Polygon(Point(0, 0).buffer(11.5).exterior)
    p = build_piece(cfg, Design("t", "magnet_figure", outline, [InkRegion("gray", (150, 150, 155), ring)]), style="outlined")
    assert any("gray outline raised" in f for f in p.design.fixes), p.design.fixes
    top = p.parts["t gray"].bounding_box()[5]
    assert top == pytest.approx(cfg["products"]["magnet_figure"]["thickness"] + cfg["relief"]["outline_raise"], abs=0.15)

def test_puffy_clip_keeps_its_pocket_on_the_back(cfg):
    p = _build(cfg, "hair_clip", "puffy")
    cx, cy = p.solid_xy(*p.attachment["center"])
    polys = [Polygon(q) for q in p.parts["t base"].slice(0.3).to_polygons()]
    holes = [q for q in polys if q.area < 200 and q.distance(Point(cx, cy)) < 1.0]
    assert holes, "pocket opens on the bed side"
    hole = max(holes, key=lambda q: q.area)
    assert hole.bounds[2] - hole.bounds[0] == pytest.approx(p.attachment["diameter"], abs=0.1)


@pytest.mark.parametrize("product,kind", [("pendant", "necklace")])
def test_puffy_loops_still_run_left_to_right(cfg, product, kind):
    p = _build(cfg, product, "puffy-outlined")
    att = p.attachment
    loop = cfg["hardware"][f"{kind}_loop"]
    sx, sy = p.solid_xy(*att["center"])
    loop_hole_check(p.parts["t base"], sx, sy, att["hole_diameter"], loop["wall"], loop["length"])


def test_styles_per_card_in_a_run(cfg, tmp_path):
    a = draw_blob_card(cfg, tmp_path, "hair_clip", 2, BLACK, YELLOW)
    b = draw_blob_card(cfg, tmp_path, "keychain", 3, BLACK, PINK)
    r = run_batch(cfg, [a, b], tmp_path / "out", styles={"*": "puffy", "key-03": "outlined"})
    assert r.problems == [] and r.plates
    by = {p.name: p for p in r.pieces}
    assert by["clip-02"].style == "puffy" and by["key-03"].style == "outlined"
    notes = r.files["notes"].read_text()
    assert "face-up" in notes
    with pytest.raises(ValueError):
        run_batch(cfg, [a], tmp_path / "bad", styles={"*": "wobbly"})


@pytest.mark.parametrize("style", ["puffy", "outlined", "figurine"])
def test_shaped_loops_stay_whole_over_color(cfg, style):
    """Test drive 4: on the puffy rainbow pendant the sun's rays reached under the loop,
    and cutting the colors out cut notches into the loop the chain hangs on. The loop
    stays whole; the bit of color it hides is trimmed instead."""
    from shapely.geometry import box

    from charm_maker.products import _add_side_loop
    from charm_maker.relief import build_relief_parts

    outline = Polygon(Point(0, 0).buffer(12).exterior)
    ray = _as_multi(box(-0.6, -5, 0.6, 12).intersection(outline))        # ink right up to the top
    design = Design("t", "pendant", outline, [InkRegion("black", (20, 20, 20), ray)])
    info = _add_side_loop(cfg, design, cfg["products"]["pendant"]["loop"])
    parts, base_name, _, notes = build_relief_parts(cfg, design, "side_loop", info, style)
    loop = info["solid"] - info["hole_solid"]
    assert (loop - parts[base_name]).volume() < 0.01, "no notches in the loop"
    assert any("under the loop" in n for n in notes)
