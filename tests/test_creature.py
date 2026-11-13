"""Flexi creatures from the ready-made parts: every piece one solid, linked but not touching, each
joint turning freely, legs only on their own piece, and the kid's face painted on the head."""

import cv2
import numpy as np
import pytest
from PIL import Image, ImageDraw

from charm_maker import creature as flexi
from charm_maker.cli import main
from charm_maker.inks import separate_colors

BLACK, PINK, WHITE = (20, 20, 20), (240, 110, 150), (255, 255, 255)


def _cat_face(cfg) -> np.ndarray:
    """A kid-style face drawn with markers on the cat's face guide (BGR)."""
    guide, (u0, u1, v0, v1) = flexi.face_guide(cfg, "cat")
    im = Image.fromarray(guide)
    d = ImageDraw.Draw(im)
    P = lambda y, z: ((y - u0) * flexi.GUIDE_PPM, (v1 - z) * flexi.GUIDE_PPM)   # noqa: E731
    for s in (1, -1):
        d.ellipse([P(s * 3.6 - 1.6, 13.6), P(s * 3.6 + 1.6, 10.6)], fill=BLACK)        # eyes
        d.ellipse([P(s * 3.6 + 0.2, 13.1), P(s * 3.6 + 0.9, 12.4)], fill=WHITE)        # shine
        d.ellipse([P(s * 6.6 - 1.5, 8.6), P(s * 6.6 + 1.5, 6.0)], fill=PINK)           # cheeks
    d.polygon([P(-1.1, 9.4), P(1.1, 9.4), P(0, 8.2)], fill=PINK, outline=BLACK, width=8)
    d.line([P(0, 8.2), P(0, 7.2)], fill=BLACK, width=12)
    return cv2.cvtColor(np.asarray(im), cv2.COLOR_RGB2BGR)


@pytest.fixture(scope="module")
def cat(cfg):
    return flexi.build_toy(cfg, "cat", "regular", "paws", "cat", face=_cat_face(cfg), name="t-cat")


def test_a_full_toy_is_linked_pieces_that_turn(cat):
    assert list(cat.pieces) == ["head", "chest", "torso", "hips", "tail"]
    assert len(cat.joints) == 4
    # Nothing to fix: one solid each, no overlaps, nothing close enough to fuse, every joint
    # turns its full swing. Only the untested joint gap is flagged.
    assert [c for c in cat.checks if "not tested" not in c] == []
    for joint, (left, right) in cat.info["swing_deg"].items():
        assert 30 <= left <= 45 and 30 <= right <= 45, joint
    w = cat.size()
    assert 90 < w[0] < 105 and 30 < w[1] < 40 and 18 < w[2] < 25


def test_the_face_is_painted_on_the_front_of_the_head(cfg, cat):
    assert set(cat.paint) == {"head black", "head pink"}
    plain = flexi.build_toy(cfg, "cat", "short", "none", "none", name="plain", checks=False)
    # The paint is a skin of the head, not an addition to it.
    whole = cat.pieces["head"].volume() + sum(p.volume() for p in cat.paint.values())
    assert whole == pytest.approx(plain.pieces["head"].volume(), rel=0.01)
    for part in cat.paint.values():
        bb = part.bounding_box()
        assert bb[0] > 10.0                          # on the face, not on the neck or the back
        assert part.volume() > 5.0


def test_legs_stay_on_their_own_piece(cfg):
    paws = flexi.build_toy(cfg, "cat", "regular", "paws", "cat", name="p", checks=False)
    bare = flexi.build_toy(cfg, "cat", "regular", "none", "cat", name="b", checks=False)
    assert paws.pieces["chest"].volume() > bare.pieces["chest"].volume() + 500
    assert paws.pieces["hips"].volume() > bare.pieces["hips"].volume() + 500
    for n in ("head", "torso", "tail"):
        assert paws.pieces[n].volume() == pytest.approx(bare.pieces[n].volume(), abs=0.5), n
    assert paws.size()[1] > bare.size()[1] + 12      # the paws stick out well past the body


@pytest.mark.parametrize("head,body,legs,tail,n", [("fish", "short", "none", "fin", 4),
                                                   ("bunny", "long", "paws", "none", 7)])
def test_other_combinations_build(cfg, head, body, legs, tail, n):
    toy = flexi.build_toy(cfg, head, body, legs, tail, name="t")
    assert len(toy.pieces) == n
    assert [c for c in toy.checks if "not tested" not in c] == []


def test_a_blank_face_guide_reads_as_no_drawing(cfg):
    for head in flexi.HEADS:
        guide, _ = flexi.face_guide(cfg, head)
        bgr = cv2.cvtColor(guide, cv2.COLOR_RGB2BGR)
        inks = separate_colors(cfg, bgr, px_per_mm=flexi.GUIDE_PPM, guide_zone=np.ones(bgr.shape[:2], bool))
        assert sum(int(layer.mask.sum()) for layer in inks.layers) < 50, head


def test_a_body_too_wide_for_its_joints_is_flagged(cfg, monkeypatch):
    """A body wider than the round ends: at the seams the pieces touch, and they bump at once."""
    def wide(n, L, zm):
        return [[flexi.ellipsoid((-(i + 0.5) * L, 0, zm), (20.0, 11.5, 8.0), k=3.0)] for i in range(n)]
    monkeypatch.setattr(flexi, "body_shapes", wide)
    toy = flexi.build_toy(cfg, "cat", "short", "none", "none", name="w")
    assert any("could fuse" in c or "overlap" in c for c in toy.checks)
    assert any("turns only" in c for c in toy.checks)


def test_creature_command_writes_the_files(tmp_path, cfg):
    face = tmp_path / "face.png"
    cv2.imwrite(str(face), _cat_face(cfg))
    assert main(["creature", "--head", "cat", "--body", "short", "--legs", "paws", "--tail", "none",
                 "--face", str(face), "--name", "mia", "--out", str(tmp_path)]) == 0
    out = tmp_path / "mia"
    for f in ("mia.3mf", "mia-preview.png", "PRINT_NOTES.md", "mia.json"):
        assert (out / f).exists(), f
    notes = (out / "PRINT_NOTES.md").read_text()
    assert "Supports: off" in notes and "On build plate only" in notes and "wiggle each joint" in notes
