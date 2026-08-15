from types import SimpleNamespace

import pytest
import torch

from ComfyUI_H3_Continuum_Join.constants import (
    CONTINUUM_INTEROP_KEY,
    MARK_AUDIO_CONTEXT,
    MARK_AUDIO_END_FRAME,
    MARK_AUDIO_OVERHANG,
    MARK_CONTEXT_FRAMES,
    MARK_VIDEO_CONTEXT,
)
from ComfyUI_H3_Continuum_Join.model_patch import (
    _wrapper_factory,
    clone_model_for_chunk,
    patch_model,
)


class Executor:
    def __init__(self):
        inner_type = type(
            "MiniMaxH3Model",
            (),
            {
                "__module__": "comfy.ldm.minimax.model",
                "blocks": (),
                "final_layer": object(),
                "patch_size": (1, 2, 2),
                "latents_dim": 24,
                "audio_latents_dim": 32,
                "rope_freqs": lambda self, position_ids, device: position_ids,
            },
        )
        self.class_obj = SimpleNamespace(diffusion_model=inner_type())

    def __call__(self, *args, **kwargs):
        return kwargs["minimax_payload"]


def _layout():
    # text 1; ref audio 2 rows; ref video 1 row; target audio 2 rows; target video 1 row
    segments = [
        (0, 1, "text"),
        (1, 3, "ref_audio"),
        (3, 4, "ref_img"),
        (4, 6, "audio"),
        (6, 7, "video"),
    ]
    pos = torch.zeros(7, 3, dtype=torch.float64)
    pos[1:3, 0] = 1
    pos[3, 0] = 1
    pos[4:6, 0] = 2
    pos[6, 0] = 2
    return SimpleNamespace(segments=segments, position_ids=pos, signature=(1, 1, 1, 1, 1))


def test_apply_model_wrapper_repairs_payload_before_executor():
    video = torch.zeros(1, 24, 1, 1, 1)
    audio = torch.zeros(1, 32, 2, 1)
    ref = {
        "kind": "video_audio",
        "latent_t": 1,
        "latent_h": 1,
        "latent_w": 1,
        "ref_audio_t": 1,
        "latent": video,
        "audio_latent": audio,
        MARK_VIDEO_CONTEXT: True,
        MARK_CONTEXT_FRAMES: 1,
        MARK_AUDIO_CONTEXT: True,
        MARK_AUDIO_END_FRAME: 1.0,
        MARK_AUDIO_OVERHANG: 0.0,
    }
    payload = {"layout": _layout(), "keyframes": [], "refs": [ref]}
    wrapper = _wrapper_factory(strict=True, debug=False)
    result = wrapper(Executor(), torch.zeros(1), minimax_payload=payload)
    assert result["cond_video_latents"] == [video]
    assert result["cond_audio_latents"] == [audio]
    assert torch.equal(result["layout"].position_ids[3:4], result["layout"].position_ids[6:7])


def test_apply_model_wrapper_repairs_keyframes_with_audio_reference_without_continuum():
    first = torch.zeros(1, 24, 1, 1, 1)
    last = torch.ones(1, 24, 1, 1, 1)
    audio = torch.zeros(1, 32, 2, 1)
    payload = {
        "keyframes": [
            {"resolved_frame_index": 0, "latent": first},
            {"resolved_frame_index": 4, "latent": last},
        ],
        "refs": [
            {"kind": "audio", "ref_audio_t": 1, "audio_latent": audio}
        ],
        # ComfyUI Core 0.33.1 overwrites this list while processing refs.
        "cond_video_latents": [],
        "cond_audio_latents": [audio],
    }
    wrapper = _wrapper_factory(strict=True, debug=False)

    result = wrapper(Executor(), torch.zeros(1), minimax_payload=payload)

    assert result["cond_video_latents"] == [first, last]
    assert result["cond_audio_latents"] == [audio]


def test_apply_model_wrapper_fails_when_actual_topology_changes():
    video = torch.zeros(1, 24, 1, 1, 1)
    audio = torch.zeros(1, 32, 2, 1)
    ref = {
        "kind": "video_audio",
        "latent_t": 1,
        "latent_h": 1,
        "latent_w": 1,
        "ref_audio_t": 1,
        "latent": video,
        "audio_latent": audio,
        MARK_VIDEO_CONTEXT: True,
        MARK_CONTEXT_FRAMES: 1,
        MARK_AUDIO_CONTEXT: True,
        MARK_AUDIO_END_FRAME: 1.0,
        MARK_AUDIO_OVERHANG: 0.0,
    }
    payload = {"layout": _layout(), "keyframes": [], "refs": [ref]}
    wrapper = _wrapper_factory(strict=True, debug=False)
    options = {
        "spectrum_h3_actual": True,
        "cond_or_uncond": [0],
        "uuids": ["positive"],
    }
    wrapper(Executor(), torch.zeros(1), transformer_options=options, minimax_payload=payload)
    payload["layout"].position_ids[-1, 1] = 1.0
    with pytest.raises(RuntimeError, match="topology changed"):
        wrapper(Executor(), torch.zeros(1), transformer_options=options, minimax_payload=payload)


class FakeModelPatcher:
    def __init__(self):
        inner_type = type(
            "MiniMaxH3Model",
            (),
            {
                "__module__": "comfy.ldm.minimax.model",
                "blocks": (),
                "final_layer": object(),
                "patch_size": (1, 2, 2),
                "latents_dim": 24,
                "audio_latents_dim": 32,
                "rope_freqs": lambda self, position_ids, device: position_ids,
            },
        )
        self.model = SimpleNamespace(diffusion_model=inner_type())
        self.model_options = {}
        self.added = []
        self.removed = []

    def clone(self):
        clone = FakeModelPatcher()
        clone.model = self.model
        clone.model_options = {k: dict(v) if isinstance(v, dict) else v for k, v in self.model_options.items()}
        return clone

    def add_wrapper_with_key(self, wrapper_type, key, wrapper):
        self.added.append((wrapper_type, key, wrapper))

    def remove_wrappers_with_key(self, wrapper_type, key):
        self.removed.append((wrapper_type, key))


def test_patch_model_validates_and_installs_per_model_wrapper(monkeypatch):
    import sys
    from types import ModuleType

    extension = ModuleType("comfy.patcher_extension")
    extension.WrappersMP = SimpleNamespace(APPLY_MODEL="apply_model")
    comfy = sys.modules.get("comfy") or ModuleType("comfy")
    monkeypatch.setitem(sys.modules, "comfy", comfy)
    monkeypatch.setitem(sys.modules, "comfy.patcher_extension", extension)

    patched = patch_model(FakeModelPatcher(), strict=True, debug=False)
    assert patched.removed[0][1] == "h3_continuum_join.apply_model.v1"
    assert patched.added[0][1] == "h3_continuum_join.apply_model.v1"
    assert patched.model_options["h3_continuum_join"]["api_version"] == 1


def test_chunk_model_copy_on_write_and_context_scoped_hint(monkeypatch):
    import sys
    from types import ModuleType

    extension = ModuleType("comfy.patcher_extension")
    extension.WrappersMP = SimpleNamespace(APPLY_MODEL="apply_model")
    comfy = sys.modules.get("comfy") or ModuleType("comfy")
    monkeypatch.setitem(sys.modules, "comfy", comfy)
    monkeypatch.setitem(sys.modules, "comfy.patcher_extension", extension)

    source = FakeModelPatcher()
    clone_calls = 0
    original_clone = FakeModelPatcher.clone

    def counted_clone(self):
        nonlocal clone_calls
        clone_calls += 1
        return original_clone(self)

    monkeypatch.setattr(FakeModelPatcher, "clone", counted_clone)
    source.model_options = {"transformer_options": {"existing": "kept"}}
    first = clone_model_for_chunk(source, strict=True, debug=False, chunk_index=1, context_frames=None)
    second = clone_model_for_chunk(source, strict=True, debug=False, chunk_index=2, context_frames=22)
    third = clone_model_for_chunk(source, strict=True, debug=False, chunk_index=3, context_frames=22)

    assert clone_calls == 3
    assert source.model_options == {"transformer_options": {"existing": "kept"}}
    assert CONTINUUM_INTEROP_KEY not in first.model_options["transformer_options"]
    request = second.model_options["transformer_options"][CONTINUUM_INTEROP_KEY]
    assert request == {
        "api": 1,
        "active": True,
        "min_actual_prefix_steps": 2,
        "chunk_index": 2,
        "context_frames": 22,
    }
    assert request is not third.model_options["transformer_options"][CONTINUUM_INTEROP_KEY]
    assert CONTINUUM_INTEROP_KEY not in source.model_options["transformer_options"]
