from __future__ import annotations

import copy
import functools
import hashlib
import json
from pathlib import Path
import shutil
from types import SimpleNamespace

import pytest

from ComfyUI_H3_Continuum_Join import run_storage as storage
from ComfyUI_H3_Continuum_Join.graph_contract import build_upstream_graph_contract
from ComfyUI_H3_Continuum_Join.v3.review_control import (
    GENERATION_MODE_REVIEW, REVIEW_ACTION_CONTINUE, REVIEW_ACTION_REGENERATE_CURRENT,
    ReviewControlError,
)
from . import test_v31_run_storage as signatures
from . import test_v38_review_run_storage as review


def closure(gain):
    def sample(x=None, **kwargs):
        return x * gain
    return sample


@pytest.mark.parametrize("option", [
    "sampler_cfg_function", "sampler_pre_cfg_function", "sampler_post_cfg_function",
    "model_function_wrapper", "denoise_mask_function",
])
def test_model_hook_changes_are_observed(option):
    model = signatures._Model()
    model.model_options[option] = closure(1)
    before, safe = storage._model_signature(model, "base")
    model.model_options[option] = closure(2)
    after, after_safe = storage._model_signature(model, "base")
    assert safe and after_safe
    assert before != after


def test_cfg1_and_internal_join_context():
    model = signatures._Model()
    before, safe = storage._model_signature(model, "base")
    model.model_options["disable_cfg1_optimization"] = True
    after, safe_after = storage._model_signature(model, "base")
    assert safe and safe_after and before != after
    model.model_options["transformer_options"] = {"h3_continuum_join_context": object()}
    join, safe_join = storage._model_signature(model, "base")
    model.model_options["transformer_options"] = {}
    clean, safe_clean = storage._model_signature(model, "base")
    assert safe_join and safe_clean and join == clean


def test_sampler_closure_only_changes_identity_with_graph_unchanged():
    graph, graph_safe, _ = build_upstream_graph_contract(
        signatures._prompt_graph(), "42", require_video_vae=True,
    )
    model, clip, vae = signatures._Model(), signatures._Clip(), signatures._VideoVAE()
    sampler = SimpleNamespace(sampler_function=closure(1), extra_options={}, inpaint_options={})
    kwargs = dict(model=model, clip=clip, video_vae=vae, sampler=sampler,
                  upstream_graph_contract=graph, upstream_graph_safe=graph_safe)
    before, safe, _ = signatures._sampling_contract(**kwargs)
    sampler.sampler_function = closure(2)
    after, after_safe, _ = signatures._sampling_contract(**kwargs)
    assert safe and after_safe
    assert before["global"]["upstream_graph"] == after["global"]["upstream_graph"]
    assert storage.revision_identity(before) != storage.revision_identity(after)
    same, same_safe, _ = signatures._sampling_contract(**kwargs)
    assert same_safe and same == after


def test_sampler_graph_only_changes_identity():
    graph = signatures._prompt_graph()
    before, safe, _ = build_upstream_graph_contract(graph, "42", require_video_vae=True)
    graph["40"]["inputs"]["sampler_name"] = "heun"
    after, after_safe, _ = build_upstream_graph_contract(graph, "42", require_video_vae=True)
    assert safe and after_safe and before != after
    assert before["version"] == after["version"] == 4
    assert before["routes"]["model"] == after["routes"]["model"]


def test_partial_and_bound_method_state_are_observed():
    class Bound:
        def __init__(self, gain):
            self.gain = gain
        def sample(self, value):
            return value * self.gain
    first, safe = storage._observe(functools.partial(Bound(1).sample, 2))
    second, safe_second = storage._observe(functools.partial(Bound(3).sample, 2))
    assert safe and safe_second and first != second


@pytest.mark.parametrize("location", ["wrappers", "patches", "model_options"])
def test_opaque_state_disables_reuse_without_preventing_contract(location):
    class Opaque:
        __slots__ = ("gain",)
        def __init__(self):
            self.gain = 1
        def __call__(self, *args):
            return self.gain
    model = signatures._Model()
    getattr(model, location)["external"] = Opaque()
    contract, safe, reasons = signatures._sampling_contract(model=model)
    assert contract["global"]["sampling_contract_version"] == 6
    assert not safe and reasons


def test_empty_callable_attributes_are_not_complete():
    class Opaque:
        def __call__(self):
            return 1
    _, safe = storage._observe(Opaque())
    assert not safe


def test_observation_bounds_preserve_ordinary_lora_keys_without_weight_traversal():
    _, keys_safe = storage._observe({f"weight.{index}" for index in range(500)})
    _, oversized_safe = storage._observe(list(range(4097)))
    module = signatures._Model().model.diffusion_model
    descriptor, module_safe = storage._observe(module)
    assert keys_safe and not oversized_safe and not module_safe
    assert descriptor["module_state_unobserved"]


def test_signature_failure_is_diagnostic_not_a_generation_stop():
    model = signatures._Model()
    model.model_dtype = lambda: (_ for _ in ()).throw(RuntimeError("custom dtype"))
    contract, safe, reasons = signatures._sampling_contract(model=model)
    assert contract and not safe and reasons


def test_core_euler_sampler_has_an_observable_runtime_signature(require_comfy_core):
    from comfy.samplers import sampler_object
    _, safe = storage._sampler_signature(sampler_object("euler"))
    assert safe


def reader(tmp_path, contract):
    controller = review._controller(tmp_path, contract)
    controller.configure_review(generation_mode=GENERATION_MODE_REVIEW,
                                review_action=REVIEW_ACTION_CONTINUE)
    return controller


@pytest.mark.parametrize("entry_point", ["head", "review", "import", "compatible", "take"])
def test_safe_false_never_adopts_a_prefix(tmp_path, entry_point):
    contract = review._contract(chunks=3)
    source = review._persist(tmp_path, contract, prefix=2, review_unit=(2, 2),
                             updated_utc="2026-10-04T00:00:00+00:00")
    controller = reader(tmp_path, contract)
    original = (source._manifest_path().read_bytes(), (source.run_root / "project.json").read_bytes())
    if entry_point == "head":
        assert controller.find_latest_review_head(contract, resume_safe=False) is None
    elif entry_point == "review":
        assert not controller._load_validated_review_prefix(contract, resume_safe=False).entries
    elif entry_point == "import":
        assert controller._find_plan_import(contract, resume_safe=False) is None
    elif entry_point == "compatible":
        assert controller._compatible_plan_prefix(source.manifest, contract, resume_safe=False) == ([], [])
    else:
        controller.take_group = 2
        controller.take_revision_id = review._project(source)["canonical_head_revision_id"]
        with pytest.raises(storage.RunStorageError, match="unobservable"):
            controller._validated_take_selection(contract, resume_safe=False)
    assert original == (source._manifest_path().read_bytes(), (source.run_root / "project.json").read_bytes())


def test_safe_false_retry_preserves_existing_take(tmp_path):
    contract = review._contract(chunks=3)
    source = review._persist(tmp_path, contract, prefix=2, review_unit=(2, 2),
                             updated_utc="2026-10-04T00:00:00+00:00")
    controller = reader(tmp_path, contract)
    controller.review_action = REVIEW_ACTION_REGENERATE_CURRENT
    before = source._manifest_path().read_bytes()
    with pytest.raises(ReviewControlError, match="could not be matched"):
        controller._load_validated_review_prefix(contract, resume_safe=False)
    assert source._manifest_path().read_bytes() == before


def test_identical_v6_review_and_take_still_reuse(tmp_path):
    contract = review._contract(chunks=3)
    source = review._persist(tmp_path, contract, prefix=2, review_unit=(2, 2),
                             updated_utc="2026-10-04T00:00:00+00:00")
    controller = reader(tmp_path, contract)
    assert len(controller._load_validated_review_prefix(contract, resume_safe=True).entries) == 2
    controller.take_group = 2
    controller.take_revision_id = review._project(source)["canonical_head_revision_id"]
    assert len(controller._validated_take_selection(contract)["entries"]) == 2


def fixture_hashes(root):
    return {str(file.relative_to(root)): hashlib.sha256(file.read_bytes()).hexdigest()
            for file in root.rglob("*") if file.is_file()}


def test_actual_old_code_v5_fixture_readable_and_immutable(tmp_path):
    fixture = Path(__file__).parent / "fixtures" / "v39_sampling_v5"
    before = fixture_hashes(fixture)
    run = tmp_path / "run"
    shutil.copytree(fixture, run)
    controller = storage.RunStorageController("legacy-read")
    controller.run_root = run
    controller.revisions_root = run / "revisions"
    manifests, catalog, chains = controller._provenance_catalog()
    assert len(manifests) == 1 and len(catalog) == 2 and len(chains) == 1
    manifest = next(iter(manifests.values()))
    assert manifest["sampling_contract_version"] == 5
    assert manifest["contract"]["global"]["sampling_contract_version"] == 5
    storage._manifest_sampling_identity(manifest)
    head = controller._validated_review_head(manifest, for_reuse=False)
    assert head["validated_prefix_count"] == 2
    assert len(head["entries"]) == 2
    contract = review._contract(chunks=manifest["contract"]["chunk_count"])
    controller.prompts = [""] * contract["chunk_count"]
    assert controller.find_latest_review_head(contract) is None
    assert controller._compatible_plan_prefix(manifest, contract) == ([], [])
    assert controller._find_plan_import(contract) is None
    controller.take_group = 2
    controller.take_revision_id = head["manifest"]["branch_provenance"]["active_chain"][-1]
    with pytest.raises(storage.RunStorageError, match="read-only"):
        controller._validated_take_selection(contract, source_lineage=manifest["contract"]["nonce_lineage_sha256"])
    assert fixture_hashes(fixture) == before
    assert fixture_hashes(run) == before
