import torch

from ComfyUI_H3_Continuum_Join import state_io
from ComfyUI_H3_Continuum_Join.constants import STATE_MAGIC


def test_state_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(state_io, "state_directory", lambda: tmp_path)
    state = {
        "magic": STATE_MAGIC,
        "schema_version": 1,
        "clip_index": 2,
        "source_frame_count": 141,
        "capacity_frames": 39,
        "width": 96,
        "height": 64,
        "video_tail": torch.randn(1, 24, 12, 4, 6),
        "audio_tail": torch.randn(1, 32, 2, 65),
        "audio_overhang": 0.0,
        "source_mode": "latent_direct",
    }
    tensor_path, json_path = state_io.save_state(state, prefix="test state", slot=3)
    assert tensor_path.exists() and json_path.exists()
    loaded = state_io.load_state(prefix="test state", slot=3)
    assert torch.equal(loaded["video_tail"], state["video_tail"])
    assert torch.equal(loaded["audio_tail"], state["audio_tail"])
    assert loaded["clip_index"] == 2


def test_state_loads_when_json_mirror_is_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(state_io, "state_directory", lambda: tmp_path)
    state = {
        "magic": STATE_MAGIC,
        "schema_version": 1,
        "clip_index": 1,
        "source_frame_count": 124,
        "capacity_frames": 39,
        "width": 96,
        "height": 64,
        "video_tail": torch.randn(1, 24, 12, 4, 6),
        "audio_tail": torch.randn(1, 32, 2, 65),
        "audio_overhang": 1.0 / 3.0,
        "source_mode": "latent_direct",
    }
    _tensor_path, json_path = state_io.save_state(state, prefix="atomic", slot=1)
    json_path.unlink()
    loaded = state_io.load_state(prefix="atomic", slot=1)
    assert torch.equal(loaded["video_tail"], state["video_tail"])
    assert loaded["clip_index"] == 1
