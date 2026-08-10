from types import SimpleNamespace

import torch

from ComfyUI_H3_Continuum_Join.constants import (
    MARK_AUDIO_CONTEXT,
    MARK_AUDIO_END_FRAME,
    MARK_AUDIO_OVERHANG,
    MARK_CONTEXT_FRAMES,
    MARK_VIDEO_CONTEXT,
)
from ComfyUI_H3_Continuum_Join.model_patch import _wrapper_factory, patch_model


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
