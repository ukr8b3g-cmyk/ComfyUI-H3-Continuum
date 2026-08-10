import json
from pathlib import Path

from ComfyUI_H3_Continuum_Join.v2.nodes import H3ContinuumSamplerV2


ROOT = Path(__file__).resolve().parents[1]

SERIALIZED_WIDGET_ORDER = [
    "prompt_mode",
    "prompt_script",
    "chunks",
    "chunk_seconds",
    "width",
    "height",
    "continuity",
    "base_seed",
    "control_after_generate",
    "audio_continuity",
    "exact_total_duration",
    "diagnostics",
    "reroll_from_chunk",
    "reroll_nonce",
    "strict_compatibility",
    "debug",
    "seam_correction",
    "show_preview",
]


def test_v215_frontend_preserves_backend_serialization_structure():
    source = (ROOT / "web" / "h3_continuum_v2.js").read_text(encoding="utf-8")
    assert not (ROOT / "web" / "h3_continuum_v214.js").exists()
    for forbidden in (
        'widget.type = "converted-widget"',
        'widget.type = "hidden"',
        "node.widgets.splice(",
        "node.removeInput(",
        "node.addInput(",
        "node.removeOutput(",
        "node.addOutput(",
    ):
        assert forbidden not in source
    assert "setWidgetCollapsed" in source
    assert "placeTransientAfter" in source
    assert "serializedBefore.every" in source
    assert "slotVisibilityRules" in source
    assert "node.removeInput(" not in source
    assert "node.addInput(" not in source
    assert "node.removeOutput(" not in source
    assert "node.addOutput(" not in source
    assert "node.widgets.splice(" not in source
    assert "ensureSeamCorrectionProxy" in source
    assert "Individual Clip Overrides" in source
    assert "button.serialize = false" in source
    assert 'name: "H3Continuum.V215StableInterface"' in source
    assert source.count("nodeType.prototype.onNodeCreated = function") == 1
    assert source.count("nodeType.prototype.onConfigure = function") == 1


def test_v215_backend_widget_order_and_workflow_values_remain_aligned():
    required = H3ContinuumSamplerV2.INPUT_TYPES()["required"]
    assert list(required)[6:] == [
        "prompt_mode",
        "prompt_script",
        "chunks",
        "chunk_seconds",
        "width",
        "height",
        "continuity",
        "base_seed",
        "audio_continuity",
        "exact_total_duration",
        "diagnostics",
        "reroll_from_chunk",
        "reroll_nonce",
        "strict_compatibility",
        "debug",
        "seam_correction",
    ]
    values = [
        "Auto",
        "Preserved fallback prompt",
        2,
        5.0,
        1344,
        768,
        "Balanced — 22 frames",
        123456789,
        "fixed",
        True,
        True,
        "Basic",
        0,
        0,
        True,
        False,
        "Auto",
        True,
    ]
    mapped = dict(zip(SERIALIZED_WIDGET_ORDER, values, strict=True))
    assert mapped["chunks"] == 2
    assert mapped["chunk_seconds"] == 5.0
    assert mapped["width"] == 1344
    assert mapped["height"] == 768
    assert mapped["continuity"] == "Balanced — 22 frames"
    assert mapped["base_seed"] == 123456789
    assert mapped["seam_correction"] == "Auto"

    data = json.loads((ROOT / "examples" / "H3_Continuum_V2_3x5s.json").read_text(encoding="utf-8"))
    node = next(item for item in data["nodes"] if item["type"] == "H3ContinuumSamplerV2")
    legacy_values = node["widgets_values"]
    legacy = dict(zip(SERIALIZED_WIDGET_ORDER[:16], legacy_values, strict=True))
    assert legacy["chunks"] == 3
    assert legacy["chunk_seconds"] == 5.0
    assert legacy["width"] == 1344
    assert legacy["height"] == 768
    assert legacy["continuity"] == "Balanced — 22 frames"
    assert legacy["base_seed"] == 123456789


def test_all_non_primary_nodes_use_native_comfyui_deprecation():
    source = (ROOT / "nodes.py").read_text(encoding="utf-8")
    assert 'if _node_id == "H3ContinuumSamplerV2"' in source
    assert "_node_class.DEPRECATED = True" in source
    assert 'f"{CATEGORY}/Legacy"' in source
    assert 'f"[Legacy] {_display_name}"' in source


def test_v215_version_metadata_matches():
    assert 'PACKAGE_VERSION = "2.1.5"' in (ROOT / "version.py").read_text(encoding="utf-8")
    assert "version = 2.1.5" in (ROOT / "metadata.ini").read_text(encoding="utf-8")
    assert 'version = "2.1.5"' in (ROOT / "pyproject.toml").read_text(encoding="utf-8")
