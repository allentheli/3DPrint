"""Clicker keychain: a keycap made from the drawing with a socket post for the MX stem,
and a case the switch snaps into, with a ring tab. Standard MX numbers, sized from the
fit test."""

import json

import pytest
from shapely.geometry import Point, Polygon, box

from charm_maker.geom import count_bodies, to_trimesh
from charm_maker.pipeline import run_batch
from charm_maker.products import build_clicker_case, build_piece
from charm_maker.shape import Design, InkRegion, _as_multi
from tests.synthetic import BLACK, PINK, YELLOW, draw_blob_card


def _keycap_design(product="clicker"):
    outline = Polygon(Point(0, 0).buffer(9.0).exterior)
    face = _as_multi(Point(0, 0).buffer(6.0))
    return Design("click-01", product, outline, [InkRegion("pink", (236, 72, 153), face)])


def _slice(solid, z):
    polys = sorted((Polygon(p) for p in solid.slice(z).to_polygons()), key=lambda p: -p.area)
    return polys


def test_keycap_has_a_real_size_post_with_the_tested_socket(cfg):
    hw, prod = cfg["hardware"], cfg["products"]["clicker"]
    c = cfg["fit"]["stem_socket_clearance"]["value"]
    k = build_piece(cfg, _keycap_design())
    assert k.attachment["kind"] == "stem_socket" and k.mirrored and not k.face_up, "face-down, post up"
    base = k.parts[k.base_part]
    assert to_trimesh(base).is_watertight
    t, h, depth = prod["thickness"], prod["post_height"], prod["socket_depth"]
    assert base.bounding_box()[5] == pytest.approx(t + h, abs=0.01)
    # Near the post's end: a 5.5 mm round post with the cross socket in it.
    post, *holes = _slice(base, t + h - 1.0)
    assert post.bounds[2] - post.bounds[0] == pytest.approx(hw["mx_keycap_post_diameter"], abs=0.05)
    assert len(holes) == 1
    cross = holes[0]
    span = hw["mx_stem_span"] + cfg["fit_test"]["stem_span_clearance"]
    assert cross.bounds[2] - cross.bounds[0] == pytest.approx(span, abs=0.02)
    assert cross.area == pytest.approx(span * (hw["mx_stem_arm_x"] + c) + span * (hw["mx_stem_arm_y"] + c)
                                       - (hw["mx_stem_arm_x"] + c) * (hw["mx_stem_arm_y"] + c), rel=0.02)
    # The socket has a floor: below its depth the post is solid.
    post, *holes = _slice(base, t + (h - depth) / 2)
    assert holes == []
    # Under the drawing's middle (the piece is built mirrored, like every face-down charm).
    sx, sy = k.solid_xy(*k.attachment["center"])
    assert post.centroid.distance(Point(sx, sy)) < 0.05
    assert k.attachment["travel_clearance"] >= 0.5, "the keycap clears the switch when pressed"


def test_a_thin_drawing_gets_a_backer_disc_for_the_post(cfg):
    thin = _as_multi(box(-12, -1.5, 12, 1.5))
    d = Design("click-02", "clicker", Polygon(box(-12.5, -2, 12.5, 2).exterior), [InkRegion("black", (20, 20, 20), thin)])
    k = build_piece(cfg, d)
    assert any("backer disc" in f for f in k.design.fixes)
    r = cfg["hardware"]["mx_keycap_post_diameter"] / 2 + cfg["products"]["clicker"]["post_margin"]
    cx, cy = k.attachment["center"]
    assert k.design.outline.buffer(1e-6).contains(Point(cx, cy).buffer(r - 0.01))


def test_case_holds_the_switch_like_the_fit_test(cfg):
    hw, prod, fit = cfg["hardware"], cfg["products"]["clicker"], cfg["fit"]
    k = build_piece(cfg, _keycap_design())
    case = build_clicker_case(cfg, k)
    body = case.parts[case.base_part]
    assert to_trimesh(body).is_watertight and count_bodies(body) == 1
    assert case.group == "cases" and case.face_up and not case.supports
    a = case.attachment
    plate_z = prod["case_floor"] + hw["mx_cavity_depth"] + hw["mx_plate_thickness"]
    assert a["plate_z"] == pytest.approx(plate_z, abs=0.01)
    height = a["height"]
    assert body.bounding_box()[5] == pytest.approx(height, abs=0.01)
    # The plate: the switch hole at the tested size, at the bottom of the cup.
    _, *holes = _slice(body, plate_z - hw["mx_plate_thickness"] / 2)
    sq = max(holes, key=lambda p: p.area)
    assert sq.bounds[2] - sq.bounds[0] == pytest.approx(fit["switch_cutout"]["value"], abs=0.03)
    # The hollow: room for the switch body and pins.
    _, *holes = _slice(body, prod["case_floor"] + hw["mx_cavity_depth"] / 2)
    hollow = max(holes, key=lambda p: p.area)
    assert hollow.bounds[2] - hollow.bounds[0] >= hw["mx_cavity_size"] - 0.03
    # The floor: closed but for the push-out hole; the whole bottom sits flat on a table.
    _, *holes = _slice(body, prod["case_floor"] / 2)
    assert len(holes) == 1, "only the push-out hole"
    # Allen: the ring hangs at half height, so the clicker sits flat on a table. The hole runs
    # left to right through the post at the top, with plastic under it, like a pendant loop.
    from tests.test_geometry import loop_hole_check

    d = fit["keyring_hole_diameter"]["value"]
    assert a["hole_z"] == pytest.approx(height / 2, abs=0.01)
    loop_hole_check(body, a["hole_center"][0], a["hole_center"][1], d, height / 2 - d / 2 - 0.1, a["post_length"])
    # The tunnel stays in the post: at half height the only enclosed hole is the hollow (the
    # post's outer wall shows as a separate piece there; above and below it is joined).
    outer, *rest = _slice(body, a["hole_z"])
    assert len([q for q in rest if outer.contains(q)]) == 1
    # The lid hangs over the hollow by less than a millimeter: no supports.
    assert (hw["mx_cavity_size"] - fit["switch_cutout"]["value"]) / 2 < 1.0


def test_clicker_keycaps_stay_flat(cfg):
    k = build_piece(cfg, _keycap_design(), style="puffy")
    assert k.style == "flat" and k.attachment["kind"] == "stem_socket"
    assert any("clicker keycaps are flat" in w for w in k.design.warnings)


def test_glue_on_fallback_is_a_plain_charm(cfg):
    import copy

    c2 = copy.deepcopy(cfg)
    c2["products"]["clicker"]["glue_on_fallback"] = True
    k = build_piece(c2, _keycap_design())
    assert k.attachment.get("kind") != "stem_socket"
    assert k.parts[k.base_part].bounding_box()[5] == pytest.approx(c2["products"]["clicker"]["thickness"], abs=0.01)
    assert any("glue onto a store-bought" in f for f in k.design.fixes)


def test_a_clicker_card_gives_a_keycap_plate_and_a_case_plate(cfg, tmp_path):
    import copy

    cfg = copy.deepcopy(cfg)
    cfg["fit"]["switch_cutout"]["tested"] = False          # the warning path, whatever the real results
    a = draw_blob_card(cfg, tmp_path, "clicker", 3, BLACK, PINK)
    b = draw_blob_card(cfg, tmp_path, "hair_clip", 4, BLACK, YELLOW)
    r = run_batch(cfg, [a, b], tmp_path / "out")
    assert r.problems == []
    names = {p.name: p for p in r.pieces}
    assert set(names) == {"click-03", "click-03-case", "clip-04"}
    where = {pp.piece.name: pl.number for pl in r.plates for pp in pl.pieces}
    assert where["click-03"] == where["clip-04"], "the keycap prints with the charms"
    assert where["click-03-case"] != where["click-03"], "the case has its own plate"
    keycap_inks = {i.name for i in names["click-03"].design.inks}
    assert keycap_inks == {"black", "pink"}, f"the printed guide square is not ink: {keycap_inks}"
    notes = r.files["notes"].read_text()
    assert f"**{cfg['printer']['layer_height_cases']} mm**" in notes and "Clicker cases" in notes
    assert "split ring through the hole in the post" in notes
    out = tmp_path / "out" / "designs"
    assert (out / "click-03-case-front.png").exists(), "the assembled view"
    case = json.loads((out / "click-03-case.json").read_text())
    assert any("switch hole" in w for w in case["warnings"]), "untested fit values are flagged"


def test_the_cup_hides_the_switch_and_the_gap(cfg):
    """Allen, after printing the first clicker: the switch showed and the keycap floated high
    above the case. The case is now a cup: the switch sits inside it, the keycap sits in its
    opening a little proud of the rim, and pressed all the way it touches nothing."""
    from shapely import affinity

    hw, prod = cfg["hardware"], cfg["products"]["clicker"]
    k = build_piece(cfg, _keycap_design())
    case = build_clicker_case(cfg, k)
    body, a = case.parts[case.base_part], case.attachment
    plate_z, rim, clr = a["plate_z"], a["rim"], prod["case_keycap_clearance"]
    # The rim stands above the whole switch, stem included: nothing of it shows from the side.
    assert rim > hw["mx_stem_top_above_plate"]
    # Where the keycap rests (its back), and pressed all the way.
    back_rest = hw["mx_stem_top_above_plate"] - min(k.attachment["socket_depth"], hw["mx_stem_height"]) + k.attachment["post_height"]
    assert back_rest < rim < back_rest + k.thickness, "the keycap's edge is inside the cup, its face above the rim"
    assert rim + a["proud"] == pytest.approx(back_rest + k.thickness, abs=0.01)
    assert back_rest - hw["mx_full_travel"] > hw["mx_housing_above_plate"] + 0.5, "pressed, it clears the switch"
    # The opening is the keycap's outline plus the clearance, at every height above the plate.
    cx, cy = k.attachment["center"]
    keycap = affinity.translate(k.design.outline, -cx, -cy)
    for z in (plate_z + 0.5, plate_z + rim / 2, plate_z + rim - 0.3):
        outer, *holes = _slice(body, z)
        opening = max(holes, key=lambda q: q.area)
        assert opening.buffer(0.05).contains(keycap.buffer(clr - 0.1)), f"the keycap fits at z={z:.1f}"
        assert keycap.buffer(clr + 0.15).contains(opening), f"no wide gap around the keycap at z={z:.1f}"
        assert outer.buffer(0.05).contains(opening.buffer(prod["case_wall"] - 0.1)), "a full wall all round"
    # The switch goes in through the opening, and the keycap covers its square top (but for
    # the corners' rounding), so nothing shows past the keycap's edge either.
    sq = box(-hw["mx_cavity_size"] / 2, -hw["mx_cavity_size"] / 2, hw["mx_cavity_size"] / 2, hw["mx_cavity_size"] / 2)
    assert keycap.buffer(clr).contains(sq), "the switch fits through the opening"
    assert keycap.buffer(0.05).contains(sq.buffer(-0.3)), "the keycap covers the switch"


def test_case_follows_the_drawing_a_little_bigger(cfg):
    """Allen: the case should be the shape of the drawing's outline, a little bigger. It
    still always has room for the switch, centered under the keycap's post."""
    from shapely import affinity
    from shapely.geometry import Point as P

    hw, prod = cfg["hardware"], cfg["products"]["clicker"]
    oval = affinity.scale(P(0, 0).buffer(1.0), 11.0, 7.5)                       # 22 x 15 mm
    d = Design("click-05", "clicker", Polygon(oval.exterior), [InkRegion("pink", (236, 72, 153), _as_multi(oval.buffer(-2)))])
    k = build_piece(cfg, d)
    case = build_clicker_case(cfg, k)
    body = case.parts[case.base_part]
    whole = _slice(body, case.attachment["height"] - 0.5)[0]
    above = box(-100, case.attachment["post_from_y"], 100, 100)              # leave out the ring post
    footprint = whole.difference(above)
    cx, cy = k.attachment["center"]
    margin = prod["case_keycap_clearance"] + prod["case_wall"]
    drawing = affinity.translate(k.design.outline, -cx, -cy).difference(above.buffer(margin))
    assert footprint.buffer(0.05).contains(drawing.buffer(margin - 0.1)), "drawing-shaped, a bit bigger"
    assert footprint.area < drawing.buffer(margin + 1.0).area * 1.15, "not a big box"
    hollow = box(-hw["mx_cavity_size"] / 2, -hw["mx_cavity_size"] / 2, hw["mx_cavity_size"] / 2, hw["mx_cavity_size"] / 2)
    assert whole.buffer(0.05).contains(hollow.buffer(1.0)), "room for the switch, with at least 1 mm of wall"
    b = footprint.bounds
    assert b[2] - b[0] > b[3] - b[1] + 3, "an oval drawing makes an oval case, not a square"


def test_clicker_card_asks_for_a_drawing_big_enough_for_the_switch(cfg, tmp_path):
    """Allen: the clicker card should ask for a size that fits the switch. It shows a
    "cover the square" guide as big as the smallest keycap."""
    import pymupdf

    from charm_maker.cards import card_layout, write_cards_pdf

    lay = card_layout(cfg, "clicker", 1)
    cx, cy, side = lay.zones["cover_square"]
    assert side == pytest.approx(cfg["products"]["clicker"]["size_min"] * cfg["process"]["card_scale"])
    bx, by, bw, bh = lay.box
    assert bx < cx - side / 2 and cx + side / 2 < bx + bw, "the square fits in the drawing box"
    pdf = write_cards_pdf(cfg, ["clicker"], tmp_path / "cards.pdf", numbers=[1])
    assert "cover the square" in pymupdf.open(str(pdf))[0].get_text()


@pytest.mark.parametrize("shape,expect_short,expect_long", [
    (Point(0, 0).buffer(4.0), 16.0, None),             # drawn too small: scaled up to cover the switch
    (box(-10, -1, 10, 1), None, 40.0),                  # long and thin: grows only until 40 mm long
])
def test_small_drawings_are_scaled_up_to_cover_the_switch(cfg, shape, expect_short, expect_long):
    d = Design("click-04", "clicker", Polygon(shape.exterior), [InkRegion("black", (20, 20, 20), _as_multi(shape.buffer(-0.8)))])
    k = build_piece(cfg, d)
    minx, miny, maxx, maxy = k.design.outline.bounds
    w, h = maxx - minx, maxy - miny
    if expect_short:
        assert min(w, h) == pytest.approx(expect_short, abs=0.1)
        assert any("scaled up" in f for f in k.design.fixes)
    if expect_long:
        assert max(w, h) == pytest.approx(expect_long, abs=0.1), "grown, but never past the largest keycap"
        assert any("backer disc" in f for f in k.design.fixes), "still too thin for the post: a disc behind it"



def test_one_plate_puts_the_case_with_the_charms(cfg, tmp_path):
    """Allen: everything in one 3MF, the clicker case on the same plate as the charms."""
    a = draw_blob_card(cfg, tmp_path, "clicker", 5, BLACK, PINK)
    b = draw_blob_card(cfg, tmp_path, "hair_clip", 6, BLACK, YELLOW)
    r = run_batch(cfg, [a, b], tmp_path / "out", one_plate=True)
    assert r.problems == [] and len(r.plates) == 1
    assert {pp.piece.name for pp in r.plates[0].pieces} == {"click-05", "click-05-case", "clip-06"}
    notes = r.files["notes"].read_text()
    assert "stand upright on this plate" in notes and f"**{cfg['printer']['layer_height_charms']} mm**" in notes
    assert "Shaped pieces (click-05-case" not in notes
