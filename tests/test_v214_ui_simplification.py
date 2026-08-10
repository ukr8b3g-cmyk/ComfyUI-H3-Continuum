from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_v214_frontend_collapses_advanced_controls_without_reordering_outputs():
    source = (ROOT / "web" / "h3_continuum_v214.js").read_text(encoding="utf-8")

    assert 'const ADVANCED_PROPERTY = "h3_show_advanced"' in source
    assert '["last_frame", "IMAGE"]' in source
    assert '["prompt_plan", "H3_CONTINUUM_PROMPT_PLAN"]' in source
    assert '["last_state", "H3_CONTINUUM_STATE"]' in source
    assert "hasAdvancedConnection(node)" in source
    assert "removeUnlinkedAdvancedSlots(node)" in source
    assert "Advanced Settings ▸" in source
    assert "placeAdvancedButton(node, button, expanded)" in source


def test_all_non_primary_nodes_use_native_comfyui_deprecation():
    source = (ROOT / "nodes.py").read_text(encoding="utf-8")

    assert 'if _node_id == "H3ContinuumSamplerV2"' in source
    assert "_node_class.DEPRECATED = True" in source
    assert 'f"{CATEGORY}/Legacy"' in source
    assert 'f"[Legacy] {_display_name}"' in source


def test_v214_version_metadata_matches():
    assert 'PACKAGE_VERSION = "2.1.4"' in (ROOT / "version.py").read_text(encoding="utf-8")
    assert "version = 2.1.4" in (ROOT / "metadata.ini").read_text(encoding="utf-8")
    assert 'version = "2.1.4"' in (ROOT / "pyproject.toml").read_text(encoding="utf-8")
