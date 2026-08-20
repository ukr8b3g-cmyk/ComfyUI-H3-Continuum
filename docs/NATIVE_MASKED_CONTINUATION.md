# Native Masked AV Continuation

V3.4 supports two intentionally different H3 continuation mechanisms.

## Native Masked Continuation

**Native Masked — exact continuation (Recommended)** is the V3.4 default for same-shot chunk continuation. It requires the MiniMax H3 per-token denoise-mask support merged in ComfyUI PR #15375 (merge commit `ff6c8a8af144fc9e9e7bc436b1b202f9316848d8`) or a newer Core revision exposing the same H3 mask capabilities.

For chunk 1, Continuum creates and samples a normal H3 target latent. There is no protected continuation prefix.

For chunk N > 1, Continuum:

1. loads the previous accepted chunk's generated H3 latent state from the normal in-memory/Run Storage contract;
2. selects the final valid continuation window directly from the stored H3 video latent, plus the generated-audio latent when Audio Continuity is enabled and Driving Audio is absent;
3. creates a fresh H3 target latent for chunk N;
4. copies the selected video latent tail into the start of the new target video stream;
5. copies the selected generated-audio tail into the start of the new target audio stream when generated-audio continuation is active;
6. constructs native H3 `noise_mask` streams with `0 = preserve` and `1 = generate`;
7. sends the target and mask through the normal ComfyUI sampler/Core MiniMax H3 path.

The previous generated latent is never decoded merely to be VAE-encoded again. Stored source tensors stay CPU-resident and are treated as immutable input. The fresh target receives copies, so the new chunk does not alias the prior accepted chunk.

Native Masked continuation does not encode the previous chunk as a `minimax_refs` continuation block. Continuum's legacy `PackedLayout.position_ids` rewrite is therefore not part of this path. Ordinary Core references and keyframes remain ordinary Core conditioning.

## Guide / Motion Context

**Guide / Motion Context** retains the earlier Continuum mechanism. The previous clip is supplied as native H3 guide/reference context, and Continuum maps that context onto the next target timeline with the existing layout/RoPE adapter.

Use Guide / Motion Context when the previous shot should influence the next shot without freezing an exact generated prefix. It is useful for softer continuity and shot transitions. It remains available intentionally and is also the compatibility behavior of the existing V2/V3.3 nodes.

## H3 temporal boundaries

H3 video targets use the native `17k + 5` pixel-frame grid. Continuum's current video context profiles are 5, 22, and 39 frames. At 24 fps these correspond to 2, 7, and 12 video-latent temporal slots.

Generated H3 audio uses a 40 Hz latent timeline. An exact shared AV continuation boundary must satisfy:

```text
context_frames * 40 / 24 = integer audio steps
```

For a valid H3 `17k + 5` video context, shared exact AV boundaries occur at 39, 90, 141, 192, ... frames. Among Continuum's current 5/22/39 profiles, 39 frames is the exact AV option:

```text
39 video frames at 24 fps = 1.625 s = 65 audio latent steps at 40 Hz
```

V3.4 therefore defaults new Native Masked workflows to **Strong — 39 frames**. With generated Audio Continuity enabled, `Auto` also resolves to 39 frames. Explicit 5- or 22-frame Native Masked generated-audio continuation is rejected with an actionable error instead of rounding the audio boundary. Those profiles remain valid for video-only Native Masked continuation and for Guide / Motion Context.

## First frame, last frame, and references

Chunk 1 keeps normal Core conditioning behavior.

On continuation chunks, any target keyframe that lies inside the protected Native Masked prefix is removed because the copied latent prefix is already the frame-0 authority. This prevents a connected first-frame guide from competing with the preserved continuation latent. A last-frame guide remains valid when its resolved target position lies after the protected prefix.

Reference images/Ref2VA, including V3.4's dynamic inputs up to 8 references, remain ordinary persistent H3 references. Video Reference and standalone reference-conditioning metadata also remain separate from continuation state. They are not marked as Continuum history and do not become part of the protected prefix contract.

## Generated audio and Driving Audio

With normal generated audio and Audio Continuity enabled, Native Masked continuation protects both the previous video tail and its exactly aligned generated-audio tail.

With Audio Continuity disabled, only video is protected; the entire new target audio stream remains generatable.

Driving Audio has different semantics. It is authoritative source audio for the final timeline. While Driving Audio is active, Continuum does not reuse the previous generated audio as continuation input in either Native Masked or Guide / Motion Context mode. Native Masked protects the previous video tail and leaves the target audio mask fully generatable. Guide / Motion Context likewise supplies only previous video context. Continuum then attaches the existing absolute-time Driving Audio guide slice for the full chunk target, including the repeated video-prefix interval in Native Masked mode. Final assembly still selects the preserved source audio and bypasses generated-audio seam processing.

This keeps one audio authority and preserves the existing absolute source-timeline alignment.

## Assembly

Native Masked continuation deliberately repeats the protected prefix at the start of chunk N > 1. The existing chunk plan records the same `trim_frames = context_frames` overlap used by assembly. Decode/assembly removes that repeated prefix once, preserving the current cumulative audio-boundary math, final frame count, and seam-processing contract.

Seam correction remains available. Native masking improves the generative boundary but does not make all decoded seam correction unnecessary.

## Run Storage and restartability

Native Masked uses mask contract version `1`.

Run Storage salts continuation-chunk generation fingerprints with the continuation method and mask-contract version. Chunk 1 has no continuation prefix, so its prompt fingerprint is intentionally unchanged and can be reused when only the continuation backend changes. Chunk 2 and later are never reused across Guide and Native Masked contracts.

Native continuation chunk plans and Session settings persist the method and mask-contract version. Legacy stored continuation chunks without those fields are treated as Guide chunks. Regenerating from a later Native Masked chunk uses the immediately preceding accepted chunk's stored CPU latent as the continuation source.

## Spectrum interoperability

Spectrum's Continuum interoperability request is separate from the continuation representation. Chunk 2 and later still request H3 Continuum Interop API v1 with an Actual Prefix of 2 sampler steps.

Native Masked does not require `patch_layout_in_place()` to make this request work. The three responsibilities remain independent:

- ComfyUI Core owns per-token video/audio denoise-mask mechanics;
- Continuum owns target-prefix construction, persistence, and assembly trimming;
- Spectrum owns forecast safety and the requested actual sampler prefix.

Spectrum remains optional. No Spectrum companion change is required for this contract.

## Compatibility and migration

Native Masked checks for the actual Core H3 mask API rather than relying only on a package version string. If the required API is missing, V3.4 reports the missing capability and identifies ComfyUI PR #15375 / merge commit `ff6c8a8af144fc9e9e7bc436b1b202f9316848d8` as the minimum implementation point.

As of August 20, 2026, the latest tagged ComfyUI release is v0.31.0 from August 8, which predates the August 18 merge of #15375. Until a tagged release contains that implementation, Native Masked requires `ff6c8a8af144fc9e9e7bc436b1b202f9316848d8` or a newer Core `master` revision.

Guide / Motion Context remains available on older supported Core builds that satisfy Continuum's existing guide/runtime requirements.

Existing V3.3 nodes retain Guide behavior. Existing V3.4 workflows created before Native Masked are migrated to Guide / Motion Context on load so their old continuation semantics remain stable. The maintained V3.4 example workflows explicitly serialize Native Masked with Strong — 39 frames.

## Runtime validation checklist

CI validates latent copying/masks, boundary mapping, method routing, references/keyframes, Run Storage identity, source immutability, Spectrum request independence, and existing assembly/duration behavior. A real H3 model run is still required to assess perceptual seam quality and model-level interaction beyond those contracts.

Recommended runtime validation:

- current ComfyUI containing PR #15375;
- H3 FL2VA model with normal Video VAE and Audio VAE;
- V3.4 sampler, `Continuation Method = Native Masked — exact continuation (Recommended)`;
- `Continuity = Strong — 39 frames`, `Audio Continuity = enabled`;
- 2 x 5 s chunks at a normal production resolution and fixed seed;
- test once with Spectrum absent and once with current Spectrum enabled;
- repeat with Driving Audio, a last-frame guide, Ref2VA references, and Video Reference as separate cases;
- verify the final assembled duration, no duplicated 39-frame prefix, no audio shift, and expected continuity at the seam.
