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


def test_neighbouring_colors_never_overlap(cfg):
    """Candy corn: orange, yellow and brown crayon bands interlock along their borders.
    The outline tracer closes gaps under 0.3 mm, so one color's outline closed over the
    neighbour's thin teeth and the color parts overlapped (0.2 mm³ flat, 0.6 mm³ figurine)."""
    import itertools

    from charm_maker.inks import InkLayer
    from charm_maker.products import build_piece
    from charm_maker.shape import fix_design

    ppm = 18.0                                         # real px per mm of a card photo
    h = w = 600
    yy, xx = np.mgrid[0:h, 0:w]
    body = ((xx - 300) ** 2 + (yy - 300) ** 2) < 280 ** 2
    teeth = (xx % 12) < 4                              # 0.2 mm crayon teeth, 0.45 mm apart
    top = (yy < 200) | ((yy < 212) & teeth)
    bottom = (yy >= 400) | ((yy >= 388) & teeth)
    colors = [("orange", (240, 120, 30)), ("yellow", (250, 220, 40)), ("brown", (110, 60, 30))]
    layers = [InkLayer(n, c, body & b) for (n, c), b in zip(colors, [top, ~top & ~bottom, bottom])]
    assert not (layers[0].mask & layers[1].mask).any(), "the pixel masks themselves are disjoint"
    for style in ("flat", "puffy", "figurine"):
        design = fix_design(cfg, [InkLayer(l.name, l.rgb, l.mask.copy()) for l in layers], ppm,
                            border_on=True, name="t", product="magnet_figure")
        for a, b in itertools.combinations(design.inks, 2):
            assert a.geometry.intersection(b.geometry).area < 1e-6, (a.name, b.name)
        piece = build_piece(cfg, design, style=style)
        for a, b in itertools.combinations(piece.parts, 2):
            assert (piece.parts[a] ^ piece.parts[b]).volume() < 1e-3, (style, a, b)


def _notes_style_scan(img, path):
    """An iPhone Notes scan: one photo on a page as many points wide as it has pixels
    (a letter card scanned at 230 dpi becomes a 27 x 36 inch page)."""
    import io

    import pymupdf

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    doc = pymupdf.open()
    page = doc.new_page(width=img.width, height=img.height)
    page.insert_image(page.rect, stream=buf.getvalue())
    doc.save(str(path))
    return path


def test_iphone_notes_scan_finds_all_four_markers(cfg, tmp_path):
    """Test drive 1: a Notes scan PDF was rendered at 300 dpi, blowing the photo up 4x
    (8196 x 10753 px). Markers 900 px wide were missed: 2 of 4 found."""
    from charm_maker.reader import detect_cards, load_image
    from tests.synthetic import card_image

    img, lay, ppm, to_px = card_image(cfg, "hair_clip", 1, tmp_path, dpi=230)
    pdf = _notes_style_scan(img, tmp_path / "scan.pdf")
    page = load_image(pdf)
    assert abs(page.shape[1] - img.width) <= 2, "rendered at the photo's own resolution, not blown up"
    found = detect_cards(cfg, page)
    assert [ci for ci, _ in found[(cfg["cards"]["type_ids"]["hair_clip"], 1)]] == [0, 1, 2, 3]


def test_a_marker_missed_at_full_size_is_found_on_a_smaller_copy(cfg, tmp_path, monkeypatch):
    """The real scan's misses (iPhone sharpening on 900 px markers) don't reproduce on clean
    synthetic cards, so simulate one: the full-size pass loses a marker, the retry on a
    smaller copy must find it, at the right place in full-size pixels."""
    import cv2
    import numpy as np

    from charm_maker.reader import detect_cards
    from tests.synthetic import card_image

    img, *_ = card_image(cfg, "hair_clip", 1, tmp_path, dpi=230)
    page = cv2.resize(cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2BGR), None, fx=2.0, fy=2.0)
    key = (cfg["cards"]["type_ids"]["hair_clip"], 1)
    truth = dict(detect_cards(cfg, page)[key])
    real = cv2.aruco.ArucoDetector

    class Flaky:
        def __init__(self, *a):
            self.d = real(*a)

        def detectMarkers(self, gray):
            corners, ids, rej = self.d.detectMarkers(gray)
            if max(gray.shape) == max(page.shape[:2]) and ids is not None:   # full size: lose one
                return corners[1:], ids[1:], rej
            return corners, ids, rej

    monkeypatch.setattr(cv2.aruco, "ArucoDetector", Flaky)
    found = dict(detect_cards(cfg, page)[key])
    assert sorted(found) == [0, 1, 2, 3]
    for ci, quad in found.items():
        assert np.abs(quad - truth[ci]).max() < 3.0, "corners are in full-size pixels"


def test_a_drawn_color_too_small_to_print_is_reported(cfg, tmp_path):
    """Test drive 1: a cat's pink tongue, 0.6 mm across on a hair clip, silently printed
    black. It may be too small to be its own color, but the run must say so."""
    pink = (236, 120, 160)            # measured from the real scan's tongue
    card = draw_strokes_card(cfg, tmp_path, "hair_clip", 7, [
        ("line", circle_pts(30), GRAY_PEN, 1.6),
        ("line", circle_pts(8, 0, -4, 20, np.pi * 1.15, np.pi * 1.85), GRAY_PEN, 1.4),    # the mouth
        ("dot", (0, -12), pink, 2.2),                                                   # the tongue
        ("dot", (-10, 8), GRAY_PEN, 3.0), ("dot", (10, 8), GRAY_PEN, 3.0),
    ], "tongue.jpg")
    r = run_batch(cfg, [card], tmp_path / "out")
    warnings = r.pieces[0].design.warnings
    assert any("small pink mark" in w and "too small to print" in w for w in warnings), warnings


def test_no_small_mark_warning_on_plain_drawings(run):
    """Camera fringe and pale fill are not reported as lost marks."""
    for p in run.pieces:
        assert not any("small" in w and "mark" in w for w in p.design.warnings), (p.name, p.design.warnings)


def test_a_slanted_whisker_is_not_a_speck():
    """Test drive 2: short slanted whiskers (1.7 mm long, 0.4 mm wide at real size) were
    removed as specks: measured upright they looked 1.44 mm, under the 1.5 mm that
    protects thin strokes. A round dot of the same area is still a speck."""
    import cv2

    from charm_maker.shape import remove_specks

    ppm = 18.0
    mask = np.zeros((200, 200), np.uint8)
    a, b = np.array([60.0, 60.0]), np.array([60.0, 60.0]) + 1.3 * ppm / np.sqrt(2)     # 45 degrees
    cv2.line(mask, tuple(int(v) for v in a), tuple(int(v) for v in b), 1, int(round(0.4 * ppm)))
    cv2.circle(mask, (150, 150), int(round(0.45 * ppm)), 1, -1)                       # a dot
    whisker, dot = mask[:110, :110].sum() / ppm ** 2, mask[110:, 110:].sum() / ppm ** 2
    assert whisker < 1.0 and dot < 1.0, "both are under the 1 mm² speck size"
    ys, xs = np.nonzero(mask[:110, :110])
    assert max(np.ptp(xs), np.ptp(ys)) + 1 < 1.5 * ppm, "upright, the whisker looks shorter than 1.5 mm"
    kept, removed = remove_specks(mask.astype(bool), 1.0 * ppm ** 2, 1.5 * ppm)
    assert kept[:110, :110].any(), "the whisker stays"
    assert not kept[110:, 110:].any() and removed == 1, "the dot goes"


def test_a_small_textured_color_is_kept(cfg, tmp_path):
    """Test drive 3: a brown house with a yellow window (7.8 mm² at real size) printed
    brown. The marker's yellow was spread over 156 slightly different shades and no
    single shade was big enough to start a color. (A first fix that pooled every shade
    split the real garlic drawing's blue pen into blue and black; only shades clearly
    unlike every color found are pooled now. Check with tools/try_real_drawings.py.)"""
    from PIL import ImageDraw

    from tests.synthetic import card_image, photograph

    img, lay, ppm, P = card_image(cfg, "hair_clip", 8, tmp_path)
    bx, by, bw, bh = lay.box
    cx, cy = bx + bw / 2, by + bh / 2
    d = ImageDraw.Draw(img)
    d.rectangle([P(cx - 25, cy + 25), P(cx + 25, cy - 25)], fill=(110, 60, 30), outline=(25, 25, 30),
                width=int(round(2.0 * ppm)))
    # The window: 6 x 10 card mm (6.7 mm² real), marker yellow with uneven texture in every
    # channel, spread over about 190 shades like the real scan's 156; no shade is big.
    x0, y0 = (int(v) for v in P(cx - 3, cy + 5))
    x1, y1 = (int(v) for v in P(cx + 3, cy - 5))
    arr = np.asarray(img).copy()
    rng = np.random.default_rng(5)
    h, w, block = y1 - y0, x1 - x0, 3
    noise = rng.normal(0, 40, ((h + block - 1) // block, (w + block - 1) // block, 3))
    noise = np.kron(noise, np.ones((block, block, 1)))[:h, :w]
    arr[y0:y1, x0:x1] = np.clip(np.array([245, 215, 40], float) + noise, 0, 255).astype(np.uint8)
    from PIL import Image

    card = photograph(Image.fromarray(arr), tmp_path / "window.jpg", seed=4)
    r = run_batch(cfg, [card], tmp_path / "out")
    names = [i.name for i in r.pieces[0].design.inks]
    assert any("yellow" in n for n in names), names


def test_pencil_is_ink_but_show_through_is_not(cfg, tmp_path):
    """Test drive 4: a butterfly and a rainbow drawn in pencil were mostly lost (gray marks
    were not ink). A grainy pencil circle must be found; a very faint drawing showing
    through from the back of the page must not."""
    import cv2
    from PIL import Image

    from tests.synthetic import card_image, photograph

    img, lay, ppm, P = card_image(cfg, "keychain", 9, tmp_path)
    bx, by, bw, bh = lay.box
    cx, cy = bx + bw / 2, by + bh / 2
    arr = np.asarray(img).copy()
    rng = np.random.default_rng(7)
    # Pencil: a 60 card-mm circle (20 mm real), graphite gray, grainy (a third of it skips).
    pencil = np.zeros(arr.shape[:2], np.uint8)
    c = tuple(int(v) for v in P(cx - 15, cy))
    cv2.circle(pencil, c, int(round(30 * ppm)), 1, max(2, int(round(0.9 * ppm))))
    grain = rng.random(arr.shape[:2]) > 0.33
    tone = np.clip(rng.normal(160, 18, arr.shape[:2]), 90, 230)
    sel = (pencil > 0) & grain
    arr[sel] = np.repeat(tone[sel][:, None], 3, axis=1).astype(np.uint8)
    # Show-through: a soft, very light circle to the right.
    ghost = np.zeros(arr.shape[:2], np.float32)
    cv2.circle(ghost, tuple(int(v) for v in P(cx + 28, cy)), int(round(10 * ppm)), 1.0, int(round(1.2 * ppm)))
    ghost = cv2.GaussianBlur(ghost, (0, 0), 2.0)
    arr = np.clip(arr.astype(np.float32) - ghost[..., None] * 16, 0, 255).astype(np.uint8)
    card = photograph(Image.fromarray(arr), tmp_path / "pencil.jpg", seed=8)
    r = run_batch(cfg, [card], tmp_path / "out")
    assert r.problems == [], r.problems
    p = r.pieces[0]
    minx, miny, maxx, maxy = p.design.outline.bounds
    border = cfg["process"]["border"]
    assert maxx - minx == pytest.approx(20 + 2 * border, abs=1.5), "the pencil circle is the whole piece"
    assert p.design.inks and p.design.inks[0].geometry.area > 30, "the pencil line is there, all the way round"


def _face(px_per_mm):
    """Test drive 3's face, at hair clip size: two 0.5 mm eyes and a thin mouth 0.33 mm
    below them, black on a brown face."""
    import cv2

    mm = lambda v: int(round(v * px_per_mm))                                        # noqa: E731
    h = w = mm(12)
    black = np.zeros((h, w), np.uint8)
    for x in (4.5, 7.5):
        cv2.circle(black, (mm(x), mm(4.5)), mm(0.27), 1, -1)
    eye_bottom = 4.5 + 0.27
    mouth_y = eye_bottom + 0.33 + 0.17
    cv2.line(black, (mm(4.0), mm(mouth_y)), (mm(8.0), mm(mouth_y)), 1, mm(0.33))
    brown = np.zeros((h, w), np.uint8)
    cv2.rectangle(brown, (mm(1), mm(1)), (mm(11), mm(9)), 1, -1)
    brown &= ~black.astype(bool)
    return black.astype(bool), brown.astype(bool)


@pytest.mark.parametrize("tidy", [False, True])
def test_eyes_next_to_a_mouth_stay_eyes(cfg, tidy):
    """Test drive 3: on a 22 mm hair clip the brown creature's 0.5 mm eyes sat 0.3 mm above
    its mouth. Thickening every line to 1 mm merged eyes and mouth into one blob. Separate
    marks now keep the gap they were drawn with."""
    from charm_maker.inks import InkLayer
    from charm_maker.shape import fix_design

    ppm = 18.0
    black, brown = _face(ppm)
    layers = [InkLayer("black", (25, 25, 30), black), InkLayer("brown", (110, 60, 30), brown)]
    d = fix_design(cfg, layers, ppm, border_on=True, name="t", product="hair_clip", tidy=tidy)
    ink = next(i for i in d.inks if i.name == "black").geometry
    assert len(ink.geoms) >= 3, f"two eyes and a mouth, not {len(ink.geoms)} blob(s)"
