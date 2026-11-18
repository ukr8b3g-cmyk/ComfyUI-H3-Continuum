import torch
import json
import pytest
from safetensors.torch import save_file

from ComfyUI_H3_Continuum_Join import state_io
from ComfyUI_H3_Continuum_Join.constants import STATE_MAGIC


@pytest.fixture
def metadata_state(tmp_path, monkeypatch):
    monkeypatch.setattr(state_io, "state_directory", lambda: tmp_path)
    state = {"magic": STATE_MAGIC, "schema_version": 1, "clip_index": 2,
             "source_frame_count": 141, "capacity_frames": 39, "width": 96, "height": 64,
             "video_tail": torch.ones(1, 24, 12, 4, 6),
             "audio_tail": torch.ones(1, 32, 2, 65),
             "audio_overhang": 0.0, "source_mode": "latent_direct"}
    tensor_path, json_path = state_io.save_state(state, prefix="metadata", slot=1)
    metadata = json.loads(json_path.read_text(encoding="utf-8"))
    # Same shapes, different clip identity: stale metadata would pass validation.
    json_path.write_text(json.dumps({**metadata, "clip_index": 1, "_state_id": "stale"}), encoding="utf-8")
    return state, metadata, tensor_path, json_path


@pytest.mark.parametrize("serialized", ["{broken", "", "null"])
def test_corrupt_embedded_metadata_never_uses_valid_stale_sidecar(metadata_state, serialized):
    state, _, tensor_path, _ = metadata_state
    tensors = {k: state[k] for k in ("video_tail", "audio_tail")}
    save_file(tensors, str(tensor_path), metadata={state_io._HEADER_KEY: serialized})
    with pytest.raises((ValueError, TypeError)):
        state_io.load_state(prefix="metadata", slot=1)


def test_valid_embedded_metadata_wins_over_stale_sidecar(metadata_state):
    state, _, tensor_path, json_path = metadata_state
    before = (tensor_path.read_bytes(), json_path.read_bytes())
    loaded = state_io.load_state(prefix="metadata", slot=1)
    assert loaded["clip_index"] == 2
    assert torch.equal(loaded["video_tail"], state["video_tail"])
    assert (tensor_path.read_bytes(), json_path.read_bytes()) == before


@pytest.mark.parametrize("sidecar", ["[]", "null", '"old"', "4", "false"])
def test_non_object_mirror_does_not_block_valid_state(metadata_state, caplog, sidecar):
    state, _, tensor_path, json_path = metadata_state
    json_path.write_text(sidecar, encoding="utf-8")
    before = (tensor_path.read_bytes(), json_path.read_bytes())
    loaded = state_io.load_state(prefix="metadata", slot=1)
    assert loaded["clip_index"] == state["clip_index"]
    for key in ("video_tail", "audio_tail"):
        assert torch.equal(loaded[key], state[key])
    assert "Ignoring unreadable" in caplog.text
    assert (tensor_path.read_bytes(), json_path.read_bytes()) == before


def test_legacy_state_still_requires_usable_sidecar(metadata_state):
    state, _, tensor_path, json_path = metadata_state
    save_file({k: state[k] for k in ("video_tail", "audio_tail")}, str(tensor_path))
    json_path.write_text("null", encoding="utf-8")
    with pytest.raises((TypeError, ValueError)):
        state_io.load_state(prefix="metadata", slot=1)


@pytest.mark.parametrize("sidecar_exists", [True, False])
def test_only_missing_embedded_metadata_can_use_legacy_sidecar(metadata_state, sidecar_exists):
    state, _, tensor_path, json_path = metadata_state
    save_file({k: state[k] for k in ("video_tail", "audio_tail")}, str(tensor_path))
    if sidecar_exists:
        loaded = state_io.load_state(prefix="metadata", slot=1)
        assert loaded["clip_index"] == 1
        assert torch.equal(loaded["audio_tail"], state["audio_tail"])
    else:
        json_path.unlink()
        with pytest.raises(ValueError, match="no embedded"):
            state_io.load_state(prefix="metadata", slot=1)


def test_invalid_embedded_schema_is_not_repaired_from_sidecar(metadata_state):
    state, metadata, tensor_path, _ = metadata_state
    save_file({k: state[k] for k in ("video_tail", "audio_tail")}, str(tensor_path),
              metadata={state_io._HEADER_KEY: json.dumps({**metadata, "schema_version": 999})})
    with pytest.raises(ValueError, match="unsupported state schema"):
        state_io.load_state(prefix="metadata", slot=1)


def test_missing_tensor_is_not_repaired_from_sidecar(metadata_state):
    state, metadata, tensor_path, _ = metadata_state
    save_file({"audio_tail": state["audio_tail"]}, str(tensor_path),
              metadata={state_io._HEADER_KEY: json.dumps(metadata)})
    with pytest.raises(Exception, match="video_tail"):
        state_io.load_state(prefix="metadata", slot=1)


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
