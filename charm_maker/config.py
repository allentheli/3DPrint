"""Load and save config.yaml."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = REPO_ROOT / "config.yaml"


def load_config(path: Path | str | None = None) -> dict[str, Any]:
    path = Path(path) if path else DEFAULT_CONFIG
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def read_config_text(path: Path | str | None = None) -> str:
    path = Path(path) if path else DEFAULT_CONFIG
    return Path(path).read_text(encoding="utf-8")


def write_config_text(text: str, path: Path | str | None = None) -> None:
    path = Path(path) if path else DEFAULT_CONFIG
    Path(path).write_text(text, encoding="utf-8")
