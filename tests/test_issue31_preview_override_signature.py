"""Phase A: real audited KJ wrapper, CPU-only observation and Run Storage gates."""
from __future__ import annotations

import hashlib
import importlib
import json
import os
import sys
import types
from pathlib import Path

import pytest
import torch
from PIL import Image

from ComfyUI_H3_Continuum_Join import preview_override_signature as adapter
from ComfyUI_H3_Continuum_Join import run_storage as storage
from . import test_v31_run_storage as signatures
from . import test_v38_review_run_storage as review
from . import test_issue31_attention_signature as attention
from .test_issue31_attention_signature import core_attention
from .test_issue31_spectrum_signature import spectrum, binding


@pytest.fixture(params=["local", "public", "legacy"])
def kj(require_comfy_core, request):
    root = os.environ.get({"local": "H3_KJ_PREVIEW_TEST_ROOT",
                           "public": "H3_KJ_PREVIEW_PUBLIC_TEST_ROOT",
                           "legacy": "H3_KJ_PREVIEW_LEGACY_TEST_ROOT"}[request.param])
    if not root:
        pytest.skip("real audited KJ Preview Override provider is not configured")
    package = types.ModuleType("issue31_kj_preview_tests_" + request.param)
    package.__path__ = [str(Path(root) / "nodes")]
    sys.modules[package.__name__] = package
    provider = importlib.import_module(package.__name__ + ".preview_override_node")
    # Positive-profile fixtures also run on the old Core. Only the audio-scale
    # provider is admitted for the new Core preview implementation.
    core = Path(provider.latent_preview.__file__).read_bytes().replace(b"\r\n", b"\n")
    source = Path(provider.__file__).read_bytes().replace(b"\r\n", b"\n")
    older_sources = {adapter._PROFILE["source_sha256"], adapter._PUBLIC_PROFILE["source_sha256"]}
    if (hashlib.sha256(core).hexdigest() == "572f6224fb912d5df9583497356f4fb2b3af56a7949e87fe431912c59f12cb39"
            and hashlib.sha256(source).hexdigest() in older_sources):
        descriptor, safe = adapter.preview_override_signature(wrapper(provider))
        assert not safe and descriptor["unsupported"] == "provider source is outside the audited profile"
        pytest.skip("Legacy KJ provider is correctly refused on this Core")
    return provider


def wrapper(kj, **settings):
    values = dict(max_resolution=512, node_id="100", jpeg_quality=90,
                  suppress_default=True, preview_frames=1, preview_fps=12)
    values.update(settings)
    return kj._PreviewOverrideWrapper(**values)


def model_with(item):
    model = signatures._Model()
    model.wrappers = {"outer_sample": {"kj_preview_override": [item]}}
    return model


def observe(model):
    return storage._model_signature(model, "fixture")


def test_no_kj_observer_and_full_sampling_contract_are_exact(monkeypatch):
    model = signatures._Model()
    model.wrappers = {"outer_sample": {"other": [lambda executor: executor()]}}
    current = observe(model)
    torch.manual_seed(31016)
    clip, vae = signatures._Clip(), signatures._VideoVAE()
    contract = signatures._sampling_contract(model=model, clip=clip, video_vae=vae, reroll_from_chunk=0)
    with monkeypatch.context() as ctx:
        ctx.setattr(storage, "observe_model_wrappers", lambda value, observer: observer(value))
        assert observe(model) == current
        old = signatures._sampling_contract(model=model, clip=clip, video_vae=vae, reroll_from_chunk=0)
    assert storage._canonical(contract) == storage._canonical(old)
    assert storage.revision_identity(contract[0]) == storage.revision_identity(old[0])


def test_real_provider_frames_and_recreated_wrapper_keep_contract(kj):
    item = wrapper(kj)
    model = model_with(item)
    before = observe(model)
    assert before[1], before[0]
    clip, vae = signatures._Clip(), signatures._VideoVAE()
    original = signatures._sampling_contract(model=model, clip=clip, video_vae=vae, reroll_from_chunk=0)
    assert original[1]
    for count in (1, 3, 0):
        item.frames[:] = [Image.new("RGB", (2, 2)) for _ in range(count)]
        frames = item.frames
        state = dict(vars(item))
        assert observe(model) == before
        current = signatures._sampling_contract(model=model, clip=clip, video_vae=vae, reroll_from_chunk=0)
        assert current == original
        assert vars(item) == state and item.frames is frames
    model.wrappers["outer_sample"]["kj_preview_override"] = [wrapper(kj)]
    assert observe(model) == before


@pytest.mark.parametrize("setting,value", [("max_resolution", 768), ("node_id", "101"),
    ("jpeg_quality", 80), ("suppress_default", False), ("preview_frames", 4), ("preview_fps", 24)])
def test_every_fixed_setting_changes_identity(kj, setting, value):
    item = wrapper(kj)
    before, safe = adapter.preview_override_signature(item)
    assert safe, before
    setattr(item, setting, value)
    after, safe = adapter.preview_override_signature(item)
    assert safe and after != before


def test_full_audit_profile_is_part_of_identity(kj, monkeypatch):
    item = wrapper(kj)
    before, safe = adapter.preview_override_signature(item)
    assert safe
    # An audit revision must change identity even with the same display ID and
    # wrapper source, so dependency-profile upgrades cannot reuse old Takes.
    profile, _ = adapter._provider_source(kj.__file__)
    monkeypatch.setitem(profile, "audit_revision", 2)
    after, safe = adapter.preview_override_signature(item)
    assert safe and before["profile"] == after["profile"]
    assert before["profile_sha256"] != after["profile_sha256"]


def other_wrapper(executor, *args, **kwargs):
    return executor(*args, **kwargs)


def test_key_and_list_execution_order_change_identity(kj):
    a, b = wrapper(kj), wrapper(kj, jpeg_quality=80)
    model = model_with(a)
    model.wrappers["outer_sample"] = {"other": [other_wrapper], "kj_preview_override": [a, b]}
    before, safe = observe(model)
    assert safe
    model.wrappers["outer_sample"] = {"kj_preview_override": [a, b], "other": [other_wrapper]}
    after, safe = observe(model)
    assert safe and after != before
    model.wrappers["outer_sample"]["kj_preview_override"] = [b, a]
    reordered, safe = observe(model)
    assert safe and reordered != after


@pytest.mark.parametrize("change", ["source", "call_code", "helper_code", "defaults", "class_attribute",
    "instance_attribute", "frames_tuple", "frames_subclass", "vae", "audio_vae", "tiny_vae",
    "foreign", "subclass", "invalid_setting", "core_factory", "imported_helper_code",
    "core_preview_code", "dispatcher_code", "core_tiny_vae"])
def test_unknown_implementations_and_out_of_scope_state_reject_reuse(kj, monkeypatch, change):
    item = wrapper(kj)
    if change == "source":
        profile, _ = adapter._provider_source(kj.__file__)
        monkeypatch.setitem(profile, "source_sha256", "f" * 64)
    elif change in ("call_code", "helper_code"):
        fn = type(item).__call__ if change == "call_code" else kj._normalize_packed_x0
        monkeypatch.setattr(fn, "__code__", fn.__code__.replace(co_consts=fn.__code__.co_consts + ("changed",)))
    elif change == "defaults":
        monkeypatch.setattr(type(item).__init__, "__defaults__", (2, 12, None, "none", None))
    elif change == "class_attribute":
        monkeypatch.setattr(type(item), "unrecognized", True, raising=False)
    elif change == "instance_attribute":
        item.unrecognized = True
    elif change == "frames_tuple":
        item.frames = ()
    elif change == "frames_subclass":
        class Frames(list):
            pass
        item.frames = Frames()
    elif change in ("vae", "audio_vae"):
        setattr(item, change, object())
    elif change == "tiny_vae":
        item.tiny_vae = "taeh3"
    elif change == "foreign":
        item = types.SimpleNamespace(**vars(item))
    elif change == "subclass":
        class Extra(type(item)):
            pass
        item = Extra(512, "100", 90, True)
    elif change == "invalid_setting":
        item.preview_frames = True
    elif change == "core_factory":
        monkeypatch.setattr(kj.latent_preview, "get_previewer", lambda *a: None)
    elif change == "core_tiny_vae":
        import latent_preview
        monkeypatch.setattr(latent_preview.args, "preview_method", latent_preview.LatentPreviewMethod.TAESD)
    else:
        if change == "imported_helper_code":
            fn = kj.load_tiny_vae_decoder
        elif change == "core_preview_code":
            fn = kj.latent_preview.Latent2RGBPreviewer.decode_latent_to_preview
        else:
            fn = sys.modules["comfy.patcher_extension"].get_all_wrappers
        monkeypatch.setattr(fn, "__code__", fn.__code__.replace(co_consts=fn.__code__.co_consts + ("changed",)))
    assert not observe(model_with(item))[1]


def test_unknown_other_wrapper_is_not_promoted(kj):
    model = model_with(wrapper(kj))
    model.wrappers["outer_sample"]["unknown"] = [torch.nn.Linear(2, 2)]
    assert not observe(model)[1]


@pytest.mark.parametrize("items", [None, (), [], object()])
def test_unknown_target_container_is_not_promoted(items):
    assert not adapter.observe_model_wrappers({"outer_sample": {"kj_preview_override": items}}, storage._observe)[1]


@pytest.mark.parametrize("container", ["root", "outer", "items"])
def test_observation_limit_rejects_reuse_without_interrupting_generation(container):
    wrappers = {"outer_sample": {"kj_preview_override": [object()]}}
    if container == "items":
        wrappers["outer_sample"]["kj_preview_override"] *= 4097
    else:
        target = wrappers if container == "root" else wrappers["outer_sample"]
        target.update({str(i): [] for i in range(4097)})
    result, safe = adapter.observe_model_wrappers(wrappers, storage._observe)
    assert not safe and result["unsupported"]


def test_observation_never_executes_provider_or_initializes_cuda(kj, monkeypatch):
    item = wrapper(kj)
    # Even frame objects whose representation or data cannot be inspected are
    # ignored. The exact builtin list is the only permitted transient container.
    class UnreadableFrame:
        def __repr__(self):
            raise AssertionError("frame inspected")
    item.frames.append(UnreadableFrame())
    def forbidden(*args, **kwargs):
        raise AssertionError("signature tried to execute GPU/preview code")
    monkeypatch.setattr(torch.cuda, "_lazy_init", forbidden)
    # Trace calls instead of patching the audited callable (which must reject).
    called = []
    watched = {kj._PreviewOverrideWrapper.__call__.__code__, kj._get_core_previewer.__code__,
               kj._frame_to_pil.__code__, kj.load_tiny_vae_decoder.__code__}
    def trace(frame, event, arg):
        if event == "call" and frame.f_code in watched:
            called.append(frame.f_code.co_name)
        return trace
    previous = sys.gettrace()
    try:
        sys.settrace(trace)
        result, safe = observe(model_with(item))
    finally:
        sys.settrace(previous)
    assert safe, result
    assert called == [] and not torch.cuda.is_initialized()


@pytest.mark.parametrize("backend", ["pytorch", "comfy_kitchen_int8"])
def test_attention_and_spectrum_combination_is_stable(kj, core_attention, spectrum, backend):
    model = attention.model_with(core_attention, backend)
    model.model_options["spectrum_h3_binding"] = binding(spectrum)
    base, safe = observe(model)
    assert safe
    item = wrapper(kj)
    model.wrappers = {"outer_sample": {"kj_preview_override": [item]}}
    before, safe = observe(model)
    assert safe
    assert before["model_options"] == base["model_options"]
    item.frames.append(Image.new("RGB", (2, 2)))
    assert observe(model) == (before, safe)


def test_saved_prefix_is_reusable_after_preview_only_change(kj, tmp_path):
    item = wrapper(kj)
    model = model_with(item)
    clip, vae = signatures._Clip(), signatures._VideoVAE()
    contract, safe, _ = signatures._sampling_contract(model=model, clip=clip, video_vae=vae, reroll_from_chunk=0)
    assert safe
    saved = signatures._persist_contract_prefix(tmp_path, contract, count=1)
    before = {str(p): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    item.frames.append(Image.new("RGB", (2, 2)))
    current, safe, _ = signatures._sampling_contract(model=model, clip=clip, video_vae=vae, reroll_from_chunk=0)
    assert safe and storage.revision_identity(current) == storage.revision_identity(contract)
    _, entries, records = signatures._load_compatible_prefix(tmp_path, saved, current)
    assert len(entries) == len(records) == 1
    assert before == {str(p): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}


@pytest.mark.parametrize("entry_point", ["review", "head", "import", "compatible", "take"])
def test_old_unsafe_preview_history_is_never_promoted(kj, tmp_path, monkeypatch, entry_point):
    item = wrapper(kj)
    item.frames.append(Image.new("RGB", (2, 2)))
    model = model_with(item)
    with monkeypatch.context() as ctx:
        ctx.setattr(storage, "observe_model_wrappers", lambda value, observer: observer(value))
        old, safe, reasons = signatures._sampling_contract(model=model, reroll_from_chunk=0)
    assert not safe
    source = review._persist(tmp_path, old, prefix=1, review_unit=(1, 1), updated_utc="2026-10-16T00:00:00+00:00")
    source.manifest["resume_safe"] = False
    source.manifest["resume_disabled_reasons"] = reasons
    source._write_manifest()
    before = {str(p): p.read_bytes() for p in source.run_root.rglob("*") if p.is_file()}
    reader = review._controller(tmp_path, old)
    reader.configure_review(generation_mode=review.GENERATION_MODE_REVIEW, review_action=review.REVIEW_ACTION_CONTINUE)
    assert not storage._reusable_manifest(source.manifest)
    if entry_point == "review": assert not reader._load_validated_review_prefix(old, resume_safe=True).entries
    elif entry_point == "head": assert reader.find_latest_review_head(old, resume_safe=True) is None
    elif entry_point == "import": assert reader._find_plan_import(old, resume_safe=True) is None
    elif entry_point == "compatible": assert reader._compatible_plan_prefix(source.manifest, old, resume_safe=True) == ([], [])
    else:
        reader.take_group = 1
        reader.take_revision_id = review._project(source)["canonical_head_revision_id"]
        with pytest.raises(storage.RunStorageError, match="read-only"):
            reader._validated_take_selection(old, resume_safe=True)
    assert before == {str(p): p.read_bytes() for p in source.run_root.rglob("*") if p.is_file()}


def test_other_profile_registration_does_not_change_identity(kj, monkeypatch):
    item = wrapper(kj)
    before, safe = adapter.preview_override_signature(item)
    assert safe
    active, _ = adapter._provider_source(kj.__file__)
    monkeypatch.setattr(adapter, "_PROFILES", (active,))
    assert adapter.preview_override_signature(item) == (before, True)
    monkeypatch.setattr(adapter, "_PROFILES", (active, dict(active, source_sha256="e" * 64)))
    assert adapter.preview_override_signature(item) == (before, True)
    monkeypatch.setattr(adapter, "_PROFILES", (active, active))
    assert not adapter.preview_override_signature(item)[1]


@pytest.mark.parametrize("contents", [None, "invalid json", "null", "[]", "{}"])
def test_missing_or_malformed_optional_profile_does_not_break_existing_paths(tmp_path, contents):
    path = tmp_path / "public.json"
    if contents is not None:
        path.write_text(contents, encoding="utf-8")
    assert adapter._load_public_profile(path) is None
    model = signatures._Model()
    assert observe(model)[1]


@pytest.mark.parametrize("field", ["id", "source_sha256"])
def test_optional_profile_collision_cannot_disable_original_profile(kj, tmp_path, monkeypatch, field):
    active, _ = adapter._provider_source(kj.__file__)
    candidate = dict(adapter._PUBLIC_PROFILE)
    candidate[field] = adapter._PROFILE[field]
    path = tmp_path / "public.json"
    path.write_text(json.dumps(candidate), encoding="utf-8")
    loaded = adapter._load_public_profile(path)
    assert loaded is None
    monkeypatch.setattr(adapter, "_PROFILES", (adapter._PROFILE,))
    item = wrapper(kj)
    expected = active["id"] == adapter._PROFILE["id"]
    assert adapter.preview_override_signature(item)[1] is expected
    assert observe(signatures._Model())[1]
