import torch

from ComfyUI_H3_Continuum_Join.constants import DIAGNOSTICS_FULL
from ComfyUI_H3_Continuum_Join.hardening import enrich_assembly_plan
from ComfyUI_H3_Continuum_Join.v3.assembly import (
    AUDIO_SEAM_OFF,
    H3ContinuumAssembleSeamExperimental,
    H3ContinuumAssembleV3,
    IMAGE_OUTPUT_CPU,
    _enforce_image_duration_in_place,
    assemble_decoded_chunks,
)
from ComfyUI_H3_Continuum_Join.v3.plan import ASSEMBLY_PLAN_MAGIC
from ComfyUI_H3_Continuum_Join.v3.video_seam import (
    analyze_decoded_boundaries,
    build_decoded_boundary_patches,
)


def _plan(*, width=8, height=8):
    return enrich_assembly_plan(
        {
            "magic": ASSEMBLY_PLAN_MAGIC,
            "schema_version": 1,
            "fps": 24,
            "width": width,
            "height": height,
            "chunk_seconds": 5.0,
            "target_frames": 240,
            "preserve_final_frame": True,
            "chunks": [
                {
                    "sequence_index": 1,
                    "chunk_index": 1,
                    "total_frames": 124,
                    "trim_frames": 0,
                    "net_frames": 124,
                    "context_frames": 0,
                    "expected_video_latent_t": 32,
                    "expected_audio_latent_t": 207,
                },
                {
                    "sequence_index": 2,
                    "chunk_index": 2,
                    "total_frames": 141,
                    "trim_frames": 22,
                    "net_frames": 119,
                    "context_frames": 22,
                    "expected_video_latent_t": 36,
                    "expected_audio_latent_t": 235,
                },
            ],
        }
    )


def _decoded(*, height=8, width=8):
    images = [
        torch.full((124, height, width, 3), 0.25, dtype=torch.float32),
        torch.full((141, height, width, 3), 0.25, dtype=torch.float32),
    ]
    audio = [
        {"waveform": torch.zeros((1, 2, 190000)), "sample_rate": 32000},
        {"waveform": torch.zeros((1, 2, 190000)), "sample_rate": 32000},
    ]
    return images, audio


def _storage_ptr(tensor):
    return tensor.untyped_storage().data_ptr()


def test_boundary_builder_owns_only_qualified_boundary_frames():
    images, _audio = _decoded(height=16, width=16)
    images[1][22] = 1.0
    current_before = images[1].clone()

    analyses = analyze_decoded_boundaries(images=images, assembly_plan=_plan())
    patches, actions = build_decoded_boundary_patches(
        images=images,
        assembly_plan=_plan(),
        analyses=analyses,
    )

    assert set(patches) == {1}
    patch = patches[1]
    assert patch.shape == (1, 16, 16, 3)
    assert patch.numel() * patch.element_size() < images[1].numel() * images[1].element_size()
    assert torch.equal(images[1], current_before)
    assert torch.allclose(patch[0], torch.full_like(patch[0], 0.25), atol=1.0e-6)
    assert "normalized exposure/color on 1 transient flash" in actions[1]


def test_exact_duration_trim_reuses_owned_image_storage_and_preserves_tail():
    buffer = torch.arange(6 * 2 * 2 * 3, dtype=torch.float32).reshape(6, 2, 2, 3)
    original_tail = buffer[-1].clone()
    storage_ptr = _storage_ptr(buffer)

    result = _enforce_image_duration_in_place(
        buffer,
        current_frames=6,
        target_frames=4,
        preserve_final_frame=True,
    )

    assert result.shape[0] == 4
    assert _storage_ptr(result) == storage_ptr
    assert torch.equal(result[-1], original_tail)


def test_exact_duration_padding_reuses_preallocated_capacity():
    buffer = torch.empty((6, 2, 2, 3), dtype=torch.float32)
    buffer[:4].copy_(torch.arange(4 * 2 * 2 * 3).reshape(4, 2, 2, 3))
    last = buffer[3].clone()
    storage_ptr = _storage_ptr(buffer)

    result = _enforce_image_duration_in_place(
        buffer,
        current_frames=4,
        target_frames=6,
        preserve_final_frame=False,
    )

    assert _storage_ptr(result) == storage_ptr
    assert torch.equal(result[4], last)
    assert torch.equal(result[5], last)


def test_assembler_accepts_external_2x_decoded_geometry_and_reports_it():
    images, audio = _decoded(height=16, width=16)
    output_images, output_audio, report = assemble_decoded_chunks(
        images=images,
        audio=audio,
        assembly_plan=_plan(width=8, height=8),
        exact_total_duration=False,
        audio_seam=AUDIO_SEAM_OFF,
        diagnostics=DIAGNOSTICS_FULL,
        image_output_device=IMAGE_OUTPUT_CPU,
    )

    assert output_images.shape == (243, 16, 16, 3)
    assert output_images.device.type == "cpu"
    assert output_audio["sample_rate"] == 32000
    assert "Decoded geometry: 16x16 vs plan 8x8 (2.000x/2.000x)" in report


def test_new_output_device_widget_is_appended_after_existing_serialized_widgets():
    base_required = list(H3ContinuumAssembleV3.INPUT_TYPES()["required"])
    experimental_required = list(
        H3ContinuumAssembleSeamExperimental.INPUT_TYPES()["required"]
    )

    assert base_required[-2:] == ["diagnostics", "image_output_device"]
    assert experimental_required[-3:] == [
        "video_seam",
        "diagnostics",
        "image_output_device",
    ]
