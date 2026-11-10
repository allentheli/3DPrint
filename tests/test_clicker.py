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
    height = prod["case_floor"] + hw["mx_cavity_depth"] + hw["mx_plate_thickness"]
    assert body.bounding_box()[5] == pytest.approx(height, abs=0.01)
    # The lid: the switch hole at the tested size.
    _, *holes = _slice(body, height - hw["mx_plate_thickness"] / 2)
    sq = max(holes, key=lambda p: p.area)
    assert sq.bounds[2] - sq.bounds[0] == pytest.approx(fit["switch_cutout"]["value"], abs=0.03)
    # The hollow: room for the switch body and pins.
    _, *holes = _slice(body, prod["case_floor"] + hw["mx_cavity_depth"] / 2)
    hollow = max(holes, key=lambda p: p.area)
    assert hollow.bounds[2] - hollow.bounds[0] >= hw["mx_cavity_size"] - 0.03
    # The floor: closed but for the push-out hole.
    _, *holes = _slice(body, prod["case_floor"] / 2)
    assert len(holes) == 2, "the push-out hole and the ring hole"
    ring = min(holes, key=lambda p: Point(*a["hole_center"]).distance(p.centroid))
    assert ring.bounds[2] - ring.bounds[0] == pytest.approx(fit["keyring_hole_diameter"]["value"], abs=0.05)
    # The ring hole is outside the box, in the tab, so a split ring can go through.
    assert a["hole_center"][1] - fit["keyring_hole_diameter"]["value"] / 2 > a["side"] / 2
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
    a = draw_blob_card(cfg, tmp_path, "clicker", 3, BLACK, PINK)
    b = draw_blob_card(cfg, tmp_path, "hair_clip", 4, BLACK, YELLOW)
    r = run_batch(cfg, [a, b], tmp_path / "out")
    assert r.problems == []
    names = {p.name: p for p in r.pieces}
    assert set(names) == {"click-03", "click-03-case", "clip-04"}
    where = {pp.piece.name: pl.number for pl in r.plates for pp in pl.pieces}
    assert where["click-03"] == where["clip-04"], "the keycap prints with the charms"
    assert where["click-03-case"] != where["click-03"], "the case has its own plate"
    notes = r.files["notes"].read_text()
    assert f"**{cfg['printer']['layer_height_cases']} mm**" in notes and "Clicker cases" in notes
    assert "split ring through the case's tab" in notes
    out = tmp_path / "out" / "designs"
    assert (out / "click-03-case-front.png").exists(), "the assembled view"
    case = json.loads((out / "click-03-case.json").read_text())
    assert any("switch hole" in w for w in case["warnings"]), "untested fit values are flagged"
