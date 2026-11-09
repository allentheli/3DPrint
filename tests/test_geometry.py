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
    assert len(coupons) == 18
    assert [c.number for c in coupons] == list(range(1, 19))
    for c in coupons:
        _assert_solid(c.solid)


def test_coupon_sizes_match_config(cfg, coupons):
    ft = cfg["fit_test"]
    key_for = {
        "clip_pocket_diameter": "clip_coupon", "keyring_hole_diameter": "keyring_coupon",
        "jump_ring_hole_diameter": "jump_ring_coupon", "magnet_pocket_diameter": "magnet_coupon",
        "switch_cutout": "switch_coupon", "stem_socket_clearance": "stem_coupon",
    }
    for c in coupons:
        w, length, t = ft[key_for[c.group]]
        sx, sy, sz = size(c.solid)
        assert sx == pytest.approx(w, abs=0.01)
        assert sy == pytest.approx(length, abs=0.01)
        extra = ft["label_raise"]
        if c.group == "stem_socket_clearance":
            extra = ft["stem_boss_height"]
        assert sz == pytest.approx(t + extra, abs=0.01)


def test_pockets_have_right_diameter_and_depth(cfg, coupons):
    hw = cfg["hardware"]
    depth_for = {"clip_pocket_diameter": hw["clip_pocket_depth"], "magnet_pocket_diameter": hw["magnet_pocket_depth"]}
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
        # Floor is thick enough for magnets.
        if c.group == "magnet_pocket_diameter":
            assert t - depth >= hw["magnet_pocket_min_floor"]


def test_through_holes_have_right_size(cfg, coupons):
    for c in (c for c in coupons if c.group in ("keyring_hole_diameter", "jump_ring_hole_diameter", "switch_cutout")):
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
        "jump_ring_hole_diameter": hw["jump_ring_hole_min_wall"],
        "magnet_pocket_diameter": hw["magnet_pocket_min_wall"],
        "switch_cutout": 1.5,
        "stem_socket_clearance": 1.5,
    }
    for c in coupons:
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
        assert maxx - minx == pytest.approx(hw["mx_stem_span"] + c.candidate, abs=0.02)
        assert maxy - miny == pytest.approx(hw["mx_stem_span"] + c.candidate, abs=0.02)
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
