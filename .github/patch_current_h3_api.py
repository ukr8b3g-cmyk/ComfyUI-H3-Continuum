from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected exactly one replacement target, found {count}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


def insert_before(path: str, marker: str, addition: str) -> None:
    replace_once(path, marker, addition + marker)


# ComfyUI #15439 removed PackedLayout.frame_count and made keyframe placement
# target-relative. frame_count remains a legacy optional capability, not a
# Continuum requirement.
replace_once(
    "compatibility.py",
    '''                keywords=(
                    "keyframes",
                    "refs",
                    "frame_count",
                ),
''',
    '''                # ComfyUI #15439 removed ``frame_count`` from PackedLayout.
                # Continuum requires only the stable keyframe/reference inputs;
                # older cores may still expose frame_count as an optional legacy
                # keyword and remain supported.
                keywords=(
                    "keyframes",
                    "refs",
                ),
''',
)
replace_once(
    "compatibility.py",
    '''    layout = h3_model.PackedLayout(
        3, 7, 2, 2, 10, keyframes=None, refs=[ref], frame_count=22
    )
''',
    '''    # This refs-only probe intentionally uses the common constructor
    # contract shared by pre- and post-#15439 ComfyUI revisions.
    layout = h3_model.PackedLayout(3, 7, 2, 2, 10, keyframes=None, refs=[ref])
''',
)

# Core #15439 no longer publishes minimax_frame_count on native first/last-frame
# conditioning. V1 Join already knows the source latent length, so use it as the
# authoritative fallback while retaining legacy metadata support.
replace_once(
    "continuation.py",
    '''    preserve_last_frame: bool,
):
''',
    '''    preserve_last_frame: bool,
    source_frame_count: int | None = None,
):
''',
)
replace_once(
    "continuation.py",
    '''        old_frame_count = metadata.get("minimax_frame_count")
        old_keyframes = [dict(item) for item in (metadata.get("minimax_keyframes") or [])]
''',
    '''        old_frame_count = metadata.get("minimax_frame_count")
        if old_frame_count is None:
            old_frame_count = source_frame_count
        old_keyframes = [dict(item) for item in (metadata.get("minimax_keyframes") or [])]
''',
)
replace_once(
    "nodes.py",
    '''            new_frame_count=shape.total_frames,
            first_frame_policy=first_frame_policy,
''',
    '''            new_frame_count=shape.total_frames,
            first_frame_policy=first_frame_policy,
            source_frame_count=current_frames,
''',
)

# Keep both video and audio keyframe latents when rebuilding mixed keyframe/ref
# payloads. Current Core can attach audio directly to keyframes.
replace_once(
    "layout_adapter.py",
    '''def normalize_condition_latents(payload):
    keyframes=list(payload.get("keyframes") or ()); refs=list(payload.get("refs") or ())
    video_latents=[item["latent"] for item in keyframes if item.get("latent") is not None]
    video_latents.extend(item["latent"] for item in refs if item.get("latent") is not None)
    payload["cond_video_latents"]=video_latents
    payload["cond_audio_latents"]=[item["audio_latent"] for item in refs if item.get("audio_latent") is not None]
''',
    '''def normalize_condition_latents(payload):
    keyframes=list(payload.get("keyframes") or ()); refs=list(payload.get("refs") or ())
    video_latents=[item["latent"] for item in keyframes if item.get("latent") is not None]
    video_latents.extend(item["latent"] for item in refs if item.get("latent") is not None)
    audio_latents=[item["audio_latent"] for item in keyframes if item.get("audio_latent") is not None]
    audio_latents.extend(item["audio_latent"] for item in refs if item.get("audio_latent") is not None)
    payload["cond_video_latents"]=video_latents
    payload["cond_audio_latents"]=audio_latents
''',
)

insert_before(
    "layout_adapter.py",
    "def _map_refs_to_segments(layout,refs):\n",
    '''def _map_keyframes_to_segments(layout,keyframes):
    available=[(int(a),int(b),str(kind)) for a,b,kind in layout.segments if kind in ("cond","cond_audio")]
    cursor=0; result=[]
    def consume(expected):
        nonlocal cursor
        if cursor>=len(available): raise LayoutCompatibilityError(f"layout ended while mapping keyframe '{expected}'")
        a,b,kind=available[cursor]; cursor+=1
        if kind!=expected: raise LayoutCompatibilityError(f"keyframe layout mismatch: expected '{expected}', found '{kind}'")
        return a,b
    for keyframe in keyframes:
        mapping={"audio":None,"video":None}
        if keyframe.get("latent") is not None: mapping["video"]=consume("cond")
        if keyframe.get("audio_latent") is not None: mapping["audio"]=consume("cond_audio")
        if mapping["video"] is None and mapping["audio"] is None:
            raise LayoutCompatibilityError("H3 keyframe has neither video nor audio latent")
        result.append(mapping)
    if cursor!=len(available): raise LayoutCompatibilityError(f"layout contains {len(available)-cursor} unmapped keyframe condition segments")
    return result
''',
)

replace_once(
    "layout_adapter.py",
    '''    keyframes=list(payload.get("keyframes") or ()); refs=list(payload.get("refs") or ()); cond_segments=[(int(a),int(b)) for a,b,kind in layout.segments if kind=="cond"]
    if len(cond_segments)!=len(keyframes): raise LayoutCompatibilityError(f"layout has {len(cond_segments)} cond segments for {len(keyframes)} keyframes")
    video_start,video_stop=_single_segment(layout,"video"); _single_segment(layout,"audio")
    text_segments=[(int(a),int(b)) for a,b,kind in layout.segments if kind=="text"]
    if len(text_segments)!=1 or text_segments[0][0]!=0: raise LayoutCompatibilityError("unexpected H3 text segment")
    text_len=text_segments[0][1]; latent_t=int(layout.signature[1]); video_rows=video_stop-video_start
    if latent_t<=0 or video_rows%latent_t: raise LayoutCompatibilityError(f"video rows {video_rows} are incompatible with latent T={latent_t}")
    frame_rows=video_rows//latent_t; target_origin=float(position_ids[video_start,0]); reference_shift=target_origin-float(text_len)
    patched_video_slots=0
    for (start,stop),keyframe in zip(cond_segments,keyframes):
        if stop-start!=frame_rows: raise LayoutCompatibilityError("keyframe rows no longer equal one target slot")
        if MARK_VIDEO_SLOT in keyframe:
            slot=int(keyframe[MARK_VIDEO_SLOT])
            if not (0<=slot<latent_t): raise LayoutCompatibilityError(f"context slot {slot} is outside target latent T={latent_t}")
            target_row=video_start+slot*frame_rows; position_ids[start:stop].copy_(position_ids[target_row:target_row+frame_rows]); patched_video_slots+=1
        elif reference_shift: position_ids[start:stop,0].add_(reference_shift)
    ref_mappings=_map_refs_to_segments(layout,refs); patched_video_refs=0; patched_audio=0
''',
    '''    keyframes=list(payload.get("keyframes") or ()); refs=list(payload.get("refs") or ())
    keyframe_mappings=_map_keyframes_to_segments(layout,keyframes)
    video_start,video_stop=_single_segment(layout,"video"); _single_segment(layout,"audio")
    text_segments=[(int(a),int(b)) for a,b,kind in layout.segments if kind=="text"]
    if len(text_segments)!=1 or text_segments[0][0]!=0: raise LayoutCompatibilityError("unexpected H3 text segment")
    latent_t=int(layout.signature[1]); video_rows=video_stop-video_start
    if latent_t<=0 or video_rows%latent_t: raise LayoutCompatibilityError(f"video rows {video_rows} are incompatible with latent T={latent_t}")
    frame_rows=video_rows//latent_t; target_origin=float(position_ids[video_start,0])
    patched_video_slots=0; patched_keyframe_audio=0
    for keyframe,mapping in zip(keyframes,keyframe_mappings):
        frame_index=int(keyframe.get("resolved_frame_index",0))
        if frame_index<0: raise LayoutCompatibilityError(f"negative resolved keyframe index {frame_index}")
        desired_start=target_origin+FRAME_RESCALE*float(frame_index)
        video_segment=mapping.get("video")
        if MARK_VIDEO_SLOT in keyframe:
            if video_segment is None: raise LayoutCompatibilityError("marked Continuum video slot has no video condition rows")
            start,stop=video_segment
            if stop-start!=frame_rows: raise LayoutCompatibilityError("legacy Continuum keyframe rows no longer equal one target slot")
            slot=int(keyframe[MARK_VIDEO_SLOT])
            if not (0<=slot<latent_t): raise LayoutCompatibilityError(f"context slot {slot} is outside target latent T={latent_t}")
            target_row=video_start+slot*frame_rows; position_ids[start:stop].copy_(position_ids[target_row:target_row+frame_rows]); patched_video_slots+=1
        elif video_segment is not None:
            start,stop=video_segment; old_start=float(position_ids[start,0]); position_ids[start:stop,0].add_(desired_start-old_start)
        audio_segment=mapping.get("audio")
        if audio_segment is not None:
            start,stop=audio_segment; old_start=float(position_ids[start,0]); position_ids[start:stop,0].add_(desired_start-old_start); patched_keyframe_audio+=1
    ref_mappings=_map_refs_to_segments(layout,refs); patched_video_refs=0; patched_audio=0
''',
)
replace_once(
    "layout_adapter.py",
    '''    if debug: LOG.info("Continuum layout: video_refs=%d legacy_slots=%d audio_windows=%d origin=%.6f rows=%d pos_id=%s",patched_video_refs,patched_video_slots,patched_audio,target_origin,position_ids.shape[0],id(position_ids))
    return {"status":"patched","video_contexts":patched_video,"video_refs":patched_video_refs,"legacy_video_slots":patched_video_slots,"audio_windows":patched_audio,"target_origin":target_origin,"position_ids_id":id(position_ids)}
''',
    '''    if debug: LOG.info("Continuum layout: video_refs=%d legacy_slots=%d audio_windows=%d keyframe_audio=%d origin=%.6f rows=%d pos_id=%s",patched_video_refs,patched_video_slots,patched_audio,patched_keyframe_audio,target_origin,position_ids.shape[0],id(position_ids))
    return {"status":"patched","video_contexts":patched_video,"video_refs":patched_video_refs,"legacy_video_slots":patched_video_slots,"audio_windows":patched_audio,"keyframe_audio_windows":patched_keyframe_audio,"target_origin":target_origin,"position_ids_id":id(position_ids)}
''',
)

replace_once(
    "model_patch.py",
    '''            # ComfyUI Core 0.33.1 replaces keyframe condition latents with
            # reference latents when both contracts are present. Rebuild the
            # combined list for First/Last Frame + standalone Reference Audio.
''',
    '''            # Core revisions differ in how mixed keyframe/reference latent
            # lists are assembled. Rebuild them deterministically, including
            # post-#15439 audio-bearing keyframes.
''',
)

# Compatibility contract tests: support both pre-#15439 and current signatures;
# keep failing closed if the stable keyframes/refs contract is actually removed.
replace_once(
    "tests/test_compatibility.py",
    '''def test_signature_contract_accepts_native_packed_layout_signature():
    def native(
        self,
        text_len,
        latent_t,
        latent_h,
        latent_w,
        audio_t,
        keyframes=None,
        refs=None,
        frame_count=None,
    ):
        pass

    assert _missing_callable_parameters(
        native,
        positional=("text_len", "latent_t", "latent_h", "latent_w", "audio_t"),
        keywords=("keyframes", "refs", "frame_count"),
    ) == []


def test_signature_contract_accepts_sol_attn_style_forwarding_wrapper():
''',
    '''def test_signature_contract_accepts_legacy_packed_layout_signature():
    def native(
        self,
        text_len,
        latent_t,
        latent_h,
        latent_w,
        audio_t,
        keyframes=None,
        refs=None,
        frame_count=None,
    ):
        pass

    assert _missing_callable_parameters(
        native,
        positional=("text_len", "latent_t", "latent_h", "latent_w", "audio_t"),
        keywords=("keyframes", "refs"),
    ) == []


def test_signature_contract_accepts_current_packed_layout_without_frame_count():
    def native(
        self,
        text_len,
        latent_t,
        latent_h,
        latent_w,
        audio_t,
        keyframes=None,
        refs=None,
    ):
        pass

    assert _missing_callable_parameters(
        native,
        positional=("text_len", "latent_t", "latent_h", "latent_w", "audio_t"),
        keywords=("keyframes", "refs"),
    ) == []


def test_signature_contract_accepts_sol_attn_style_forwarding_wrapper():
''',
)
replace_once(
    "tests/test_compatibility.py",
    '''        keywords=("keyframes", "refs", "frame_count"),
    ) == []


def test_signature_contract_still_fails_closed_for_real_keyword_removal():
''',
    '''        keywords=("keyframes", "refs"),
    ) == []


def test_signature_contract_still_fails_closed_for_real_keyword_removal():
''',
)
replace_once(
    "tests/test_compatibility.py",
    '''        keywords=("keyframes", "refs", "frame_count"),
    ) == ["keyframes", "refs", "frame_count"]
''',
    '''        keywords=("keyframes", "refs"),
    ) == ["keyframes", "refs"]
''',
)

# V1 Join regression for current Core's removal of minimax_frame_count, plus a
# guard that arbitrary current-Core guide positions remain rejected rather than
# being mistaken for a final-frame anchor.
replace_once("tests/test_nodes_logic.py", "import torch\n", "import pytest\nimport torch\n")
insert_before(
    "tests/test_nodes_logic.py",
    "\ndef test_prepare_video_only_context():\n",
    '''\ndef test_prepare_conditioning_uses_source_frame_count_when_core_metadata_is_absent():
    old_last = torch.ones(1, 24, 1, 2, 2)
    conditioning = [[torch.zeros(1, 2, 3), {"minimax_keyframes": [{"resolved_frame_index": 123, "latent": old_last}]}]]
    out = _prepare_conditioning(
        conditioning,
        video_context=torch.randn(1, 24, 7, 2, 2),
        audio_context=None,
        audio_grid_offset=0.0,
        context_frames=22,
        new_frame_count=141,
        first_frame_policy=POLICY_REPLACE,
        preserve_last_frame=True,
        source_frame_count=124,
    )
    keyframes = out[0][1]["minimax_keyframes"]
    assert len(keyframes) == 1
    assert keyframes[0]["resolved_frame_index"] == 140


def test_prepare_conditioning_still_rejects_arbitrary_current_core_guides():
    conditioning = [[torch.zeros(1, 2, 3), {"minimax_keyframes": [{"resolved_frame_index": 60, "latent": torch.ones(1, 24, 1, 2, 2)}]}]]
    with pytest.raises(ValueError, match="unsupported existing H3 keyframe index 60"):
        _prepare_conditioning(
            conditioning,
            video_context=torch.randn(1, 24, 7, 2, 2),
            audio_context=None,
            audio_grid_offset=0.0,
            context_frames=22,
            new_frame_count=141,
            first_frame_policy=POLICY_REPLACE,
            preserve_last_frame=True,
            source_frame_count=124,
        )

''',
)

# Layout regressions for both legacy text-relative keyframes and current Core's
# target-relative keyframes/cond_audio segments.
replace_once(
    "tests/test_layout_adapter.py",
    '''def _fake_layout(*, with_last_keyframe=False):
    # text=3, optional one stock keyframe, a 22-frame video/audio context ref,
    # target audio=10 steps, target video=7 slots x 2 rows.
    row = 0
    segments = [(row, row + 3, "text")]
    row += 3
    if with_last_keyframe:
        segments.append((row, row + 2, "cond"))
        row += 2
''',
    '''def _fake_layout(*, with_last_keyframe=False, keyframe_target_relative=False, with_keyframe_audio=False):
    # text=3, optional one stock keyframe, a 22-frame video/audio context ref,
    # target audio=10 steps, target video=7 slots x 2 rows.
    row = 0
    segments = [(row, row + 3, "text")]
    row += 3
    keyframe_video = None
    keyframe_audio = None
    if with_last_keyframe:
        keyframe_video = (row, row + 2)
        segments.append((*keyframe_video, "cond"))
        row += 2
        if with_keyframe_audio:
            keyframe_audio = (row, row + 8)
            segments.append((*keyframe_audio, "cond_audio"))
            row += 8
''',
)
replace_once(
    "tests/test_layout_adapter.py",
    '''    if with_last_keyframe:
        # Stock last keyframe is text-relative before refs shift the target.
        pos[3:5, 0] = 3.0 + 35.0
''',
    '''    if with_last_keyframe:
        # Pre-#15439 Core used text-relative keyframe time; current Core already
        # uses the target origin after reference spans. Both must normalize to 75.
        keyframe_origin = 75.0 if keyframe_target_relative else 3.0 + 35.0
        kv0, kv1 = keyframe_video
        pos[kv0:kv1, 0] = keyframe_origin
        if keyframe_audio is not None:
            ka0, ka1 = keyframe_audio
            pos[ka0 : ka0 + 4, 0] = torch.arange(4, dtype=torch.float64) + keyframe_origin
            pos[ka0 + 4 : ka1, 0] = torch.arange(4, dtype=torch.float64) + keyframe_origin
''',
)
replace_once(
    "tests/test_layout_adapter.py",
    '''        "keyframes": [{"resolved_frame_index": 140, "latent": image}],
''',
    '''        "keyframes": [{"resolved_frame_index": 21, "latent": image}],
''',
)
insert_before(
    "tests/test_layout_adapter.py",
    "\ndef test_negative_audio_grid_offset_places_context_before_target_origin():\n",
    '''\ndef test_current_core_target_relative_keyframe_is_not_double_shifted():
    layout, _video_ref_span, _target_video_span = _fake_layout(
        with_last_keyframe=True, keyframe_target_relative=True
    )
    image = torch.zeros(1, 24, 1, 2, 2)
    video = torch.zeros(1, 24, 7, 2, 2)
    audio = torch.zeros(1, 32, 2, 37)
    payload = {
        "layout": layout,
        "keyframes": [{"resolved_frame_index": 21, "latent": image}],
        "refs": [_context_ref(video, audio)],
    }
    patch_layout_in_place(payload)
    cond_start = next(a for a, _b, kind in layout.segments if kind == "cond")
    assert torch.all(layout.position_ids[cond_start : cond_start + 2, 0] == 75.0)


def test_current_core_audio_keyframe_is_mapped_and_preserved_with_refs():
    layout, _video_ref_span, _target_video_span = _fake_layout(
        with_last_keyframe=True,
        keyframe_target_relative=True,
        with_keyframe_audio=True,
    )
    image = torch.zeros(1, 24, 1, 2, 2)
    guide_audio = torch.zeros(1, 32, 2, 4)
    video = torch.zeros(1, 24, 7, 2, 2)
    context_audio = torch.zeros(1, 32, 2, 37)
    payload = {
        "layout": layout,
        "keyframes": [{"resolved_frame_index": 21, "latent": image, "audio_latent": guide_audio}],
        "refs": [_context_ref(video, context_audio)],
    }
    normalize_condition_latents(payload)
    result = patch_layout_in_place(payload)
    cond_audio_start = next(a for a, _b, kind in layout.segments if kind == "cond_audio")
    assert torch.isclose(
        layout.position_ids[cond_audio_start, 0],
        torch.tensor(75.0, dtype=torch.float64),
    )
    assert result["keyframe_audio_windows"] == 1
    assert payload["cond_audio_latents"][0] is guide_audio
    assert payload["cond_audio_latents"][1] is context_audio

''',
)

# Record the compatibility repair without prematurely bumping the release.
insert_before(
    "CHANGELOG.md",
    "## 3.3.0\n",
    '''## Unreleased

- Restored compatibility with ComfyUI #15439, which removed the legacy `PackedLayout.frame_count` keyword and made native H3 keyframe placement target-relative.
- Normalized keyframe coordinates semantically so pre-#15439 text-relative layouts and current target-relative layouts both land on the same target timeline without double-shifting.
- Added current-Core `cond_audio` keyframe handling and preserved audio keyframe latents when mixed with Continuum reference context.
- Kept V1 First/Last Frame continuation working after Core stopped publishing `minimax_frame_count` by using the source H3 latent length as the authoritative fallback; arbitrary guide positions still fail closed.

''',
)

print("Applied current ComfyUI H3 PackedLayout compatibility reconciliation.")
