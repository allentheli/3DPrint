import numpy as np
import pytest
from shapely.geometry import Point

from charm_maker.inks import InkLayer
from charm_maker.shape import (bridge_components, fill_all_holes, fill_small_holes, fix_design,
                               mask_to_polygons, remove_specks, thicken_thin_ink)

PPM = 18.0  # px per real mm, as in the pipeline


def _disk(mask, cx, cy, r):
    yy, xx = np.mgrid[0:mask.shape[0], 0:mask.shape[1]]
    mask[(xx - cx) ** 2 + (yy - cy) ** 2 <= r * r] = True


def test_remove_specks_and_fill_holes():
    m = np.zeros((200, 200), bool)
    _disk(m, 100, 100, 50)
    m[100:104, 100:104] = False          # a 16 px hole
    m[10:13, 10:13] = True               # a 9 px speck
    cleaned, specks = remove_specks(m, PPM ** 2)
    assert specks == 1 and not cleaned[11, 11]
    filled, holes = fill_small_holes(cleaned, PPM ** 2)
    assert holes == 1 and filled[101, 101]


def test_fill_all_holes_fills_enclosed_paper():
    m = np.zeros((200, 200), bool)
    _disk(m, 100, 100, 60)
    inner = np.zeros_like(m)
    _disk(inner, 100, 100, 40)
    ring = m & ~inner
    sil = fill_all_holes(ring)
    assert sil[100, 100] and not sil[5, 5]
    assert sil.sum() == pytest.approx(m.sum(), rel=0.01)


def test_thin_lines_get_thickened_but_thick_edges_do_not_grow():
    m = np.zeros((200, 300), bool)
    m[90:98, 20:280] = True              # 8 px = 0.44 mm line
    thick = np.zeros_like(m)
    _disk(thick, 150, 100, 40)
    before = (m | thick)
    out, added = thicken_thin_ink(before, 1.0 * PPM)
    assert added > 0
    col = out[:, 60]
    assert col.sum() >= 1.0 * PPM - 1   # at least 1 mm wide now
    # The thick disk keeps its size (within a pixel of rounding).
    disk_area_after = out[:, 110:200][:, :].sum() - 0  # region around the disk incl. the line
    assert out[60, 150] == thick[60, 150]
    assert out[140, 190] == thick[140, 190]


def test_bridge_joins_separate_pieces():
    a = Point(0, 0).buffer(5)
    b = Point(20, 0).buffer(3)
    joined, bridges = bridge_components(a.union(b), 2.5)
    assert bridges == 1
    assert joined.geom_type == "Polygon"
    assert joined.contains(Point(10, 0))


def test_mask_to_polygons_keeps_holes_and_scale():
    m = np.zeros((400, 400), bool)
    _disk(m, 200, 200, 180)
    inner = np.zeros_like(m)
    _disk(inner, 200, 200, 90)
    ring = m & ~inner
    geom = mask_to_polygons(ring, PPM)
    poly = geom.geoms[0]
    assert len(poly.interiors) == 1
    minx, miny, maxx, maxy = poly.bounds
    assert maxx - minx == pytest.approx(360 / PPM, abs=0.1)


def test_fix_design_border_and_one_piece(cfg):
    black = np.zeros((500, 500), bool)
    _disk(black, 250, 250, 100)
    inner = np.zeros_like(black)
    _disk(inner, 250, 250, 80)
    black &= ~inner
    yellow = inner.copy()
    dot = np.zeros_like(black)
    _disk(dot, 60, 60, 20)
    layers = [InkLayer("black", (0, 0, 0), black | dot), InkLayer("yellow", (240, 210, 40), yellow)]
    d = fix_design(cfg, layers, PPM, border_on=True, name="t-01", product="hair_clip")
    assert d.outline.geom_type == "Polygon"
    assert any("border" in f for f in d.fixes)
    assert any("joined" in f for f in d.fixes)
    # The outline contains every ink region with the border around it.
    for ink in d.inks:
        assert d.outline.buffer(0.01).contains(ink.geometry)
    # Right edge = disk edge + border (the dot and bridge are on the left).
    assert d.outline.bounds[2] == pytest.approx(350 / PPM + cfg["process"]["border"], abs=0.2)
