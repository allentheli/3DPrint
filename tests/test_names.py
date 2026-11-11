"""Pieces named after the kid who drew them (keychain-jack), from the names sheet, with the
card number kept as a note, and a who's-who map of each plate."""

import json
import zipfile

from charm_maker.pipeline import kid_file_name, read_names, run_batch
from tests.synthetic import BLACK, PINK, draw_blob_card


def test_kid_file_name(cfg):
    assert kid_file_name(cfg, "keychain", "Jack") == "keychain-jack"
    assert kid_file_name(cfg, "hair_clip", "Zoë Lee") == "clip-zoe-lee"
    assert kid_file_name(cfg, "pendant", "  MIA!! ") == "necklace-mia"
    assert kid_file_name(cfg, "keychain", " ") == "" and kid_file_name(cfg, "keychain", "??") == ""


def test_named_run(cfg, tmp_path):
    photos = tmp_path / "photos"
    photos.mkdir()
    for product, n in [("keychain", 3), ("keychain", 4), ("keychain", 5), ("keychain", 6), ("clicker", 1)]:
        draw_blob_card(cfg, photos, product, n, BLACK, PINK)
    inputs = sorted(photos.glob("*.jpg"))

    rows, sheet, problems = read_names(cfg, inputs, tmp_path / "out")
    assert sheet.exists() and not problems
    assert sorted(card for card, _ in rows) == ["click-01", "key-03", "key-04", "key-05", "key-06"]

    names = {"key-03": "Jack", "key-04": "Mia", "key-05": "jack", "click-01": "Jack"}   # key-06: name left blank
    res = run_batch(cfg, inputs, tmp_path / "out", names=names, styles={"key-03": "puffy"},
                    overrides=["key-04 pink=Black"])
    got = {p.name: p for p in res.pieces}
    assert set(got) == {"keychain-jack", "keychain-mia", "keychain-jack-2", "key-06", "clicker-jack", "clicker-jack-case"}
    assert got["keychain-jack"].style == "puffy", "flags still go by the card number"
    assert got["keychain-jack"].design.card == "key-03" and got["key-06"].design.card == ""
    assert not any("renamed" in w for p in res.pieces for w in p.design.warnings)

    out = tmp_path / "out"
    summary = json.loads((out / "designs" / "keychain-mia.json").read_text())
    assert summary["card"] == "key-04"
    pink = {n: f for n, f in _assignments(res, "keychain-mia").items() if n.endswith(" pink")}
    assert pink and all(f.name == "Black" for f in pink.values()), "a filament override by card number still applies"
    assert (out / "designs" / "clicker-jack-case-preview.png").exists()
    plate_files = [v for v in res.files["plates"].values()]
    assert all(v["map"].exists() for v in plate_files)
    names_in_3mf = "".join(zipfile.ZipFile(v["3mf"]).read(n).decode(errors="ignore")
                           for v in plate_files for n in zipfile.ZipFile(v["3mf"]).namelist() if n.endswith(".config"))
    assert "keychain-jack" in names_in_3mf and "clicker-jack-case" in names_in_3mf
    assert "plate-1-map.png" in (out / "PRINT_NOTES.md").read_text()


def _assignments(res, name):
    for plate in res.plates:
        for pp in plate.pieces:
            if pp.piece.name == name:
                return pp.assignments
    raise KeyError(name)
