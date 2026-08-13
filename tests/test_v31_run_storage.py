from __future__ import annotations

import copy
import json
from types import SimpleNamespace

import torch
import pytest
import ctypes

from ComfyUI_H3_Continuum_Join.run_storage import (
    RunStorageController,
    _apply_nonce_contract,
    _fsync_file,
    _pid_exists_windows,
    automatic_project_key,
    build_sampling_contract,
    resolve_run_storage_name,
    revision_identity,
)
from ComfyUI_H3_Continuum_Join.graph_contract import (
    CHECKPOINT_FL2VA,
    CHECKPOINT_REF2VA,
    build_upstream_graph_contract,
    classify_h3_checkpoint,
)
from ComfyUI_H3_Continuum_Join.state import make_plan
from ComfyUI_H3_Continuum_Join.v2.session import make_chunk_entry
from ComfyUI_H3_Continuum_Join.v3.nodes import _validate_regenerate_storage


class _Nested:
    def __init__(self, parts):
        self.parts = parts

    def unbind(self):
        return self.parts


def _entry(position: int, *, prompt: str = "same fixed prompt"):
    continuation = position > 0
    frame_count = 141 if continuation else 124
    video_t = 42 if continuation else 37
    audio_t = 235 if continuation else 207
    plan = make_plan(
        continuation=continuation,
        clip_index=position + 1,
        total_frames=frame_count,
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
                    torch.full((1, 24, video_t, 4, 6), float(position)),
                    torch.full((1, 32, 2, audio_t), float(position)),
                )
            )
        },
        plan=plan,
        prompt=prompt,
        prompt_hash=str(position + 1) * 64,
        seed=100 + position,
        context_frames=22 if continuation else 0,
        motion_score=float(position),
        reused=False,
    )


def _controller(tmp_path, *, chunk_count: int = 3):
    controller = RunStorageController("run-storage-test")
    controller.revisions_root = tmp_path / "revisions"
    controller.revision_id = "revision-test"
    controller.revision_root = controller.revisions_root / controller.revision_id
    hashes = [f"contract-{position}" for position in range(chunk_count)]
    controller.contract = {
        "chunk_count": chunk_count,
        "chunk_contract_hashes": hashes,
    }
    controller.prompts = ["same fixed prompt"] * chunk_count
    controller.manifest = {
        "contract": controller.contract,
        "chunks": [],
        "status": "in_progress",
    }
    return controller, hashes


def test_three_chunks_are_committed_to_distinct_files(tmp_path):
    controller, _ = _controller(tmp_path)
    source_entries = [_entry(position) for position in range(3)]

    for position, entry in enumerate(source_entries):
        controller.commit_chunk(entry, position=position)

    chunks_root = controller.revision_root / "chunks"
    assert [path.name for path in sorted(chunks_root.glob("*.safetensors"))] == [
        "chunk_0001.safetensors",
        "chunk_0002.safetensors",
        "chunk_0003.safetensors",
    ]
    records = controller.manifest["chunks"]
    assert [record["sequence_index"] for record in records] == [0, 1, 2]
    assert [record["entry"]["sequence_index"] for record in records] == [0, 1, 2]
    assert all(len(record["file_sha256"]) == 64 for record in records)
    assert [entry["sequence_index"] for entry in source_entries] == [0, 0, 0]

    persisted = json.loads(controller._manifest_path().read_text(encoding="utf-8"))
    assert [record["filename"] for record in persisted["chunks"]] == [
        "chunk_0001.safetensors",
        "chunk_0002.safetensors",
        "chunk_0003.safetensors",
    ]


def test_interrupted_fixed_prompt_run_resumes_the_correct_prefix(tmp_path):
    first, hashes = _controller(tmp_path)
    first.commit_chunk(_entry(0), position=0)
    first.commit_chunk(_entry(1), position=1)

    resumed, _ = _controller(tmp_path)
    resumed.manifest = json.loads(first._manifest_path().read_text(encoding="utf-8"))
    entries, records = resumed._valid_prefix(resumed.manifest, hashes)

    assert [entry["seed"] for entry in entries] == [100, 101]
    assert [entry["clip_index"] for entry in entries] == [1, 2]
    assert [record["filename"] for record in records] == [
        "chunk_0001.safetensors",
        "chunk_0002.safetensors",
    ]

    resumed.commit_chunk(_entry(2), position=2)
    assert [record["filename"] for record in resumed.manifest["chunks"]] == [
        "chunk_0001.safetensors",
        "chunk_0002.safetensors",
        "chunk_0003.safetensors",
    ]


def test_fsync_file_accepts_a_completed_file_on_windows(tmp_path):
    target = tmp_path / "chunk.tmp"
    target.write_bytes(b"complete")
    _fsync_file(target)


def test_chunk_sha256_rejects_same_size_corruption(tmp_path):
    controller, _ = _controller(tmp_path)
    controller.commit_chunk(_entry(0), position=0)
    record = controller.manifest["chunks"][0]
    target = controller.revision_root / "chunks" / record["filename"]
    payload = bytearray(target.read_bytes())
    payload[-1] ^= 1
    target.write_bytes(payload)
    with pytest.raises(Exception, match="SHA-256 mismatch"):
        controller._load_entry(record, "same fixed prompt")


def test_automatic_storage_name_is_stable_for_sampler_node():
    first = resolve_run_storage_name(
        project_id="", legacy_run_name="", automatic_key="242"
    )
    second = resolve_run_storage_name(
        project_id="", legacy_run_name="", automatic_key="242"
    )
    assert first == second
    assert first.startswith("run_auto_")


def test_windows_pid_probe_uses_open_process(monkeypatch):
    class Function:
        def __init__(self, result):
            self.result = result
            self.argtypes = None
            self.restype = None

        def __call__(self, *args):
            return self.result

    class Kernel32:
        OpenProcess = Function(123)
        CloseHandle = Function(True)

    monkeypatch.setattr(ctypes, "WinDLL", lambda *args, **kwargs: Kernel32(), raising=False)
    monkeypatch.setattr(ctypes, "set_last_error", lambda value: None)
    monkeypatch.setattr(ctypes, "get_last_error", lambda: 0)
    assert _pid_exists_windows(12345)


def test_automatic_project_key_ignores_settings_but_tracks_topology():
    prompt = _prompt_graph()
    first = automatic_project_key(prompt, "42")
    prompt["10"]["inputs"]["unet_name"] = "different-model.safetensors"
    assert automatic_project_key(prompt, "42") == first
    prompt["42"]["inputs"]["model"] = ["10", 0]
    assert automatic_project_key(prompt, "42") != first


def test_regenerate_from_requires_run_storage():
    _validate_regenerate_storage("Off", 0)
    _validate_regenerate_storage("Save + Auto Resume", 2)
    with pytest.raises(ValueError, match="requires Run Storage"):
        _validate_regenerate_storage("Off", 2)


def _sample_function(*args, **kwargs):
    return None


class _Sampler:
    sampler_function = _sample_function
    extra_options = {}
    inpaint_options = {}


class _Patcher:
    def __init__(self, model):
        self.model = model
        self.wrappers = {}
        self.patches = {}
        self.object_patches = {}
        self.model_options = {}


class _Model:
    def __init__(self):
        self.model = SimpleNamespace(diffusion_model=torch.nn.Linear(2, 2))
        self.wrappers = {}
        self.patches = {}
        self.model_options = {}

    def model_dtype(self):
        return torch.float32

    def model_size(self):
        return 4


class _Clip:
    def __init__(self):
        self.cond_stage_model = torch.nn.Linear(2, 2)
        self.patcher = _Patcher(self.cond_stage_model)
        core = SimpleNamespace(
            name_or_path="minimax-qwen",
            vocab_size=100,
            model_max_length=1024,
            padding_side="right",
            truncation_side="right",
            bos_token_id=1,
            eos_token_id=2,
            pad_token_id=0,
        )
        self.tokenizer = SimpleNamespace(
            qwen3vl_32b=SimpleNamespace(tokenizer=core)
        )
        self.tokenizer_options = {}
        self.layer_idx = None
        self.use_clip_schedule = False


class _VideoVAE:
    def __init__(self):
        self.first_stage_model = torch.nn.Linear(2, 2)
        self.patcher = _Patcher(self.first_stage_model)
        self.vae_dtype = torch.float16
        self.latent_channels = 24
        self.downscale_ratio = 16
        self.upscale_ratio = 16


def _sampling_contract(
    *, model=None, clip=None, video_vae=None, sampler=None, reroll_nonce=0,
    conditioning_mode="i2va", first_frame_hash="a" * 64,
    last_frame_hash="", reference_contract=None,
    upstream_graph_contract=None, upstream_graph_safe=None,
    upstream_graph_reasons=None,
):
    return build_sampling_contract(
        model=model or _Model(),
        model_fingerprint_value="f" * 64,
        clip=clip or _Clip(),
        video_vae=video_vae or _VideoVAE(),
        sampler=sampler or _Sampler(),
        sigmas=torch.tensor([1.0, 0.0]),
        prompt_plan={
            "chunks": 3,
            "hashes": ["1" * 64, "2" * 64, "3" * 64],
            "mode": "list",
        },
        width=96,
        height=64,
        chunk_seconds=5.0,
        continuity="Balanced",
        audio_continuity=True,
        base_seed=1,
        reroll_from_chunk=2,
        reroll_nonce=reroll_nonce,
        first_frame_hash=first_frame_hash,
        last_frame_hash=last_frame_hash,
        strict_compatibility=True,
        reference_contract=reference_contract,
        conditioning_mode=conditioning_mode,
        upstream_graph_contract=upstream_graph_contract,
        upstream_graph_safe=upstream_graph_safe,
        upstream_graph_reasons=upstream_graph_reasons,
    )


def test_clip_and_required_video_vae_are_part_of_sampling_contract():
    clip = _Clip()
    vae = _VideoVAE()
    first, safe, reasons = _sampling_contract(clip=clip, video_vae=vae)
    assert safe, reasons

    with torch.no_grad():
        clip.cond_stage_model.weight.add_(1)
    changed_clip, safe, reasons = _sampling_contract(clip=clip, video_vae=vae)
    assert safe, reasons
    assert revision_identity(first) != revision_identity(changed_clip)

    with torch.no_grad():
        vae.first_stage_model.weight.add_(1)
    changed_vae, safe, reasons = _sampling_contract(clip=clip, video_vae=vae)
    assert safe, reasons
    assert revision_identity(changed_clip) != revision_identity(changed_vae)


def test_t2va_contract_omits_video_vae_signature():
    model = _Model()
    clip = _Clip()
    vae = _VideoVAE()
    sampler = _Sampler()
    first, safe, reasons = _sampling_contract(
        model=model,
        clip=clip,
        video_vae=vae,
        sampler=sampler,
        conditioning_mode="t2va",
        first_frame_hash="",
    )
    assert safe, reasons
    assert first["global"]["conditioning_mode"] == "t2va"
    assert "video_vae" not in first["global"]
    assert "first_frame_hash" not in first["global"]

    with torch.no_grad():
        vae.first_stage_model.weight.add_(1)
    changed, safe, reasons = _sampling_contract(
        model=model,
        clip=clip,
        video_vae=vae,
        sampler=sampler,
        conditioning_mode="t2va",
        first_frame_hash="",
    )
    assert safe, reasons
    assert revision_identity(first) == revision_identity(changed)


def test_conditioning_mode_change_invalidates_all_chunk_contracts():
    i2va, safe, reasons = _sampling_contract()
    assert safe, reasons
    t2va, safe, reasons = _sampling_contract(
        conditioning_mode="t2va",
        first_frame_hash="",
    )
    assert safe, reasons
    assert i2va["chunk_contract_hashes"] != t2va["chunk_contract_hashes"]
    assert all(
        left != right
        for left, right in zip(
            i2va["chunk_contract_hashes"], t2va["chunk_contract_hashes"]
        )
    )


def test_unobservable_clip_disables_resume_but_preserves_contract():
    clip = _Clip()
    clip.tokenizer = None
    contract, safe, reasons = _sampling_contract(clip=clip)
    assert not safe
    assert contract["global"]["clip"]
    assert any("CLIP/Qwen" in reason for reason in reasons)


def _write_nonce_manifest(root, name, contract, status):
    target = root / name
    target.mkdir(parents=True)
    (target / "manifest.json").write_text(
        json.dumps(
            {
                "run_storage_schema_version": 1,
                "status": status,
                "updated_utc": "2026-08-13T00:00:00+00:00",
                "contract": contract,
                "nonce_lifecycle": contract["nonce_lifecycle"],
            }
        ),
        encoding="utf-8",
    )


def test_auto_nonce_resumes_interrupted_revision(tmp_path):
    controller, _ = _controller(tmp_path)
    draft, safe, reasons = _sampling_contract()
    assert safe, reasons
    interrupted = _apply_nonce_contract(
        draft, requested_nonce=0, effective_nonce=2
    )
    _write_nonce_manifest(
        controller.revisions_root, "interrupted", interrupted, "interrupted"
    )

    nonce, decision = controller._resolve_effective_nonce(
        draft, requested_nonce=0, resume_safe=True
    )
    assert (nonce, decision) == (2, "resume_interrupted")


def test_auto_nonce_increments_only_after_completed_revision(tmp_path):
    controller, _ = _controller(tmp_path)
    draft, safe, reasons = _sampling_contract()
    assert safe, reasons
    completed = _apply_nonce_contract(
        draft, requested_nonce=0, effective_nonce=2
    )
    _write_nonce_manifest(
        controller.revisions_root, "completed", completed, "complete"
    )

    nonce, decision = controller._resolve_effective_nonce(
        draft, requested_nonce=0, resume_safe=True
    )
    assert (nonce, decision) == (3, "new_revision")


def test_explicit_nonce_is_never_auto_incremented(tmp_path):
    controller, _ = _controller(tmp_path)
    draft, safe, reasons = _sampling_contract(reroll_nonce=7)
    assert safe, reasons

    nonce, decision = controller._resolve_effective_nonce(
        draft, requested_nonce=7, resume_safe=True
    )
    assert (nonce, decision) == (7, "explicit")


def _prompt_graph(model_name="minimax_h3_fl2va.safetensors"):
    return {
        "10": {
            "class_type": "UNETLoader",
            "inputs": {"unet_name": model_name, "weight_dtype": "default"},
        },
        "11": {
            "class_type": "PathchSageAttentionKJ",
            "inputs": {"model": ["10", 0], "sage_attention": "auto"},
        },
        "12": {
            "class_type": "SpectrumApplyMiniMaxH3",
            "inputs": {"model": ["11", 0], "enabled": True, "warmup_steps": 1},
        },
        "20": {
            "class_type": "CLIPLoader",
            "inputs": {"clip_name": "qwen3vl_h3.safetensors", "type": "minimax_h3"},
        },
        "30": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": "minimax_h3_video_vae_fp16.safetensors"},
        },
        "42": {
            "class_type": "H3ContinuumSamplerProduction",
            "inputs": {"model": ["12", 0], "clip": ["20", 0], "video_vae": ["30", 0]},
        },
    }


def test_upstream_graph_fingerprint_tracks_loader_and_patch_order():
    graph, safe, reasons = build_upstream_graph_contract(
        _prompt_graph(), "42", require_video_vae=True
    )
    assert safe, reasons
    changed, changed_safe, changed_reasons = build_upstream_graph_contract(
        _prompt_graph("minimax_h3_ref2va.safetensors"),
        "42",
        require_video_vae=True,
    )
    assert changed_safe, changed_reasons
    assert graph["sha256"] != changed["sha256"]
    model_route = graph["routes"]["model"]["node"]
    assert model_route["class_type"] == "SpectrumApplyMiniMaxH3"
    assert model_route["inputs"]["model"]["node"]["class_type"] == "PathchSageAttentionKJ"


def test_sampling_contract_combines_graph_and_runtime_weight_probe():
    graph, graph_safe, graph_reasons = build_upstream_graph_contract(
        _prompt_graph(), "42", require_video_vae=True
    )
    model = _Model()
    first, safe, reasons = _sampling_contract(
        model=model,
        upstream_graph_contract=graph,
        upstream_graph_safe=graph_safe,
        upstream_graph_reasons=graph_reasons,
    )
    assert safe, reasons
    assert "runtime" in first["global"]["model"]
    assert "graph_route" in first["global"]["model"]
    with torch.no_grad():
        model.model.diffusion_model.weight.add_(1)
    changed, safe, reasons = _sampling_contract(
        model=model,
        upstream_graph_contract=graph,
        upstream_graph_safe=graph_safe,
        upstream_graph_reasons=graph_reasons,
    )
    assert safe, reasons
    assert revision_identity(first) != revision_identity(changed)


def test_official_h3_sigma_shift_is_accepted_in_model_route():
    prompt = _prompt_graph()
    prompt["13"] = {
        "class_type": "MiniMaxH3SigmaShift",
        "inputs": {"model": ["12", 0], "shift": 3.0},
    }
    prompt["42"]["inputs"]["model"] = ["13", 0]
    graph, safe, reasons = build_upstream_graph_contract(
        prompt, "42", require_video_vae=True
    )
    assert safe, reasons
    assert graph["routes"]["model"]["node"]["class_type"] == "MiniMaxH3SigmaShift"


def test_upstream_graph_fingerprint_accepts_runtime_turbo_and_sage_nodes():
    prompt = _prompt_graph()
    prompt["11"] = {
        "class_type": "MiniMaxH3MemoryEfficientSageAttentionPatch",
        "inputs": {"model": ["10", 0]},
    }
    prompt["12"] = {
        "class_type": "Power Lora Loader (rgthree)",
        "inputs": {
            "model": ["11", 0],
            "lora_1": {
                "on": True,
                "lora": "minimax_h3_fl2v_turbo_8step.safetensors",
                "strength": 1.0,
                "strengthTwo": 0.0,
            },
        },
    }
    graph, safe, reasons = build_upstream_graph_contract(
        prompt, "42", require_video_vae=True
    )
    assert safe, reasons


def test_checkpoint_classifier_uses_base_unet_filename():
    prompt = _prompt_graph()
    prompt["10"]["inputs"]["unet_name"] = "minimax_h3_ref2va_pruned_int8.safetensors"
    assert classify_h3_checkpoint(prompt, "42") == CHECKPOINT_REF2VA
    prompt["10"]["inputs"]["unet_name"] = "minimax_h3_fl2va_pruned_int8.safetensors"
    assert classify_h3_checkpoint(prompt, "42") == CHECKPOINT_FL2VA
    changed_prompt = copy.deepcopy(prompt)
    changed_prompt["12"]["inputs"]["lora_1"]["strength"] = 0.8
    changed, changed_safe, changed_reasons = build_upstream_graph_contract(
        changed_prompt, "42", require_video_vae=True
    )
    assert changed_safe, changed_reasons
    assert graph["sha256"] != changed["sha256"]
    model_route = graph["routes"]["model"]["node"]
    assert model_route["class_type"] == "Power Lora Loader (rgthree)"
    assert (
        model_route["inputs"]["model"]["node"]["class_type"]
        == "MiniMaxH3MemoryEfficientSageAttentionPatch"
    )


def test_unknown_upstream_wrapper_disables_resume():
    prompt = _prompt_graph()
    prompt["12"]["class_type"] = "UnknownExperimentalWrapper"
    _, safe, reasons = build_upstream_graph_contract(
        prompt, "42", require_video_vae=True
    )
    assert not safe
    assert any("UnknownExperimentalWrapper" in reason for reason in reasons)


def test_t2va_graph_contract_does_not_require_video_vae_route():
    prompt = _prompt_graph()
    del prompt["42"]["inputs"]["video_vae"]
    graph, safe, reasons = build_upstream_graph_contract(
        prompt, "42", require_video_vae=False
    )
    assert safe, reasons
    assert "video_vae" not in graph["routes"]
