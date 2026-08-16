import torch

from ComfyUI_H3_Continuum_Join.constants import DIAGNOSTICS_OPTIONS
from ComfyUI_H3_Continuum_Join.v3.assembly import (
    H3ContinuumAssembleSeamExperimental,
    VIDEO_SEAM_ANALYZE,
    VIDEO_SEAM_AUTO,
    VIDEO_SEAM_AUTO_2,
)
from ComfyUI_H3_Continuum_Join.v3.nodes import NODE_CLASS_MAPPINGS
from ComfyUI_H3_Continuum_Join.v3.seam_test_source import (
    H3ContinuumSeamTestSource,
    TEST_SIZE_256,
)
from ComfyUI_H3_Continuum_Join.v3.video_seam import analyze_decoded_boundaries


def _source_outputs():
    image = torch.full((1, 256, 256, 3), 0.5, dtype=torch.float32)
    return H3ContinuumSeamTestSource().create(
        image,
        exposure_change=0.08,
        test_resolution=TEST_SIZE_256,
    )


def test_seam_test_source_is_registered():
    assert NODE_CLASS_MAPPINGS["H3ContinuumSeamTestSource"] is H3ContinuumSeamTestSource


def test_seam_test_source_is_public_in_root_registration():
    from ComfyUI_H3_Continuum_Join import nodes as root_nodes

    node_class = root_nodes.NODE_CLASS_MAPPINGS["H3ContinuumSeamTestSource"]
    assert not getattr(node_class, "DEPRECATED", False)
    assert node_class.CATEGORY == "MiniMax H3/Continuum/Testing"
    assert root_nodes.NODE_DISPLAY_NAME_MAPPINGS["H3ContinuumSeamTestSource"] == (
        "H3 Continuum Seam Test Source (Experimental)"
    )


def test_seam_test_source_emits_realistic_three_chunk_contract():
    images, audio, plan, instructions = _source_outputs()
    assert [tuple(item.shape) for item in images] == [
        (124, 256, 256, 3),
        (141, 256, 256, 3),
        (141, 256, 256, 3),
    ]
    assert len(audio) == 3
    assert plan["target_frames"] == 360
    assert [item["trim_frames"] for item in plan["chunks"]] == [0, 22, 22]
    assert "Analyze Only" in instructions
    assert "Auto 2" in instructions


def test_controlled_boundaries_are_classified_as_exposure_ramps():
    images, _audio, plan, _instructions = _source_outputs()
    analyses = analyze_decoded_boundaries(images=images, assembly_plan=plan)
    assert len(analyses) == 2
    assert all(item.exposure_ramp_candidate for item in analyses)
    assert [item.classification for item in analyses] == [
        "exposure_ramp",
        "exposure_ramp",
    ]


def test_auto_two_corrects_only_the_controlled_ramp_frames():
    images, audio, plan, _instructions = _source_outputs()
    node = H3ContinuumAssembleSeamExperimental()
    common = {
        "images": images,
        "audio": audio,
        "assembly_plan": [plan],
        "exact_total_duration": [False],
        "audio_seam": ["Off"],
        "diagnostics": [DIAGNOSTICS_OPTIONS[0]],
    }
    analyzed_images, _analyzed_audio, analyzed_report = node.assemble(
        video_seam=[VIDEO_SEAM_ANALYZE],
        **common,
    )
    auto_images, _auto_audio, auto_report = node.assemble(
        video_seam=[VIDEO_SEAM_AUTO],
        **common,
    )
    auto_two_images, _auto_two_audio, auto_two_report = node.assemble(
        video_seam=[VIDEO_SEAM_AUTO_2],
        **common,
    )
    assert torch.equal(auto_images, analyzed_images)
    assert "class=exposure_ramp" in analyzed_report
    assert "action=kept native boundary" in auto_report
    assert not torch.equal(auto_two_images, analyzed_images)
    assert auto_two_report.count(
        "normalized exposure/color on 4 exposure ramp boundary frame(s)"
    ) == 2
