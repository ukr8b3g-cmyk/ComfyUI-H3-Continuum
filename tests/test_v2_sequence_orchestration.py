from types import SimpleNamespace
import hashlib
import torch
from ComfyUI_H3_Continuum_Join.constants import CONTINUUM_INTEROP_KEY, DIAGNOSTICS_BASIC, PROMPT_MODE_FIXED, V2_CONTINUITY_OPTIONS
from ComfyUI_H3_Continuum_Join.temporal import audio_latent_t, video_latent_t
from ComfyUI_H3_Continuum_Join.v2.h3_builder import IdentityAssets, _tensor_fingerprint
from ComfyUI_H3_Continuum_Join.v2.prompts import make_prompt_plan
from ComfyUI_H3_Continuum_Join.v2 import sequence

class Nested:
    def __init__(self,parts): self.parts=list(parts)
    def unbind(self): return self.parts

def _latent(width,height,frames):
    return {"samples":Nested((torch.zeros(1,24,video_latent_t(frames),height//16,width//16),torch.zeros(1,32,2,audio_latent_t(frames))))}
class FakeClip:
    def __init__(self,events): self.events=events
    def tokenize(self,prompt,images): self.events.append(("tokenize",prompt,len(images))); return prompt
    def encode_from_tokens_scheduled(self,tokens): self.events.append(("encode",tokens)); return [[torch.zeros(1,1,2),{}]]


def test_identity_fingerprint_hashes_full_resized_rgb_tensor():
    image = torch.zeros((1, 96, 64, 3), dtype=torch.float32)
    image[0, 95, 63, 2] = 1.0
    digest = hashlib.sha256()
    digest.update(str(tuple(image.shape)).encode("ascii"))
    digest.update(str(image.dtype).encode("ascii"))
    digest.update(image.contiguous().view(torch.uint8).numpy().tobytes(order="C"))
    assert _tensor_fingerprint(image) == digest.hexdigest()

def test_v2_samples_every_chunk_before_any_decode(monkeypatch):
    events=[]; width,height=96,64
    fake_model=SimpleNamespace(model=SimpleNamespace(diffusion_model=SimpleNamespace()),model_options={},wrappers={},model_dtype=lambda:torch.bfloat16,model_size=lambda:0)
    assets=IdentityAssets(None,None,None,None,"none")
    monkeypatch.setattr(sequence,"check_comfy_h3_runtime",lambda:[])
    def clone_model_for_chunk(model,*,strict,debug,chunk_index,context_frames):
        options=dict(model.model_options); transformer_options=dict(options.get("transformer_options") or {})
        if context_frames is not None: transformer_options[CONTINUUM_INTEROP_KEY]={"api":1,"active":True,"min_actual_prefix_steps":2}
        options["transformer_options"]=transformer_options; events.append(("clone",chunk_index,context_frames))
        return SimpleNamespace(model=model.model,model_options=options,wrappers=model.wrappers,model_dtype=model.model_dtype,model_size=model.model_size)
    monkeypatch.setattr(sequence,"clone_model_for_chunk",clone_model_for_chunk)
    monkeypatch.setattr(sequence,"prepare_identity_assets",lambda *a,**k:assets)
    monkeypatch.setattr(sequence,"encode_identity_latents",lambda *a,**k:assets)
    monkeypatch.setattr(sequence,"empty_h3_latent",_latent)
    monkeypatch.setattr(sequence,"accelerator_summary",lambda model:"accelerators")
    def sample_chunk(**kwargs):
        frames=kwargs["latent"]["samples"].unbind()[0].shape[2]; hint=kwargs["model"].model_options["transformer_options"].get(CONTINUUM_INTEROP_KEY); events.append(("sample",int(frames),kwargs["seed"],hint)); return kwargs["latent"]
    def decode_sequence(**kwargs):
        events.append(("decode",len(kwargs["entries"]))); return torch.zeros(362,2,2,3),{"waveform":torch.zeros(1,2,round(362/24*32000)),"sample_rate":32000},[]
    monkeypatch.setattr(sequence,"sample_chunk",sample_chunk); monkeypatch.setattr(sequence,"decode_sequence",decode_sequence)
    monkeypatch.setattr(sequence,"decode_sequence_with_seam",lambda **kwargs: (_ for _ in ()).throw(AssertionError("Off must not enter the V2.1 seam decoder")))
    plan=make_prompt_plan(mode=PROMPT_MODE_FIXED,script="continuous shot",chunks=3,chunk_seconds=5.0)
    images,audio,last_state,session,report=sequence.run_sequence(model=fake_model,clip=FakeClip(events),video_vae=object(),audio_vae=object(),sampler=object(),sigmas=torch.tensor([1.0,0.0]),first_frame=None,last_frame=None,prompt_plan=plan,width=width,height=height,continuity=V2_CONTINUITY_OPTIONS[1],base_seed=42,audio_continuity=True,exact_total_duration=True,diagnostics_mode=DIAGNOSTICS_BASIC,reroll_from_chunk=0,reroll_nonce=0,strict_compatibility=True,debug=False)
    sample_positions=[i for i,e in enumerate(events) if e[0]=="sample"]; decode_position=next(i for i,e in enumerate(events) if e[0]=="decode")
    assert len(sample_positions)==3 and max(sample_positions)<decode_position
    sample_events=[e for e in events if e[0]=="sample"]
    assert sample_events[0][3] is None
    assert sample_events[1][3]["min_actual_prefix_steps"]==2 and sample_events[2][3]["min_actual_prefix_steps"]==2
    assert [e[2] for e in events if e[0]=="clone"]==[None,22,22]
    assert sum(e[0]=="encode" for e in events)==1
    assert images.shape[0]==360 and audio["waveform"].shape[-1]==480000
    assert last_state["clip_index"]==3 and len(session["chunks"])==3
    assert "call-local MODEL clone per chunk" in report
