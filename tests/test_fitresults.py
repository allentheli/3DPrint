import shutil

from charm_maker.config import DEFAULT_CONFIG, load_config
from charm_maker.fitresults import apply_fit_results


def _untested_copy(tmp_path):
    """The config as before any fit test (real results are recorded in it over time)."""
    import re

    cfg_path = tmp_path / "config.yaml"
    shutil.copy(DEFAULT_CONFIG, cfg_path)
    cfg_path.write_text(re.sub(r"tested: true[^\n]*", "tested: false", cfg_path.read_text()))
    return cfg_path


def test_apply_fit_results_updates_values_and_keeps_comments(tmp_path):
    cfg_path = _untested_copy(tmp_path)
    before = cfg_path.read_text()
    changes = apply_fit_results(cfg_path, [3, 4, 9, 11, 14, 16, 21])
    assert len(changes) == 7
    cfg = load_config(cfg_path)
    assert cfg["fit"]["clip_pocket_diameter"]["value"] == 11.8
    assert cfg["fit"]["keyring_hole_diameter"]["value"] == 4.5
    assert cfg["fit"]["earring_hole_diameter"]["value"] == 1.8
    assert cfg["fit"]["switch_cutout"]["value"] == 14.0
    assert cfg["fit"]["stem_socket_clearance"]["value"] == 0.15
    assert cfg["fit"]["necklace_hole_diameter"]["value"] == 3.0
    assert cfg["fit"]["flexi_joint_gap"]["value"] == 0.50
    for g in cfg["fit"].values():
        assert g["tested"] is True
    after = cfg_path.read_text()
    # Comments and everything outside the fit block are untouched.
    assert after.count("#") == before.count("#") + 7
    assert after.split("# Hardware sizes")[1] == before.split("# Hardware sizes")[1]


def test_partial_results_leave_other_groups_untested(tmp_path):
    cfg_path = _untested_copy(tmp_path)
    apply_fit_results(cfg_path, [2])
    cfg = load_config(cfg_path)
    assert cfg["fit"]["clip_pocket_diameter"]["tested"] is True
    assert cfg["fit"]["keyring_hole_diameter"]["tested"] is False
