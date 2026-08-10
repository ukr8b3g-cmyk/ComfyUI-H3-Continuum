from pathlib import Path

from ComfyUI_H3_Continuum_Join.nodes import NODE_CLASS_MAPPINGS
from ComfyUI_H3_Continuum_Join.constants import (
    PROMPT_FORMAT_OPTIONS,
    SEAM_CORRECTION_AUTO,
)


def test_v2_nodes_are_registered_without_removing_v1():
    expected = {
        "H3ContinuumJoin",
        "H3ContinuumFinish",
        "H3ContinuumAssemble",
        "H3ContinuumSaveState",
        "H3ContinuumLoadState",
        "H3ContinuumSamplerV2",
        "H3ContinuumPromptPlanPreview",
        "H3ContinuumSaveSession",
        "H3ContinuumLoadSession",
        "H3ContinuumSessionInfo",
    }
    assert expected.issubset(NODE_CLASS_MAPPINGS)


def test_v2_sampler_accepts_connectable_prompt_plan():
    schema = NODE_CLASS_MAPPINGS["H3ContinuumSamplerV2"].INPUT_TYPES()
    assert "prompt_plan" in schema["optional"]


def test_v2_sampler_registers_preview_setting_bridge_and_sixteen_prompt_inputs():
    schema = NODE_CLASS_MAPPINGS["H3ContinuumSamplerV2"].INPUT_TYPES()
    optional = schema["optional"]

    assert schema["required"]["prompt_mode"][0] == PROMPT_FORMAT_OPTIONS
    assert schema["required"]["prompt_mode"][1]["default"] == "Auto"
    assert optional["sequence_prompt"][0] == "STRING"
    assert optional["sequence_prompt"][1]["forceInput"] is True
    assert optional["show_preview"][1]["default"] is True
    for index in range(1, 17):
        prompt_input = optional[f"clip_{index}_prompt"]
        assert prompt_input[0] == "STRING"
        assert prompt_input[1]["forceInput"] is True


def test_v2_sampler_defaults_to_auto_seam_correction():
    schema = NODE_CLASS_MAPPINGS["H3ContinuumSamplerV2"].INPUT_TYPES()
    assert schema["required"]["seam_correction"][1]["default"] == SEAM_CORRECTION_AUTO


def test_v2_interface_keeps_sequence_socket_and_stable_override_slots():
    root = Path(__file__).resolve().parents[1]
    source = (root / "web" / "h3_continuum_v2.js").read_text(encoding="utf-8")
    assert 'const SEQUENCE_PROMPT_INPUT = "sequence_prompt"' in source
    assert "syncPromptInputs(node)" in source
    assert "node.removeInput(" not in source
    assert "node.addInput(" not in source
