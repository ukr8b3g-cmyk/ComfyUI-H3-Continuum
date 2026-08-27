from ComfyUI_H3_Continuum_Join.constants import CHUNK_SECONDS_TOOLTIP
from ComfyUI_H3_Continuum_Join.v2.nodes import (
    H3ContinuumPromptPlanPreview,
    H3ContinuumSampler,
    H3ContinuumSamplerV2,
)
from ComfyUI_H3_Continuum_Join.v3.driving_nodes import (
    H3ContinuumSamplerV34,
    H3ContinuumSamplerV35,
)
from ComfyUI_H3_Continuum_Join.v3.nodes import (
    H3ContinuumSamplerProduction,
    H3ContinuumSamplerV3,
)


def _chunk_seconds_schema(node_class):
    return node_class.INPUT_TYPES()["required"]["chunk_seconds"][1]


def test_all_shared_sampler_and_prompt_plan_schemas_allow_thirty_seconds():
    node_classes = (
        H3ContinuumSamplerV2,
        H3ContinuumPromptPlanPreview,
        H3ContinuumSampler,
        H3ContinuumSamplerV3,
        H3ContinuumSamplerProduction,
        H3ContinuumSamplerV34,
        H3ContinuumSamplerV35,
    )
    for node_class in node_classes:
        schema = _chunk_seconds_schema(node_class)
        assert schema["default"] == 5.0
        assert schema["min"] == 4.0
        assert schema["max"] == 30.0
        assert schema["step"] == 0.1
        assert schema["tooltip"] == CHUNK_SECONDS_TOOLTIP


def test_chunk_seconds_tooltip_describes_validated_and_high_cost_ranges():
    assert "5–15 seconds" in CHUNK_SECONDS_TOOLTIP
    assert "above 15 seconds are supported" in CHUNK_SECONDS_TOOLTIP
    assert "VRAM" in CHUNK_SECONDS_TOOLTIP
    assert "high resolution" in CHUNK_SECONDS_TOOLTIP
    assert "shared by every chunk" in CHUNK_SECONDS_TOOLTIP
