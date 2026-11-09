"""Milestone 2: loaded slots, calibration, palette matching, the off-palette question,
half-drawn cards, the party batch, and the filament chips."""

import shutil
import zipfile

import pymupdf
import pytest

from charm_maker.cards import half_drawn_numbers, write_calibration_pdf, write_cards_pdf
from charm_maker.chips import build_chips, estimate_minutes, write_chips
from charm_maker.config import DEFAULT_CONFIG, load_config
from charm_maker.geom import count_bodies, to_trimesh
from charm_maker.palette import color_distance, load_palette, save_calibration, set_slot
from charm_maker.pipeline import run_batch
from tests.synthetic import (BLACK, BLUE, ORANGE, PINK, YELLOW, draw_blob_card, draw_calibration_card,
                             draw_cat_card, draw_half_drawn_card, draw_heart_keychain)

LOADED = [(1, "White PLA", "#F2F2F2"), (2, "Black PLA", "#1A1A1A"), (3, "Yellow PLA", "#FCBF49"), (4, "Pink PLA", "#EC4899")]


@pytest.fixture()
def cfg_path(tmp_path):
    p = tmp_path / "config.yaml"
    shutil.copy(DEFAULT_CONFIG, p)
    for slot, name, color in LOADED:
        set_slot(p, slot, name, color)
    return p


@pytest.fixture(scope="module")
def party(tmp_path_factory):
    """Calibration card plus eight drawings, run in one request, like the party."""
    d = tmp_path_factory.mktemp("party")
    cfg_p = d / "config.yaml"
    shutil.copy(DEFAULT_CONFIG, cfg_p)
    for slot, name, color in LOADED:
        set_slot(cfg_p, slot, name, color)
    cfg = load_config(cfg_p)
    photos = d / "photos"
    photos.mkdir()
    draw_calibration_card(cfg, load_palette(cfg), photos, {2: BLACK, 3: YELLOW, 4: PINK})
    draw_cat_card(cfg, photos, number=3)
    draw_blob_card(cfg, photos, "hair_clip", 4, BLACK, PINK)
    draw_blob_card(cfg, photos, "hair_clip", 5, PINK, YELLOW)
    draw_blob_card(cfg, photos, "keychain", 1, BLACK, YELLOW, extra=(PINK, 0, 0, 12))
    draw_heart_keychain(cfg, photos, number=2)
    draw_half_drawn_card(cfg, photos, "hair_clip", 12, PINK)
    draw_half_drawn_card(cfg, photos, "hair_clip", 14, YELLOW)
    draw_half_drawn_card(cfg, photos, "keychain", 13, YELLOW)
    result = run_batch(cfg, [photos], d / "out", config_path=cfg_p)
    return result, cfg_p


# --- loaded slots ---------------------------------------------------------

def test_load_command_keeps_comments_and_clears_calibration(cfg_path):
    before = cfg_path.read_text()
    assert "# Spools Allen owns" in before
    save_calibration(cfg_path, {4: (237, 78, 138)})
    assert load_palette(load_config(cfg_path)).slots[4].marker_rgb == (237, 78, 138)
    msg = set_slot(cfg_path, 4, "Blue PLA", "#1D4ED8")
    assert "Rescan the calibration card" in msg
    pal = load_palette(load_config(cfg_path))
    assert pal.slots[4].filament.name == "Blue PLA" and pal.slots[4].marker_rgb is None
    set_slot(cfg_path, 4, "empty")
    assert 4 not in load_palette(load_config(cfg_path)).slots
    after = cfg_path.read_text()
    for marker in ("# Spools Allen owns", "# Matching kid ink", "# Fit-critical values", "off_palette_distance"):
        assert marker in after


def test_white_is_the_base_and_needs_no_marker(cfg_path):
    pal = load_palette(load_config(cfg_path))
    assert pal.base_slot().slot == 1
    assert [s.slot for s in pal.ink_slots()] == [2, 3, 4]


# --- cards ----------------------------------------------------------------

def test_kid_cards_carry_the_new_rules(cfg_path, tmp_path):
    cfg = load_config(cfg_path)
    pdf = write_cards_pdf(cfg, ["hair_clip"], tmp_path / "c.pdf", count=1)
    text = pymupdf.open(str(pdf))[0].get_text()
    for rule in ("Use the colors in the printer", "Big and bold", "Color it in"):
        assert rule in text
    for old in ("black + 1 color", "no pencil", "fat marker"):
        assert old not in text


def test_half_drawn_cards_and_calibration_card(cfg_path, tmp_path):
    cfg = load_config(cfg_path)
    nums = half_drawn_numbers(cfg)
    assert nums[0] == 11 and len(nums) == 10
    pdf = write_cards_pdf(cfg, ["hair_clip", "keychain"], tmp_path / "h.pdf", numbers=nums)
    assert pymupdf.open(str(pdf)).page_count == 20
    cal = write_calibration_pdf(cfg, load_palette(cfg), tmp_path / "cal.pdf")
    text = pymupdf.open(str(cal))[0].get_text()
    assert "Slot 3" in text and "Yellow PLA" in text and "white is the paper" in text


# --- calibration and matching ---------------------------------------------

def test_calibration_scan_stores_marker_colors(party):
    result, cfg_p = party
    pal = load_palette(load_config(cfg_p))
    assert pal.calibrated
    assert color_distance(pal.slots[3].marker_rgb, YELLOW) < 12
    assert color_distance(pal.slots[4].marker_rgb, PINK) < 12
    assert any("slot 3" in line for line in result.calibration)


def test_party_batch_is_one_plate_with_loaded_spools(party):
    result, _ = party
    assert result.problems == [] and result.question is None
    assert len(result.pieces) == 8
    assert len(result.plates) == 1 and not result.plates[0].swaps
    loaded = {"White PLA": 1, "Black PLA": 2, "Yellow PLA": 3, "Pink PLA": 4}
    for f, slot in result.plates[0].slots().items():
        assert loaded[f.name] == slot
    notes = result.files["notes"].read_text()
    assert "No spool swaps" in notes


def test_inks_land_on_the_right_slots(party):
    result, _ = party
    by_name = {p.name: p for p in result.pieces}
    def slots(name):
        p = by_name[name]
        return {n.split(" ", 1)[1]: s for n, s in p.part_slots.items()}
    assert slots("clip-03") == {"base": 1, "black": 2, "yellow": 3}
    assert slots("clip-04") == {"base": 1, "black": 2, "pink": 4}
    assert slots("key-01") == {"base": 1, "black": 2, "yellow": 3, "pink": 4}
    for p in result.pieces:
        assert not p.part_off_palette


def test_half_drawn_outline_becomes_black_ink(party):
    result, _ = party
    for name in ("clip-12", "clip-14", "key-13"):
        p = next(x for x in result.pieces if x.name == name)
        black = next(i for i in p.design.inks if i.name == "black")
        assert black.geometry.area > 20
        union = None
        for s in p.parts.values():
            assert to_trimesh(s).is_watertight
            union = s if union is None else union + s
        assert count_bodies(union) == 1


# --- colors that aren't loaded -------------------------------------------

@pytest.fixture(scope="module")
def odd_photos(tmp_path_factory, party):
    _, cfg_p = party
    cfg = load_config(cfg_p)
    d = tmp_path_factory.mktemp("odd")
    draw_blob_card(cfg, d, "hair_clip", 6, BLACK, ORANGE)
    draw_blob_card(cfg, d, "hair_clip", 7, BLACK, PINK, extra=(BLUE, 0, 0, 9))
    draw_blob_card(cfg, d, "keychain", 4, BLACK, YELLOW)
    return d, cfg_p


def test_strict_mode_asks_once_and_writes_no_plates(odd_photos, tmp_path):
    d, cfg_p = odd_photos
    result = run_batch(load_config(cfg_p), [d], tmp_path / "out", off_palette=None, allow_uncalibrated=False)
    assert result.question is not None and not result.plates
    q = result.files["question"].read_text()
    assert "clip-06" in q and "orange" in q and "clip-07" in q and "blue" in q
    assert "key-04" not in q
    # Never merged silently: the orange is its own flagged part.
    p6 = next(p for p in result.pieces if p.name == "clip-06")
    assert any(i["color"] == "orange" for i in p6.part_off_palette.values())
    # Placeholder suggestions never come from the generic palette.
    assert "none in your spool list" in q


def test_off_palette_nearest_gives_one_plate(odd_photos, tmp_path):
    d, cfg_p = odd_photos
    result = run_batch(load_config(cfg_p), [d], tmp_path / "out", off_palette="nearest")
    assert result.question is None and len(result.plates) == 1 and not result.plates[0].swaps
    p6 = next(p for p in result.pieces if p.name == "clip-06")
    plate = result.plates[0]
    a = next(pp.assignments for pp in plate.pieces if pp.piece.name == "clip-06")
    assert a["clip-06 orange"].name == "Yellow PLA"


def test_off_palette_swap_gets_its_own_plate(odd_photos, tmp_path):
    d, cfg_p = odd_photos
    cfg = load_config(cfg_p)
    cfg["filaments"] = [{"name": "Orange PLA", "color": "#F77F00"}, {"name": "Blue PLA", "color": "#1D4ED8"}]
    result = run_batch(cfg, [d], tmp_path / "out", off_palette="swap")
    assert result.question is None
    main = [p for p in result.plates if not p.swaps]
    swaps = [p for p in result.plates if p.swaps]
    assert [pp.piece.name for pp in main[0].pieces] == ["key-04"]
    assert result.plates.index(main[0]) == 0, "plates without swaps print first"
    put_in = {sw.put_in.name for p in swaps for sw in p.swaps}
    assert put_in == {"Orange PLA", "Blue PLA"}
    for p in swaps:
        for sw in p.swaps:
            assert sw.take_out is None or sw.take_out.name != "White PLA"
            used = {f for pp in p.pieces for f in pp.assignments.values()}
            assert sw.take_out not in used
    notes = result.files["notes"].read_text()
    assert "Before printing" in notes and "After printing: put" in notes


def test_per_card_answer_with_map(odd_photos, tmp_path):
    d, cfg_p = odd_photos
    result = run_batch(load_config(cfg_p), [d], tmp_path / "out",
                       overrides=["clip-06 orange=Pink PLA", "clip-07 blue=Black PLA"])
    assert result.question is None and len(result.plates) == 1


# --- chips ----------------------------------------------------------------

def test_filament_chips(cfg_path, tmp_path):
    cfg = load_config(cfg_path)
    pal = load_palette(cfg)
    chips = build_chips(cfg, pal)
    assert [c.slot for c in chips] == [1, 2, 3, 4]
    for c in chips:
        assert count_bodies(c.solid) == 1 and to_trimesh(c.solid).is_watertight
        # The slot number is cut in: less volume than the plain tag.
        assert c.solid.volume() < cfg["chips"]["width"] * cfg["chips"]["length"] * cfg["chips"]["thickness"]
        lo = c.solid.bounding_box()
        assert lo[5] == pytest.approx(cfg["chips"]["thickness"])
    assert estimate_minutes(cfg, chips) <= cfg["chips"]["budget_minutes"]
    paths = write_chips(cfg, pal, tmp_path)
    xml = zipfile.ZipFile(paths["3mf"]).read("Metadata/model_settings.config").decode()
    for slot in (1, 2, 3, 4):
        assert f'value="chip slot {slot}"' in xml and f'<metadata key="extruder" value="{slot}"/>' in xml
    assert "By object" in paths["notes"].read_text()


def test_chips_need_loaded_slots():
    with pytest.raises(ValueError):
        build_chips(load_config(), load_palette({"filaments": [], "loaded": {}}))


def test_strict_mode_asks_about_calibration(cfg_path, tmp_path):
    """Strict mode: spool colors can't tell an orange marker from a golden-yellow one,
    so without a calibration scan the batch stops and asks instead of guessing."""
    cfg = load_config(cfg_path)
    photos = tmp_path / "p"
    photos.mkdir()
    draw_blob_card(cfg, photos, "hair_clip", 4, BLACK, PINK)
    draw_blob_card(cfg, photos, "hair_clip", 6, BLACK, ORANGE)
    r = run_batch(cfg, [photos], tmp_path / "out", off_palette=None, allow_uncalibrated=False)
    assert r.question is not None and not r.plates
    assert "calibration card hasn't been scanned" in r.question
    assert "slot 3 Yellow PLA" in r.question
    r2 = run_batch(cfg, [photos], tmp_path / "out2", allow_uncalibrated=True)
    assert r2.question is None and r2.plates


def test_default_run_never_stops_and_keeps_colors_apart(odd_photos, tmp_path):
    """The everyday default: no questions, every color its own part, a head start on spools."""
    d, cfg_p = odd_photos
    result = run_batch(load_config(cfg_p), [d], tmp_path / "out")
    assert result.question is None and result.plates and result.problems == []
    p6 = next(p for p in result.pieces if p.name == "clip-06")
    names = {n.split(" ", 1)[1] for n in p6.parts}
    assert names == {"base", "black", "orange"}
    assert "Bambu Studio" in " ".join(p6.design.warnings)
