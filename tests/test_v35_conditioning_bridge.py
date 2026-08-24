from __future__ import annotations

import torch

from ComfyUI_H3_Continuum_Join.nodes import (
    NODE_CLASS_MAPPINGS,
    NODE_DISPLAY_NAME_MAPPINGS,
)
from ComfyUI_H3_Continuum_Join.v3 import conditioning_bridge_nodes
from ComfyUI_H3_Continuum_Join.v3.conditioning_bridge_nodes import (
    H3ContinuumConditioningBridgeV35,
)
from ComfyUI_H3_Continuum_Join.v3.refine_context import (
    MAGIC as REFINE_CONTEXT_MAGIC,
)
from ComfyUI_H3_Continuum_Join.v3.second_pass import (
    prepare_physical_refine_groups,
)


def _group(
    group_id: int,
    *,
    logical_chunks: list[int],
    temporal: int,
    terminal: bool,
) -> dict:
    return {
        "group_id": group_id,
        "logical_chunks": logical_chunks,
        "physical_prompt": f"physical prompt {group_id}",
        "prompt_policy": "paired_timeline_v1" if terminal else "single",
        "physical_frames": 260 if terminal else 124,
        "trim_prefix_frames": 22 if terminal else 0,
        "terminal_merged": terminal,
        "source_width": 640,
        "source_height": 640,
        "source_batch": 1,
        "latent_channels": 24,
        "source_latent_t": temporal,
        "source_latent_h": 40,
        "source_latent_w": 40,
        "source_audio_shape": [1, 8, temporal * 4],
    }


def _fixture():
    groups = [
        _group(0, logical_chunks=[1], temporal=37, terminal=False),
        _group(1, logical_chunks=[2, 3], temporal=77, terminal=True),
    ]
    plan = {
        "width": 640,
        "height": 640,
        "second_pass_contract": {
            "version": 1,
            "physical_groups": groups,
        },
    }
    videos = [
        {"samples": torch.zeros((1, 24, group["source_latent_t"], 48, 48))}
        for group in groups
    ]
    context_groups = (
        {
            "group_id": 0,
            "logical_chunks": (1,),
            "physical_clip_index": 1,
            "context_frames": 0,
        },
        {
            "group_id": 1,
            "logical_chunks": (2, 3),
            "physical_clip_index": 2,
            "context_frames": 22,
        },
    )
    context = {
        "magic": REFINE_CONTEXT_MAGIC,
        "complete": True,
        "groups": context_groups,
    }
    return groups, plan, videos, context


def test_conditioning_bridge_public_schema_and_registration():
    node_id = "H3ContinuumConditioningBridgeV35"
    node_class = NODE_CLASS_MAPPINGS[node_id]
    assert node_class is H3ContinuumConditioningBridgeV35
    assert NODE_DISPLAY_NAME_MAPPINGS[node_id] == (
        "H3 Continuum Conditioning Bridge V3.5"
    )
    assert node_class.CATEGORY == "MiniMax H3/Continuum/Advanced"
    assert node_class.DEPRECATED is False
    assert node_class.INPUT_IS_LIST is True
    assert node_class.OUTPUT_IS_LIST == (True, True, False, False)
    assert node_class.RETURN_TYPES == (
        "MODEL",
        "CONDITIONING",
        "H3_CONTINUUM_ASSEMBLY_PLAN",
        "STRING",
    )
    assert node_class.RETURN_NAMES == (
        "group_models",
        "conditioning",
        "updated_assembly_plan",
        "status",
    )
    schema = node_class.INPUT_TYPES()
    assert list(schema["required"]) == [
        "model",
        "clip",
        "video_latents",
        "assembly_plan",
        "refine_context",
    ]
    assert list(schema["optional"]) == ["video_vae"]


def test_prepare_keeps_one_complete_conditioning_per_physical_group():
    groups, plan, videos, context = _fixture()
    conditioning_objects = [
        [["group-0-entry-a", {"slot": 0}], ["group-0-entry-b", {"slot": 1}]],
        [["group-1-entry-a", {"slot": 0}], ["group-1-entry-b", {"slot": 1}]],
    ]
    clone_calls = []

    def validate_context(value, *, assembly_plan):
        assert value is context
        assert assembly_plan is plan
        return context

    def adapt(group, **kwargs):
        assert kwargs["target_latent_h"] == 48
        assert kwargs["target_latent_w"] == 48
        return conditioning_objects[group["group_id"]], {"adapted": True}

    def clone(model, **kwargs):
        clone_calls.append(kwargs)
        return f"model-{kwargs['chunk_index']}"

    prepared = prepare_physical_refine_groups(
        model="base-model",
        clip="clip",
        video_latents=videos,
        assembly_plan=plan,
        refine_context=context,
        validate_refine_context_fn=validate_context,
        adapt_group_conditioning_fn=adapt,
        clone_model_fn=clone,
    )

    assert prepared["physical_group_count"] == 2
    assert len(prepared["group_models"]) == len(prepared["conditioning"]) == 2
    assert prepared["group_models"] == ["model-1", "model-2"]
    assert prepared["conditioning"] == conditioning_objects
    assert prepared["conditioning"][0] is conditioning_objects[0]
    assert prepared["conditioning"][1] is conditioning_objects[1]
    assert [len(item) for item in prepared["conditioning"]] == [2, 2]
    assert [detail["group"]["logical_chunks"] for detail in prepared["details"]] == [
        [1],
        [2, 3],
    ]
    assert [detail["context_frames"] for detail in prepared["details"]] == [0, 22]
    assert clone_calls == [
        {
            "strict": False,
            "debug": False,
            "chunk_index": 1,
            "context_frames": None,
        },
        {
            "strict": False,
            "debug": False,
            "chunk_index": 2,
            "context_frames": 22,
        },
    ]
    assert prepared["updated_assembly_plan"]["width"] == 768
    assert prepared["updated_assembly_plan"]["height"] == 768
    assert plan["width"] == 640
    assert groups[1]["logical_chunks"] == [2, 3]


def test_node_preserves_outer_physical_group_list_without_flattening(monkeypatch):
    _groups, plan, videos, context = _fixture()
    complete_conditioning = [
        [["first-entry", {"group": 0}], ["second-entry", {"group": 0}]],
        [["terminal-entry-a", {"group": 1}], ["terminal-entry-b", {"group": 1}]],
    ]
    prepared = {
        "group_models": ["model-0", "model-1"],
        "conditioning": complete_conditioning,
        "updated_assembly_plan": {"width": 768, "height": 768},
        "physical_group_count": 2,
        "warnings": [],
        "details": [
            {
                "group_index": 0,
                "group": {"logical_chunks": [1], "prompt_policy": "single"},
                "conditioning_source": "refine_context",
                "physical_clip_index": 1,
                "context_frames": 0,
            },
            {
                "group_index": 1,
                "group": {
                    "logical_chunks": [2, 3],
                    "prompt_policy": "paired_timeline_v1",
                },
                "conditioning_source": "refine_context",
                "physical_clip_index": 2,
                "context_frames": 22,
            },
        ],
    }
    captured = {}

    def fake_prepare(**kwargs):
        captured.update(kwargs)
        return prepared

    monkeypatch.setattr(
        conditioning_bridge_nodes,
        "prepare_physical_refine_groups",
        fake_prepare,
    )
    result = H3ContinuumConditioningBridgeV35().prepare(
        model=["base-model"],
        clip=["clip"],
        video_latents=videos,
        assembly_plan=[plan],
        refine_context=[context],
        video_vae=["vae"],
    )

    assert captured["model"] == "base-model"
    assert captured["clip"] == "clip"
    assert captured["video_latents"] is videos
    assert captured["assembly_plan"] is plan
    assert captured["refine_context"] is context
    assert captured["video_vae"] == "vae"
    assert result[0] == ["model-0", "model-1"]
    assert result[1] is complete_conditioning
    assert len(result[1]) == 2
    assert [len(item) for item in result[1]] == [2, 2]
    assert result[2] is prepared["updated_assembly_plan"]
    assert "logical_chunks=[2, 3]" in result[3]
    assert "AV LATENT, Noise, and Audio Lock" in result[3]
