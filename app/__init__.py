import tomllib
from pathlib import Path

_PROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"
__version__ = tomllib.loads(_PROJECT.read_text(encoding="utf-8"))["project"]["version"]
