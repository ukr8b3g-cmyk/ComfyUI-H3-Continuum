from ComfyUI_H3_Continuum_Join.nodes import NODE_CLASS_MAPPINGS


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
