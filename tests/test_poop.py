"""Poop containers and the screw-top tool: sound solids, a right-hand thread that
clears while unscrewing, no supports needed, see-through holes, and a usable opening."""

import math

import manifold3d as m3d
import numpy as np
import pytest
import trimesh

from charm_maker.cli import main
from charm_maker.geom import count_bodies, to_trimesh
from charm_maker.poopjar import (KINDS, _union, build_container, helix, overhang_area,
                                 unscrew_overlap)
from charm_maker.screwtop import add_screw_top, load_model, unscrew_check


def test_thread_is_a_valid_right_hand_helix():
    h = helix(25.7, 0.7, 10.0, 50.0, 50.0, 60.0)
    assert to_trimesh(h).is_watertight
    assert overhang_area(h) == pytest.approx(0.0, abs=0.5)
    # The crest climbs counterclockwise: at a higher slice the widest point has turned +.
    def crest_angle(z):
        pts = np.asarray(h.slice(z).to_polygons()[0])
        r = np.hypot(pts[:, 0], pts[:, 1])
        p = pts[np.argmax(r)]
        return math.degrees(math.atan2(p[1], p[0]))
    a1, a2 = crest_angle(51.0), crest_angle(51.5)
    turn = (a2 - a1 + 180) % 360 - 180
    assert turn == pytest.approx(360 * 0.5 / 10.0, abs=4.0)


@pytest.fixture(scope="module", params=KINDS)
def container(cfg, request):
    return build_container(cfg, request.param, "medium")


def test_container_is_sound_and_fits(cfg, container):
    assert to_trimesh(container.jar).is_watertight
    assert count_bodies(container.jar) == 1
    assert count_bodies(container.lid) == 1
    assert (container.jar ^ container.lid).volume() < 0.01, "lid must not overlap the body when closed"


def test_lid_unscrews_counterclockwise_and_not_clockwise(cfg, container):
    assert unscrew_overlap(cfg, container, direction=1) < 0.01
    assert unscrew_overlap(cfg, container, direction=-1) > 1.0


def _stop_angle(lid, body, cx, cy, lead):
    """How far past its built (facing front) pose a lid turns, tightening, before it touches."""
    for i in range(0, 80):
        dz = 0.025 * i
        moved = lid.translate([-cx, -cy, 0.0]).rotate([0.0, 0.0, -360.0 * dz / lead]).translate([cx, cy, -dz])
        if (body ^ moved).volume() > 0.001:
            return 360.0 * dz / lead
    return 360.0 * 2.0 / lead


def test_heads_stop_facing_front(cfg, container):
    """Allen's printed duck: screwed shut, the head did not face front. It could turn about
    45 degrees past front before anything stopped it. Now the body stops every lid within
    a few degrees of the way it was built (head and beak forward)."""
    angle = _stop_angle(container.lid, container.jar, container.body.cx, 0.0, cfg["poop_jar"]["thread_lead"])
    assert angle <= 6.0, f"{container.name} turns {angle:.0f} degrees past front"


def test_no_supports_needed(cfg, container):
    assert overhang_area(container.jar) < 1.0
    cap = _union([s for s, _ in container.cap_for_printing().values()])
    assert overhang_area(cap) < 12.0


def test_see_through_and_fillable(cfg, container):
    """Allen's printed duck (2026-11-13): the 4 mm diamond holes hid the poop. Now tall windows
    with thin bars: at least 20 cm² of window on every container, in windows wide enough to see
    through, yet narrow enough that the poop stays in."""
    assert container.info["windows"] == "slots"
    assert container.info["open_cm2"] >= 20.0, f"{container.name}: only {container.info['open_cm2']} cm² of window"
    assert 6.0 <= cfg["poop_jar"]["slot_width"] <= 9.0
    assert container.info["opening_mm"] >= 20.0
    assert container.info["volume_ml"] >= 60.0


def _fake_poop_eater(tmp_path):
    """A stand-in for a downloaded model: a lattice-like cup and a solid head on top,
    as two overlapping shells in one file (like the real ones)."""
    cup = m3d.Manifold.cylinder(40.0, 28.0, 28.0, 96) - m3d.Manifold.cylinder(40.0, 26.0, 26.0, 96).translate([0, 0, 2.0])
    for k in range(18):
        for z in (10.0, 22.0):
            cup = cup - m3d.Manifold.cube([8.0, 6.0, 6.0], True).translate([27.0, 0, z]).rotate([0, 0, 20.0 * k + (10 if z > 15 else 0)])
    collar = m3d.Manifold.cylinder(8.0, 28.0, 14.0, 96).translate([0, 0, 38.0])
    head = m3d.Manifold.batch_hull([m3d.Manifold.cylinder(1.0, 14.0, 14.0, 96).translate([0, 0, 40.0]),
                                    m3d.Manifold.sphere(22.0, 96).translate([0, 0, 64.0])]).trim_by_plane([0, 0, 1], 40.0)
    meshes = []
    for part in (cup + collar, head):
        mm = part.to_mesh()
        meshes.append(trimesh.Trimesh(np.asarray(mm.vert_properties)[:, :3], np.asarray(mm.tri_verts), process=False))
    path = tmp_path / "fake-eater.stl"
    trimesh.util.concatenate(meshes).export(path)
    return path


def test_screw_top_on_a_downloaded_model(cfg, tmp_path):
    model = load_model(_fake_poop_eater(tmp_path))
    st = add_screw_top(cfg, model, 50.0)
    assert to_trimesh(st.body).is_watertight and to_trimesh(st.lid).is_watertight
    assert count_bodies(st.body) == 1 and count_bodies(st.lid) == 1
    assert (st.body ^ st.lid).volume() < 0.01
    assert unscrew_check(st, cfg["poop_jar"]["thread_lead"]) < 0.01
    assert _stop_angle(st.lid, st.body, *st.axis, cfg["poop_jar"]["thread_lead"]) <= 6.0, "the head stops facing front"
    assert st.info["opening_mm"] >= 18.0
    # The head prints on its cut face; the socket adds nothing that needs support.
    assert overhang_area(st.lid_for_printing()) < 5.0


def test_screw_top_refuses_a_head_too_small(cfg, tmp_path):
    model = load_model(_fake_poop_eater(tmp_path))
    with pytest.raises(ValueError, match="opening"):
        add_screw_top(cfg, model, 41.0)            # the head is narrow just above its base


def test_cli_writes_files(tmp_path):
    assert main(["poop-containers", "--kinds", "heart", "--out", str(tmp_path / "c")]) == 0
    d = tmp_path / "c" / "poop-heart-medium"
    for f in ("poop-heart-medium.3mf", "preview-filled.png", "preview-plate.png", "PRINT_NOTES.md"):
        assert (d / f).exists(), f
    assert main(["screw-top", str(_fake_poop_eater(tmp_path)), "--cut", "50", "--name", "fake", "--out", str(tmp_path / "s")]) == 0
    assert (tmp_path / "s" / "fake" / "fake.3mf").exists()


def test_screw_top_notes_ask_for_supports_when_the_head_needs_them(cfg, tmp_path):
    """The real duck's beak hangs out over the bed and needs the original's tree supports,
    but the notes promised "no supports" for every head. They measure the head now."""
    from charm_maker.screwtop import write_screw_top

    model = load_model(_fake_poop_eater(tmp_path))
    plain = write_screw_top(cfg, add_screw_top(cfg, model, 50.0), tmp_path / "plain", "plain")
    assert "No supports" in (tmp_path / "plain" / "PRINT_NOTES.md").read_text()
    model = load_model(_fake_poop_eater(tmp_path))
    b = model.bounding_box()
    cx, cy = (b[0] + b[3]) / 2, (b[1] + b[4]) / 2
    beak = m3d.Manifold.cube([16.0, 8.0, 6.0], True).translate([cx + 24.0, cy, 66.0])   # sticks out of the head
    duck = model + beak
    write_screw_top(cfg, add_screw_top(cfg, duck, 50.0), tmp_path / "beak", "beak")
    notes = (tmp_path / "beak" / "PRINT_NOTES.md").read_text()
    assert "Enable support" in notes and "No supports" not in notes

