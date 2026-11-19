import json
import tomllib
from pathlib import Path

from app import __version__

ROOT = Path(__file__).resolve().parents[2]


def test_app_version_matches_pyproject() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert __version__ == project["project"]["version"]


def test_openapi_snapshot_uses_the_app_version() -> None:
    spec = json.loads((ROOT / "docs/openapi.json").read_text(encoding="utf-8"))

    assert spec["info"]["version"] == __version__
