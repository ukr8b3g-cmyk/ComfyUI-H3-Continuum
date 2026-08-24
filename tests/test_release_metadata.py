from __future__ import annotations

import configparser
from pathlib import Path
import tomllib


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_VERSION = "3.5.0"


def test_v35_release_metadata_is_consistent():
    version_source = (ROOT / "version.py").read_text(encoding="utf-8")
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    metadata = configparser.ConfigParser()
    metadata.read(ROOT / "metadata.ini", encoding="utf-8")

    assert f'PACKAGE_VERSION = "{EXPECTED_VERSION}"' in version_source
    assert pyproject["project"]["version"] == EXPECTED_VERSION
    assert metadata["project"]["version"] == EXPECTED_VERSION


def test_v35_public_documents_identify_the_current_release():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_ja = (ROOT / "README_JA.md").read_text(encoding="utf-8")
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

    assert readme.startswith(f"# ComfyUI-H3-Continuum {EXPECTED_VERSION}\n")
    assert readme_ja.startswith(f"# ComfyUI-H3-Continuum {EXPECTED_VERSION}\n")
    assert f"## {EXPECTED_VERSION}" in changelog
