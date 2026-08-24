from __future__ import annotations

import gc

import pytest
import torch

from ComfyUI_H3_Continuum_Join.constants import DIAGNOSTICS_BASIC
from ComfyUI_H3_Continuum_Join.hardening import enrich_assembly_plan
from ComfyUI_H3_Continuum_Join.temporal import audio_latent_t, video_latent_t
from ComfyUI_H3_Continuum_Join.v3.assembly import (
    AUDIO_SEAM_OFF,
    VIDEO_SEAM_OFF,
)
from ComfyUI_H3_Continuum_Join.v3.assembly_v35 import (
    assemble_decoded_chunks_v35,
)
from ComfyUI_H3_Continuum_Join.v3.file_backed_buffer import (
    BUFFER_BACKEND_DISK,
    BUFFER_BACKEND_RAM,
    get_file_backed_image_manager,
)
from ComfyUI_H3_Continuum_Join.v3.plan import ASSEMBLY_PLAN_MAGIC


class ProbeCancelled(BaseException):
    pass


def _fixture():
    total_frames = 124
    target_frames = 120
    sample_rate = 240
    chunk = {
        "sequence_index": 1,
        "chunk_index": 1,
        "total_frames": total_frames,
        "trim_frames": 0,
        "net_frames": total_frames,
        "context_frames": 0,
        "expected_video_latent_t": video_latent_t(total_frames),
        "expected_audio_latent_t": audio_latent_t(total_frames),
    }
    plan = enrich_assembly_plan(
        {
            "magic": ASSEMBLY_PLAN_MAGIC,
            "schema_version": 1,
            "fps": 24,
            "width": 8,
            "height": 8,
            "chunk_seconds": 5.0,
            "target_frames": target_frames,
            "preserve_final_frame": True,
            "chunks": [chunk],
        }
    )
    values = torch.arange(total_frames, dtype=torch.float32) / total_frames
    images = [values.reshape(-1, 1, 1, 1).expand(-1, 8, 8, 3).clone()]
    samples = int(round(total_frames / 24 * sample_rate))
    audio = [
        {
            "waveform": torch.linspace(0.0, 1.0, samples).reshape(1, 1, -1),
            "sample_rate": sample_rate,
        }
    ]
    return images, audio, plan


def _assemble(images, audio, plan, *, backend, root, interrupt_check):
    return assemble_decoded_chunks_v35(
        images=images,
        audio=audio,
        assembly_plan=plan,
        exact_total_duration=True,
        audio_seam=AUDIO_SEAM_OFF,
        video_seam=VIDEO_SEAM_OFF,
        diagnostics=DIAGNOSTICS_BASIC,
        buffer_backend=backend,
        backing_root=root,
        interrupt_check=interrupt_check,
    )


def _collect(root, *values):
    del values
    gc.collect()
    manager = get_file_backed_image_manager(root)
    manager.collect_ready()
    gc.collect()
    manager.collect_ready()


def test_interrupt_polling_keeps_ram_and_disk_outputs_bit_exact(tmp_path):
    images, audio, plan = _fixture()
    checks = 0

    def check():
        nonlocal checks
        checks += 1

    ram = _assemble(
        images,
        audio,
        plan,
        backend=BUFFER_BACKEND_RAM,
        root=tmp_path,
        interrupt_check=check,
    )
    disk = _assemble(
        images,
        audio,
        plan,
        backend=BUFFER_BACKEND_DISK,
        root=tmp_path,
        interrupt_check=check,
    )

    assert checks >= 20
    assert torch.equal(disk[0], ram[0])
    assert torch.equal(disk[1]["waveform"], ram[1]["waveform"])
    assert disk[1]["sample_rate"] == ram[1]["sample_rate"]

    disk_image = disk[0]
    del disk
    del disk_image
    _collect(tmp_path)
    assert not list(tmp_path.glob("*.bin"))
    assert not list(tmp_path.glob("*.json"))


def test_mid_copy_cancel_aborts_unpublished_disk_pair(tmp_path):
    images, audio, plan = _fixture()
    checks = 0

    def cancel_during_copy():
        nonlocal checks
        checks += 1
        if checks == 4:
            raise ProbeCancelled("P2-4 synthetic ESC")

    with pytest.raises(ProbeCancelled, match="synthetic ESC"):
        _assemble(
            images,
            audio,
            plan,
            backend=BUFFER_BACKEND_DISK,
            root=tmp_path,
            interrupt_check=cancel_during_copy,
        )

    manager = get_file_backed_image_manager(tmp_path)
    assert checks == 4
    assert manager.tracked_count() == 0
    assert manager.pending_count() == 0
    assert not list(tmp_path.glob("*.bin"))
    assert not list(tmp_path.glob("*.json"))


def test_cancel_immediately_after_allocation_aborts_disk_pair(tmp_path):
    images, audio, plan = _fixture()

    def cancel_after_allocation():
        raise ProbeCancelled("P2-4 pre-copy ESC")

    with pytest.raises(ProbeCancelled, match="pre-copy ESC"):
        _assemble(
            images,
            audio,
            plan,
            backend=BUFFER_BACKEND_DISK,
            root=tmp_path,
            interrupt_check=cancel_after_allocation,
        )

    manager = get_file_backed_image_manager(tmp_path)
    assert manager.tracked_count() == 0
    assert manager.pending_count() == 0
    assert not list(tmp_path.glob("*.bin"))
    assert not list(tmp_path.glob("*.json"))
