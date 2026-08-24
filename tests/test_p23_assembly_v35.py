from __future__ import annotations

import gc
import inspect
from pathlib import Path

import pytest
import torch

from ComfyUI_H3_Continuum_Join.constants import (
    DIAGNOSTICS_BASIC,
    DIAGNOSTICS_FULL,
)
from ComfyUI_H3_Continuum_Join.hardening import enrich_assembly_plan
from ComfyUI_H3_Continuum_Join.temporal import audio_latent_t, video_latent_t
from ComfyUI_H3_Continuum_Join.v3 import assembly_v35
from ComfyUI_H3_Continuum_Join.v3.assembly import (
    AUDIO_SEAM_AUTO,
    AUDIO_SEAM_OFF,
    VIDEO_SEAM_ANALYZE,
    VIDEO_SEAM_AUTO,
    VIDEO_SEAM_AUTO_2,
    VIDEO_SEAM_OFF,
)
from ComfyUI_H3_Continuum_Join.v3.driving_nodes import (
    H3ContinuumAssembleSeamV34,
    H3ContinuumAssembleSeamV35,
)
from ComfyUI_H3_Continuum_Join.v3.file_backed_buffer import (
    AutoBufferDecision,
    BUFFER_BACKEND_AUTO,
    BUFFER_BACKEND_DISK,
    BUFFER_BACKEND_RAM,
    get_file_backed_image_manager,
)
from ComfyUI_H3_Continuum_Join.v3.plan import ASSEMBLY_PLAN_MAGIC


_FPS = 24
_SAMPLE_RATE = 240


def _logical_chunk(
    sequence_index: int,
    *,
    total_frames: int,
    trim_frames: int,
) -> dict:
    return {
        "sequence_index": sequence_index,
        "chunk_index": sequence_index,
        "total_frames": total_frames,
        "trim_frames": trim_frames,
        "net_frames": total_frames - trim_frames,
        "context_frames": trim_frames,
        "expected_video_latent_t": video_latent_t(total_frames),
        "expected_audio_latent_t": audio_latent_t(total_frames),
    }


def _physical_group(
    logical_chunks: list[int],
    *,
    total_frames: int,
    trim_frames: int,
    frame_start: int,
    terminal_merged: bool,
) -> dict:
    net_frames = total_frames - trim_frames
    return {
        "logical_chunk_indices": logical_chunks,
        "terminal_merged": terminal_merged,
        "total_frames": total_frames,
        "trim_frames": trim_frames,
        "net_frames": net_frames,
        "context_frames": trim_frames,
        "expected_video_latent_t": video_latent_t(total_frames),
        "expected_audio_latent_t": audio_latent_t(total_frames),
        "frame_start": frame_start,
        "frame_stop": frame_start + net_frames,
    }


def _plan(kind: str, *, target_frames: int | None = None, preserve=True) -> dict:
    if kind == "single":
        chunks = [_logical_chunk(1, total_frames=124, trim_frames=0)]
        groups = None
        default_target = 120
    elif kind == "single_pad":
        chunks = [_logical_chunk(1, total_frames=124, trim_frames=5)]
        groups = None
        default_target = 120
    elif kind == "terminal_2x5":
        chunks = [
            _logical_chunk(1, total_frames=124, trim_frames=0),
            _logical_chunk(2, total_frames=141, trim_frames=22),
        ]
        groups = [
            _physical_group(
                [1, 2],
                total_frames=243,
                trim_frames=0,
                frame_start=0,
                terminal_merged=True,
            )
        ]
        default_target = 240
    elif kind == "long_terminal_3x5":
        chunks = [
            _logical_chunk(1, total_frames=124, trim_frames=0),
            _logical_chunk(2, total_frames=141, trim_frames=22),
            _logical_chunk(3, total_frames=141, trim_frames=22),
        ]
        groups = [
            _physical_group(
                [1],
                total_frames=124,
                trim_frames=0,
                frame_start=0,
                terminal_merged=False,
            ),
            _physical_group(
                [2, 3],
                total_frames=260,
                trim_frames=22,
                frame_start=124,
                terminal_merged=True,
            ),
        ]
        default_target = 360
    else:
        raise AssertionError(f"unknown fixture kind: {kind}")

    plan = enrich_assembly_plan(
        {
            "magic": ASSEMBLY_PLAN_MAGIC,
            "schema_version": 1,
            "fps": _FPS,
            "width": 8,
            "height": 8,
            "chunk_seconds": 5.0,
            "target_frames": int(
                default_target if target_frames is None else target_frames
            ),
            "preserve_final_frame": bool(preserve),
            "chunks": chunks,
        }
    )
    if groups is not None:
        plan["decode_groups"] = groups
        plan["physical_decode_group_count"] = len(groups)
    return plan


def _units(plan: dict) -> list[dict]:
    return list(plan.get("decode_groups") or plan["chunks"])


def _decoded(
    plan: dict,
    *,
    seam_case: str = "ordered",
    sample_rate: int = _SAMPLE_RATE,
) -> tuple[list[torch.Tensor], list[dict]]:
    images: list[torch.Tensor] = []
    audio: list[dict] = []
    for group_index, unit in enumerate(_units(plan)):
        total_frames = int(unit["total_frames"])
        if seam_case == "ordered":
            frame_values = (
                group_index * 0.25
                + torch.arange(total_frames, dtype=torch.float32) / 4096.0
            )
            image = frame_values.view(-1, 1, 1, 1).expand(-1, 8, 8, 3).clone()
        else:
            image = torch.full((total_frames, 8, 8, 3), 0.25)
            if group_index == 1:
                trim = int(unit["trim_frames"])
                if seam_case == "transient":
                    image[trim] = 1.0
                elif seam_case == "exposure":
                    image[trim:] = 0.33
                    image[trim : trim + 4] = torch.tensor(
                        [0.27, 0.29, 0.31, 0.33]
                    ).view(4, 1, 1, 1)
                elif seam_case != "clean":
                    raise AssertionError(f"unknown seam case: {seam_case}")

        sample_count = int(round(total_frames / _FPS * sample_rate))
        time_values = (
            group_index * 10000
            + torch.arange(sample_count, dtype=torch.float32)
        )
        waveform = torch.stack((time_values, -time_values), dim=0).unsqueeze(0)
        images.append(image)
        audio.append({"waveform": waveform, "sample_rate": sample_rate})
    return images, audio


def _v34(
    images,
    audio,
    plan,
    *,
    exact: bool,
    audio_seam: str = AUDIO_SEAM_OFF,
    video_seam: str = VIDEO_SEAM_OFF,
):
    return H3ContinuumAssembleSeamV34().assemble(
        images=images,
        audio=audio,
        assembly_plan=plan,
        exact_total_duration=exact,
        audio_seam=audio_seam,
        video_seam=video_seam,
        diagnostics=DIAGNOSTICS_BASIC,
    )


def _v35(
    images,
    audio,
    plan,
    *,
    exact: bool,
    backend: str,
    backing_root: Path,
    audio_seam: str = AUDIO_SEAM_OFF,
    video_seam: str = VIDEO_SEAM_OFF,
):
    return assembly_v35.assemble_decoded_chunks_v35(
        images=images,
        audio=audio,
        assembly_plan=plan,
        exact_total_duration=exact,
        audio_seam=audio_seam,
        video_seam=video_seam,
        diagnostics=DIAGNOSTICS_BASIC,
        buffer_backend=backend,
        backing_root=backing_root,
    )


def _assert_av_equal(left, right) -> None:
    assert torch.equal(left[0], right[0])
    assert left[1]["sample_rate"] == right[1]["sample_rate"]
    assert torch.equal(left[1]["waveform"], right[1]["waveform"])


def _collect_released_disk_tensor(root: Path) -> None:
    gc.collect()
    get_file_backed_image_manager(root).collect_ready()


@pytest.mark.parametrize(
    ("kind", "exact", "expected_frames"),
    (
        ("single", False, 124),
        ("single", True, 120),
        ("terminal_2x5", False, 243),
        ("terminal_2x5", True, 240),
        ("long_terminal_3x5", False, 362),
        ("long_terminal_3x5", True, 360),
    ),
)
def test_ram_and_disk_are_bit_exact_with_v34_required_layouts(
    tmp_path,
    kind,
    exact,
    expected_frames,
):
    plan = _plan(kind)
    images, audio = _decoded(plan)
    baseline = _v34(images, audio, plan, exact=exact)
    ram = _v35(
        images,
        audio,
        plan,
        exact=exact,
        backend=BUFFER_BACKEND_RAM,
        backing_root=tmp_path,
    )
    disk = _v35(
        images,
        audio,
        plan,
        exact=exact,
        backend=BUFFER_BACKEND_DISK,
        backing_root=tmp_path,
    )

    assert int(baseline[0].shape[0]) == expected_frames
    _assert_av_equal(ram, baseline)
    _assert_av_equal(disk, baseline)
    disk_image = disk[0]
    del disk
    del disk_image
    _collect_released_disk_tensor(tmp_path)


@pytest.mark.parametrize(
    ("video_seam", "seam_case"),
    (
        (VIDEO_SEAM_OFF, "transient"),
        (VIDEO_SEAM_ANALYZE, "transient"),
        (VIDEO_SEAM_AUTO, "transient"),
        (VIDEO_SEAM_AUTO_2, "exposure"),
    ),
)
@pytest.mark.parametrize("backend", (BUFFER_BACKEND_RAM, BUFFER_BACKEND_DISK))
@pytest.mark.parametrize("exact", (False, True))
def test_all_video_seam_modes_are_bit_exact_with_v34(
    tmp_path,
    video_seam,
    seam_case,
    backend,
    exact,
):
    plan = _plan("long_terminal_3x5")
    images, audio = _decoded(plan, seam_case=seam_case)
    baseline = _v34(
        images,
        audio,
        plan,
        exact=exact,
        video_seam=video_seam,
    )
    candidate = _v35(
        images,
        audio,
        plan,
        exact=exact,
        backend=backend,
        backing_root=tmp_path,
        video_seam=video_seam,
    )

    _assert_av_equal(candidate, baseline)
    if backend == BUFFER_BACKEND_DISK:
        disk_image = candidate[0]
        del candidate
        del disk_image
        _collect_released_disk_tensor(tmp_path)


@pytest.mark.parametrize("backend", (BUFFER_BACKEND_RAM, BUFFER_BACKEND_DISK))
@pytest.mark.parametrize("exact", (False, True))
def test_audio_seam_auto_is_bit_exact_with_v34(tmp_path, backend, exact):
    plan = _plan("long_terminal_3x5")
    images, audio = _decoded(plan, seam_case="clean")
    previous_samples = int(round(124 / _FPS * _SAMPLE_RATE))
    context_samples = int(round(22 / _FPS * _SAMPLE_RATE))
    first_time = torch.arange(previous_samples, dtype=torch.float32)
    second_count = int(round(260 / _FPS * _SAMPLE_RATE))
    second_time = torch.arange(
        previous_samples - context_samples,
        previous_samples - context_samples + second_count,
        dtype=torch.float32,
    )
    first_wave = torch.sin(first_time * (2.0 * torch.pi / 31.0))
    second_wave = torch.sin(second_time * (2.0 * torch.pi / 31.0))
    audio[0]["waveform"] = first_wave.view(1, 1, -1).expand(1, 2, -1).clone()
    audio[1]["waveform"] = second_wave.view(1, 1, -1).expand(1, 2, -1).clone()
    baseline = _v34(
        images,
        audio,
        plan,
        exact=exact,
        audio_seam=AUDIO_SEAM_AUTO,
    )
    candidate = _v35(
        images,
        audio,
        plan,
        exact=exact,
        backend=backend,
        backing_root=tmp_path,
        audio_seam=AUDIO_SEAM_AUTO,
    )

    _assert_av_equal(candidate, baseline)
    assert "audio seam 1->2" in baseline[2]
    assert "fade=0 samples" not in baseline[2]
    assert "fallback to native boundary" not in baseline[2]
    if backend == BUFFER_BACKEND_DISK:
        disk_image = candidate[0]
        del candidate
        del disk_image
        _collect_released_disk_tensor(tmp_path)


@pytest.mark.parametrize("backend", (BUFFER_BACKEND_RAM, BUFFER_BACKEND_DISK))
@pytest.mark.parametrize("exact", (False, True))
def test_32khz_cumulative_rounding_and_audio_seam_match_v34(
    tmp_path,
    backend,
    exact,
):
    plan = _plan("long_terminal_3x5")
    images, audio = _decoded(plan, seam_case="clean", sample_rate=32000)
    baseline = _v34(
        images,
        audio,
        plan,
        exact=exact,
        audio_seam=AUDIO_SEAM_AUTO,
    )
    candidate = _v35(
        images,
        audio,
        plan,
        exact=exact,
        backend=backend,
        backing_root=tmp_path,
        audio_seam=AUDIO_SEAM_AUTO,
    )

    _assert_av_equal(candidate, baseline)
    expected_frames = 360 if exact else 362
    assert candidate[1]["waveform"].shape[-1] == int(
        round(expected_frames / _FPS * 32000)
    )
    if backend == BUFFER_BACKEND_DISK:
        disk_image = candidate[0]
        del candidate
        del disk_image
        _collect_released_disk_tensor(tmp_path)


@pytest.mark.parametrize("backend", (BUFFER_BACKEND_RAM, BUFFER_BACKEND_DISK))
def test_padding_and_final_frame_preservation_match_v34(tmp_path, backend):
    trim_plan = _plan("single", target_frames=120, preserve=True)
    trim_images, trim_audio = _decoded(trim_plan)
    trim_baseline = _v34(trim_images, trim_audio, trim_plan, exact=True)
    trim_candidate = _v35(
        trim_images,
        trim_audio,
        trim_plan,
        exact=True,
        backend=backend,
        backing_root=tmp_path / "trim",
    )
    _assert_av_equal(trim_candidate, trim_baseline)
    assert torch.equal(trim_candidate[0][-1], trim_images[0][-1])

    pad_plan = _plan("single_pad", preserve=False)
    pad_images, pad_audio = _decoded(pad_plan)
    pad_baseline = _v34(pad_images, pad_audio, pad_plan, exact=True)
    pad_candidate = _v35(
        pad_images,
        pad_audio,
        pad_plan,
        exact=True,
        backend=backend,
        backing_root=tmp_path / "pad",
    )
    _assert_av_equal(pad_candidate, pad_baseline)
    assert torch.equal(pad_candidate[0][-1], pad_images[0][-1])

    if backend == BUFFER_BACKEND_DISK:
        trim_image = trim_candidate[0]
        pad_image = pad_candidate[0]
        del trim_candidate, pad_candidate
        del trim_image, pad_image
        _collect_released_disk_tensor(tmp_path / "trim")
        _collect_released_disk_tensor(tmp_path / "pad")


@pytest.mark.parametrize("backend", (BUFFER_BACKEND_RAM, BUFFER_BACKEND_DISK))
def test_tail_trim_without_final_anchor_matches_v34(tmp_path, backend):
    plan = _plan("single", target_frames=120, preserve=False)
    images, audio = _decoded(plan)
    baseline = _v34(images, audio, plan, exact=True)
    candidate = _v35(
        images,
        audio,
        plan,
        exact=True,
        backend=backend,
        backing_root=tmp_path,
    )

    _assert_av_equal(candidate, baseline)
    assert torch.equal(candidate[0][-1], images[0][119])
    assert not torch.equal(candidate[0][-1], images[0][-1])
    if backend == BUFFER_BACKEND_DISK:
        disk_image = candidate[0]
        del candidate
        del disk_image
        _collect_released_disk_tensor(tmp_path)


def test_long_terminal_uses_physical_group_order_and_trim_contract(tmp_path):
    plan = _plan("long_terminal_3x5")
    images, audio = _decoded(plan)
    result = _v35(
        images,
        audio,
        plan,
        exact=False,
        backend=BUFFER_BACKEND_RAM,
        backing_root=tmp_path,
    )

    assert result[0].shape[0] == 362
    assert torch.equal(result[0][:124], images[0])
    assert torch.equal(result[0][124:], images[1][22:260])
    expected_samples = int(round(362 / _FPS * _SAMPLE_RATE))
    assert result[1]["waveform"].shape[-1] == expected_samples


def test_disk_storage_alias_keeps_backing_file_alive_until_last_view(tmp_path):
    plan = _plan("single")
    images, audio = _decoded(plan)
    output, _, _ = _v35(
        images,
        audio,
        plan,
        exact=True,
        backend=BUFFER_BACKEND_DISK,
        backing_root=tmp_path,
    )
    manager = get_file_backed_image_manager(tmp_path)
    managed = list(tmp_path.glob("*.bin"))
    assert len(managed) == 1
    assert managed[0].stat().st_size == output.numel() * output.element_size()

    alias = output[1:]
    del output
    gc.collect()
    held = manager.collect_ready()
    assert held.reclaimed == 0
    assert held.deferred == 1
    assert managed[0].exists()
    assert torch.equal(alias[0], images[0][1])

    del alias
    gc.collect()
    released = manager.collect_ready()
    assert released.reclaimed == 1
    assert not list(tmp_path.glob("*.bin"))
    assert not list(tmp_path.glob("*.json"))


def test_disk_write_error_aborts_unpublished_allocation(tmp_path, monkeypatch):
    plan = _plan("single")
    images, audio = _decoded(plan)
    original = assembly_v35._copy_natural_interval

    def fail_after_allocation(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("synthetic direct-write failure")

    monkeypatch.setattr(assembly_v35, "_copy_natural_interval", fail_after_allocation)
    with pytest.raises(RuntimeError, match="synthetic direct-write failure"):
        _v35(
            images,
            audio,
            plan,
            exact=True,
            backend=BUFFER_BACKEND_DISK,
            backing_root=tmp_path,
        )

    manager = get_file_backed_image_manager(tmp_path)
    assert manager.tracked_count() == 0
    assert manager.pending_count() == 0
    assert not list(tmp_path.glob("*.bin"))
    assert not list(tmp_path.glob("*.json"))


def test_invalid_driving_audio_aborts_before_disk_publish(tmp_path, monkeypatch):
    plan = _plan("single")
    images, audio = _decoded(plan)
    original_allocate = assembly_v35.allocate_file_backed_image

    def allocate_at_test_root(shape, *, dtype, backing_root=None):
        return original_allocate(shape, dtype=dtype, backing_root=tmp_path)

    monkeypatch.setattr(
        assembly_v35,
        "allocate_file_backed_image",
        allocate_at_test_root,
    )
    invalid_driving = {
        "waveform": torch.zeros((1, 1, 1240), dtype=torch.float32),
        "sample_rate": 0,
    }
    with pytest.raises(ValueError, match="sample_rate"):
        H3ContinuumAssembleSeamV35().assemble(
            images,
            audio,
            plan,
            True,
            AUDIO_SEAM_OFF,
            VIDEO_SEAM_OFF,
            BUFFER_BACKEND_DISK,
            DIAGNOSTICS_BASIC,
            driving_audio=invalid_driving,
        )

    manager = get_file_backed_image_manager(tmp_path)
    assert manager.tracked_count() == 0
    assert manager.pending_count() == 0
    assert not list(tmp_path.glob("*.bin"))
    assert not list(tmp_path.glob("*.json"))


def test_auto_backend_is_default_while_manual_values_remain_available():
    schema = H3ContinuumAssembleSeamV35.INPUT_TYPES()
    backend_options = schema["required"]["buffer_backend"][0]
    backend_config = schema["required"]["buffer_backend"][1]
    assert tuple(backend_options) == (
        BUFFER_BACKEND_AUTO,
        BUFFER_BACKEND_RAM,
        BUFFER_BACKEND_DISK,
    )
    assert backend_config["default"] == BUFFER_BACKEND_AUTO


@pytest.mark.parametrize(
    "selected_backend",
    (BUFFER_BACKEND_RAM, BUFFER_BACKEND_DISK),
)
def test_auto_backend_uses_selected_writer_and_reports_decision(
    tmp_path,
    monkeypatch,
    selected_backend,
):
    gib = 1024**3
    plan = _plan("single")
    images, audio = _decoded(plan)
    decision = AutoBufferDecision(
        selected_backend=selected_backend,
        final_image_bytes=120 * 8 * 8 * 3 * 4,
        backing_root=tmp_path,
        available_memory_bytes=16 * gib,
        total_memory_bytes=64 * gib,
        memory_reserve_bytes=int(64 * gib * 0.10),
        ram_image_limit_bytes=4 * gib,
        disk_free_bytes=(100 * gib if selected_backend == BUFFER_BACKEND_DISK else None),
        disk_reserve_bytes=2 * gib,
        reason="synthetic test decision",
    )
    monkeypatch.setattr(
        assembly_v35,
        "select_auto_buffer_backend",
        lambda final_image_bytes, backing_root=None: decision,
    )

    candidate = _v35(
        images,
        audio,
        plan,
        exact=True,
        backend=BUFFER_BACKEND_AUTO,
        backing_root=tmp_path,
    )
    baseline = _v35(
        images,
        audio,
        plan,
        exact=True,
        backend=selected_backend,
        backing_root=tmp_path / "manual",
    )

    _assert_av_equal(candidate, baseline)
    assert f"Buffer Backend: Auto -> {selected_backend}" in candidate[2]
    assert f"selected={selected_backend}" in candidate[2]
    assert "reason=synthetic test decision" in candidate[2]

    candidate_image = candidate[0]
    baseline_image = baseline[0]
    del candidate, baseline, candidate_image, baseline_image
    if selected_backend == BUFFER_BACKEND_DISK:
        _collect_released_disk_tensor(tmp_path)
        _collect_released_disk_tensor(tmp_path / "manual")


def test_direct_image_path_has_no_full_materialization_operations():
    source = inspect.getsource(assembly_v35)
    for forbidden in (
        "torch.cat(",
        "torch.stack(",
        ".clone(",
        ".contiguous(",
        "correct_decoded_boundaries",
    ):
        assert forbidden not in source


def test_small_patch_copy_intersects_prefix_and_final_anchor_spans_only():
    destination = torch.full((5, 1, 1, 1), -1.0)
    spans = (
        assembly_v35.CopySpan(0, 4, 0),
        assembly_v35.CopySpan(9, 10, 4),
    )
    crossing_patch = torch.tensor([30.0, 40.0, 50.0]).reshape(3, 1, 1, 1)
    assembly_v35._copy_natural_interval(
        destination,
        crossing_patch,
        natural_start=3,
        spans=spans,
    )
    anchor_patch = torch.tensor([90.0]).reshape(1, 1, 1, 1)
    assembly_v35._copy_natural_interval(
        destination,
        anchor_patch,
        natural_start=9,
        spans=spans,
    )

    assert destination[:, 0, 0, 0].tolist() == [-1.0, -1.0, -1.0, 30.0, 90.0]


def test_node_accepts_comfy_positional_list_inputs(tmp_path, monkeypatch):
    plan = _plan("single")
    images, audio = _decoded(plan)
    original_allocate = assembly_v35.allocate_file_backed_image

    def allocate_at_test_root(shape, *, dtype, backing_root=None):
        return original_allocate(shape, dtype=dtype, backing_root=tmp_path)

    monkeypatch.setattr(
        assembly_v35,
        "allocate_file_backed_image",
        allocate_at_test_root,
    )
    node = H3ContinuumAssembleSeamV35()
    result = node.assemble(
        images,
        audio,
        [plan],
        [True],
        [AUDIO_SEAM_OFF],
        [VIDEO_SEAM_OFF],
        [BUFFER_BACKEND_DISK],
        [DIAGNOSTICS_FULL],
    )
    baseline = _v34(images, audio, plan, exact=True)

    assert node.INPUT_IS_LIST is True
    _assert_av_equal(result, baseline)
    assert "Buffer Backend: Disk-backed" in result[2]
    assert "Projected assembly buffers [V3.5]" in result[2]
    disk_image = result[0]
    del result
    del disk_image
    _collect_released_disk_tensor(tmp_path)


@pytest.mark.parametrize("stored_in_plan", (False, True))
def test_driving_audio_selection_is_bit_exact_with_v34(
    tmp_path,
    stored_in_plan,
):
    plan = _plan("single", preserve=True)
    images, audio = _decoded(plan)
    driving_samples = int(round(124 / _FPS * _SAMPLE_RATE))
    driving = {
        "waveform": torch.arange(
            driving_samples,
            dtype=torch.float32,
        ).view(1, 1, -1),
        "sample_rate": _SAMPLE_RATE,
    }
    direct = None if stored_in_plan else driving
    if stored_in_plan:
        plan = dict(plan)
        plan["_h3_continuum_driving_audio_v1"] = driving

    baseline = H3ContinuumAssembleSeamV34().assemble(
        images,
        audio,
        plan,
        True,
        AUDIO_SEAM_AUTO,
        VIDEO_SEAM_OFF,
        DIAGNOSTICS_BASIC,
        driving_audio=direct,
    )
    candidate = H3ContinuumAssembleSeamV35().assemble(
        images,
        audio,
        plan,
        True,
        AUDIO_SEAM_AUTO,
        VIDEO_SEAM_OFF,
        BUFFER_BACKEND_RAM,
        DIAGNOSTICS_BASIC,
        driving_audio=direct,
    )

    _assert_av_equal(candidate, baseline)
    assert "Driving Audio: preserved source selected" in candidate[2]
