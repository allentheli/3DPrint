"""Tidy: the outline's own strokes redrawn at one even thickness with smooth edges;
dots, blobs and colored-in areas keep their shape. Off unless asked for."""

import cv2
import numpy as np
import pytest
from skimage.morphology import skeletonize

from charm_maker.inks import InkLayer
from charm_maker.pipeline import run_batch
from charm_maker.shape import fix_design
from tests.synthetic import BLACK, PINK, YELLOW, draw_blob_card

PPM = 18.0          # px per real mm, as on a card photo


def _canvas():
    return np.zeros((720, 720), np.uint8)


def _wobbly_ring(mask, cx, cy, r_mm, rng):
    """A hand-drawn circle: the line width wanders between 0.5 and 1.6 mm and the edge is jagged."""
    for t in np.linspace(0, 2 * np.pi, 400, endpoint=False):
        w = 1.05 + 0.55 * np.sin(5 * t) + rng.normal(0, 0.15)
        x = cx + r_mm * PPM * np.cos(t) + rng.normal(0, 3.0)
        y = cy + r_mm * PPM * np.sin(t) + rng.normal(0, 3.0)
        cv2.circle(mask, (int(x), int(y)), max(1, int(round(w * PPM / 2))), 1, -1)


def _widths(mask):
    """Stroke widths (mm) measured along the middle of the line."""
    skel = skeletonize(mask)
    dist = cv2.distanceTransform(mask.astype(np.uint8), cv2.DIST_L2, 5)
    return 2.0 * dist[skel] / PPM


def _black(design):
    return next(i for i in design.inks if i.name == "black")


def _raster(geom):
    m = _canvas()
    for p in getattr(geom, "geoms", [geom]):
        pts = np.array([(x * PPM, 720 - y * PPM) for x, y in p.exterior.coords], np.int32)
        cv2.fillPoly(m, [pts], 1)
        for r in p.interiors:
            cv2.fillPoly(m, [np.array([(x * PPM, 720 - y * PPM) for x, y in r.coords], np.int32)], 0)
    return m.astype(bool)


def _design(cfg, layers, tidy):
    copies = [InkLayer(l.name, l.rgb, l.mask.copy()) for l in layers]
    return fix_design(cfg, copies, PPM, border_on=True, name="t", product="keychain", tidy=tidy)


def test_strokes_get_one_even_width(cfg):
    m = _canvas()
    _wobbly_ring(m, 360, 360, 12, np.random.default_rng(1))
    layers = [InkLayer("black", (25, 25, 30), m.astype(bool))]
    plain, tidy = _design(cfg, layers, False), _design(cfg, layers, True)
    before = _widths(_raster(_black(plain).geometry))
    after = _widths(_raster(_black(tidy).geometry))
    assert np.std(after) < 0.5 * np.std(before), "the line width no longer wanders"
    w = float(np.median(after))
    assert cfg["process"]["min_ink_width"] - 0.1 <= w <= cfg["tidy"]["max_line_width"] + 0.1
    assert any(f.startswith("tidy:") for f in tidy.fixes)
    # Smooth edges: a jagged edge makes the outline longer than a smooth ring's
    # (inner and outer circles, about 2 x 2 pi x 12 mm). Tidy at least halves the excess.
    ideal = 2 * 2 * np.pi * 12
    assert _black(tidy).geometry.length - ideal < 0.5 * (_black(plain).geometry.length - ideal)


def test_eyes_and_a_short_mouth_survive(cfg):
    m = _canvas()
    _wobbly_ring(m, 360, 360, 14, np.random.default_rng(2))
    eyes = [(300, 320), (420, 320)]
    for e in eyes:
        cv2.circle(m, e, int(1.1 * PPM), 1, -1)                                   # 2.2 mm eyes
    cv2.line(m, (340, 420), (360, 440), 1, int(0.5 * PPM))                       # a short "v" mouth
    cv2.line(m, (360, 440), (380, 420), 1, int(0.5 * PPM))
    tidy = _design(cfg, [InkLayer("black", (25, 25, 30), m.astype(bool))], True)
    ink = _raster(_black(tidy).geometry)
    for x, y in eyes:
        eye = ink[y - 30:y + 30, x - 30:x + 30].sum() / PPM ** 2
        assert eye == pytest.approx(np.pi * 1.1 ** 2, rel=0.25), "eyes keep their size"
    assert ink[425:445, 345:375].any(), "the mouth is still there"


def test_colors_fill_up_to_a_thinner_outline(cfg):
    """A colored-in area inside a bold outline: the color keeps its shape and meets the
    (now thinner, even) outline with no white gap, like a sticker."""
    outline = _canvas()
    cv2.rectangle(outline, (200, 200), (520, 520), 1, int(2.4 * PPM))          # a bold 2.4 mm line
    fill = _canvas()
    cv2.rectangle(fill, (225, 225), (495, 495), 1, -1)
    fill &= ~outline.astype(bool)
    layers = [InkLayer("black", (25, 25, 30), outline.astype(bool)), InkLayer("yellow", (245, 215, 40), fill.astype(bool))]
    plain, tidy = _design(cfg, layers, False), _design(cfg, layers, True)
    from shapely.geometry import box
    from shapely.ops import unary_union

    yellow = lambda d: next(i for i in d.inks if i.name == "yellow")              # noqa: E731
    assert yellow(tidy).geometry.area >= 0.97 * yellow(plain).geometry.area
    # Inside the outline's middle line, a thinner outline must not leave white. Traced
    # colors always sit one pixel (0.06 mm) apart, far below what the nozzle can print.
    inside = box(200 / PPM, (720 - 520) / PPM, 520 / PPM, (720 - 200) / PPM)
    gap = lambda d: inside.difference(unary_union([_black(d).geometry, yellow(d).geometry]).buffer(1 / PPM)).area  # noqa: E731
    assert gap(tidy) < 0.5, "no white gap between the outline and the color"
    assert gap(tidy) < gap(plain), "the sliver she left between coloring and outline is closed too"

def test_tidy_is_off_unless_asked_and_works_per_card(cfg, tmp_path):
    a = draw_blob_card(cfg, tmp_path, "hair_clip", 3, BLACK, YELLOW)
    b = draw_blob_card(cfg, tmp_path, "keychain", 4, BLACK, PINK)
    r = run_batch(cfg, [a, b], tmp_path / "out", tidy={"key-04"})
    tidied = {p.name: any(f.startswith("tidy:") for f in p.design.fixes) for p in r.pieces}
    assert tidied == {"clip-03": False, "key-04": True}
    r = run_batch(cfg, [a, b], tmp_path / "out2")
    assert not any(f.startswith("tidy:") for p in r.pieces for f in p.design.fixes)


def test_cli_tidy_flag(cfg, tmp_path):
    import json

    from charm_maker.cli import main

    a = draw_blob_card(cfg, tmp_path, "hair_clip", 3, BLACK, YELLOW)
    b = draw_blob_card(cfg, tmp_path, "keychain", 4, BLACK, PINK)

    def tidied(out):
        return {n: any(f.startswith("tidy:") for f in json.loads((out / "designs" / f"{n}.json").read_text())["fixes"])
                for n in ("clip-03", "key-04")}

    assert main(["run", str(a), str(b), "--out", str(tmp_path / "one"), "--tidy", "key-04"]) == 0
    assert tidied(tmp_path / "one") == {"clip-03": False, "key-04": True}
    assert main(["run", str(a), str(b), "--out", str(tmp_path / "all"), "--tidy"]) == 0
    assert tidied(tmp_path / "all") == {"clip-03": True, "key-04": True}
