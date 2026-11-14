"""Rough print times, to print each kid's quickest pieces before they go home (Allen, 2026-11-14)."""

from charm_maker.pipeline import run_batch
from tests.synthetic import BLACK, PINK, YELLOW, draw_blob_card


def test_quickest_first_and_plate_times(cfg, tmp_path):
    photos = tmp_path / "photos"
    photos.mkdir()
    draw_blob_card(cfg, photos, "keychain", 3, BLACK, PINK)
    draw_blob_card(cfg, photos, "clicker", 1, BLACK, YELLOW)
    draw_blob_card(cfg, photos, "keychain", 4, BLACK, PINK)
    res = run_batch(cfg, sorted(photos.glob("*.jpg")), tmp_path / "out",
                    names={"key-03": "Jack", "click-01": "Jack", "key-04": "Mia"}, styles={"key-04": "puffy"})
    assert not res.problems, res.problems
    quick = res.files["quickest"]
    assert list(quick) == ["jack", "mia"]
    jack = quick["jack"]
    assert [it["what"] for it in jack] == ["keychain", "clicker (with its case)"], "the clicker and its tall case take longest"
    assert jack[1]["pieces"] == ["clicker-jack", "clicker-jack-case"]
    # The same keychain drawn puffy changes color over many more layers, so it takes longer.
    assert quick["mia"][0]["minutes"] > jack[0]["minutes"]
    est = next(iter(res.files["plates"].values()))["estimate"]
    assert est["changes"] > 0 and est["minutes"] > jack[1]["minutes"]
    notes = res.files["notes"].read_text()
    assert "## Quickest first" in notes and "**Jack:** keychain" in notes and "Rough time: about" in notes


def test_a_quick_plate_and_what_to_take_out(cfg, tmp_path):
    """Allen, 2026-11-14: "when I ask give the quick one for each on a separate plate and tell me
    which one I need to take out from the main plate"; the kids' plates still hold everything."""
    photos = tmp_path / "photos"
    photos.mkdir()
    draw_blob_card(cfg, photos, "keychain", 3, BLACK, PINK)
    draw_blob_card(cfg, photos, "clicker", 1, BLACK, YELLOW)
    draw_blob_card(cfg, photos, "keychain", 4, BLACK, PINK)
    res = run_batch(cfg, sorted(photos.glob("*.jpg")), tmp_path / "out",
                    names={"key-03": "Jack", "click-01": "Jack", "key-04": "Mia"}, quick={"key-03", "key-04"})
    assert not res.problems, res.problems
    names = [v["3mf"].name for v in res.files["plates"].values()]
    assert names == ["jack-clicker-keychain.3mf", "mia-keychain.3mf", "quick_jack-keychain_mia-keychain.3mf"]
    assert res.files["take_out"] == [("keychain-jack", "jack-clicker-keychain"), ("keychain-mia", "mia-keychain")]
    notes = res.files["notes"].read_text()
    assert "take these out of the kids' plates" in notes and "`keychain-jack` from `jack-clicker-keychain.3mf`" in notes
    bad = run_batch(cfg, sorted(photos.glob("*.jpg")), tmp_path / "bad", quick={"key-09"})
    assert any("--quick key-09: no such card" in p for p in bad.problems)
