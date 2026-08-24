from __future__ import annotations

import pytest
import torch

from ComfyUI_H3_Continuum_Join.constants import (
    DIAGNOSTICS_BASIC,
    DIAGNOSTICS_FULL,
    DIAGNOSTICS_OFF,
)
from ComfyUI_H3_Continuum_Join import hardening
from ComfyUI_H3_Continuum_Join.hardening import enrich_assembly_plan
from ComfyUI_H3_Continuum_Join.v3 import memory_attribution as memory
from ComfyUI_H3_Continuum_Join.v3 import driving_nodes as driving_nodes_module
from ComfyUI_H3_Continuum_Join.v3.driving_nodes import (
    H3ContinuumAssembleSeamV34,
    H3ContinuumAssembleSeamV35,
    NODE_CLASS_MAPPINGS,
    NODE_DISPLAY_NAME_MAPPINGS,
)
from ComfyUI_H3_Continuum_Join.v3.plan import ASSEMBLY_PLAN_MAGIC


def _terminal_plan():
    plan = enrich_assembly_plan(
        {
            "magic": ASSEMBLY_PLAN_MAGIC,
            "schema_version": 1,
            "fps": 24,
            "width": 96,
            "height": 64,
            "chunk_seconds": 5.0,
            "target_frames": 360,
            "preserve_final_frame": True,
            "chunks": [
                {
                    "sequence_index": 1,
                    "chunk_index": 1,
                    "total_frames": 124,
                    "trim_frames": 0,
                    "net_frames": 124,
                    "context_frames": 0,
                    "expected_video_latent_t": 37,
                    "expected_audio_latent_t": 207,
                },
                {
                    "sequence_index": 2,
                    "chunk_index": 2,
                    "total_frames": 141,
                    "trim_frames": 22,
                    "net_frames": 119,
                    "context_frames": 22,
                    "expected_video_latent_t": 42,
                    "expected_audio_latent_t": 235,
                },
                {
                    "sequence_index": 3,
                    "chunk_index": 3,
                    "total_frames": 141,
                    "trim_frames": 22,
                    "net_frames": 119,
                    "context_frames": 22,
                    "expected_video_latent_t": 42,
                    "expected_audio_latent_t": 235,
                },
            ],
        }
    )
    plan["decode_groups"] = [
        {
            "logical_chunk_indices": [1],
            "terminal_merged": False,
            "total_frames": 124,
            "trim_frames": 0,
            "net_frames": 124,
            "context_frames": 0,
            "expected_video_latent_t": 37,
            "expected_audio_latent_t": 207,
            "frame_start": 0,
            "frame_stop": 124,
        },
        {
            "logical_chunk_indices": [2, 3],
            "terminal_merged": True,
            "total_frames": 260,
            "trim_frames": 22,
            "net_frames": 238,
            "context_frames": 22,
            "expected_video_latent_t": 77,
            "expected_audio_latent_t": 433,
            "frame_start": 124,
            "frame_stop": 362,
        },
    ]
    plan["physical_decode_group_count"] = 2
    return plan


def _decoded(*, image_dtype=torch.float16, device=None):
    images = [
        torch.empty((124, 4, 6, 3), dtype=image_dtype, device=device),
        torch.empty((260, 4, 6, 3), dtype=image_dtype, device=device),
    ]
    audio = [
        {
            "waveform": torch.empty(
                (1, 2, 500000),
                dtype=torch.float32,
                device=device,
            ),
            "sample_rate": 32000,
        },
        {
            "waveform": torch.empty(
                (1, 2, 500000),
                dtype=torch.float32,
                device=device,
            ),
            "sample_rate": 32000,
        },
    ]
    return images, audio


def test_snapshot_is_cpu_safe_read_only_and_deduplicates_retained_storage(
    monkeypatch,
):
    video_storage = torch.arange(24, dtype=torch.float32)
    audio_storage = torch.arange(12, dtype=torch.float32)
    entries = [
        {"video": video_storage[:16], "audio": audio_storage[:8]},
        {"video": video_storage[8:], "audio": audio_storage[4:]},
    ]
    monkeypatch.setattr(memory.torch.cuda, "is_available", lambda: False)
    for name in (
        "memory_allocated",
        "memory_reserved",
        "max_memory_allocated",
        "synchronize",
        "reset_peak_memory_stats",
        "empty_cache",
    ):
        monkeypatch.setattr(
            memory.torch.cuda,
            name,
            lambda *args, _name=name, **kwargs: (_ for _ in ()).throw(
                AssertionError(f"unexpected CUDA call: {_name}")
            ),
        )

    line = memory.format_attribution_snapshot(
        "test",
        retained_entries=entries,
    )
    assert f"retained_video={video_storage.untyped_storage().nbytes()} bytes" in line
    assert f"retained_audio={audio_storage.untyped_storage().nbytes()} bytes" in line
    assert "CUDA_allocated=n/a" in line
    assert "CUDA_peak_allocated_since_external_reset=n/a" in line


def test_snapshot_counter_failure_is_reported_as_unavailable(monkeypatch):
    monkeypatch.setattr(memory, "_process_counters", lambda: (None, None))
    monkeypatch.setattr(memory, "_cuda_counters", lambda: (None, None, None))
    line = memory.format_attribution_snapshot("failure-safe")
    assert "RSS=n/a" in line
    assert "system_available=n/a" in line
    assert "CUDA_reserved=n/a" in line


def test_snapshot_counts_refine_context_storage_once():
    shared = torch.arange(32, dtype=torch.float32)
    refine_context = {
        "groups": (
            {
                "conditioning": (
                    (shared[:8], {"reference": shared[8:16]}),
                ),
                "first_image": shared[16:24],
            },
        ),
        "alias": shared[4:28],
    }

    line = memory.format_attribution_snapshot(
        "refine-context",
        retained_refine_context=refine_context,
    )

    expected = shared.untyped_storage().nbytes()
    assert f"retained_refine_context_CPU={expected} bytes" in line
    assert "retained_refine_context_GPU=0 bytes" in line


def test_cuda_snapshot_reads_counters_without_allocator_mutation(monkeypatch):
    monkeypatch.setattr(memory.torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(memory.torch.cuda, "memory_allocated", lambda: 11)
    monkeypatch.setattr(memory.torch.cuda, "memory_reserved", lambda: 22)
    monkeypatch.setattr(memory.torch.cuda, "max_memory_allocated", lambda: 33)
    for name in (
        "synchronize",
        "reset_peak_memory_stats",
        "empty_cache",
    ):
        monkeypatch.setattr(
            memory.torch.cuda,
            name,
            lambda *args, _name=name, **kwargs: (_ for _ in ()).throw(
                AssertionError(f"unexpected CUDA mutation: {_name}")
            ),
        )

    line = memory.format_attribution_snapshot("cuda-read-only")

    assert "CUDA_allocated=0.0 MiB" in line
    assert "CUDA_reserved=0.0 MiB" in line
    assert "CUDA_peak_allocated_since_external_reset=0.0 MiB" in line


@pytest.mark.parametrize(
    "method",
    (
        "capture_sequence_start",
        "capture_group",
        "capture_sequence_complete",
    ),
)
def test_each_collector_stage_is_fail_soft(method):
    class ExplodingCollector:
        def __init__(self):
            self.lines = []

        def __getattr__(self, name):
            if name.startswith("capture_"):
                return lambda **_kwargs: (_ for _ in ()).throw(
                    RuntimeError(f"{name} failed")
                )
            raise AttributeError(name)

    collector = ExplodingCollector()
    memory.capture_attribution_fail_soft(collector, method)

    assert collector.lines == [
        f"Memory attribution [{method}]: unavailable "
        f"(RuntimeError: {method} failed)"
    ]


def test_sequence_start_and_complete_failures_do_not_replace_sampling_result():
    class ExplodingCollector:
        def __init__(self):
            self.lines = []

        def capture_sequence_start(self):
            raise RuntimeError("start failed")

        def capture_sequence_complete(self, **_kwargs):
            raise RuntimeError("complete failed")

    collector = ExplodingCollector()
    entries = [{"video": torch.zeros(1), "audio": torch.zeros(1)}]
    session = {"chunks": entries}
    refine_context = {"groups": ()}
    base_result = (entries, "state", session, "base report", refine_context)
    base_calls = []

    def base(
        *,
        video_vae,
        latent_only,
        diagnostics_mode,
        memory_attribution,
        _memory_attribution_collector=None,
    ):
        base_calls.append(_memory_attribution_collector)
        return base_result

    result = hardening.run_sequence_with_hardening(
        base,
        (),
        {
            "video_vae": object(),
            "latent_only": True,
            "diagnostics_mode": DIAGNOSTICS_FULL,
            "memory_attribution": True,
            "_memory_attribution_collector": collector,
        },
    )

    assert base_calls == [collector]
    assert result[:3] == base_result[:3]
    assert result[4] is refine_context
    assert "base report" in result[3]
    assert "capture_sequence_start" in result[3]
    assert "capture_sequence_complete" in result[3]


@pytest.mark.parametrize("diagnostics", (DIAGNOSTICS_BASIC, DIAGNOSTICS_OFF))
def test_v35_attribution_is_absent_outside_detailed_report(diagnostics):
    base_result = ("entries", "state", "session", "base report", "context")
    calls = []

    def base(
        *,
        video_vae,
        latent_only,
        diagnostics_mode,
        memory_attribution,
        _memory_attribution_collector=None,
    ):
        calls.append(_memory_attribution_collector)
        return base_result

    result = hardening.run_sequence_with_hardening(
        base,
        (),
        {
            "video_vae": object(),
            "latent_only": True,
            "diagnostics_mode": diagnostics,
            "memory_attribution": True,
        },
    )

    assert result is base_result
    assert calls == [None]
    assert "Memory [V3.5" not in result[3]


def test_v34_private_flag_off_keeps_existing_detailed_report_path():
    entries = [{"video": torch.zeros(1), "audio": torch.zeros(1)}]
    session = {"chunks": entries}
    calls = []

    def base(
        *,
        video_vae,
        latent_only,
        diagnostics_mode,
        memory_attribution=False,
        _memory_attribution_collector=None,
    ):
        calls.append((memory_attribution, _memory_attribution_collector))
        return entries, "state", session, "base report"

    result = hardening.run_sequence_with_hardening(
        base,
        (),
        {
            "video_vae": object(),
            "latent_only": True,
            "diagnostics_mode": DIAGNOSTICS_FULL,
            "memory_attribution": False,
        },
    )

    assert calls == [(False, None)]
    assert result[0] is entries
    assert result[2] is session
    assert "Memory [sequence start]" in result[3]
    assert "Memory [sequence complete]" in result[3]
    assert "Memory [V3.5" not in result[3]


def test_projection_uses_physical_groups_actual_dtypes_and_exact_target():
    images, audio = _decoded()
    off = memory.project_assembly_buffers(
        images=images,
        audio=audio,
        assembly_plan=_terminal_plan(),
        exact_total_duration=False,
    )
    assert off.natural_frames == 362
    assert off.target_frames == 362
    assert off.natural_image_bytes == 52128
    assert off.natural_audio_bytes == 3861336
    assert off.final_image_bytes == 52128
    assert off.final_audio_bytes == 3861336
    assert off.frame_count_adjustment_required is False

    exact = memory.project_assembly_buffers(
        images=images,
        audio=audio,
        assembly_plan=_terminal_plan(),
        exact_total_duration=True,
    )
    assert exact.natural_frames == 362
    assert exact.target_frames == 360
    assert exact.natural_image_bytes == 52128
    assert exact.natural_audio_bytes == 3861336
    assert exact.final_image_bytes == 51840
    assert exact.final_audio_bytes == 3840000
    assert exact.frame_count_adjustment_required is True


def test_projection_uses_python_int_for_real_1152_square_output():
    images, audio = _decoded(device="meta")
    images = [
        torch.empty((124, 1152, 1152, 3), dtype=torch.float32, device="meta"),
        torch.empty((260, 1152, 1152, 3), dtype=torch.float32, device="meta"),
    ]
    projection = memory.project_assembly_buffers(
        images=images,
        audio=audio,
        assembly_plan=_terminal_plan(),
        exact_total_duration=True,
    )
    assert projection.final_image_bytes == 5733089280
    assert isinstance(projection.final_image_bytes, int)


def test_v35_assembler_adds_projection_only_for_detailed_report(monkeypatch):
    input_images, input_audio = _decoded()
    output_images = torch.zeros((1, 1, 1, 3))
    output_audio = {"waveform": torch.zeros((1, 2, 1)), "sample_rate": 32000}
    base_calls = []

    def fake_v35_assemble(**kwargs):
        base_calls.append(kwargs)
        return (
            output_images,
            output_audio,
            "base report\nMemory [assemble preflight]: test\n"
            "Memory [assemble complete]: test",
        )

    monkeypatch.setattr(
        driving_nodes_module,
        "assemble_decoded_chunks_v35",
        fake_v35_assemble,
    )
    node = H3ContinuumAssembleSeamV35()
    detailed_images, detailed_audio, detailed_report = node.assemble(
        images=input_images,
        audio=input_audio,
        assembly_plan=_terminal_plan(),
        exact_total_duration=True,
        audio_seam="Auto",
        video_seam="Auto",
        buffer_backend="RAM",
        diagnostics=DIAGNOSTICS_FULL,
    )
    assert detailed_images is output_images
    assert detailed_audio is output_audio
    assert "Projected assembly buffers [V3.5]" in detailed_report
    assert detailed_report.index("Memory [assemble preflight]") < detailed_report.index(
        "Projected assembly buffers [V3.5]"
    )
    assert detailed_report.index("Projected assembly buffers [V3.5]") < (
        detailed_report.index("Memory [assemble complete]")
    )

    _, _, basic_report = node.assemble(
        images=input_images,
        audio=input_audio,
        assembly_plan=_terminal_plan(),
        exact_total_duration=True,
        audio_seam="Auto",
        video_seam="Auto",
        buffer_backend="RAM",
        diagnostics=DIAGNOSTICS_BASIC,
    )
    assert "Projected assembly buffers [V3.5]" not in basic_report
    assert len(base_calls) == 2


def test_v35_assembler_projection_failure_never_replaces_base_execution(monkeypatch):
    output_images = torch.zeros((1, 1, 1, 3))
    output_audio = {"waveform": torch.zeros((1, 2, 1)), "sample_rate": 32000}
    monkeypatch.setattr(
        driving_nodes_module,
        "assemble_decoded_chunks_v35",
        lambda **kwargs: (output_images, output_audio, "base report"),
    )
    images, audio, report = H3ContinuumAssembleSeamV35().assemble(
        images=[],
        audio=[],
        assembly_plan={},
        exact_total_duration=True,
        audio_seam="Auto",
        video_seam="Auto",
        buffer_backend="RAM",
        diagnostics=DIAGNOSTICS_FULL,
    )
    assert images is output_images
    assert audio is output_audio
    assert "Projected assembly buffers [V3.5]: unavailable" in report


def test_v35_assembler_is_registered_without_replacing_v34():
    from ComfyUI_H3_Continuum_Join import nodes as root_nodes

    assert NODE_CLASS_MAPPINGS["H3ContinuumAssembleSeamV34"] is (
        H3ContinuumAssembleSeamV34
    )
    assert NODE_CLASS_MAPPINGS["H3ContinuumAssembleSeamV35"] is (
        H3ContinuumAssembleSeamV35
    )
    assert root_nodes.NODE_CLASS_MAPPINGS["H3ContinuumAssembleSeamV35"] is (
        H3ContinuumAssembleSeamV35
    )
    assert NODE_DISPLAY_NAME_MAPPINGS["H3ContinuumAssembleSeamV35"] == (
        "H3 Continuum Assemble + Seam V3.5"
    )
