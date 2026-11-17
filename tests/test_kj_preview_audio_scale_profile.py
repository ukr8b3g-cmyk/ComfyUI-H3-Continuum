"""Bounded audio-scale provider admission; keep older contracts fail-closed."""
import copy
import hashlib
import json
from types import SimpleNamespace

import pytest
import torch
from PIL import Image

from ComfyUI_H3_Continuum_Join import preview_override_signature as adapter
from ComfyUI_H3_Continuum_Join import run_storage as storage
from .test_issue31_preview_override_signature import kj, wrapper, model_with
from . import test_v31_run_storage as signatures
from . import test_v38_review_run_storage as review
from . import test_preview_reuse_diagnostics as diagnostics


@pytest.mark.parametrize('existing_index', [0, 1])
@pytest.mark.parametrize('field', ['id', 'source_sha256'])
def test_new_profile_collision_preserves_both_existing_profiles(tmp_path, existing_index, field):
    existing = (adapter._PROFILE, adapter._PUBLIC_PROFILE)
    candidate = copy.deepcopy(adapter._AUDIO_SCALE_PROFILE)
    assert candidate is not None and all(existing)
    original = copy.deepcopy(existing)
    candidate[field] = existing[existing_index][field]
    path = tmp_path / 'extra.json'
    path.write_text(json.dumps(candidate), encoding='utf-8')
    assert adapter._load_public_profile(path, existing_profiles=existing) is None
    assert existing == original


@pytest.mark.parametrize('contents', [None, 'invalid json', 'null', '{}'])
def test_unavailable_extra_profile_does_not_change_existing_registration(tmp_path, contents):
    existing = (adapter._PROFILE, adapter._PUBLIC_PROFILE)
    original = copy.deepcopy(existing)
    path = tmp_path / 'extra.json'
    if contents is not None:
        path.write_text(contents, encoding='utf-8')
    assert adapter._load_public_profile(path, existing_profiles=existing) is None
    assert existing == original


def test_extra_profile_registration_keeps_known_identity(kj, monkeypatch):
    item = wrapper(kj)
    active, _ = adapter._provider_source(kj.__file__)
    before = adapter.preview_override_signature(item)
    assert before[1]
    monkeypatch.setattr(adapter, '_PROFILES', (active,))
    assert adapter.preview_override_signature(item) == before


@pytest.mark.parametrize('entry_point', ['review', 'head', 'import', 'compatible', 'take'])
def test_new_profile_does_not_promote_pre_admission_saved_take(kj, tmp_path, monkeypatch, entry_point):
    item = wrapper(kj)
    model = model_with(item)
    active, _ = adapter._provider_source(kj.__file__)
    # Record a real unknown-profile contract before this exact provider is admitted.
    with monkeypatch.context() as old:
        old.setattr(adapter, '_PROFILES', tuple(p for p in adapter._PROFILES if p is not active))
        source = diagnostics.controller_at(tmp_path / 'run')
        source.prepare(**diagnostics.prepare_kwargs(model))
        entry = review._entry(0, source.contract)
        source.commit_group((entry,), positions=(0,))
        source.mark_review_group(start=1, end=1, physical_group=1)
        source.finalize(session={'session_id':'before-admission','chunks':[entry]},
            report='CPU fixture',review_pause_metadata=source.review_pause_metadata())
    assert source.manifest['resume_safe'] is False
    assert 'KJ/Core preview implementation is outside the audited source profiles' in source.manifest['resume_disabled_reasons']
    current, safe, _ = signatures._sampling_contract(model=model, reroll_from_chunk=0)
    assert safe
    before = {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in source.run_root.rglob('*') if p.is_file()}
    reader = review._controller(tmp_path, current)
    reader.run_name = source.run_name
    reader.configure_review(generation_mode=review.GENERATION_MODE_REVIEW,review_action=review.REVIEW_ACTION_CONTINUE)
    assert not review._project(source)['group_revisions'][0]['generation_reusable']
    assert not storage._reusable_manifest(source.manifest)
    if entry_point == 'review':
        assert not reader._load_validated_review_prefix(current,resume_safe=True).entries
    elif entry_point == 'head':
        assert reader.find_latest_review_head(current,resume_safe=True) is None
    elif entry_point == 'import':
        assert reader._find_plan_import(current,resume_safe=True) is None
    elif entry_point == 'compatible':
        assert reader._compatible_plan_prefix(source.manifest,current,resume_safe=True) == ([],[])
    else:
        reader.take_group = 1
        reader.take_revision_id = review._project(source)['canonical_head_revision_id']
        with pytest.raises(storage.RunStorageError,match='read-only'):
            reader._validated_take_selection(current,
                source_lineage=source.contract['nonce_lineage_sha256'],resume_safe=True)
    assert before == {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in source.run_root.rglob('*') if p.is_file()}


@pytest.mark.parametrize('suppress_default', [False, True])
@pytest.mark.parametrize('audio_scale', [None, 3.0])
def test_real_wrapper_preserves_cpu_av_inputs_and_executor_result(kj, monkeypatch, suppress_default, audio_scale):
    """Execute the wrapper; substitute display-only preview output, not sampling."""
    import comfy.model_base
    import comfy.model_patcher
    import comfy.utils

    active, _ = adapter._provider_source(kj.__file__)
    patched_scale = active['id'] == adapter._AUDIO_SCALE_PROFILE['id']
    reads = []
    class Sampling:
        @property
        def audio_scale(self):
            reads.append('patched')
            return audio_scale
    model = torch.nn.Module()
    model.model_type = comfy.model_base.ModelType.FLOW_AV
    model.latent_format = SimpleNamespace(latent_rgb_factors=None)
    model.model_sampling = SimpleNamespace(audio_scale=17.0)
    patcher = comfy.model_patcher.ModelPatcher(model,torch.device('cpu'),torch.device('cpu'))
    patcher.object_patches['model_sampling'] = Sampling()
    # Real Core pack/unpack and object-patch access, tiny CPU data only.
    video = torch.arange(24*2*2*2,dtype=torch.float32).reshape(1,24,2,2,2)
    audio = torch.arange(32*2*3,dtype=torch.float32).reshape(1,32,2,3)
    noise, shapes = comfy.utils.pack_latents((video,audio))
    latent = noise.clone()
    mask = torch.ones_like(noise)
    sigmas = torch.tensor([1.,0.])
    originals = [x.clone() for x in (noise,latent,mask,sigmas)]
    returned = object()
    sampler = object()
    observed = []
    class Executor:
        class_obj = SimpleNamespace(model_patcher=patcher)
        def __call__(self,n,l,s,sg,m,callback,disabled,seed,*,latent_shapes):
            assert n is noise and l is latent and s is sampler and sg is sigmas and m is mask
            assert disabled is True and seed == 42 and latent_shapes is shapes
            callback(0,n,l,1)
            return returned
    class Preview:
        def decode_latent_to_preview(self,value):
            return Image.new('RGB',(2,2))
    item = wrapper(kj,node_id=None,suppress_default=suppress_default)
    assert adapter.preview_override_signature(item)[1]
    monkeypatch.setattr(kj,'_get_core_previewer',lambda *a:Preview())
    monkeypatch.setattr(torch.cuda,'is_available',lambda:False)
    def callback(step,x0,x,total):
        observed.append((step,x0 is noise,x is latent,total))
    result = item(Executor(),noise,latent,sampler,sigmas,mask,callback,True,42,shapes)
    assert result is returned and observed == [(0,True,True,1)]
    assert reads == (['patched'] if patched_scale else [])
    assert len(item.frames) == 1
    assert all(torch.equal(a,b) for a,b in zip((noise,latent,mask,sigmas),originals))
    assert not torch.cuda.is_initialized()
