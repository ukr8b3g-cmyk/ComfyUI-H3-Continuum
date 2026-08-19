# H3 Continuum reference interoperability contract

H3 Continuum carries the previous chunk into the next MiniMax H3 call as a normal native `minimax_refs` entry. That reference is a continuation anchor, not an ordinary user reference.

## Stable metadata

The continuation reference contains the namespaced dictionary:

```python
ref["_h3_continuum"] = {
    "api": 1,
    "role": "video_context",
    "audio_role": "audio_context" or None,
    "preserve_rope": True,
}
```

This metadata is intentionally suitable for third-party model patches to inspect without importing H3 Continuum.

`preserve_rope=True` means the reference provides temporal/geometric continuity and should keep native H3 positional/RoPE treatment by default. A patch that changes reference positional frequencies, positional embeddings, reference-key RoPE channels, or equivalent geometry-sensitive attention state should exclude this reference unless the user explicitly requests otherwise.

## Native packing

ComfyUI's native H3 `PackedLayout` still owns the actual packed rows. A Continuum `video` or `video_audio` reference produces visual rows with segment kind `ref_img` (plus `ref_audio` rows when audio is present). Therefore consumers must not identify user image references from `layout.segments` alone.

To distinguish references correctly:

1. read `minimax_payload["refs"]` in native order;
2. read `minimax_payload["layout"].segments`;
3. pair each visual native ref (`image`, `video`, `video_audio`) with the corresponding `ref_img` segment in order;
4. inspect `_h3_continuum` on the paired ref;
5. fail closed if the number/order cannot be reconciled.

This avoids accidentally treating the previous-chunk Continuum context as a normal image/style reference.

## Compatibility

The contract is additive. Native H3 ignores unknown keys on the ref dictionary, so normal ComfyUI packing remains unchanged. Existing internal `_h3cj_*` markers remain for Continuum's own compatibility logic; external consumers should prefer `_h3_continuum`.
