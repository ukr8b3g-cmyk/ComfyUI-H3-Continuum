from __future__ import annotations

import hashlib
from types import SimpleNamespace

import pytest
import torch

from ComfyUI_H3_Continuum_Join.run_storage import (
    REVIEW_CONTROL_VERSION,
    RUN_STORAGE_SCHEMA_VERSION,
    SAMPLING_CONTRACT_VERSION,
    RunStorageController,
    RunStorageError,
    _apply_reroll_branch_contract,
    _nonce_lineage_hash,
    _review_contract_mismatches,
    _storage_revision_identity,
    revision_identity,
)
from ComfyUI_H3_Continuum_Join.branch_provenance import (
    TAKE_ACTION_CONTINUE,
    TAKE_ACTION_USE,
    physical_groups,
)
from ComfyUI_H3_Continuum_Join.state import make_plan
from ComfyUI_H3_Continuum_Join.v2.seeds import derive_chunk_seed
from ComfyUI_H3_Continuum_Join.v2.session import make_chunk_entry, make_session
from ComfyUI_H3_Continuum_Join.v2 import session_io
from ComfyUI_H3_Continuum_Join.v2.sequence import _preserved_prefix
from ComfyUI_H3_Continuum_Join.reference import REFERENCE_SIZE_MATCH_OUTPUT
from ComfyUI_H3_Continuum_Join.v3.reference_routing import (
    REFERENCE_SLOT_IDS, compile_reference_routing_schedule,
)
from ComfyUI_H3_Continuum_Join.v3.reference_runtime import (
    ReferenceInputSet, ReferenceRoutingRuntime,
)
from ComfyUI_H3_Continuum_Join.v3.reference_storage_contract import (
    build_reference_storage_plan, routed_session_identity, session_routing_settings,
)
from ComfyUI_H3_Continuum_Join.v3.nodes import (
    H3ContinuumSamplerProduction,
    H3ContinuumSamplerV3,
    PROJECTION_CURRENT_REVIEW_UNIT,
    PROJECTION_FULL_ACCEPTED_PREFIX,
    _apply_review_decode_scope,
    _review_decode_chunk_range,
    resolve_projection_decision,
)
from ComfyUI_H3_Continuum_Join.v3.plan import prepare_physical_decode_entries
from ComfyUI_H3_Continuum_Join.v3.review_control import (
    GENERATION_MODE_FULL_RUN,
    GENERATION_MODE_REVIEW,
    REVIEW_ACTION_CONTINUE,
    REVIEW_ACTION_FINISH_REMAINING,
    REVIEW_ACTION_REGENERATE_CURRENT,
    REVISION_STATUS_COMPLETE,
    REVISION_STATUS_IN_PROGRESS,
    REVISION_STATUS_INTERRUPTED,
    REVISION_STATUS_REVIEW_READY,
    ReviewControlError,
)


class _Nested:
    def __init__(self, parts):
        self.parts = parts

    def unbind(self):
        return self.parts


def _prompt_hashes(chunks: int, tag: str = "base") -> list[str]:
    return [
        hashlib.sha256(f"{tag}-prompt-{index + 1}".encode("utf-8")).hexdigest()
        for index in range(chunks)
    ]


def _contract(
    *,
    chunks: int = 6,
    boundary: int = 0,
    nonce: int = 0,
    terminal: bool = False,
    prompt_tag: str = "base",
    reference_tag: str | None = None,
    driving_tag: str | None = None,
) -> dict:
    global_contract = {
        "sampling_contract_version": SAMPLING_CONTRACT_VERSION,
        "runtime_signature_version": 1,
        "conditioning_mode": "t2va",
        "width": 96,
        "height": 64,
        "chunk_seconds": 5.0,
        "continuity": "Balanced — 22 frames",
        "audio_continuity": True,
        "base_seed": 1234,
    }
    if terminal:
        global_contract["execution_semantics"] = {
            "flf_execution": "terminal_merged_10s_seed_v2",
            "terminal_seed_policy": "terminal_pair_seed_v2",
        }
    if reference_tag is not None:
        global_contract["reference"] = {"identity": reference_tag}
    if driving_tag is not None:
        global_contract["driving_audio"] = {"identity": driving_tag}
    contract = {
        "global": global_contract,
        "chunk_count": int(chunks),
        "prompt_mode": "Fixed",
        "prompt_hashes": _prompt_hashes(chunks, prompt_tag),
        "reroll_from_chunk": int(boundary),
        "last_frame_hash": "",
    }
    contract["nonce_lineage_sha256"] = _nonce_lineage_hash(contract)
    return _apply_reroll_branch_contract(
        contract,
        boundary=boundary,
        requested_nonce=nonce,
        effective_nonce=nonce,
    )


def _entry(position: int, contract: dict):
    continuation = position > 0
    plan = make_plan(
        continuation=continuation,
        clip_index=position + 1,
        total_frames=141 if continuation else 124,
        trim_frames=22 if continuation else 0,
        width=96,
        height=64,
        context_frames=22 if continuation else 0,
        state_capacity_frames=39,
        requested_extend_seconds=5,
        debug=False,
    )
    return make_chunk_entry(
        latent={
            "samples": _Nested(
                (
                    torch.full(
                        (1, 24, 42 if continuation else 37, 2, 2),
                        float(position),
                    ),
                    torch.full(
                        (1, 32, 2, 235 if continuation else 207),
                        float(position),
                    ),
                )
            )
        },
        plan=plan,
        prompt=f"prompt {position + 1}",
        prompt_hash=contract["prompt_hashes"][position],
        seed=derive_chunk_seed(
            int(contract["global"]["base_seed"]),
            position,
            int(contract["effective_reroll_nonce"])
            if int(contract["reroll_from_chunk"]) > 0
            and position + 1 >= int(contract["reroll_from_chunk"])
            else 0,
        ),
        context_frames=22 if continuation else 0,
        motion_score=float(position),
        reused=False,
    )


def _controller(tmp_path, contract: dict) -> RunStorageController:
    controller = RunStorageController("phase-d-review")
    controller.run_root = tmp_path / "run"
    controller.revisions_root = controller.run_root / "revisions"
    controller.contract = contract
    controller.revision_id, controller.contract_sha256 = revision_identity(contract)
    controller.revision_root = controller.revisions_root / controller.revision_id
    controller.prompts = [f"prompt {index + 1}" for index in range(contract["chunk_count"])]
    controller.effective_reroll_nonce = int(contract["effective_reroll_nonce"])
    lifecycle = dict(contract["nonce_lifecycle"])
    controller.manifest = {
        "run_storage_schema_version": RUN_STORAGE_SCHEMA_VERSION,
        "sampling_contract_version": SAMPLING_CONTRACT_VERSION,
        "run_name": controller.run_name,
        "revision_id": controller.revision_id,
        "contract_sha256": controller.contract_sha256,
        "contract": contract,
        "resume_safe": True,
        "resume_disabled_reasons": [],
        "nonce_lifecycle": lifecycle,
        "status": REVISION_STATUS_IN_PROGRESS,
        "created_utc": "2026-08-31T00:00:00+00:00",
        "updated_utc": "2026-08-31T00:00:00+00:00",
        "chunks": [],
        "report_summary": "",
    }
    return controller


def _persist(
    tmp_path,
    contract: dict,
    *,
    prefix: int,
    review_unit: tuple[int, int] | None,
    updated_utc: str,
) -> RunStorageController:
    controller = _controller(tmp_path, contract)
    entries = [_entry(position, contract) for position in range(prefix)]
    terminal = bool(
        ((contract.get("global") or {}).get("execution_semantics") or {}).get(
            "flf_execution"
        ) == "terminal_merged_10s_seed_v2"
    )
    for group in physical_groups(
        chunks=int(contract["chunk_count"]),
        terminal_merge_enabled=terminal,
    ):
        if group.end > prefix:
            break
        positions = tuple(range(group.start - 1, group.end))
        controller.commit_group(
            tuple(entries[position] for position in positions),
            positions=positions,
        )
    if review_unit is not None:
        start, end = review_unit
        controller.review_generation_mode = GENERATION_MODE_REVIEW
        controller.review_execution = SimpleNamespace(
            max_new_physical_groups=1,
            next_review_unit_start=start,
            next_review_unit_end=end,
            next_review_physical_group=start,
        )
        controller.mark_review_group(
            start=start,
            end=end,
            physical_group=start,
        )
    controller.finalize(
        session={"session_id": f"session-{controller.revision_id}", "chunks": entries},
        report="phase d test",
        review_pause_metadata=controller.review_pause_metadata(),
    )
    controller.manifest["updated_utc"] = updated_utc
    controller._write_manifest()
    return controller


def _resolve(
    tmp_path,
    contract: dict,
    *,
    generation_mode: str = GENERATION_MODE_REVIEW,
    review_action: str = REVIEW_ACTION_CONTINUE,
    take_action: str = "Automatic",
    take_group: int = 0,
    take_revision_id: str = "",
    manual_regenerate_from: int = 0,
):
    controller = RunStorageController("phase-d-review")
    controller.run_root = tmp_path / "run"
    controller.revisions_root = controller.run_root / "revisions"
    controller.prompts = [f"prompt {index + 1}" for index in range(contract["chunk_count"])]
    controller.contract = contract
    controller.configure_review(
        generation_mode=generation_mode,
        review_action=review_action,
        manual_regenerate_from=manual_regenerate_from,
        take_action=take_action,
        take_group=take_group,
        take_revision_id=take_revision_id,
    )
    resolved, nonce, decision = controller._resolve_review_contract(
        contract,
        requested_nonce=0,
        resume_safe=True,
    )
    return controller, resolved, nonce, decision


def _project(controller: RunStorageController) -> dict:
    import json

    return json.loads((controller.run_root / "project.json").read_text(encoding="utf-8"))


def test_review_mismatch_diagnostic_reports_runtime_section_not_values():
    import copy

    stored = _contract()
    stored["global"]["model"] = {
        "runtime": {"weight_probe": [{"sample": "private-old-value"}], "patches": {}},
        "graph_route": {"model": "unchanged"},
    }
    current = copy.deepcopy(stored)
    current["global"]["model"]["runtime"]["weight_probe"][0]["sample"] = "private-new-value"
    before = copy.deepcopy((stored, current))
    rng = torch.random.get_rng_state().clone()
    differences = _review_contract_mismatches(stored, current)
    assert len(differences) == 1
    assert differences[0].startswith("global.model.runtime.weight_probe: saved=")
    assert "private" not in differences[0]
    assert (stored, current) == before
    assert torch.equal(torch.random.get_rng_state(), rng)


def test_retry_mismatched_head_explains_failure_without_reusing_or_writing(tmp_path):
    import copy

    stored = _contract()
    controller = _persist(
        tmp_path, stored, prefix=1, review_unit=(1, 1),
        updated_utc="2026-09-07T00:00:00+00:00",
    )
    before = {p: p.read_bytes() for p in controller.run_root.rglob("*") if p.is_file()}
    current = copy.deepcopy(stored)
    current["global"]["base_seed"] += 1
    current["nonce_lineage_sha256"] = _nonce_lineage_hash(current)
    with pytest.raises(ReviewControlError, match="existing reviewed unit") as error:
        _resolve(tmp_path, current, review_action=REVIEW_ACTION_REGENERATE_CURRENT)
    assert "global.base_seed: saved=" in str(error.value)
    assert controller.revision_id in str(error.value)
    assert before == {p: p.read_bytes() for p in controller.run_root.rglob("*") if p.is_file()}


def test_retry_without_any_saved_run_explains_missing_head(tmp_path):
    with pytest.raises(ReviewControlError, match="No compatible saved review head"):
        _resolve(tmp_path, _contract(), review_action=REVIEW_ACTION_REGENERATE_CURRENT)
    assert not (tmp_path / "run").exists()


def test_review_mismatch_diagnostic_ignores_derived_nonce_and_unchanged_contract():
    import copy

    stored = _contract()
    current = copy.deepcopy(stored)
    current["effective_reroll_nonce"] = 99
    assert _review_contract_mismatches(stored, current) == []


def test_matching_retry_does_not_run_mismatch_diagnostic(tmp_path, monkeypatch):
    import ComfyUI_H3_Continuum_Join.run_storage as storage

    contract = _contract()
    _persist(tmp_path, contract, prefix=1, review_unit=(1, 1),
             updated_utc="2026-09-07T00:00:00+00:00")

    def unexpected(*args, **kwargs):
        pytest.fail("Compatible retry must not execute mismatch diagnostics")

    monkeypatch.setattr(storage, "_review_contract_mismatches", unexpected)
    controller, _, nonce, _ = _resolve(
        tmp_path, contract, review_action=REVIEW_ACTION_REGENERATE_CURRENT,
    )
    assert controller.review_head["validated_prefix_count"] == 1
    assert nonce == 1


def _take(project: dict, *, group: int, nonce: int) -> dict:
    return next(
        revision
        for revision in project["group_revisions"]
        if int(revision["group"]["physical_group"]) == group
        and int(revision["variation_nonce"]) == nonce
    )


def _rr_r5_contract(*, changed_group: int = 0) -> dict:
    selectors = {slot: "off" for slot in REFERENCE_SLOT_IDS}
    selectors["R1"] = "all" if not changed_group else ",".join(
        str(index) for index in range(1, 5) if index != changed_group
    )
    if changed_group:
        selectors["R4"] = str(changed_group)
    routing = ReferenceRoutingRuntime(
        schedule=compile_reference_routing_schedule(
            total_chunks=4, terminal_merge_enabled=False,
            mode="Custom", selectors_by_slot=selectors,
        ),
        inputs=ReferenceInputSet(
            (torch.full((1, 64, 64, 3), 0.1), None, None,
             torch.full((1, 64, 64, 3), 0.4), *([None] * 5)),
            96, 64, REFERENCE_SIZE_MATCH_OUTPUT,
        ),
    )
    plan = build_reference_storage_plan(
        runtime=routing, prompts=[f"prompt {index}" for index in range(1, 5)],
        first_frame_hash="none", last_frame_hash="none",
    )
    contract = _contract(chunks=4)
    contract["global"]["reference_routing_contract_version"] = 1
    contract["reference_group_contracts"] = plan.group_contracts
    contract["nonce_lineage_sha256"] = _nonce_lineage_hash(contract)
    return _apply_reroll_branch_contract(
        contract, boundary=0, requested_nonce=0, effective_nonce=0,
    )


def test_rr_r5_selected_foreign_take_requires_whole_compatible_prefix(tmp_path):
    source = _persist(
        tmp_path, _rr_r5_contract(), prefix=2, review_unit=(2, 2),
        updated_utc="2026-09-24T00:00:00+00:00",
    )
    selected = _take(_project(source), group=2, nonce=0)
    controller, resolved, _, decision = _resolve(
        tmp_path, _rr_r5_contract(changed_group=4),
        take_action=TAKE_ACTION_USE, take_group=2,
        take_revision_id=selected["revision_id"],
    )
    assert decision == "select_take"
    assert controller.review_runtime_metrics["review_decision_created"] == 1
    assert controller._plan_import is not None
    assert controller.selected_take_chain == []
    assert len(controller.validated_prefix.entries) == 2
    assert resolved["nonce_lineage_sha256"] != source.contract["nonce_lineage_sha256"]
    assert source.manifest["chunks"][0]["storage_revision_id"] == source.revision_id
    controller.contract = resolved
    sampling_revision_id, controller.contract_sha256 = revision_identity(resolved)
    controller.revision_id = controller.storage_revision_id_override
    controller.revision_root = controller.revisions_root / controller.revision_id
    controller.manifest = {
        "run_storage_schema_version": RUN_STORAGE_SCHEMA_VERSION,
        "sampling_contract_version": SAMPLING_CONTRACT_VERSION,
        "run_name": controller.run_name,
        "revision_id": controller.revision_id,
        "sampling_revision_id": sampling_revision_id,
        "contract_sha256": controller.contract_sha256,
        "contract": resolved,
        "nonce_lifecycle": dict(resolved["nonce_lifecycle"]),
        "status": REVISION_STATUS_IN_PROGRESS,
        "created_utc": "2026-09-24T01:00:00+00:00",
        "updated_utc": "2026-09-24T01:00:00+00:00",
        "chunks": [],
    }
    controller._write_manifest()
    controller.resume_safe = True
    imported = controller._adopt_plan_prefix(controller._plan_import)
    assert len(imported) == 2
    assert all(record["storage_revision_id"] == controller.revision_id for record in imported)
    assert controller.manifest["prefix_import"]["selected_take"]["revision_id"] == selected["revision_id"]
    assert controller.pending_branch_cut["selected_revision_id"] != selected["revision_id"]
    controller.finalize(
        session={"session_id": "routed-take", "chunks": list(controller.validated_prefix.entries)},
        report="routed Take import", review_pause_metadata=controller.review_pause_metadata(),
    )
    assert controller.manifest["status"] == REVISION_STATUS_REVIEW_READY
    assert source.manifest["chunks"][0]["storage_revision_id"] == source.revision_id


def test_rr_r5_selected_foreign_take_rejects_changed_group_without_fallback(tmp_path):
    source = _persist(
        tmp_path, _rr_r5_contract(), prefix=2, review_unit=(2, 2),
        updated_utc="2026-09-24T00:00:00+00:00",
    )
    selected = _take(_project(source), group=2, nonce=0)
    with pytest.raises(RunStorageError, match="physical group starting with chunk 2"):
        _resolve(
            tmp_path, _rr_r5_contract(changed_group=2),
            take_action=TAKE_ACTION_USE, take_group=2,
            take_revision_id=selected["revision_id"],
        )


def test_rr_r5_explicit_session_keeps_only_compatible_complete_groups(tmp_path, monkeypatch):
    old = _rr_r5_contract()
    current = _rr_r5_contract(changed_group=2)
    old_plan = SimpleNamespace(group_contracts=old["reference_group_contracts"],
                               routing_config_sha256="a" * 64)
    current_plan = SimpleNamespace(group_contracts=current["reference_group_contracts"])
    identity = routed_session_identity("base")
    saved = make_session(
        chunks=[_entry(index, old) for index in range(3)],
        width=32, height=32, chunk_seconds=5.0,
        identity_hash=identity, model_fingerprint_value="f" * 64,
        parent_session_id=None, reroll_from_chunk=0,
        settings={"reference_routing_v1": session_routing_settings(old_plan, 3)},
    )
    monkeypatch.setattr(session_io, "session_directory", lambda: tmp_path)
    session_io.save_session(saved, prefix="rr-r5", slot=1)
    saved = session_io.load_session(prefix="rr-r5", slot=1)
    preserved, notes = _preserved_prefix(
        session=saved, prompt_hashes=current["prompt_hashes"], chunks=4,
        reroll_from_chunk=0, width=32, height=32, chunk_seconds=5.0,
        identity_hash=identity, last_frame_hash="none",
        reference_storage_plan=current_plan,
    )
    assert len(preserved) == 1
    assert any("Reference group changed" in note for note in notes)


def test_rr_r5_plan_import_stops_at_first_changed_physical_group(tmp_path):
    source = _persist(
        tmp_path, _rr_r5_contract(), prefix=3, review_unit=(3, 3),
        updated_utc="2026-09-24T00:00:00+00:00",
    )
    destination = RunStorageController("phase-d-review")
    destination.run_root = source.run_root
    destination.revisions_root = source.revisions_root
    destination.prompts = [f"prompt {index}" for index in range(1, 5)]
    current = _rr_r5_contract(changed_group=3)
    imported = destination._find_plan_import(current)
    assert imported is not None
    assert imported["validated_prefix_count"] == 2
    assert [record["sequence_index"] for record in imported["records"]] == [0, 1]
    assert imported["revision_id"] == source.revision_id


def test_rr_r5_review_decision_uses_fixed_imported_prefix_once(tmp_path):
    source = _persist(
        tmp_path, _rr_r5_contract(), prefix=2, review_unit=(2, 2),
        updated_utc="2026-09-24T00:00:00+00:00",
    )
    controller, resolved, _, decision = _resolve(
        tmp_path, _rr_r5_contract(changed_group=3),
        review_action=REVIEW_ACTION_CONTINUE,
    )
    assert controller._plan_import is not None
    assert len(controller.validated_prefix.entries) == 2
    assert controller.review_runtime_metrics["review_decision_created"] == 1
    assert controller.review_runtime_metrics["review_reconcile"] == 0
    assert controller.review_execution.next_review_unit_start == 3
    assert resolved["nonce_lineage_sha256"] != source.contract["nonce_lineage_sha256"]
    assert decision == "inactive"


def test_rr_r5_foreign_take_preserves_verified_nonce_variation(tmp_path):
    source_contract = _apply_reroll_branch_contract(
        _rr_r5_contract(), boundary=3,
        requested_nonce=1, effective_nonce=1,
    )
    source = _persist(
        tmp_path, source_contract, prefix=3, review_unit=(3, 3),
        updated_utc="2026-09-24T00:00:00+00:00",
    )
    selected = _take(_project(source), group=3, nonce=1)
    controller, resolved, nonce, decision = _resolve(
        tmp_path, _rr_r5_contract(changed_group=4),
        take_action=TAKE_ACTION_USE, take_group=3,
        take_revision_id=selected["revision_id"],
    )
    assert decision == "select_take"
    assert (resolved["reroll_from_chunk"], nonce) == (3, 1)
    assert len(controller.validated_prefix.entries) == 3
    assert controller._plan_import is not None


def _persist_resolved_branch(
    controller: RunStorageController,
    contract: dict,
    *,
    new_positions: tuple[int, ...],
) -> RunStorageController:
    controller.contract = contract
    sampling_revision_id, controller.contract_sha256 = revision_identity(contract)
    controller.revision_id = controller.storage_revision_id_override
    controller.revision_root = controller.revisions_root / controller.revision_id
    controller.effective_reroll_nonce = int(contract["effective_reroll_nonce"])
    controller.manifest = {
        "run_storage_schema_version": RUN_STORAGE_SCHEMA_VERSION,
        "sampling_contract_version": SAMPLING_CONTRACT_VERSION,
        "run_name": controller.run_name,
        "revision_id": controller.revision_id,
        "sampling_revision_id": sampling_revision_id,
        "contract_sha256": controller.contract_sha256,
        "contract": contract,
        "resume_safe": True,
        "resume_disabled_reasons": [],
        "nonce_lifecycle": dict(contract["nonce_lifecycle"]),
        "status": REVISION_STATUS_IN_PROGRESS,
        "created_utc": "2026-09-03T01:00:00+00:00",
        "updated_utc": "2026-09-03T01:00:00+00:00",
        "chunks": list(controller.selected_take_records),
        "report_summary": "",
        "review_control_version": REVIEW_CONTROL_VERSION,
        "branch_regenerate_from": int(contract["reroll_from_chunk"]),
        "effective_reroll_nonce": int(contract["effective_reroll_nonce"]),
        "branch_provenance": {
            "version": 1,
            "active_chain": [
                item["revision_id"] for item in controller.selected_take_chain
            ],
            "selection": {
                "action": controller.take_action,
                "revision_id": controller.take_revision_id,
                "physical_group": controller.take_group,
            },
            "branch_cut": dict(controller.pending_branch_cut or {}),
        },
    }
    entries = list(controller.selected_take_revision["entries"])
    for position in new_positions:
        entry = _entry(position, contract)
        entries.append(entry)
        controller.commit_chunk(entry, position=position)
    if new_positions:
        start = new_positions[0] + 1
        end = new_positions[-1] + 1
        controller.mark_review_group(
            start=start,
            end=end,
            physical_group=start,
        )
    controller.finalize(
        session={"session_id": "branch-session", "chunks": entries},
        report="branch",
        review_pause_metadata=controller.review_pause_metadata(),
    )
    return controller


def test_l0_partial_normal_completion_becomes_review_ready(tmp_path):
    controller = _persist(
        tmp_path,
        _contract(),
        prefix=1,
        review_unit=(1, 1),
        updated_utc="2026-08-31T00:00:01+00:00",
    )
    assert controller.manifest["status"] == REVISION_STATUS_REVIEW_READY
    assert controller.manifest["review_unit"] == {
        "start": 1,
        "end": 1,
        "physical_group": 1,
    }
    assert controller.manifest["review_pause_reason"] == "review_each_chunk"
    assert controller.manifest["review_control_version"] == REVIEW_CONTROL_VERSION


def test_l1_full_completion_is_complete_and_keeps_latest_review_unit(tmp_path):
    controller = _persist(
        tmp_path,
        _contract(chunks=3),
        prefix=3,
        review_unit=(3, 3),
        updated_utc="2026-08-31T00:00:01+00:00",
    )
    assert controller.manifest["status"] == REVISION_STATUS_COMPLETE
    assert controller.manifest["review_unit"]["start"] == 3


def test_l2_incomplete_without_intentional_pause_is_interrupted(tmp_path):
    controller = _persist(
        tmp_path,
        _contract(),
        prefix=1,
        review_unit=None,
        updated_utc="2026-08-31T00:00:01+00:00",
    )
    assert controller.manifest["status"] == REVISION_STATUS_INTERRUPTED
    assert "review_unit" not in controller.manifest


def test_l3_commit_keeps_manifest_in_progress(tmp_path):
    contract = _contract()
    controller = _controller(tmp_path, contract)
    controller.commit_chunk(_entry(0, contract), position=0)
    assert controller.manifest["status"] == REVISION_STATUS_IN_PROGRESS
    persisted = controller._manifest_path().read_text(encoding="utf-8")
    assert '"status": "in_progress"' in persisted


def test_l4_review_ready_is_reloaded_as_validated_head(tmp_path):
    contract = _contract()
    original = _persist(
        tmp_path,
        contract,
        prefix=2,
        review_unit=(2, 2),
        updated_utc="2026-08-31T00:00:02+00:00",
    )
    reloaded, _, _, _ = _resolve(tmp_path, contract)
    assert reloaded.review_head["revision_id"] == original.revision_id
    assert reloaded.review_head["validated_prefix_count"] == 2


def test_n0_n2_three_consecutive_regenerates_advance_nonce_and_seed(tmp_path):
    base = _contract()
    _persist(
        tmp_path,
        base,
        prefix=2,
        review_unit=(2, 2),
        updated_utc="2026-08-31T00:00:01+00:00",
    )
    nonces = []
    seeds = []
    for variation in (1, 2, 3):
        _, resolved, nonce, _ = _resolve(
            tmp_path,
            base,
            review_action=REVIEW_ACTION_REGENERATE_CURRENT,
        )
        assert resolved["reroll_from_chunk"] == 2
        assert nonce == variation
        nonces.append(nonce)
        seeds.append(derive_chunk_seed(1234, 1, nonce))
        _persist(
            tmp_path,
            resolved,
            prefix=2,
            review_unit=(2, 2),
            updated_utc=f"2026-08-31T00:00:0{variation + 1}+00:00",
        )
    assert nonces == [1, 2, 3]
    assert len(set(seeds)) == 3


def test_n3_continue_after_nonce_two_keeps_branch_and_nonce(tmp_path):
    branch = _contract(boundary=2, nonce=2)
    _persist(
        tmp_path,
        branch,
        prefix=2,
        review_unit=(2, 2),
        updated_utc="2026-08-31T00:00:03+00:00",
    )
    _, resolved, nonce, _ = _resolve(tmp_path, _contract())
    assert (resolved["reroll_from_chunk"], nonce) == (2, 2)


def test_complete_three_chunk_run_can_start_fresh_review_and_advance_one_chunk(
    tmp_path,
):
    base = _contract(chunks=3)
    _persist(
        tmp_path,
        base,
        prefix=3,
        review_unit=(3, 3),
        updated_utc="2026-08-31T00:00:01+00:00",
    )

    first, chunk_1, nonce_1, _ = _resolve(
        tmp_path,
        base,
        manual_regenerate_from=1,
    )
    assert (chunk_1["reroll_from_chunk"], nonce_1) == (1, 1)
    assert first.review_execution.max_new_physical_groups == 1
    assert (
        first.review_execution.next_review_unit_start,
        first.review_execution.next_review_unit_end,
    ) == (1, 1)
    _persist(
        tmp_path,
        chunk_1,
        prefix=1,
        review_unit=(1, 1),
        updated_utc="2026-08-31T00:00:02+00:00",
    )

    second, chunk_2, nonce_2, _ = _resolve(tmp_path, base)
    assert (chunk_2["reroll_from_chunk"], nonce_2) == (1, 1)
    assert (
        second.review_execution.next_review_unit_start,
        second.review_execution.next_review_unit_end,
    ) == (2, 2)
    _persist(
        tmp_path,
        chunk_2,
        prefix=2,
        review_unit=(2, 2),
        updated_utc="2026-08-31T00:00:03+00:00",
    )

    third, chunk_3, nonce_3, _ = _resolve(tmp_path, base)
    assert (chunk_3["reroll_from_chunk"], nonce_3) == (1, 1)
    assert (
        third.review_execution.next_review_unit_start,
        third.review_execution.next_review_unit_end,
    ) == (3, 3)
    complete = _persist(
        tmp_path,
        chunk_3,
        prefix=3,
        review_unit=(3, 3),
        updated_utc="2026-08-31T00:00:04+00:00",
    )
    assert complete.manifest["status"] == REVISION_STATUS_COMPLETE


def test_n4_interrupted_nonce_two_resume_does_not_advance(tmp_path):
    branch = _contract(boundary=2, nonce=2)
    _persist(
        tmp_path,
        branch,
        prefix=2,
        review_unit=None,
        updated_utc="2026-08-31T00:00:03+00:00",
    )
    _, resolved, nonce, _ = _resolve(tmp_path, _contract())
    assert (resolved["reroll_from_chunk"], nonce) == (2, 2)


def test_n5_finish_remaining_keeps_current_branch_nonce(tmp_path):
    branch = _contract(boundary=2, nonce=2)
    _persist(
        tmp_path,
        branch,
        prefix=3,
        review_unit=(3, 3),
        updated_utc="2026-08-31T00:00:03+00:00",
    )
    controller, resolved, nonce, _ = _resolve(
        tmp_path,
        _contract(),
        review_action=REVIEW_ACTION_FINISH_REMAINING,
    )
    assert (resolved["reroll_from_chunk"], nonce) == (2, 2)
    assert controller.review_execution.max_new_physical_groups is None


def test_finish_remaining_complete_records_the_final_generated_group(tmp_path):
    contract = _contract(chunks=6, boundary=2, nonce=2)
    controller = _controller(tmp_path, contract)
    controller.review_generation_mode = GENERATION_MODE_REVIEW
    controller.review_execution = SimpleNamespace(max_new_physical_groups=None)
    entries = []
    for position in range(6):
        entry = _entry(position, contract)
        entries.append(entry)
        controller.commit_chunk(entry, position=position)
        if position >= 3:
            controller.mark_review_group(
                start=position + 1,
                end=position + 1,
                physical_group=position + 1,
            )
    controller.finalize(
        session={"session_id": "finish", "chunks": entries},
        report="finish",
        review_pause_metadata=controller.review_pause_metadata(),
    )
    assert controller.manifest["status"] == REVISION_STATUS_COMPLETE
    assert controller.manifest["review_unit"] == {
        "start": 6,
        "end": 6,
        "physical_group": 6,
    }


def test_full_run_complete_does_not_create_review_unit(tmp_path):
    contract = _contract(chunks=3, boundary=2, nonce=2)
    controller = _controller(tmp_path, contract)
    controller.review_generation_mode = GENERATION_MODE_FULL_RUN
    controller.review_execution = SimpleNamespace(max_new_physical_groups=None)
    controller.inherited_review_unit = {
        "start": 2,
        "end": 2,
        "physical_group": 2,
    }
    entries = []
    for position in range(3):
        entry = _entry(position, contract)
        entries.append(entry)
        controller.commit_chunk(entry, position=position)
        controller.mark_review_group(
            start=position + 1,
            end=position + 1,
            physical_group=position + 1,
        )
    assert controller.review_pause_metadata() is None
    controller.finalize(
        session={"session_id": "full", "chunks": entries},
        report="full",
        review_pause_metadata=None,
    )
    assert controller.manifest["status"] == REVISION_STATUS_COMPLETE
    assert "review_unit" not in controller.manifest


def test_b0_canonical_head_prefers_highest_valid_nonce(tmp_path):
    _persist(
        tmp_path,
        _contract(boundary=2, nonce=1),
        prefix=2,
        review_unit=(2, 2),
        updated_utc="2026-08-31T00:00:02+00:00",
    )
    latest = _persist(
        tmp_path,
        _contract(boundary=2, nonce=2),
        prefix=2,
        review_unit=(2, 2),
        updated_utc="2026-08-31T00:00:03+00:00",
    )
    controller, _, _, _ = _resolve(tmp_path, _contract())
    assert controller.review_head["revision_id"] == latest.revision_id


def test_b1_corrupt_newest_branch_falls_back_to_latest_valid_head(tmp_path):
    fallback = _persist(
        tmp_path,
        _contract(boundary=2, nonce=1),
        prefix=2,
        review_unit=(2, 2),
        updated_utc="2026-08-31T00:00:02+00:00",
    )
    corrupt = _persist(
        tmp_path,
        _contract(boundary=2, nonce=2),
        prefix=2,
        review_unit=(2, 2),
        updated_utc="2026-08-31T00:00:03+00:00",
    )
    record = corrupt.manifest["chunks"][-1]
    target = corrupt.revision_root / "chunks" / record["filename"]
    payload = bytearray(target.read_bytes())
    payload[-1] ^= 1
    target.write_bytes(payload)

    controller, _, nonce, _ = _resolve(tmp_path, _contract())
    assert controller.review_head["revision_id"] == fallback.revision_id
    assert nonce == 1
    assert any("rejected" in note for note in controller.notes)


@pytest.mark.parametrize(
    "different",
    (
        _contract(prompt_tag="other"),
        _contract(reference_tag="other-reference"),
        _contract(driving_tag="other-driving"),
    ),
)
def test_b2_b4_incompatible_prompt_reference_or_driving_lineage_is_excluded(
    tmp_path,
    different,
):
    _persist(
        tmp_path,
        _contract(),
        prefix=2,
        review_unit=(2, 2),
        updated_utc="2026-08-31T00:00:02+00:00",
    )
    controller = RunStorageController("phase-d-review")
    controller.run_root = tmp_path / "run"
    controller.revisions_root = controller.run_root / "revisions"
    controller.prompts = [
        f"prompt {index + 1}" for index in range(different["chunk_count"])
    ]
    assert controller.find_latest_review_head(different) is None


def test_terminal_merge_review_and_consecutive_regenerate_are_atomic(tmp_path):
    base = _contract(chunks=3, terminal=True)
    first = _persist(
        tmp_path,
        base,
        prefix=1,
        review_unit=(1, 1),
        updated_utc="2026-08-31T00:00:01+00:00",
    )
    controller, resolved, nonce, _ = _resolve(tmp_path, base)
    execution = controller.review_execution
    assert first.manifest["status"] == REVISION_STATUS_REVIEW_READY
    assert (execution.next_review_unit_start, execution.next_review_unit_end) == (2, 3)
    assert nonce == 0

    complete = _persist(
        tmp_path,
        resolved,
        prefix=3,
        review_unit=(2, 3),
        updated_utc="2026-08-31T00:00:02+00:00",
    )
    assert complete.manifest["status"] == REVISION_STATUS_COMPLETE
    assert complete.manifest["review_unit"] == {
        "start": 2,
        "end": 3,
        "physical_group": 2,
    }

    _, first_regen, nonce1, _ = _resolve(
        tmp_path,
        base,
        review_action=REVIEW_ACTION_REGENERATE_CURRENT,
    )
    assert (first_regen["reroll_from_chunk"], nonce1) == (2, 1)
    _persist(
        tmp_path,
        first_regen,
        prefix=3,
        review_unit=(2, 3),
        updated_utc="2026-08-31T00:00:03+00:00",
    )
    _, second_regen, nonce2, _ = _resolve(
        tmp_path,
        base,
        review_action=REVIEW_ACTION_REGENERATE_CURRENT,
    )
    assert (second_regen["reroll_from_chunk"], nonce2) == (2, 2)


def test_terminal_merge_head_rejects_a_single_logical_half(tmp_path):
    contract = _contract(chunks=3, terminal=True)
    stored = _persist(
        tmp_path,
        contract,
        prefix=3,
        review_unit=(2, 3),
        updated_utc="2026-08-31T00:00:02+00:00",
    )
    stored.manifest["review_unit"] = {
        "start": 3,
        "end": 3,
        "physical_group": 3,
    }
    stored._write_manifest()
    controller = RunStorageController("phase-d-review")
    controller.run_root = tmp_path / "run"
    controller.revisions_root = controller.run_root / "revisions"
    controller.prompts = ["prompt 1", "prompt 2", "prompt 3"]
    assert controller.find_latest_review_head(
        contract,
        smart_regenerate_only=True,
    ) is None
    assert any("atomic Terminal Merge" in note for note in controller.notes)


def test_restart_restores_continue_regenerate_finish_and_full_branch(tmp_path):
    branch = _contract(boundary=2, nonce=2)
    _persist(
        tmp_path,
        branch,
        prefix=3,
        review_unit=(3, 3),
        updated_utc="2026-08-31T00:00:03+00:00",
    )
    for action, expected_boundary, expected_nonce in (
        (REVIEW_ACTION_CONTINUE, 2, 2),
        (REVIEW_ACTION_REGENERATE_CURRENT, 3, 3),
        (REVIEW_ACTION_FINISH_REMAINING, 2, 2),
    ):
        _, resolved, nonce, _ = _resolve(
            tmp_path,
            _contract(),
            review_action=action,
        )
        assert resolved["reroll_from_chunk"] == expected_boundary
        assert nonce == expected_nonce
    controller, resolved, nonce, _ = _resolve(
        tmp_path,
        _contract(),
        generation_mode=GENERATION_MODE_FULL_RUN,
    )
    assert (resolved["reroll_from_chunk"], nonce) == (2, 2)
    assert controller.review_execution.max_new_physical_groups is None


def test_legacy_revision_resumes_but_is_not_a_smart_regenerate_head(tmp_path):
    legacy = _persist(
        tmp_path,
        _contract(chunks=3),
        prefix=3,
        review_unit=None,
        updated_utc="2026-08-31T00:00:01+00:00",
    )
    assert legacy.manifest["status"] == REVISION_STATUS_COMPLETE
    assert "review_control_version" not in legacy.manifest

    controller = RunStorageController("phase-d-review")
    controller.run_root = tmp_path / "run"
    controller.revisions_root = controller.run_root / "revisions"
    controller.prompts = ["prompt 1", "prompt 2", "prompt 3"]
    assert controller.find_latest_review_head(_contract(chunks=3)) is not None
    assert controller.find_latest_review_head(
        _contract(chunks=3),
        smart_regenerate_only=True,
    ) is None
    with pytest.raises(ReviewControlError, match="existing reviewed unit"):
        _resolve(
            tmp_path,
            _contract(chunks=3),
            review_action=REVIEW_ACTION_REGENERATE_CURRENT,
        )


def test_review_controls_remain_internal_not_public_widgets():
    schema = H3ContinuumSamplerProduction.INPUT_TYPES()
    for name in ("generation_mode", "review_action", "max_new_physical_groups"):
        assert name not in schema.get("required", {})
        assert name not in schema.get("optional", {})


def test_finalize_rejects_review_unit_that_is_not_prefix_head(tmp_path):
    contract = _contract()
    controller = _controller(tmp_path, contract)
    entries = [_entry(0, contract), _entry(1, contract)]
    for position, entry in enumerate(entries):
        controller.commit_chunk(entry, position=position)
    controller.review_execution = SimpleNamespace(
        max_new_physical_groups=1,
        next_review_unit_start=1,
        next_review_unit_end=1,
        next_review_physical_group=1,
    )
    controller.review_generation_mode = GENERATION_MODE_REVIEW
    controller.mark_review_group(start=1, end=1, physical_group=1)
    with pytest.raises(RunStorageError, match="review pause metadata is invalid"):
        controller.finalize(
            session={"session_id": "bad", "chunks": entries},
            report="bad",
            review_pause_metadata=controller.review_pause_metadata(),
        )


def test_exception_marks_in_progress_revision_interrupted_without_nonce_change(
    tmp_path,
):
    contract = _contract(boundary=2, nonce=2)
    controller = _controller(tmp_path, contract)
    controller.manifest.update(
        review_control_version=REVIEW_CONTROL_VERSION,
        branch_regenerate_from=2,
        effective_reroll_nonce=2,
    )

    class _Lock:
        def acquire(self):
            return None

        def release(self):
            return None

    controller.lock = _Lock()
    with pytest.raises(RuntimeError, match="simulated crash"):
        with controller:
            raise RuntimeError("simulated crash")
    assert controller.manifest["status"] == REVISION_STATUS_INTERRUPTED
    assert controller.manifest["branch_regenerate_from"] == 2
    assert controller.manifest["effective_reroll_nonce"] == 2


def test_n2b_schema_v2_is_read_as_legacy_chain_without_rewrite(tmp_path):
    legacy = _persist(
        tmp_path,
        _contract(chunks=3),
        prefix=2,
        review_unit=(2, 2),
        updated_utc="2026-09-03T00:00:01+00:00",
    )
    legacy.manifest["run_storage_schema_version"] = 2
    legacy.manifest.pop("sampling_revision_id", None)
    legacy.manifest.pop("branch_provenance", None)
    legacy._write_manifest()
    before = legacy._manifest_path().read_bytes()

    controller = RunStorageController("phase-d-review")
    controller.run_root = legacy.run_root
    controller.revisions_root = legacy.revisions_root
    controller.prompts = ["prompt 1", "prompt 2", "prompt 3"]
    head = controller.find_latest_review_head(_contract(chunks=3))
    assert head is not None
    _, catalog, chains = controller._provenance_catalog()
    assert len(catalog) == 2
    assert len(chains[legacy.revision_id]) == 2
    assert legacy._manifest_path().read_bytes() == before
    sampling_revision_id, contract_sha256 = revision_identity(_contract(chunks=3))
    v3_storage_revision_id = _storage_revision_identity(
        contract_sha256=contract_sha256,
        take_action="Automatic",
        selected_revision_id="",
        effective_nonce=0,
        branch_boundary=0,
    )
    assert v3_storage_revision_id != sampling_revision_id


def test_n2b_take_a_b_selection_and_continue_preserve_old_branch(tmp_path):
    take_a = _persist(
        tmp_path,
        _contract(chunks=5, boundary=3, nonce=1),
        prefix=3,
        review_unit=(3, 3),
        updated_utc="2026-09-03T00:00:01+00:00",
    )
    take_b = _persist(
        tmp_path,
        _contract(chunks=5, boundary=3, nonce=2),
        prefix=3,
        review_unit=(3, 3),
        updated_utc="2026-09-03T00:00:02+00:00",
    )
    project = _project(take_b)
    revision_a = _take(project, group=3, nonce=1)
    revision_b = _take(project, group=3, nonce=2)
    assert revision_a["revision_id"] != revision_b["revision_id"]

    selected, resolved, nonce, decision = _resolve(
        tmp_path,
        _contract(chunks=5),
        take_action=TAKE_ACTION_CONTINUE,
        take_group=3,
        take_revision_id=revision_b["revision_id"],
    )
    assert (resolved["reroll_from_chunk"], nonce, decision) == (
        4,
        3,
        "branch_from_take",
    )
    selected_sources = [
        record["storage_revision_id"] for record in selected.selected_take_records
    ]
    _persist_resolved_branch(selected, resolved, new_positions=(3,))
    branched = _project(selected)
    assert branched["canonical_chain"][:3] == [
        item["revision_id"] for item in selected.selected_take_chain
    ]
    assert branched["canonical_head_revision_id"] == branched["canonical_chain"][-1]
    assert revision_a["revision_id"] in {
        item["revision_id"] for item in branched["group_revisions"]
    }
    assert revision_b["revision_id"] in {
        item["revision_id"] for item in branched["group_revisions"]
    }
    assert [
        record["storage_revision_id"]
        for record in selected.manifest["chunks"][:3]
    ] == selected_sources
    assert selected.manifest["chunks"][3]["storage_revision_id"] == selected.revision_id
    assert selected.manifest["branch_provenance"]["branch_cut"] == {
        "selected_revision_id": revision_b["revision_id"],
        "after_physical_group": 3,
    }
    assert take_a._manifest_path().exists()
    assert take_b._manifest_path().exists()
    restarted, restarted_contract, restarted_nonce, _ = _resolve(
        tmp_path,
        _contract(chunks=5),
    )
    assert restarted.review_head["revision_id"] == selected.revision_id
    assert restarted.review_head["validated_prefix_count"] == 4
    assert (restarted_contract["reroll_from_chunk"], restarted_nonce) == (4, 3)


def test_n2b_use_take_changes_canonical_without_generating(tmp_path):
    _persist(
        tmp_path,
        _contract(chunks=4, boundary=3, nonce=1),
        prefix=3,
        review_unit=(3, 3),
        updated_utc="2026-09-03T00:00:01+00:00",
    )
    latest = _persist(
        tmp_path,
        _contract(chunks=4, boundary=3, nonce=2),
        prefix=3,
        review_unit=(3, 3),
        updated_utc="2026-09-03T00:00:02+00:00",
    )
    project = _project(latest)
    revision_a = _take(project, group=3, nonce=1)
    selected, resolved, nonce, decision = _resolve(
        tmp_path,
        _contract(chunks=4),
        take_action=TAKE_ACTION_USE,
        take_group=3,
        take_revision_id=revision_a["revision_id"],
    )
    assert selected.review_execution.max_new_physical_groups == 0
    assert decision == "select_take"
    _persist_resolved_branch(selected, resolved, new_positions=())
    switched = _project(selected)
    assert switched["canonical_head_revision_id"] == revision_a["revision_id"]
    assert selected.generated_count == 0
    assert selected.manifest["status"] == REVISION_STATUS_REVIEW_READY

    restarted, _, restarted_nonce, _ = _resolve(tmp_path, _contract(chunks=4))
    assert restarted.review_head["revision_id"] == selected.revision_id
    assert restarted_nonce == nonce


def test_n2b_corrupt_project_recovers_last_valid_canonical_candidate(tmp_path):
    first = _persist(
        tmp_path,
        _contract(chunks=3),
        prefix=1,
        review_unit=(1, 1),
        updated_utc="2026-09-03T00:00:01+00:00",
    )
    expected = _project(first)["canonical_head_revision_id"]
    (first.run_root / "project.json").write_text("{broken", encoding="utf-8")
    controller = RunStorageController("phase-d-review")
    controller.run_root = first.run_root
    controller.revisions_root = first.revisions_root
    controller.prompts = ["prompt 1", "prompt 2", "prompt 3"]
    _, catalog, chains = controller._provenance_catalog()
    storage_revision_id, chain = controller._canonical_project_selection(
        catalog=catalog,
        chains=chains,
    )
    assert storage_revision_id == first.revision_id
    assert chain[-1] == expected


@pytest.mark.parametrize(
    "status",
    [REVISION_STATUS_IN_PROGRESS, REVISION_STATUS_INTERRUPTED],
)
def test_n2b_incomplete_revision_is_not_a_take_candidate(tmp_path, status):
    complete = _persist(
        tmp_path,
        _contract(chunks=3),
        prefix=1,
        review_unit=(1, 1),
        updated_utc="2026-09-03T00:00:01+00:00",
    )
    incomplete = _controller(tmp_path, _contract(chunks=3, boundary=2, nonce=1))
    incomplete.commit_chunk(_entry(0, incomplete.contract), position=0)
    incomplete.manifest.update(
        status=status,
        updated_utc="2026-09-03T00:00:02+00:00",
    )
    incomplete._write_manifest()

    manifests, catalog, chains = incomplete._provenance_catalog()
    assert complete.revision_id in chains
    assert incomplete.revision_id in manifests
    assert incomplete.revision_id not in chains
    assert all(
        revision["storage_revision_id"] != incomplete.revision_id
        for revision in catalog.values()
    )


def test_n2b_wrong_group_selector_is_rejected(tmp_path):
    stored = _persist(
        tmp_path,
        _contract(chunks=3),
        prefix=2,
        review_unit=(2, 2),
        updated_utc="2026-09-03T00:00:01+00:00",
    )
    revision = _take(_project(stored), group=2, nonce=0)
    with pytest.raises(RunStorageError, match="group does not match"):
        _resolve(
            tmp_path,
            _contract(chunks=3),
            take_action=TAKE_ACTION_USE,
            take_group=1,
            take_revision_id=revision["revision_id"],
        )


def _production_kwargs():
    return {
        "model": object(),
        "clip": object(),
        "video_vae": object(),
        "sampler": object(),
        "sigmas": torch.tensor([1.0, 0.0]),
        "sequence_prompt": "prompt",
        "prompt_mode": "Fixed",
        "chunks": 2,
        "chunk_seconds": 5.0,
        "width": 96,
        "height": 64,
        "continuity": "Balanced — 22 frames",
        "base_seed": 1234,
        "audio_continuity": True,
        "diagnostics": "Basic",
        "reroll_from_chunk": "Auto",
        "reroll_nonce": 0,
        "strict_compatibility": False,
        "debug": False,
        "show_preview": False,
        "run_storage": "Save + Auto Resume",
        "generation_mode": GENERATION_MODE_REVIEW,
        "review_action": REVIEW_ACTION_CONTINUE,
    }


def test_production_internal_review_configures_storage_and_finalizes_metadata(
    monkeypatch,
):
    import ComfyUI_H3_Continuum_Join.run_storage as run_storage

    class _Storage:
        def __init__(self):
            self.configured = None
            self.finalized = None
            self.review_execution = SimpleNamespace(status_hint="review status")

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def configure_review(self, **kwargs):
            self.configured = kwargs

        def summary(self, *, detailed=False):
            return "storage summary"

        def review_pause_metadata(self):
            return {
                "review_unit": {"start": 1, "end": 1, "physical_group": 1},
                "review_pause_reason": "review_each_chunk",
            }

        def finalize(self, **kwargs):
            self.finalized = kwargs

    storage = _Storage()
    monkeypatch.setattr(run_storage, "run_storage_scope", lambda *a, **k: storage)
    monkeypatch.setattr(run_storage, "automatic_project_key", lambda *a, **k: "key")
    monkeypatch.setattr(
        H3ContinuumSamplerV3,
        "run",
        lambda self, **kwargs: (
            {"samples": torch.zeros(1)},
            {"samples": torch.zeros(1)},
            {"target_frames": 120},
            {
                "last_state": {},
                "session": {"session_id": "session", "chunks": [{}]},
                "report": "sampling report",
            },
        ),
    )

    outputs = H3ContinuumSamplerProduction().run(**_production_kwargs())
    assert storage.configured == {
        "generation_mode": GENERATION_MODE_REVIEW,
        "review_action": REVIEW_ACTION_CONTINUE,
        "manual_regenerate_from": 0,
        "take_group": 0,
        "take_revision_id": "",
        "take_action": "Automatic",
    }
    assert storage.finalized["review_pause_metadata"]["review_unit"]["start"] == 1
    assert "review status" in outputs[3]


def test_production_uses_reconciled_review_unit_for_decode_scope(monkeypatch):
    import ComfyUI_H3_Continuum_Join.run_storage as run_storage

    contract = _contract(chunks=3)
    entries = [_entry(position, contract) for position in range(3)]
    full_decode, full_plan = prepare_physical_decode_entries(
        entries,
        chunk_seconds=5.0,
        preserve_final_frame=False,
        terminal_merged=False,
    )

    class _Storage:
        review_generation_mode = None
        review_execution = None
        finalized = None

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def configure_review(self, **kwargs):
            self.review_generation_mode = kwargs["generation_mode"]

        def summary(self, *, detailed=False):
            return "storage summary"

        def review_pause_metadata(self):
            return {
                "review_unit": {"start": 2, "end": 2, "physical_group": 2},
                "review_pause_reason": "review_each_chunk",
            }

        def finalize(self, **kwargs):
            self.finalized = kwargs

    storage = _Storage()
    monkeypatch.setattr(run_storage, "run_storage_scope", lambda *a, **k: storage)
    monkeypatch.setattr(run_storage, "automatic_project_key", lambda *a, **k: "key")

    def fake_v3_run(self, **kwargs):
        storage.review_execution = SimpleNamespace(
            status_hint="review status",
            finish_remaining=False,
            next_review_unit_start=2,
            next_review_unit_end=2,
            partial_review=True,
            smart_regenerate=False,
        )
        return (
            [{"samples": entry["video"]} for entry in full_decode],
            [{"samples": entry["audio"]} for entry in full_decode],
            full_plan,
            {
                "last_state": {},
                "session": {"session_id": "session", "chunks": entries},
                "report": "sampling report",
            },
        )

    monkeypatch.setattr(H3ContinuumSamplerV3, "run", fake_v3_run)
    kwargs = _production_kwargs()
    kwargs["chunks"] = 3
    outputs = H3ContinuumSamplerProduction().run(**kwargs)

    assert len(outputs[0]) == len(outputs[1]) == 1
    assert torch.equal(outputs[0][0]["samples"], entries[1]["video"])
    assert outputs[2]["target_frames"] == 120
    assert outputs[2]["chunks"][0]["chunk_index"] == 2
    assert len(storage.finalized["session"]["chunks"]) == 3
    assert "Decode preview: Chunk 2" in outputs[3]


def test_review_decode_range_only_selects_a_current_review_unit():
    execution = SimpleNamespace(
        finish_remaining=False,
        next_review_unit_start=2,
        next_review_unit_end=2,
        partial_review=True,
        smart_regenerate=False,
    )
    storage = SimpleNamespace(
        review_generation_mode=GENERATION_MODE_REVIEW,
        review_execution=execution,
    )
    assert _review_decode_chunk_range(
        storage,
        capture_refine_context=False,
    ) == (2, 2)
    assert _review_decode_chunk_range(
        storage,
        capture_refine_context=True,
    ) == (2, 2)

    execution.partial_review = False
    assert _review_decode_chunk_range(
        storage,
        capture_refine_context=False,
    ) is None
    execution.smart_regenerate = True
    assert _review_decode_chunk_range(
        storage,
        capture_refine_context=False,
    ) == (2, 2)
    execution.finish_remaining = True
    assert _review_decode_chunk_range(
        storage,
        capture_refine_context=False,
    ) is None


def test_projection_decision_is_pure_and_refuses_to_split_physical_groups():
    session = {"chunks": [{}, {}, {}]}
    execution = SimpleNamespace(
        finish_remaining=False,
        next_review_unit_start=2,
        next_review_unit_end=3,
        partial_review=False,
        smart_regenerate=True,
    )

    decision = resolve_projection_decision(
        review_execution=execution,
        effective_result_status=REVISION_STATUS_REVIEW_READY,
        session=session,
        physical_group_facts=((1,), (2, 3)),
    )
    assert decision.kind == PROJECTION_CURRENT_REVIEW_UNIT
    assert (decision.start_chunk, decision.end_chunk) == (2, 3)

    split_terminal_group = resolve_projection_decision(
        review_execution=SimpleNamespace(
            finish_remaining=False,
            next_review_unit_start=2,
            next_review_unit_end=2,
            partial_review=True,
            smart_regenerate=False,
        ),
        effective_result_status=REVISION_STATUS_REVIEW_READY,
        session=session,
        physical_group_facts=((1,), (2, 3)),
    )
    assert split_terminal_group.kind == PROJECTION_FULL_ACCEPTED_PREFIX

    complete = resolve_projection_decision(
        review_execution=execution,
        effective_result_status=REVISION_STATUS_COMPLETE,
        session=session,
        physical_group_facts=((1,), (2, 3)),
    )
    assert complete.kind == PROJECTION_FULL_ACCEPTED_PREFIX


def test_partial_review_rebuilds_decode_outputs_without_truncating_session():
    contract = _contract(chunks=3)
    entries = [_entry(position, contract) for position in range(3)]
    full_decode, full_plan = prepare_physical_decode_entries(
        entries,
        chunk_seconds=5.0,
        preserve_final_frame=False,
        terminal_merged=False,
    )
    verified_route_plan = {"mode": "Custom", "accepted_chunks": 3, "groups": []}
    full_plan["reference_routing_v1"] = verified_route_plan
    result = {
        "last_state": {},
        "session": {"session_id": "session", "chunks": entries},
        "report": "sampling report",
    }
    outputs = (
        [{"samples": entry["video"]} for entry in full_decode],
        [{"samples": entry["audio"]} for entry in full_decode],
        full_plan,
        result,
        {"full_refine_context": True},
    )
    refine_context = outputs[4]
    storage = SimpleNamespace(
        review_generation_mode=GENERATION_MODE_REVIEW,
        review_execution=SimpleNamespace(
            finish_remaining=False,
            next_review_unit_start=2,
            next_review_unit_end=2,
            partial_review=True,
            smart_regenerate=False,
        ),
    )

    scoped = _apply_review_decode_scope(
        outputs,
        storage=storage,
        capture_refine_context=True,
        configured_chunks=3,
        chunk_seconds=5.0,
        first_frame=None,
        last_frame=None,
        timeline_video_source=None,
    )

    assert len(scoped[0]) == len(scoped[1]) == 1
    assert torch.equal(scoped[0][0]["samples"], entries[1]["video"])
    assert torch.equal(scoped[1][0]["samples"], entries[1]["audio"])
    assert scoped[2]["target_frames"] == 120
    assert scoped[2]["reference_routing_v1"] is verified_route_plan
    assert scoped[2]["chunks"][0]["sequence_index"] == 1
    assert scoped[2]["chunks"][0]["chunk_index"] == 2
    assert scoped[2]["second_pass_contract"]["physical_groups"][0][
        "logical_chunks"
    ] == [2]
    assert len(scoped[3]["session"]["chunks"]) == 3
    assert scoped[3]["session"] is result["session"]
    assert scoped[3]["report"].endswith("Decode preview: Chunk 2")
    assert scoped[4] is refine_context


def test_production_review_mode_rejects_run_storage_off():
    kwargs = _production_kwargs()
    kwargs["run_storage"] = "Off"
    with pytest.raises(ValueError, match="requires Run Storage"):
        H3ContinuumSamplerProduction().run(**kwargs)
