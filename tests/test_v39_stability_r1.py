import pytest
import torch
from ComfyUI_H3_Continuum_Join.v3 import refine_context as rc

def group(keyframe):
    return rc.make_refine_group(
        group_id=0,logical_chunks=[1],physical_frames=124,prompt_policy='single',
        physical_prompt='prompt',source_video_shape=(1,24,37,2,3),
        physical_clip_index=1,context_frames=0,first_image=None,last_image=None,
        conditioning=[[torch.zeros(1,2,3),{'minimax_keyframes':[keyframe]}]],
    )

@pytest.mark.parametrize('resize',[False,True])
@pytest.mark.parametrize('kind',['audio','video','mixed'])
def test_modalities_preserve_audio_and_frozen_source(kind,resize,request):
    if resize and kind!='audio':
        request.getfixturevalue('require_comfy_core')
    keyframe={'resolved_frame_index':0}
    if kind!='video': keyframe['audio_latent']=torch.arange(32*2*7).reshape(1,32,2,7).float()
    if kind!='audio': keyframe['latent']=torch.ones(1,24,1,2,3)
    source=group(keyframe)
    frozen=source['conditioning'][0][1]['minimax_keyframes'][0]
    before={k:v.clone() for k,v in frozen.items() if torch.is_tensor(v)}
    result,stats=rc.adapt_group_conditioning(source,4 if resize else 2,6 if resize else 3)
    actual=result[0][1]['minimax_keyframes'][0]
    assert actual is not frozen
    assert actual['resolved_frame_index']==0
    if kind!='video':
        assert actual['audio_latent'] is frozen['audio_latent']
        assert torch.equal(actual['audio_latent'],before['audio_latent'])
    if kind=='audio':
        assert 'latent' not in actual
        assert stats['keyframes_resized']==0
    else:
        assert actual['latent'].shape[-2:]==((4,6) if resize else (2,3))
    for k,v in before.items(): assert torch.equal(frozen[k],v)

@pytest.mark.parametrize('payload',[{}, {'latent':torch.zeros(1,2,3)},
    {'audio_latent':torch.zeros(1,2)},
    {'latent':torch.zeros(1,2,3),'audio_latent':torch.zeros(1,32,2,7)},
    {'latent':torch.zeros(1,24,1,2,3),'audio_latent':'broken'}])
def test_invalid_payload_is_not_hidden_by_another_modality(payload):
    with pytest.raises(rc.RefineConditioningAdaptationError):
        rc.adapt_group_conditioning(group({'resolved_frame_index':0,**payload}),4,6)
