from __future__ import annotations

import configparser
from pathlib import Path
import re
import tomllib

import pytest


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_VERSION = "3.10.3"


def test_v35_release_metadata_is_consistent():
    version_source = (ROOT / "version.py").read_text(encoding="utf-8")
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    metadata = configparser.ConfigParser()
    metadata.read(ROOT / "metadata.ini", encoding="utf-8")

    assert f'PACKAGE_VERSION = "{EXPECTED_VERSION}"' in version_source
    assert pyproject["project"]["version"] == EXPECTED_VERSION
    assert metadata["project"]["version"] == EXPECTED_VERSION


def test_public_documents_identify_the_current_v39_main():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_ja = (ROOT / "README_JA.md").read_text(encoding="utf-8")
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

    assert readme.startswith(f"# ComfyUI-H3-Continuum {EXPECTED_VERSION} — V3.9\n")
    assert readme_ja.startswith(f"# ComfyUI-H3-Continuum {EXPECTED_VERSION} — V3.9\n")
    assert f"## {EXPECTED_VERSION}" in changelog


@pytest.mark.parametrize("name, declaration", [
    ("INSTALL_JA.txt", r"最新版パッケージは([0-9.]+)です"),
    ("PACKAGE_INFO_JA.txt", r"最新版パッケージは([0-9.]+)です"),
    ("PACKAGE_VALIDATION.txt", r"Latest package: ([0-9.]+)\.\*\*"),
    ("PROJECT_STATE.md", r"Latest package: ([0-9.]+)\.\*\*"),
])
def test_current_download_guidance_matches_package_metadata(name, declaration):
    text = (ROOT / name).read_text(encoding="utf-8")
    match = re.search(declaration, text)
    assert match and match.group(1) == EXPECTED_VERSION
    downloads = text[match.end():]
    release = re.search(r"releases/tag/v([0-9.]+)\)", downloads)
    assert release and release.group(1) == EXPECTED_VERSION
    assert f"/releases/download/v{EXPECTED_VERSION}/ComfyUI-H3-Continuum-v{EXPECTED_VERSION}.zip" in downloads
    assert f"/releases/download/v{EXPECTED_VERSION}/SHA256SUMS.txt" in downloads


def test_install_command_selects_current_package():
    text = (ROOT / "INSTALL_JA.txt").read_text(encoding="utf-8")
    versions = re.findall(r"comfy node install comfyui-h3-continuum@([0-9.]+)", text)
    assert versions and set(versions) == {EXPECTED_VERSION}


@pytest.mark.parametrize("name, label", [
    ("README.md", "Current release and GPU verification"),
    ("README_JA.md", "最新版の検証記録"),
])
def test_current_readme_notes_link_matches_its_version(name, label):
    text = (ROOT / name).read_text(encoding="utf-8")
    row = next(line for line in text.splitlines() if line.startswith(f"| {label} |"))
    link = re.search(r"\[(v[0-9.]+)[^\]]*\]\((docs/RELEASE_NOTES_[^)]+)\)", row)
    assert link and link.group(1) == f"v{EXPECTED_VERSION}"
    target = f"docs/RELEASE_NOTES_V{EXPECTED_VERSION.replace('.', '')}.md"
    assert link.group(2) == target
    notes = (ROOT / target).read_text(encoding="utf-8")
    assert EXPECTED_VERSION in notes.splitlines()[0]
