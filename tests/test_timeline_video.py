from __future__ import annotations

import io
from types import SimpleNamespace

import torch

from ComfyUI_H3_Continuum_Join.timeline_video import (
    TIMELINE_VIDEO_SIZE_BALANCED,
    TIMELINE_VIDEO_SIZE_EFFICIENT,
    TIMELINE_VIDEO_SIZE_MATCH_OUTPUT,
    combine_timeline_video_identity,
    encode_timeline_video_chunk,
    prepare_timeline_video_source,
    validate_timeline_video_prompts,
)
from ComfyUI_H3_Continuum_Join.v3.nodes import (
    H3ContinuumSamplerProduction,
    H3ContinuumSamplerTimelineVideo,
)


class _Trimmed:
    def __init__(self, frames):
        self.frames = frames

    def get_components(self):
        return SimpleNamespace(images=self.frames, audio=None, frame_rate=24.0)


class _Video:
    def __init__(self, frames, duration=10.0, width=32, height=32):
        self.frames = frames
        self.duration = duration
        self.width = width
        self.height = height
        self.calls = []
        self.stream = io.BytesIO(b"timeline-video-test")

    def get_duration(self):
        return self.duration

    def get_dimensions(self):
        return self.width, self.height

    def get_stream_source(self):
        return self.stream

    def as_trimmed(self, start_time=0, duration=0, strict_duration=True):
        self.calls.append((start_time, duration, strict_duration))
        return _Trimmed(self.frames)


class _VAE:
    def __init__(self):
        self.calls = []

    def encode(self, frames):
        self.calls.append(frames)
        return torch.zeros((1, 24, 8, 2, 2))


def _source(size_mode=TIMELINE_VIDEO_SIZE_MATCH_OUTPUT):
    video = _Video(torch.zeros((120, 32, 32, 3)))
    source = prepare_timeline_video_source(
        video,
        chunks=2,
        chunk_seconds=5.0,
        output_width=32,
        output_height=32,
        size_mode=size_mode,
    )
    return video, source


def test_v33_unifies_optional_timeline_video_and_keeps_v324_schema():
    legacy = H3ContinuumSamplerProduction.INPUT_TYPES()
    unified = H3ContinuumSamplerTimelineVideo.INPUT_TYPES()
    assert "timeline_video" not in legacy["required"]
    assert "timeline_video_size" not in legacy["required"]
    assert "timeline_video" not in unified["required"]
    assert unified["optional"]["timeline_video"][0] == "VIDEO"

    from ComfyUI_H3_Continuum_Join import nodes as root_nodes

    assert root_nodes.NODE_DISPLAY_NAME_MAPPINGS["H3ContinuumSamplerTimelineVideo"] == (
        "H3 Continuum Sampler V3.3"
    )
    assert root_nodes.NODE_DISPLAY_NAME_MAPPINGS["H3ContinuumSamplerProduction"] == (
        "[Legacy] H3 Continuum Sampler V3.2.4"
    )


def test_timeline_node_without_video_delegates_to_stable_engine(monkeypatch):
    calls = []

    def fake_run(self, **kwargs):
        calls.append(kwargs)
        return "stable"

    monkeypatch.setattr(H3ContinuumSamplerProduction, "run", fake_run)
    result = H3ContinuumSamplerTimelineVideo().run(
        timeline_video=None,
        timeline_video_size="Efficient - 0.4 MP",
        marker="no-video",
    )

    assert result == "stable"
    assert calls == [{"marker": "no-video"}]


def test_timeline_node_with_video_prepares_source(monkeypatch):
    video = object()
    source = object()
    prepared = []
    delegated = []

    def fake_prepare(value, **kwargs):
        prepared.append((value, kwargs))
        return source

    def fake_run(self, **kwargs):
        delegated.append(kwargs)
        return "timeline"

    monkeypatch.setattr(
        "ComfyUI_H3_Continuum_Join.timeline_video.prepare_timeline_video_source",
        fake_prepare,
    )
    monkeypatch.setattr(H3ContinuumSamplerProduction, "run", fake_run)
    result = H3ContinuumSamplerTimelineVideo().run(
        timeline_video=video,
        timeline_video_size="Efficient - 0.4 MP",
        chunks=2,
        chunk_seconds=5.0,
        width=800,
        height=800,
    )

    assert result == "timeline"
    assert prepared == [
        (
            video,
            {
                "chunks": 2,
                "chunk_seconds": 5.0,
                "output_width": 800,
                "output_height": 800,
                "size_mode": "Efficient - 0.4 MP",
            },
        )
    ]
    assert delegated == [
        {
            "timeline_video_source": source,
            "chunks": 2,
            "chunk_seconds": 5.0,
            "width": 800,
            "height": 800,
        }
    ]


def test_timeline_contract_is_deterministic_and_chunked():
    _, first = _source()
    _, second = _source()
    assert first.contract == second.contract
    assert len(first.contract["chunk_slices"]) == 2
    assert first.contract["chunk_slices"][1]["start_seconds"] == 5.0


def test_efficient_mode_resolves_about_point_four_megapixels():
    video = _Video(torch.zeros((120, 1080, 1920, 3)), width=1920, height=1080)
    source = prepare_timeline_video_source(
        video,
        chunks=1,
        chunk_seconds=5.0,
        output_width=1344,
        output_height=768,
        size_mode=TIMELINE_VIDEO_SIZE_EFFICIENT,
    )
    assert 350_000 <= source.target_width * source.target_height <= 450_000


def test_balanced_mode_resolves_about_point_six_megapixels():
    video = _Video(torch.zeros((120, 1080, 1920, 3)), width=1920, height=1080)
    source = prepare_timeline_video_source(
        video,
        chunks=1,
        chunk_seconds=5.0,
        output_width=1344,
        output_height=768,
        size_mode=TIMELINE_VIDEO_SIZE_BALANCED,
    )
    assert 550_000 <= source.target_width * source.target_height <= 650_000


def test_encode_processes_only_requested_chunk_and_builds_core_payload():
    video, source = _source()
    vae = _VAE()
    assets = encode_timeline_video_chunk(vae, source, 1)
    assert video.calls == [(5.0, 5.0, False)]
    assert len(vae.calls) == 1
    assert int(vae.calls[0].shape[0]) % 17 == 5
    assert assets.item["type"] == "video"
    assert assets.block["kind"] == "video"
    assert assets.block["ref_audio_t"] == 0


def test_timeline_identity_is_noop_when_absent_and_changes_when_present():
    _, source = _source()
    assert combine_timeline_video_identity("visual", None) == "visual"
    assert combine_timeline_video_identity("visual", source) != "visual"


def test_missing_video_tag_warns_without_stopping():
    _, source = _source()
    assert "H3C-P103" in validate_timeline_video_prompts(["A dancer moves."], source)
    assert validate_timeline_video_prompts(["Follow <Video 1>."], source) == ""
