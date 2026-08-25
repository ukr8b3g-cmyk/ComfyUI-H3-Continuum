from __future__ import annotations

from types import SimpleNamespace

import pytest
import torch

from ComfyUI_H3_Continuum_Join.v2 import h3_builder


class _Clip:
    def __init__(self):
        self.calls = 0
        self.layer_idx = None
        self.use_clip_schedule = False
        self.tokenizer_options = {}
        self.apply_hooks_to_conds = None
        self.patcher = SimpleNamespace(
            patches_uuid="patch-a",
            forced_hooks=None,
            current_hooks=None,
            hook_patches={},
        )

    def tokenize(self, prompt, **kwargs):
        return prompt, kwargs

    def encode_from_tokens_scheduled(self, _tokens):
        self.calls += 1
        return [[
            torch.tensor([[[1.0, 2.0]]]),
            {
                "pooled_output": torch.tensor([[3.0]]),
                "nested": {"items": ["original"]},
            },
        ]]


def _encode(clip, prompt="prompt", first=None, last=None, events=None):
    return h3_builder.encode_prompt_conditioning_cached(
        clip,
        prompt,
        first_image=first,
        last_image=last,
        first_image_fingerprint=h3_builder._tensor_fingerprint(first),
        last_image_fingerprint=h3_builder._tensor_fingerprint(last),
        cache_enabled=True,
        cache_event=None if events is None else events.append,
    )


def test_cache_hit_is_bit_exact_and_only_metadata_containers_are_copied():
    clip = _Clip()
    first = _encode(clip)
    second = _encode(clip)

    assert clip.calls == 1
    assert torch.equal(first[0][0], second[0][0])
    assert first[0][0] is second[0][0]
    assert first is not second
    assert first[0][1] is not second[0][1]
    assert first[0][1]["nested"] is not second[0][1]["nested"]
    assert first[0][1]["nested"]["items"] is not second[0][1]["nested"]["items"]
    second[0][1]["nested"]["items"].append("mutation")
    third = _encode(clip)
    assert third[0][1]["nested"]["items"] == ["original"]


def test_prompt_first_last_clip_patch_and_layer_changes_are_misses():
    clip = _Clip()
    first = torch.zeros((1, 4, 4, 3))
    last = torch.ones((1, 4, 4, 3))
    _encode(clip, first=first, last=last)
    _encode(clip, prompt="changed", first=first, last=last)
    _encode(clip, prompt="changed", first=first.clone().fill_(0.5), last=last)
    _encode(clip, prompt="changed", first=first.clone().fill_(0.5), last=None)
    clip.patcher.patches_uuid = "patch-b"
    _encode(clip, prompt="changed", first=first.clone().fill_(0.5), last=None)
    clip.layer_idx = -2
    _encode(clip, prompt="changed", first=first.clone().fill_(0.5), last=None)
    assert clip.calls == 6


def test_image_fingerprint_includes_shape_dtype_and_exact_content():
    base = torch.zeros((1, 4, 4, 3), dtype=torch.float32)
    changed = base.clone()
    changed[0, 0, 0, 0] = 1.0
    fingerprints = {
        h3_builder._tensor_fingerprint(base),
        h3_builder._tensor_fingerprint(base.reshape(1, 2, 8, 3)),
        h3_builder._tensor_fingerprint(base.to(torch.float64)),
        h3_builder._tensor_fingerprint(changed),
    }
    assert len(fingerprints) == 4


@pytest.mark.parametrize(
    "mutate",
    [
        lambda clip: setattr(clip, "use_clip_schedule", True),
        lambda clip: setattr(clip, "tokenizer_options", {"weight": "custom"}),
        lambda clip: setattr(clip, "apply_hooks_to_conds", object()),
        lambda clip: setattr(clip.patcher, "forced_hooks", object()),
        lambda clip: setattr(clip.patcher, "current_hooks", object()),
        lambda clip: setattr(clip.patcher, "hook_patches", {"hook": object()}),
    ],
)
def test_special_clip_modes_bypass_cache(mutate):
    clip = _Clip()
    events = []
    mutate(clip)
    _encode(clip, events=events)
    _encode(clip, events=events)
    assert clip.calls == 2
    assert events == ["bypass_special_clip", "bypass_special_clip"]


def test_lru_keeps_only_sixteen_entries_and_evicts_oldest():
    clip = _Clip()
    for index in range(17):
        _encode(clip, prompt=f"prompt-{index}")
    cache = getattr(clip, h3_builder._PROMPT_CACHE_ATTR)
    assert len(cache) == 16
    assert clip.calls == 17
    _encode(clip, prompt="prompt-0")
    assert clip.calls == 18
    assert len(cache) == 16


def test_cuda_conditioning_is_not_retained(monkeypatch):
    clip = _Clip()
    events = []
    monkeypatch.setattr(h3_builder, "_contains_cuda_tensor", lambda _value: True)
    _encode(clip, events=events)
    _encode(clip, events=events)
    assert clip.calls == 2
    assert events == ["bypass_cuda_output", "bypass_cuda_output"]
    cache = getattr(clip, h3_builder._PROMPT_CACHE_ATTR)
    assert len(cache) == 0


def test_cache_container_failure_falls_back_to_uncached_encode():
    clip = _Clip()
    events = []
    setattr(clip, h3_builder._PROMPT_CACHE_ATTR, {})
    _encode(clip, events=events)
    _encode(clip, events=events)
    assert clip.calls == 2
    assert events == ["bypass_cache_error", "bypass_cache_error"]
