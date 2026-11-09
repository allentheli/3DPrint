"""Lessons from real kids' drawings (the MIT-licensed Amateur Drawings examples, run
locally with tools/try_real_drawings.py). Each test rebuilds one real-world failure on a
synthetic card so it stays fixed: faint pens, thin smiles, crayon gaps, small dark eyes
among similar colors, light-blue pens near the guides, and pale inks starting on white."""

import numpy as np
import pytest

from charm_maker.pipeline import run_batch
from tests.synthetic import draw_strokes_card

FAINT_PINK = (222, 138, 162)      # measured from a real thin pink pen photo
LIGHT_BLUE = (120, 160, 225)
GRAY_PEN = (70, 70, 75)
ORANGE = (246, 124, 43)
ORANGE_2 = (253, 180, 28)
PEACH = (249, 200, 150)
YELLOW = (251, 240, 80)
EYES = (84, 71, 49)


def circle_pts(r, cx=0.0, cy=0.0, n=60, a0=0.0, a1=2 * np.pi):
    return [(cx + r * np.cos(t), cy + r * np.sin(t)) for t in np.linspace(a0, a1, n)]


@pytest.fixture(scope="module")
def run(cfg, tmp_path_factory):
    d = tmp_path_factory.mktemp("realworld")
    cards = [
        # A faint thin pink pen pig body: only a 0.5 mm card line (0.17 mm real).
        draw_strokes_card(cfg, d, "keychain", 11 - 10, [("line", circle_pts(55), FAINT_PINK, 0.5)], "faint.jpg"),
        # A thin gray pen face with a small smile and two dot eyes.
        draw_strokes_card(cfg, d, "pendant", 2, [
            ("line", circle_pts(40), GRAY_PEN, 0.6),
            ("line", circle_pts(14, 0, -6, 20, np.pi * 1.15, np.pi * 1.85), GRAY_PEN, 0.6),   # the smile
            ("dot", (-12, 10), GRAY_PEN, 3.0), ("dot", (12, 10), GRAY_PEN, 3.0),
        ], "smile.jpg"),
        # Crayon: a disc colored in with strokes that leave 0.9 mm card slivers of paper.
        draw_strokes_card(cfg, d, "magnet_figure", 3, [("crayon", circle_pts(55), ORANGE, 0.9)], "crayon.jpg"),
        # Over the color limit: three near-identical oranges/yellows plus small dark eyes.
        draw_strokes_card(cfg, d, "magnet_figure", 4, [
            ("crayon", [(-60, -60), (0, -60), (0, 0), (-60, 0)], ORANGE, 0.0),
            ("crayon", [(0, -60), (60, -60), (60, 0), (0, 0)], ORANGE_2, 0.0),
            ("crayon", [(-60, 0), (0, 0), (0, 60), (-60, 60)], PEACH, 0.0),
            ("crayon", [(0, 0), (60, 0), (60, 60), (0, 60)], YELLOW, 0.0),
            ("dot", (-20, 30), EYES, 12.0), ("dot", (20, 30), EYES, 12.0),
        ], "eyes.jpg"),
        # A light-blue pen in a corner of a hair clip card, away from the printed guides.
        draw_strokes_card(cfg, d, "hair_clip", 5, [
            ("line", [(-30, 30), (-10, 32), (5, 28)], LIGHT_BLUE, 1.2),
            ("line", circle_pts(22, -15, 10), LIGHT_BLUE, 1.2),
        ], "lightblue.jpg"),
    ]
    return run_batch(cfg, cards, d / "out")


def _piece(run, name):
    return next(p for p in run.pieces if p.name == name)


def _parts(run, name):
    """Part short name -> starting filament name."""
    p = _piece(run, name)
    plate = next(pl for pl in run.plates if any(pp.piece is p for pp in pl.pieces))
    a = next(pp.assignments for pp in plate.pieces if pp.piece is p)
    return {n.split(" ", 1)[1]: f.name for n, f in a.items()}


def test_every_card_becomes_a_piece(run):
    assert run.problems == []
    assert sorted(p.name for p in run.pieces) == ["clip-05", "fig-03", "fig-04", "key-01", "pend-02"]


def test_faint_thin_pen_is_found_and_starts_on_its_color(run):
    parts = _parts(run, "key-01")
    inks = {k: v for k, v in parts.items() if k != "base"}
    assert inks and all(v == "Pink" for v in inks.values()), parts
    ring = sum(i.geometry.area for i in _piece(run, "key-01").design.inks)
    # A 37 mm circle of 1 mm line is about 115 mm²; most of it must be there.
    assert ring > 80


def test_thin_smile_survives(run):
    p = _piece(run, "pend-02")
    from shapely.geometry import box
    ink = p.design.inks[0].geometry
    # The smile sits between the eyes and the chin: some ink must be in that band.
    minx, miny, maxx, maxy = p.design.outline.bounds
    cx = (minx + maxx) / 2
    cy = (miny + maxy) / 2 - 3.0           # outline includes the loop; drawing center is lower
    band = box(cx - 4, cy - 6, cx + 4, cy - 1)
    assert ink.intersection(band).area > 1.0
    assert _parts(run, "pend-02")[p.design.inks[0].name] == "Black"


def test_crayon_slivers_are_filled(run):
    p = _piece(run, "fig-03")
    assert any("gaps in the coloring" in f for f in p.design.fixes)
    orange = next(i for i in p.design.inks if i.name != "base")
    # The colored-in disc (about 37 mm across) is nearly solid, not striped.
    assert len(list(orange.geometry.geoms)) <= 3
    disc_area = np.pi * (55 / 3) ** 2
    assert orange.geometry.area > 0.85 * disc_area


def test_small_dark_eyes_survive_the_color_limit(run):
    parts = _parts(run, "fig-04")
    inks = {k: v for k, v in parts.items() if k != "base"}
    assert len(inks) <= 3
    assert "Black" in inks.values(), parts
    assert any("most alike" in w for w in _piece(run, "fig-04").design.warnings)


def test_light_blue_pen_near_guides_is_kept(run):
    p = _piece(run, "clip-05")
    inks = {k: v for k, v in _parts(run, "clip-05").items() if k != "base"}
    assert inks and set(inks.values()) <= {"Blue", "Purple"}, inks
    # The printed "cover the circle" guide must not show up as ink.
    total = sum(i.geometry.area for i in p.design.inks)
    assert total < 120
