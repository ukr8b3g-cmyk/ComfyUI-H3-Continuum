"""RR-R6 public boundary and read-only Reference Plan contracts."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID
import zipfile

import pytest
import torch

from ComfyUI_H3_Continuum_Join import nodes as public_nodes
from ComfyUI_H3_Continuum_Join.v3 import driving_nodes
from ComfyUI_H3_Continuum_Join.v3.reference_images_v39 import (
    H3ContinuumReferenceImagesV39,
    REFERENCE_IMAGES_V39_TYPE,
    ReferenceImagesV39Bundle,
    effective_reference_inputs,
)
from ComfyUI_H3_Continuum_Join.v3.reference_plan_inspector import (
    format_reference_plan,
    project_reference_plan,
)
from ComfyUI_H3_Continuum_Join.v3.reference_routing import (
    REFERENCE_SLOT_IDS,
    compile_reference_routing_schedule,
)
from ComfyUI_H3_Continuum_Join.v3.reference_runtime import (
    ReferenceInputSet,
    ReferenceRoutingRuntime,
)
from ComfyUI_H3_Continuum_Join.v3.reference_storage_contract import canonical_sha256
from ComfyUI_H3_Continuum_Join.v3.refine_context import (
    RefineContextError,
    make_refine_context,
    make_refine_group,
    validate_refine_context,
)
from ComfyUI_H3_Continuum_Join.v3.second_pass import run_second_pass_groups


def test_v39_has_one_typed_reference_input_and_v38_is_unchanged():
    assert public_nodes.NODE_CLASS_MAPPINGS["H3ContinuumSamplerV39"] is (
        driving_nodes.H3ContinuumSamplerV39
    )
    old = driving_nodes.H3ContinuumSamplerV38.INPUT_TYPES()
    new = driving_nodes.H3ContinuumSamplerV39.INPUT_TYPES()
    assert new["required"] == old["required"]
    assert "reference_routing_mode" not in new["required"]
    assert not any(f"reference_r{index}_chunks" in new["required"]
                   for index in range(1, 10))
    assert set(new["optional"]) == (set(old["optional"])
                                   - {"reference_image_1", "reference_image_2", "reference_image_3", "image_references", "reference_image_4", "reference_image_5"}
                                   | {"reference_images"})
    assert new["optional"]["reference_images"][0] == H3ContinuumReferenceImagesV39.RETURN_TYPES[0]
    assert public_nodes.NODE_CLASS_MAPPINGS["H3ContinuumReferenceImagesV39"] is H3ContinuumReferenceImagesV39
    assert tuple(H3ContinuumReferenceImagesV39.INPUT_TYPES()["optional"]) == tuple(
        f"reference_image_{index}" for index in range(1, 10)
    )


def test_all_uses_the_same_routed_engine(monkeypatch):
    calls = []
    plan = {"mode": "Custom", "accepted_chunks": 0, "connected_slots": ["R1"], "groups": []}
    outputs = (object(), object(), {"reference_routing_v1": plan}, "status", object())

    def old_run(_self, **kwargs):
        calls.append(kwargs)
        return outputs

    monkeypatch.setattr(driving_nodes.H3ContinuumSamplerV38, "run", old_run)
    image = object()
    bundle = ReferenceImagesV39Bundle((image, *(None for _ in range(8))), "All chunks", ("off",) * 9)
    result = driving_nodes.H3ContinuumSamplerV39().run(reference_images=bundle, chunks=3, marker=7)
    assert result["result"] is outputs
    assert calls[0]["marker"] == 7
    assert calls[0]["reference_image_1"] is image
    assert calls[0]["_reference_routing_settings"] == {
        "R1": "all", **{f"R{index}": "off" for index in range(2, 10)}
    }


def test_custom_passes_selectors_privately_and_displays_verified_backend_plan(monkeypatch):
    calls = []
    plan = {
        "mode": "Custom", "accepted_chunks": 1,
        "connected_slots": ["R1"],
        "groups": [{
            "physical_group": 1, "logical_chunks": [1], "status": "generated",
            "descriptor": {"references": [{"source_slot_id": "R1", "picture_number": 2}]},
            "contract_sha256": "a" * 64, "warnings": [],
        }],
    }

    def old_run(_self, **kwargs):
        calls.append(kwargs)
        return ([], [], {"reference_routing_v1": plan}, "status", None)

    monkeypatch.setattr(driving_nodes.H3ContinuumSamplerV38, "run", old_run)
    image = object()
    bundle = ReferenceImagesV39Bundle((image, *(None for _ in range(8))), "Per chunk", ("2-3", *("off" for _ in range(8))))
    result = driving_nodes.H3ContinuumSamplerV39().run(
        reference_images=bundle, chunks=3, marker=7,
    )
    assert calls[0]["marker"] == 7
    assert calls[0]["_reference_routing_settings"] == {
        **{f"R{index}": "off" for index in range(1, 10)},
        "R1": "2,3", "R9": "off",
    }
    assert result["ui"]["h3_reference_plan"] == [format_reference_plan(plan)]
    assert "R1=<Picture 2>" in result["ui"]["h3_reference_plan"][0]


def test_plan_inspector_uses_observed_or_frozen_contract_not_a_frontend_guess():
    selectors = {slot: "off" for slot in REFERENCE_SLOT_IDS}
    selectors.update(R1="1", R4="2")
    schedule = compile_reference_routing_schedule(
        total_chunks=3, terminal_merge_enabled=False,
        mode="Custom", selectors_by_slot=selectors,
    )
    runtime = ReferenceRoutingRuntime(
        schedule=schedule,
        inputs=ReferenceInputSet((None,) * 9, 64, 64, "Match Output"),
    )
    first = {
        "descriptor": {"references": [{"source_slot_id": "R1", "picture_number": 1}]},
        "sha256": "a" * 64,
    }
    second = {
        "descriptor": {"references": [{"source_slot_id": "R4", "picture_number": 1}]},
        "sha256": "b" * 64,
    }
    runtime.storage_plan = SimpleNamespace(group_for=lambda group: {1: first, 2: second}[group])
    runtime.observed_group_contracts[2] = deepcopy(second)
    runtime.group_warnings[2] = ("R9 is disconnected",)
    runtime.accepted_chunks = 2
    runtime.generated_groups = (2,)
    projected = project_reference_plan(runtime)
    assert [item["status"] for item in projected["groups"]] == [
        "reused", "generated", "pending",
    ]
    assert projected["groups"][0]["contract_sha256"] == "a" * 64
    assert projected["groups"][1]["warnings"] == ["R9 is disconnected"]
    assert "descriptor" not in projected["groups"][2]
    assert "configured no References" in format_reference_plan(projected)
    assert first["descriptor"]["references"][0]["picture_number"] == 1


def test_invalid_bundle_mode_does_not_call_v38(monkeypatch):
    monkeypatch.setattr(
        driving_nodes.H3ContinuumSamplerV38, "run",
        lambda *_args, **_kwargs: pytest.fail("legacy path was called"),
    )
    bad = ReferenceImagesV39Bundle((None,) * 9, "Other", ("off",) * 9)
    with pytest.raises(ValueError, match="nine-slot V3.9 bundle"):
        driving_nodes.H3ContinuumSamplerV39().run(reference_images=bad)


def test_inline_helper_keeps_sparse_slot_ids_and_saved_future_chunks():
    image1, image4, image9 = object(), object(), object()
    values = {"reference_use": "Per chunk", "reference_image_1": image1,
              "reference_image_4": image4, "reference_image_9": image9,
              "reference_r1_chunks": "1,3,6", "reference_r4_chunks": "2-4",
              "reference_r9_chunks": "all"}
    (bundle,) = H3ContinuumReferenceImagesV39().pack(**values)
    assert bundle.images[3] is image4 and bundle.images[8] is image9
    assert bundle.selectors[3] == "2,3,4"
    first, extra, routes = effective_reference_inputs(bundle, chunks=3)
    assert first[0] is image1 and extra.images[0] is image4 and extra.images[5] is image9
    assert routes["R1"] == "1,3"
    assert routes["R4"] == "2,3"
    assert routes["R9"] == "1,2,3"
    assert effective_reference_inputs(bundle, chunks=6)[2]["R1"] == "1,3,6"
    assert bundle.selectors[0] == "1,3,6"


@pytest.mark.parametrize("saved,expected", [
    ("1,2", [("R1",), ("R1",), ()]),
    ("1,2,3", [("R1",), ("R1",), ("R1",)]),
    (",".join(str(n) for n in range(1, 17)), [("R1",), ("R1",), ("R1",)]),
    ("off", [(), (), ()]),
])
def test_external_assignment_range_uses_actual_chunks_without_rewriting_saved_value(saved, expected):
    bundle, = H3ContinuumReferenceImagesV39().pack(
        reference_use="Per chunk", reference_r1_chunks=saved,
        reference_image_1=object(),
    )
    original = bundle.selectors
    _, _, selectors = effective_reference_inputs(bundle, chunks=3)
    schedule = compile_reference_routing_schedule(
        total_chunks=3, terminal_merge_enabled=False,
        mode="Custom", selectors_by_slot=selectors,
    )
    assert schedule.valid
    assert [route.reference_slot_ids for route in schedule.logical_routes] == expected
    assert bundle.selectors == original


@pytest.mark.parametrize("saved", ["1,1", "1-3,3", "invalid"])
def test_unused_reference_retains_text_and_is_validated_when_connected(saved):
    helper = H3ContinuumReferenceImagesV39()
    inputs = dict(reference_use="Per chunk", reference_image_1=object(),
                  reference_r1_chunks="2", reference_r2_chunks=saved)
    bundle, = helper.pack(**inputs)
    _, _, selectors = effective_reference_inputs(bundle, chunks=2)
    assert selectors["R1"] == "2" and selectors["R2"] == "off"
    assert inputs["reference_r2_chunks"] == bundle.selectors[1] == saved
    with pytest.raises(ValueError, match="invalid V3.9 Reference chunk selection"):
        helper.pack(**inputs, reference_image_2=object())


def test_new_workflow_rewires_all_nine_slots_and_isolates_saved_runs():
    directory = Path(__file__).resolve().parents[1] / "examples" / "workflows"
    old = json.loads((directory / "MiniMax_H3_Continuum_V38X2.json").read_text(encoding="utf-8"))
    name = "MiniMax_H3_Continuum_V39_Reference_Inline.json"
    new_bytes = (directory / name).read_bytes()
    new = json.loads(new_bytes)
    with zipfile.ZipFile(directory / name.replace(".json", ".zip")) as archive:
        assert archive.namelist() == [name]
        assert archive.read(name) == new_bytes
    assert len(old["nodes"]) == len(new["nodes"])
    assert len(old["links"]) == len(new["links"])
    old_sampler = next(node for node in old["nodes"] if node["id"] == 312)
    sampler = next(node for node in new["nodes"] if node["id"] == 312)
    helper = next(node for node in new["nodes"] if node["id"] == 348)
    assert sampler["type"] == "H3ContinuumSamplerV39"
    # The user-supplied V38X2+Decode Cache Helper graph has an appended
    # Timeline Video mode that the earlier repository template lacked.
    project_id = sampler["widgets_values_named"]["project_id"]
    assert UUID(project_id).version == 4
    assert project_id != old_sampler["widgets_values_named"]["project_id"]
    expected_values = old_sampler["widgets_values"].copy()
    project_index = expected_values.index(old_sampler["widgets_values_named"]["project_id"])
    expected_values[project_index] = project_id
    assert sampler["widgets_values"][:-1] == expected_values
    assert sampler["widgets_values"][-1] == "Repeat Reference"
    assert sampler["widgets_values_named"]["video_reference_mode"] == "Repeat Reference"
    assert "reference_routing_mode" not in sampler["widgets_values_named"]
    assert not any(item["name"].startswith("reference_image_") for item in sampler["inputs"])
    assert helper["type"] == "H3ContinuumReferenceImagesV39"
    assert helper["widgets_values"] == ["All chunks", *(["off"] * 9)]
    assert [item["name"] for item in helper["inputs"]] == [
        f"reference_image_{index}" for index in range(1, 10)
    ]
    links = {item[0]: item for item in new["links"]}
    for slot, link_id in enumerate((351, 350, 349, 393, 394, 395), start=0):
        assert links[link_id][3:5] == [348, slot]
    assert links[392][3:6] == [312, len(sampler["inputs"]) - 1, REFERENCE_IMAGES_V39_TYPE]
    nodes = {node["id"]: node for node in new["nodes"]}
    assert nodes[344]["type"] == "H3DecodeCacheHelper"
    assert nodes[317]["mode"] == 4  # Preserve the supplied image loader bypass.
    assert nodes[355]["widgets_values"] == ["MiniMax_H3_00001_.mp4", "image"]
    assert nodes[315]["widgets_values"] == ["prnas_.mp3", None, None]
    assert sampler["inputs"][8]["name"] == "reference_video_1"
    assert sampler["inputs"][9]["name"] == "driving_audio"


def _routed_refine_fixture():
    descriptor = {
        "physical_group": 1, "logical_chunks": [1],
        "references": [{"source_slot_id": "R4", "picture_number": 1}],
    }
    route = {"descriptor": descriptor, "sha256": canonical_sha256(descriptor)}
    conditioning = [[torch.zeros((1, 1, 2)), {"minimax_frame_count": 124}]]
    captured = make_refine_group(
        conditioning=conditioning, group_id=0, logical_chunks=(1,),
        physical_frames=124, prompt_policy="single", physical_prompt="@R4 runs",
        source_video_shape=(1, 24, 37, 2, 3), physical_clip_index=1,
        context_frames=0, reference_routing_group_contract=route,
    )
    context = make_refine_context(
        [captured], source_width=48, source_height=32,
        conditioning_mode="t2va",
    )
    group = {
        "group_id": 0, "logical_chunks": [1], "physical_frames": 124,
        "physical_prompt": "@R4 runs", "prompt_policy": "single",
        "trim_prefix_frames": 0, "terminal_merged": False,
        "source_width": 48, "source_height": 32,
        "source_batch": 1, "latent_channels": 24,
        "source_latent_t": 37, "source_latent_h": 2,
        "source_latent_w": 3, "source_audio_shape": [1, 8, 148],
    }
    plan = {
        "width": 48, "height": 32,
        "second_pass_contract": {"version": 1, "physical_groups": [group]},
        "reference_routing_v1": {"groups": [{
            "contract_sha256": route["sha256"], "descriptor": deepcopy(descriptor),
        }]},
    }
    return context, plan, route


def test_refine_capture_is_bound_to_the_exact_first_pass_route():
    context, plan, route = _routed_refine_fixture()
    assert validate_refine_context(context, assembly_plan=plan) is context
    assert context["groups"][0]["reference_routing_v1"] == route
    changed = deepcopy(plan)
    changed["reference_routing_v1"]["groups"][0]["contract_sha256"] = "0" * 64
    with pytest.raises(RefineContextError, match="differs from First Pass Plan"):
        validate_refine_context(context, assembly_plan=changed)


@pytest.mark.parametrize("with_context,status", [
    (True, "verified"), (False, "not_inherited"),
])
def test_second_pass_reports_reference_inheritance_only_for_matching_context(
    with_context, status,
):
    context, plan, route = _routed_refine_fixture()
    video = {"samples": torch.zeros((1, 24, 37, 2, 3))}
    audio = {"samples": torch.zeros((1, 8, 148))}
    calls = []

    def encode_prompt(_clip, prompt, **_kwargs):
        calls.append(prompt)
        return [[torch.zeros((1, 1, 2)), {}]]

    result = run_second_pass_groups(
        model=object(), clip=object(), sampler=object(),
        sigmas=torch.tensor([0.2, 0.0]),
        video_latents=[video], audio_latents=[audio], assembly_plan=plan,
        refine_seed=123, refine_context=context if with_context else None,
        encode_prompt_fn=encode_prompt,
        clone_model_fn=lambda model, **_kwargs: model,
        adapt_group_conditioning_fn=lambda group, **_kwargs: (
            [[item[0], dict(item[1])] for item in group["conditioning"]],
            {"warnings": ()},
        ),
        latent_builder=lambda v, a: {"video": v, "audio": a},
        sample_fn=lambda **kwargs: kwargs["latent"],
        stream_extractor=lambda sampled: (sampled["video"], sampled["audio"]),
    )
    _refined, output_audio, updated, report = result
    record = updated["second_pass_contract"]["reference_inheritance"][0]
    assert record["status"] == status
    assert record["contract_sha256"] == (route["sha256"] if with_context else None)
    assert output_audio[0] is audio
    assert f"reference_inheritance={status}" in report
    assert calls == ([] if with_context else ["@R4 runs"])
