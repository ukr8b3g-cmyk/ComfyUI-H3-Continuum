import torch

from ComfyUI_H3_Continuum_Join.constants import DIAGNOSTICS_OPTIONS
from ComfyUI_H3_Continuum_Join.hardening import enrich_assembly_plan
from ComfyUI_H3_Continuum_Join.v3.assembly import (
    H3ContinuumAssembleSeamExperimental,
    VIDEO_SEAM_ANALYZE,
    VIDEO_SEAM_AUTO,
    VIDEO_SEAM_OFF,
)
from ComfyUI_H3_Continuum_Join.v3.nodes import NODE_CLASS_MAPPINGS
from ComfyUI_H3_Continuum_Join.v3.plan import ASSEMBLY_PLAN_MAGIC
from ComfyUI_H3_Continuum_Join.v3.video_seam import analyze_video_boundary


def _frames(values, *, height=8, width=8):
    return (
        torch.tensor(values, dtype=torch.float32)
        .reshape(-1, 1, 1, 1)
        .expand(-1, height, width, 3)
        .clone()
    )


def _plan():
    return enrich_assembly_plan(
        {
            "magic": ASSEMBLY_PLAN_MAGIC,
            "schema_version": 1,
            "fps": 24,
            "width": 8,
            "height": 8,
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


def _decoded():
    images = [
        torch.full((124, 8, 8, 3), 0.25, dtype=torch.float32),
        torch.full((141, 8, 8, 3), 0.25, dtype=torch.float32),
    ]
    audio = [
        {"waveform": torch.zeros((1, 2, 190000)), "sample_rate": 32000},
        {"waveform": torch.zeros((1, 2, 190000)), "sample_rate": 32000},
    ]
    return images, audio


def test_clean_boundary_keeps_the_nominal_cut():
    previous = _frames([0.1, 0.2, 0.3, 0.4, 0.5, 0.6])
    current = _frames([0.5, 0.6, 0.7, 0.8, 0.9])
    analysis = analyze_video_boundary(previous, current, trim_frames=2)
    assert analysis.recommended_rewind == 0
    assert not analysis.scene_cut
    assert not analysis.transient_flash_candidate
    assert analysis.classification == "clean_boundary"


def test_single_frame_flash_recommends_an_earlier_candidate():
    previous = _frames([0.1, 0.2, 0.3, 0.4, 0.5, 0.6])
    current = _frames([0.5, 0.6, 1.0, 0.8, 0.9])
    analysis = analyze_video_boundary(previous, current, trim_frames=2)
    assert analysis.recommended_rewind == 1
    assert analysis.improvement >= 0.06
    assert not analysis.scene_cut
    assert analysis.transient_flash_candidate
    assert analysis.flash_reversal >= 0.35
    assert analysis.flash_global_fraction >= 0.75
    assert analysis.classification == "transient_flash"


def test_persistent_content_change_is_guarded_as_a_scene_cut():
    previous = _frames([0.1, 0.2, 0.3, 0.4, 0.5, 0.6])
    current = _frames([0.5, 0.6, 0.95, 0.95, 0.95])
    analysis = analyze_video_boundary(previous, current, trim_frames=2)
    assert analysis.scene_cut
    assert analysis.recommended_rewind == 0
    assert not analysis.transient_flash_candidate
    assert analysis.classification == "scene_cut"


def test_small_global_reversal_is_classified_as_micro_flash():
    previous = _frames([0.4, 0.4, 0.4, 0.4, 0.4, 0.4])
    current = _frames([0.4, 0.4, 0.408, 0.4, 0.4, 0.4])
    analysis = analyze_video_boundary(previous, current, trim_frames=2)
    assert not analysis.transient_flash_candidate
    assert analysis.micro_flash_candidate
    assert analysis.classification == "micro_flash"


def test_persistent_global_change_is_classified_as_exposure_ramp():
    previous = _frames([0.4, 0.4, 0.4, 0.4, 0.4, 0.4])
    current = _frames([0.4, 0.4, 0.42, 0.44, 0.46, 0.48])
    analysis = analyze_video_boundary(previous, current, trim_frames=2)
    assert not analysis.transient_flash_candidate
    assert analysis.exposure_ramp_candidate
    assert analysis.classification == "exposure_ramp"


def test_local_velocity_jump_is_classified_as_motion_hitch():
    def moving_bar(position):
        frame = torch.zeros((16, 16, 3), dtype=torch.float32)
        frame[:, position : position + 2, :] = 1.0
        return frame

    previous = torch.stack([moving_bar(position) for position in [1, 2, 3, 4, 5, 6]])
    current = torch.stack([moving_bar(position) for position in [4, 5, 9, 10, 11, 12]])
    analysis = analyze_video_boundary(previous, current, trim_frames=2)
    assert not analysis.transient_flash_candidate
    assert not analysis.micro_flash_candidate
    assert analysis.motion_hitch_candidate
    assert analysis.motion_jump_ratio >= 1.60
    assert analysis.classification == "motion_hitch"


def test_local_motion_is_not_reported_as_a_global_flash():
    previous = torch.full((6, 8, 8, 3), 0.4, dtype=torch.float32)
    current = torch.full((5, 8, 8, 3), 0.4, dtype=torch.float32)
    current[2, :2, :2, :] = 1.0
    analysis = analyze_video_boundary(previous, current, trim_frames=2)
    assert analysis.flash_global_fraction < 0.75
    assert not analysis.transient_flash_candidate


def test_analyze_only_preserves_assembled_image_and_audio_content():
    images, audio = _decoded()
    node = H3ContinuumAssembleSeamExperimental()
    common = {
        "images": images,
        "audio": audio,
        "assembly_plan": [_plan()],
        "exact_total_duration": [False],
        "audio_seam": ["Off"],
        "diagnostics": [DIAGNOSTICS_OPTIONS[0]],
    }
    off_images, off_audio, _off_report = node.assemble(
        video_seam=[VIDEO_SEAM_OFF],
        **common,
    )
    analyzed_images, analyzed_audio, report = node.assemble(
        video_seam=[VIDEO_SEAM_ANALYZE],
        **common,
    )
    assert torch.equal(analyzed_images, off_images)
    assert torch.equal(analyzed_audio["waveform"], off_audio["waveform"])
    assert analyzed_audio["sample_rate"] == off_audio["sample_rate"]
    assert "action=analysis only" in report
    assert "decoded frames and audio are unchanged" in report


def test_auto_replaces_only_qualified_transient_boundary_frame():
    images, audio = _decoded()
    images[1][22] = 1.0
    node = H3ContinuumAssembleSeamExperimental()
    common = {
        "images": images,
        "audio": audio,
        "assembly_plan": [_plan()],
        "exact_total_duration": [False],
        "audio_seam": ["Off"],
        "diagnostics": [DIAGNOSTICS_OPTIONS[0]],
    }
    off_images, off_audio, _ = node.assemble(
        video_seam=[VIDEO_SEAM_OFF],
        **common,
    )
    corrected_images, corrected_audio, report = node.assemble(
        video_seam=[VIDEO_SEAM_AUTO],
        **common,
    )
    assert float(off_images[124].mean().item()) == 1.0
    assert float(corrected_images[124].mean().item()) == 0.25
    assert torch.equal(corrected_images[:124], off_images[:124])
    assert torch.equal(corrected_images[125:], off_images[125:])
    assert torch.equal(corrected_audio["waveform"], off_audio["waveform"])
    assert "Video Seam: Auto" in report
    assert (
        "action=normalized exposure/color on 1 transient flash boundary frame(s)"
        in report
    )


def test_auto_normalizes_only_the_micro_flash_boundary_frame():
    images, audio = _decoded()
    images[1][22] = 0.258
    node = H3ContinuumAssembleSeamExperimental()
    common = {
        "images": images,
        "audio": audio,
        "assembly_plan": [_plan()],
        "exact_total_duration": [False],
        "audio_seam": ["Off"],
        "diagnostics": [DIAGNOSTICS_OPTIONS[0]],
    }
    off_images, off_audio, _ = node.assemble(
        video_seam=[VIDEO_SEAM_OFF],
        **common,
    )
    corrected_images, corrected_audio, report = node.assemble(
        video_seam=[VIDEO_SEAM_AUTO],
        **common,
    )
    assert torch.allclose(off_images[124], torch.full_like(off_images[124], 0.258))
    assert torch.allclose(
        corrected_images[124],
        torch.full_like(corrected_images[124], 0.25),
        atol=1.0e-6,
    )
    assert torch.equal(corrected_images[:124], off_images[:124])
    assert torch.equal(corrected_images[125:], off_images[125:])
    assert torch.equal(corrected_audio["waveform"], off_audio["waveform"])
    assert "class=micro_flash" in report
    assert "action=normalized exposure/color on 1 micro-flash boundary frame(s)" in report


def test_auto_2_smooths_exposure_ramp_without_changing_frame_count():
    images, audio = _decoded()
    images[1][22:] = 0.33
    images[1][22:26] = torch.tensor([0.27, 0.29, 0.31, 0.33]).view(4, 1, 1, 1)
    node = H3ContinuumAssembleSeamExperimental()
    common = {
        "images": images,
        "audio": audio,
        "assembly_plan": [_plan()],
        "exact_total_duration": [False],
        "audio_seam": ["Off"],
        "diagnostics": ["Off"],
    }
    native_images, native_audio, _ = node.assemble(video_seam=["Auto"], **common)
    corrected_images, corrected_audio, report = node.assemble(
        video_seam=["Auto 2"], **common
    )

    assert corrected_images.shape == native_images.shape
    assert torch.equal(corrected_images[:124], native_images[:124])
    assert torch.equal(corrected_images[128:], native_images[128:])
    corrected_means = corrected_images[124:128].mean(dim=(1, 2, 3))
    assert torch.all(corrected_means[1:] >= corrected_means[:-1])
    assert float(corrected_means[0]) < 0.27
    assert float(corrected_means[-1]) < 0.33
    assert torch.equal(corrected_audio["waveform"], native_audio["waveform"])
    assert "Video Seam: Auto 2 (Experimental)" in report
    assert "class=exposure_ramp" in report
    assert "action=normalized exposure/color on 4 exposure ramp boundary frame(s)" in report


def test_auto_1_keeps_exposure_ramp_native():
    images, audio = _decoded()
    images[1][22:] = 0.33
    images[1][22:26] = torch.tensor([0.27, 0.29, 0.31, 0.33]).view(4, 1, 1, 1)
    node = H3ContinuumAssembleSeamExperimental()
    output_images, _, report = node.assemble(
        images=images,
        audio=audio,
        assembly_plan=[_plan()],
        exact_total_duration=[False],
        audio_seam=["Off"],
        video_seam=["Auto"],
        diagnostics=["Off"],
    )

    expected = torch.tensor([0.27, 0.29, 0.31, 0.33])
    actual = output_images[124:128].mean(dim=(1, 2, 3))
    assert torch.allclose(actual, expected)
    assert "Video Seam: Auto;" in report
    assert "class=exposure_ramp" in report
    assert "action=kept native boundary" in report


def test_auto_preserves_spatial_detail_in_corrected_frame():
    images, audio = _decoded()
    detail = torch.linspace(0.15, 0.35, 8 * 8 * 3).reshape(8, 8, 3)
    images[0][-1] = detail
    images[1][21] = detail
    images[1][22] = detail + 0.2
    images[1][23] = detail
    node = H3ContinuumAssembleSeamExperimental()
    corrected_images, _corrected_audio, report = node.assemble(
        images=images,
        audio=audio,
        assembly_plan=[_plan()],
        exact_total_duration=[False],
        audio_seam=["Off"],
        video_seam=[VIDEO_SEAM_AUTO],
        diagnostics=[DIAGNOSTICS_OPTIONS[0]],
    )
    assert torch.allclose(corrected_images[124], detail, atol=1.0e-6)
    assert "action=normalized exposure/color" in report


def test_auto_preserves_clean_boundary():
    images, audio = _decoded()
    node = H3ContinuumAssembleSeamExperimental()
    common = {
        "images": images,
        "audio": audio,
        "assembly_plan": [_plan()],
        "exact_total_duration": [False],
        "audio_seam": ["Off"],
        "diagnostics": [DIAGNOSTICS_OPTIONS[0]],
    }
    off_images, off_audio, _ = node.assemble(
        video_seam=[VIDEO_SEAM_OFF],
        **common,
    )
    corrected_images, corrected_audio, report = node.assemble(
        video_seam=[VIDEO_SEAM_AUTO],
        **common,
    )
    assert torch.equal(corrected_images, off_images)
    assert torch.equal(corrected_audio["waveform"], off_audio["waveform"])
    assert "action=kept native boundary" in report


def test_experimental_seam_analyzer_is_registered_separately():
    assert (
        NODE_CLASS_MAPPINGS["H3ContinuumAssembleSeamExperimental"]
        is H3ContinuumAssembleSeamExperimental
    )
    assert NODE_CLASS_MAPPINGS["H3ContinuumAssembleV3"] is not H3ContinuumAssembleSeamExperimental


def test_experimental_seam_analyzer_is_public_in_root_registration():
    from ComfyUI_H3_Continuum_Join import nodes as root_nodes

    node_class = root_nodes.NODE_CLASS_MAPPINGS["H3ContinuumAssembleSeamExperimental"]
    assert not getattr(node_class, "DEPRECATED", False)
    assert node_class.CATEGORY == "MiniMax H3/Continuum"
    assert root_nodes.NODE_DISPLAY_NAME_MAPPINGS["H3ContinuumAssembleSeamExperimental"] == (
        "H3 Continuum Assemble + Seam"
    )
    assert root_nodes.NODE_DISPLAY_NAME_MAPPINGS["H3ContinuumAssembleV3"] == (
        "[Legacy] H3 Continuum Assemble V3.2.4"
    )
