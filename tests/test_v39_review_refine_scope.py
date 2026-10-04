"""Real conditioning/Second Pass contracts for V3.9 output-scope projection."""
from copy import deepcopy

import pytest
import torch

from ComfyUI_H3_Continuum_Join.v3 import driving_nodes
from ComfyUI_H3_Continuum_Join.v3 import refine_context as rc
from ComfyUI_H3_Continuum_Join.v3.reference_storage_contract import canonical_sha256
from ComfyUI_H3_Continuum_Join.v3.second_pass import run_second_pass_groups


def fixture(chunks=((1,), (2,), (3,)), captured=2, selected=(0, 1)):
    groups, plans, routes = [], [], []
    for index, logical in enumerate(chunks):
        descriptor = {"physical_group": index + 1, "logical_chunks": list(logical),
                      "references": [{"source_slot_id": "R1", "picture_number": 2}]}
        route = {"descriptor": descriptor, "sha256": canonical_sha256(descriptor)}
        if index < captured:
            groups.append(rc.make_refine_group(
                conditioning=[[torch.full((1, 1, 2), float(index + 1)), {
                    "minimax_frame_count": 124,
                    "minimax_keyframes": [{"audio_latent": torch.ones(1, 32, 2, 7)}],
                }]], group_id=index, logical_chunks=logical, physical_frames=124,
                prompt_policy="single", physical_prompt=f"prompt {index + 1}",
                source_video_shape=(1, 24, 37, 2, 3), physical_clip_index=logical[0],
                context_frames=0 if index == 0 else 22,
                reference_routing_group_contract=route,
            ))
        plans.append({
            "group_id": index, "logical_chunks": list(logical), "physical_frames": 124,
            "physical_prompt": f"prompt {index + 1}", "prompt_policy": "single",
            "trim_prefix_frames": 0 if index == 0 else 22,
            "terminal_merged": len(logical) == 2, "source_width": 48, "source_height": 32,
            "source_batch": 1, "latent_channels": 24, "source_latent_t": 37,
            "source_latent_h": 2, "source_latent_w": 3, "source_audio_shape": [1, 8, 148],
        })
        routes.append({"physical_group": index + 1, "logical_chunks": list(logical),
                       "status": "reused" if index < captured else "pending",
                       "requested_slots": ["R1"], "warnings": [],
                       **({"contract_sha256": route["sha256"], "descriptor": descriptor}
                          if index < captured else {})})
    context = rc.make_refine_context(groups, source_width=48, source_height=32,
                                    conditioning_mode="t2va", complete=captured == len(chunks))
    plan = {"width": 48, "height": 32,
            "second_pass_contract": {"version": 1, "physical_groups": [
                {**plans[index], "group_id": position} for position, index in enumerate(selected)]},
            "reference_routing_v1": {"mode": "custom", "accepted_chunks": captured,
                                     "connected_slots": ["R1"], "groups": routes}}
    return context, plan


@pytest.mark.parametrize("selected", [(0,), (0, 1), (1,)])
def test_partial_views_are_complete_for_output_without_completing_sequence(selected):
    source, plan = fixture(selected=selected)
    view = rc.project_refine_context(source, plan)
    assert source["complete"] is view["complete"] is False
    assert rc.OUTPUT_SCOPE_KEY not in source
    assert view[rc.OUTPUT_SCOPE_KEY]["source_group_ids"] == selected
    assert rc.validate_refine_context(view, assembly_plan=plan) is view
    for local_index, source_index in enumerate(selected):
        assert view["groups"][local_index]["group_id"] == local_index
        assert view["groups"][local_index]["physical_clip_index"] == source_index + 1
        assert view["groups"][local_index]["conditioning"] is source["groups"][source_index]["conditioning"]


def test_complete_full_output_is_exact_context_passthrough():
    context, plan = fixture(captured=3, selected=(0, 1, 2))
    assert rc.project_refine_context(context, plan) is context


def test_terminal_pair_is_one_physical_scope():
    source, plan = fixture(chunks=((1,), (2, 3), (4,)), selected=(1,))
    view = rc.project_refine_context(source, plan)
    assert view["groups"][0]["logical_chunks"] == (2, 3)
    broken = deepcopy(plan)
    broken["second_pass_contract"]["physical_groups"][0]["logical_chunks"] = [2]
    assert rc.project_refine_context(source, broken) is source


def test_missing_capture_keeps_optional_fallback():
    source, plan = fixture(captured=1)
    assert rc.project_refine_context(source, plan) is source


@pytest.mark.parametrize("field,value", [
    ("physical_frames", 125), ("physical_prompt", "different"),
    ("trim_prefix_frames", 23), ("source_latent_t", 38), ("source_latent_w", 4),
])
def test_mismatched_partial_evidence_is_diagnostic_not_a_new_stop(field, value):
    source, plan = fixture(selected=(1,))
    plan["second_pass_contract"]["physical_groups"][0][field] = value
    result = rc.project_refine_context(source, plan)
    assert rc.OUTPUT_SCOPE_KEY not in result
    assert result["complete"] is False
    assert any("Output scope unavailable:" in note for note in result["notes"])


@pytest.mark.parametrize("corruption", ["hash", "duplicate", "pending"])
def test_reference_identity_cannot_be_guessed_by_local_group_index(corruption):
    source, plan = fixture(selected=(1,))
    routes = plan["reference_routing_v1"]["groups"]
    if corruption == "hash":
        routes[1]["contract_sha256"] = "0" * 64
    elif corruption == "duplicate":
        routes.append(deepcopy(routes[1]))
    else:
        routes[1].pop("descriptor")
    view = rc.project_refine_context(source, plan)
    assert rc.OUTPUT_SCOPE_KEY not in view


def test_projected_context_is_still_revalidated_at_second_pass_boundary():
    source, plan = fixture(selected=(1,))
    view = rc.project_refine_context(source, plan)
    plan["second_pass_contract"]["physical_groups"][0]["physical_prompt"] = "changed"
    with pytest.raises(rc.RefineContextError, match="physical_prompt"):
        rc.validate_refine_context(view, assembly_plan=plan)


def test_chunk_two_actual_second_pass_uses_its_conditions_and_preserves_audio():
    source, plan = fixture(selected=(1,))
    view = rc.project_refine_context(source, plan)
    video = {"samples": torch.zeros(1, 24, 37, 2, 3)}
    audio = {"samples": torch.ones(1, 8, 148)}
    calls = []
    def sample(**kwargs):
        calls.append(kwargs["conditioning"])
        return kwargs["latent"]
    _video, output_audio, updated, report = run_second_pass_groups(
        model=object(), clip=object(), sampler=object(), sigmas=torch.tensor([.2, 0.]),
        video_latents=[video], audio_latents=[audio], assembly_plan=plan,
        refine_seed=123, refine_context=view,
        encode_prompt_fn=lambda *args, **kwargs: pytest.fail("must not reencode prompt alone"),
        clone_model_fn=lambda model, **kwargs: model,
        latent_builder=lambda v, a: {"video": v, "audio": a},
        sample_fn=sample, stream_extractor=lambda latent: (latent["video"], latent["audio"]),
    )
    assert float(calls[0][0][0][0, 0, 0]) == 2.0
    assert output_audio[0] is audio
    assert updated["second_pass_contract"]["reference_inheritance"][0]["status"] == "verified"
    assert "conditioning_source=refine_context" in report
    assert "prompt_only_fallback" not in report
    assert source["groups"][1]["group_id"] == 1


def test_v39_boundary_projects_only_its_runtime_output(monkeypatch):
    source, plan = fixture(selected=(1,))
    from ComfyUI_H3_Continuum_Join.v3.nodes import _PARTIAL_REVIEW_SECOND_PASS_WARNING
    old = (object(), object(), plan, _PARTIAL_REVIEW_SECOND_PASS_WARNING, object(), source)
    monkeypatch.setattr(driving_nodes.H3ContinuumSamplerV38, "run", lambda *args, **kwargs: old)
    result = driving_nodes.H3ContinuumSamplerV39().run(chunks=3)["result"]
    assert result[:3] == old[:3]
    assert result[4] is old[4]
    assert result[5][rc.OUTPUT_SCOPE_KEY]["source_group_ids"] == (1,)
    assert "output-scope conditioning verified" in result[3]
    assert old[3] == _PARTIAL_REVIEW_SECOND_PASS_WARNING
