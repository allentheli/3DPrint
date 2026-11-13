"""Geometry checks: watertight, one body, right sizes, pockets inside with enough wall."""

import math

import manifold3d as m3d
import pytest
from shapely.geometry import Point, Polygon

from charm_maker.fittest import build_coupons, build_fit_plate
from charm_maker.geom import size, teardrop, to_trimesh
from charm_maker.labels import _GLYPHS, label_shape
from charm_maker.stand import build_stand, stand_parts


@pytest.fixture(scope="module")
def coupons(cfg):
    return build_coupons(cfg)


@pytest.fixture(scope="module")
def stand(cfg):
    return build_stand(cfg)


def _assert_solid(solid: m3d.Manifold):
    assert solid.status() == m3d.Error.NoError
    assert not solid.is_empty()
    assert len(solid.decompose()) == 1, "must be one connected part"
    tm = to_trimesh(solid)
    assert tm.is_watertight
    assert tm.volume > 0


def _inner_contours(solid: m3d.Manifold, z: float):
    """Contours of the slice at z, excluding the largest (the outline)."""
    polys = solid.slice(z).to_polygons()
    polys = [Polygon(p) for p in polys]
    polys.sort(key=lambda p: -p.area)
    return polys[0], polys[1:]


def test_every_coupon_is_a_single_watertight_solid(coupons):
    assert len(coupons) == 22
    assert [c.number for c in coupons] == list(range(1, 23))
    for c in coupons:
        if c.group == "flexi_joint_gap":          # a body and an arm, printed already joined
            _assert_solid(c.extras["body"])
            _assert_solid(c.extras["arm"])
        else:
            _assert_solid(c.solid)


LOOP_GROUPS = ("earring_hole_diameter", "necklace_hole_diameter",   # tags with their own shape
               "flexi_joint_gap")


def test_coupon_sizes_match_config(cfg, coupons):
    ft = cfg["fit_test"]
    key_for = {
        "clip_pocket_diameter": "clip_coupon", "keyring_hole_diameter": "keyring_coupon",
        "switch_cutout": "switch_coupon", "stem_socket_clearance": "stem_coupon",
    }
    for c in (c for c in coupons if c.group not in LOOP_GROUPS):
        w, length, t = ft[key_for[c.group]]
        sx, sy, sz = size(c.solid)
        assert sx == pytest.approx(w, abs=0.01)
        assert sy == pytest.approx(length, abs=0.01)
        extra = ft["label_raise"]
        if c.group == "stem_socket_clearance":
            extra = ft["stem_boss_height"]
        if c.group == "switch_cutout":          # a closed box: floor, hollow, lid
            extra = ft["switch_housing_floor"] + cfg["hardware"]["mx_cavity_depth"]
        assert sz == pytest.approx(t + extra, abs=0.01)


def test_pockets_have_right_diameter_and_depth(cfg, coupons):
    hw = cfg["hardware"]
    depth_for = {"clip_pocket_diameter": hw["clip_pocket_depth"]}
    for c in (c for c in coupons if c.group in depth_for):
        t = c.outline and size(c.solid)[2] - cfg["fit_test"]["label_raise"]
        depth = depth_for[c.group]
        outline, inner = _inner_contours(c.solid, t - depth / 2)
        assert len(inner) == 1, "pocket should show as one hole in a slice through it"
        hole = inner[0]
        minx, miny, maxx, maxy = hole.bounds
        assert maxx - minx == pytest.approx(c.candidate, abs=0.03)
        assert maxy - miny == pytest.approx(c.candidate, abs=0.03)
        # Below the pocket floor the slice is solid.
        _, below = _inner_contours(c.solid, t - depth - 0.1)
        assert below == []


def test_switch_housings_are_closed_boxes_like_the_case(cfg, coupons):
    """Allen: the switch pieces should be a house for the switch, with a bottom. The lid has
    the square hole, under it a hollow with room for the switch body and pins, then a
    floor that is closed except for a push-out hole."""
    hw, ft = cfg["hardware"], cfg["fit_test"]
    for c in (c for c in coupons if c.group == "switch_cutout"):
        e = c.extras
        lid_z = e["height"] - ft["switch_coupon"][2] / 2
        _, inner = _inner_contours(c.solid, lid_z)
        assert len(inner) == 1
        minx, miny, maxx, maxy = inner[0].bounds
        assert maxx - minx == pytest.approx(c.candidate, abs=0.03), "the snap-fit hole"
        assert maxy - miny == pytest.approx(c.candidate, abs=0.03)
        _, inner = _inner_contours(c.solid, e["floor"] + e["cavity_depth"] / 2)
        minx, miny, maxx, maxy = inner[0].bounds
        assert maxx - minx >= hw["mx_cavity_size"] - 0.03, "room for the switch body"
        assert e["cavity_depth"] >= 8.3 - hw["mx_plate_thickness"], "room for the pins below the lid"
        _, inner = _inner_contours(c.solid, e["floor"] / 2)
        assert len(inner) == 1, "a floor, with only the push-out hole in it"
        minx, miny, maxx, maxy = inner[0].bounds
        assert maxx - minx == pytest.approx(e["pushout"], abs=0.1)


def test_through_holes_have_right_size(cfg, coupons):
    for c in (c for c in coupons if c.group == "keyring_hole_diameter"):
        t = size(c.solid)[2] - cfg["fit_test"]["label_raise"]
        for z in (0.1, t / 2, t - 0.1):
            _, inner = _inner_contours(c.solid, z)
            assert len(inner) == 1
            minx, miny, maxx, maxy = inner[0].bounds
            assert maxx - minx == pytest.approx(c.candidate, abs=0.03)
            assert maxy - miny == pytest.approx(c.candidate, abs=0.03)


def test_features_sit_inside_with_enough_wall(cfg, coupons):
    hw = cfg["hardware"]
    min_wall = {
        "clip_pocket_diameter": hw["clip_pocket_min_wall"],
        "keyring_hole_diameter": hw["keyring_hole_min_wall"],
        "switch_cutout": 1.5,
        "stem_socket_clearance": 1.5,
    }
    for c in (c for c in coupons if c.group not in LOOP_GROUPS):
        cx, cy = c.feature_center
        if c.group == "switch_cutout":
            half = c.feature_size / 2
            feature = Polygon([(cx - half, cy - half), (cx + half, cy - half), (cx + half, cy + half), (cx - half, cy + half)])
        else:
            feature = Point(cx, cy).buffer(c.feature_size / 2)
        assert c.outline.contains(feature)
        wall = c.outline.exterior.distance(feature)
        assert wall >= min_wall[c.group] - 1e-6, f"piece {c.number}: wall {wall:.2f} < {min_wall[c.group]}"


def test_stem_socket_is_a_plus_with_clearance(cfg, coupons):
    hw = cfg["hardware"]
    ft = cfg["fit_test"]
    for c in (c for c in coupons if c.group == "stem_socket_clearance"):
        top = size(c.solid)[2]
        _, inner = _inner_contours(c.solid, top - ft["stem_socket_depth"] / 2)
        assert len(inner) == 1
        minx, miny, maxx, maxy = inner[0].bounds
        span = hw["mx_stem_span"] + ft["stem_span_clearance"]
        assert maxx - minx == pytest.approx(span, abs=0.02)
        assert maxy - miny == pytest.approx(span, abs=0.02)
        # Socket bottom is closed: a slice just below the socket is the boss, no hole.
        _, below = _inner_contours(c.solid, top - ft["stem_socket_depth"] - 0.1)
        assert below == []


def test_stand_is_sound(cfg, stand):
    _assert_solid(stand)
    s = cfg["stand"]
    sx, sy, sz = size(stand)
    assert sx == pytest.approx(s["base_width"], abs=0.01)
    # Nothing overhangs the base footprint.
    assert sy == pytest.approx(s["base_depth"], abs=0.01)
    # Sits flat on the bed.
    lo = stand.bounding_box()[2]
    assert lo == pytest.approx(0.0, abs=1e-6)


def test_stand_recess_fits_washer(cfg):
    s = cfg["stand"]
    hw = cfg["hardware"]
    p = stand_parts(cfg)
    full = (p["base"] + p["upright"] + p["lip"]).trim_by_plane([0, 0, 1], 0)
    with_recess = build_stand(cfg)
    removed = full.volume() - with_recess.volume()
    d = hw["washer_diameter"] + s["washer_recess_clearance"]
    expected = teardrop(d).area * s["washer_recess_depth"]
    # The recess may notch into the base below the ledge, so a little more is fine.
    assert expected <= removed <= expected * 1.1
    assert d >= hw["washer_diameter"] + 0.2
    assert s["washer_recess_depth"] >= hw["washer_thickness"]
    assert s["upright_thickness"] - s["washer_recess_depth"] == pytest.approx(s["front_wall"])
    # The roof of the teardrop must stay inside the upright.
    assert hw["magnet_height_above_bottom"] + d / 2 * math.sqrt(2) < s["upright_height"]


def test_plate_layout_has_no_overlaps(cfg):
    plate = build_fit_plate(cfg)
    names = list(plate.placed)
    boxes = {n: plate.placed[n].bounding_box() for n in names}
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            ax0, ay0, _, ax1, ay1, _ = boxes[a]
            bx0, by0, _, bx1, by1, _ = boxes[b]
            overlap = ax0 < bx1 and bx0 < ax1 and ay0 < by1 and by0 < ay1
            assert not overlap, f"{a} overlaps {b}"
    pw, ph = plate.plate_size
    bed = cfg["printer"]["bed_size"]
    assert pw <= bed[0] and ph <= bed[1]


def test_label_glyphs_are_valid():
    for ch in _GLYPHS:
        shape = label_shape(ch, 4.0, 0.8)
        assert not shape.is_empty and shape.area > 0
    two = label_shape("18", 4.0, 0.8)
    assert len(getattr(two, "geoms", [two])) == 2


def loop_hole_check(solid, x_c: float, y_c: float, d: float, wall: float, length: float):
    """The loop's hole runs left to right (along X): a cut across X at the loop shows a
    hole of diameter d with plastic below it; the bottom layer has no hole (so it
    does not go front to back)."""
    turned = solid.rotate([0.0, 90.0, 0.0])            # (x, y, z) -> (z, y, -x)
    for dx in (-length / 2 + 0.2, 0.0, length / 2 - 0.2):
        polys = [Polygon(p) for p in turned.slice(-(x_c + dx)).to_polygons()]
        polys.sort(key=lambda p: -p.area)
        holes = [p for p in polys[1:] if any(q.contains(p) for q in polys if q is not p)]
        assert holes, f"no hole at x offset {dx}"
        hole = min(holes, key=lambda p: abs(p.centroid.y - y_c))
        minz, miny, maxz, maxy = hole.bounds          # slice coords: (world z, world y)
        assert maxy - miny == pytest.approx(d, abs=0.06)
        assert minz >= wall - 0.06, "plastic under the hole"
    bottom = [Polygon(p) for p in solid.slice(0.05).to_polygons()]
    bottom.sort(key=lambda p: -p.area)
    assert not any(bottom[0].contains(p) and p.distance(Point(x_c, y_c)) < d for p in bottom[1:]), \
        "the hole must not go front to back"


def test_loop_coupons_have_sideways_holes(cfg, coupons):
    for c in (c for c in coupons if c.group == "necklace_hole_diameter"):
        x_c, y_c = c.feature_center
        loop = cfg["hardware"]["necklace_loop"]
        loop_hole_check(c.solid, x_c, y_c, c.candidate, loop["wall"], loop["length"])
        assert size(c.solid)[2] == pytest.approx(c.extras["loop_height"], abs=0.01)


def test_earring_coupons_have_the_jump_ring_tab(cfg, coupons):
    """The same small tab the earrings get, one hole size per coupon, through front to back."""
    t = cfg["fit_test"]["earring_tab_coupon"][2]
    for c in (c for c in coupons if c.group == "earring_hole_diameter"):
        x_c, y_c = c.feature_center
        for z in (0.2, t / 2):
            face = [Polygon(q) for q in c.solid.slice(z).to_polygons()]
            holes = [q for q in face if q.contains(Point(x_c, y_c))]
            assert len(holes) % 2 == 0, f"piece {c.number}: the hole goes through"
        inner = [q for q in (Polygon(q) for q in c.solid.slice(t / 2).to_polygons()) if q.contains(Point(x_c, y_c))]
        hole = min(inner, key=lambda q: q.area)
        assert hole.bounds[2] - hole.bounds[0] == pytest.approx(c.candidate, abs=0.1)
        assert c.outline.bounds[3] - y_c == pytest.approx(c.candidate / 2 + c.extras["wall"], abs=0.15)
        assert size(c.solid)[2] == pytest.approx(t + cfg["fit_test"]["label_raise"], abs=0.01)


def test_one_group_can_be_reprinted_alone(cfg, tmp_path):
    from charm_maker.fittest import build_fit_plate, write_fit_test

    plate = build_fit_plate(cfg, only="earring_hole_diameter")
    assert [c.number for c in plate.coupons] == [7, 8, 9] and plate.stand is None
    paths = write_fit_test(cfg, plate, tmp_path)
    guide = paths["guide-md"].read_text()
    assert "one group again" in guide and "Stand and washer" not in guide and "7, 8, 9" in guide


def test_stem_posts_are_the_real_keycap_size(cfg, coupons):
    """Allen: test the 5.5 mm post the clicker keycap will really have. The plastic left
    at the tips of the cross must still print as at least one nozzle-width line."""
    hw = cfg["hardware"]
    for c in (c for c in coupons if c.group == "stem_socket_clearance"):
        post, inner = _inner_contours(c.solid, size(c.solid)[2] - 1.0)   # a slice through the post
        minx, miny, maxx, maxy = post.bounds
        assert maxx - minx == pytest.approx(hw["mx_keycap_post_diameter"], abs=0.05)
        assert len(inner) == 1, "one cross-shaped hole"
        thinnest = post.exterior.distance(inner[0])
        assert thinnest >= 0.45, f"piece {c.number}: only {thinnest:.2f} mm at the cross tips"


def test_flexi_joint_coupons_swing_and_hold(cfg, coupons):
    """The frog flexi's joint (2026-11-13): a round knob on the arm in a cup in the body,
    printed already joined. Arm and body never touch, the arm swings about 30 degrees each
    way and then stops, and the knob cannot come out: it moves no more than its gap."""
    joints = [c for c in coupons if c.group == "flexi_joint_gap"]
    assert [c.number for c in joints] == [19, 20, 21, 22]
    assert [c.candidate for c in joints] == cfg["fit"]["flexi_joint_gap"]["candidates"]
    for c in joints:
        body, arm = c.extras["body"], c.extras["arm"]
        cx, cy = c.feature_center
        assert (body ^ arm).volume() < 1e-6, "printed apart"

        def turned(deg):
            return arm.translate([-cx, -cy, 0]).rotate([0, 0, deg]).translate([cx, cy, 0])

        for deg in (-30, -15, 15, 30):
            assert (turned(deg) ^ body).volume() < 1e-3, f"piece {c.number} swings to {deg} degrees"
        for deg in (-45, 45):
            assert (turned(deg) ^ body).volume() > 1e-3, f"piece {c.number} stops before {deg} degrees"
        g = c.candidate
        # Held: it can rattle by about its gap (a bit more sideways, along the 45-degree lips)
        # but never far enough to come out.
        for move in ([0, 0, g + 0.15], [0, 0, -(g + 0.15)], [1.3, 0, 0], [0, 1.3, 0], [-1.3, 0, 0]):
            assert (arm.translate(move) ^ body).volume() > 1e-3, f"piece {c.number}: the knob is held ({move})"
        assert (arm.translate([0, 0, g - 0.05]) ^ body).volume() < 1e-3, "the gap is all around, up too"

