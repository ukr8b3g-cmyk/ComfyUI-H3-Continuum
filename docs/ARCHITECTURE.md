# Architecture — H3 Continuum Join 2.0

## 1. Design goals

1. Preserve the V1 native H3 continuation behavior.
2. Integrate N chunks without duplicating V1 temporal/layout logic.
3. Keep SageAttention, Sol-Attn, and Spectrum external and independently updatable.
4. Avoid global ComfyUI class mutation.
5. Fail closed when native H3 layout contracts change.
6. Prevent H3/VAE/CLIP model switching between continuation chunks.
7. Keep accepted chunk latents on CPU and bound transient decode memory.
8. Preserve exact long-chain A/V timing.

## 2. Module layers

```text
UI
  nodes.py                   V1 compatibility nodes
  v2/nodes.py                integrated V2 nodes

V2 orchestration
  v2/sequence.py             phases, session reuse, reroll, reports
  v2/sampling.py             ComfyUI-native sampler path
  v2/h3_builder.py           empty AV latent, prompt and keyframe conditioning
  v2/decoder.py              deferred decode, preallocated assembly
  v2/prompts.py              Fixed/List/Timeline parser
  v2/session.py              in-memory accepted chunk/session model
  v2/session_io.py           atomic session persistence
  v2/motion.py               conservative latent motion analysis
  v2/seeds.py                deterministic per-chunk seed derivation
  v2/diagnostics.py          lightweight seam measurements

Shared continuation core
  continuation.py            native H3 video/video_audio reference construction
  model_patch.py             per-MODEL APPLY_MODEL wrapper
  layout_adapter.py          in-place MM-RoPE placement and payload normalization
  temporal.py                H3 17k+5 / 24fps / 40Hz grid
  state.py                   V1 State and Plan schemas
  media.py                   V1 trim/assembly helpers
  compatibility.py           runtime contract checks
```

V2 calls the shared continuation core. It does not implement a second continuation algorithm.

## 3. Three execution phases

### Phase 1 — conditioning preparation

- Resize first/last images once.
- VAE-encode their keyframe latents once.
- Tokenize and encode each unique Prompt once.
- Clone the externally patched MODEL once and add the Continuum APPLY_MODEL wrapper.

No H3 diffusion sampling begins until this phase completes.

### Phase 2 — H3-only loop

For each chunk:

1. Create native H3 NestedTensor AV latent.
2. Select 5/22/39-frame Context or Auto.
3. Add one native `video` / `video_audio` reference block.
4. Call the standard ComfyUI guider/sampler path.
5. Let Spectrum create and tear down its own run through its public wrappers.
6. Copy the sampled full AV latent to CPU once.
7. Derive the next V1-compatible State from that CPU chunk.

Video and Audio VAE decode are deliberately absent from this loop.

### Phase 3 — deferred decode

- Decode each CPU chunk after all H3 sampling.
- Immediately move decoded tensors to CPU.
- Remove the overlap.
- Copy images into one preallocated final IMAGE tensor.
- Place audio into cumulative 24fps-derived sample ranges.
- Release each raw chunk before decoding the next.
- Apply exact final duration if enabled.

## 4. Native H3 continuation representation

V1 and V2 both represent the previous tail as one reference block:

```text
kind: video or video_audio
latent: native H3 video latent tail
latent_t/h/w: native geometry
audio_latent: optional native H3 audio latent tail
ref_audio_t: audio latent length
_h3cj_* metadata: timeline placement contract
```

The outer APPLY_MODEL wrapper receives the payload built by ComfyUI, moves only marked Continuum reference rows onto the target timeline, and normalizes keyframe/reference latent lists.

## 5. Accelerator composition

### SageAttention

Continuum never replaces the attention kernel. Existing attention overrides remain intact.

### Sol-Attn

Sol-Attn registers H3 target spans by the identity of `PackedLayout.position_ids`. Continuum modifies this tensor in place and never replaces it. Sol conditioning sink and Morton tracking therefore retain their registration.

### Spectrum

Spectrum remains an external OUTER_SAMPLE / PREDICT_NOISE / SAMPLER_SAMPLE / DIFFUSION_MODEL wrapper stack. V2 calls the normal ComfyUI `guider.sample()` once per chunk. Spectrum starts and ends an independent runtime run for each call. Continuum imports no Spectrum private functions.

The recommended model chain is:

```text
UNET → Sage → Sol → LoRA → Spectrum → V2 Sampler
```

V2 then clones this ModelPatcher once; Spectrum's ON_CLONE callback creates an independent runtime binding on the clone.

## 6. State and Session

### V1 State

Contains only the maximum retained continuation tail and temporal metadata. It can start V2 through `initial_state`.

### V2 Session

Contains all accepted raw chunk AV latents plus:

- Prompt and SHA-256 Prompt hash
- per-chunk Seed
- Continuum Plan
- selected Context frames and motion score
- model/accelerator fingerprint
- branch parent/session identifiers

Tensors remain on CPU. Save Session writes safetensors and a JSON mirror atomically. The authoritative metadata is embedded in safetensors.

## 7. Reroll semantics

- `reroll_from_chunk=0`: reuse every matching accepted prefix.
- `reroll_from_chunk=N`: preserve chunks before N and regenerate N onward.
- A Prompt mismatch automatically stops reuse before the changed chunk.
- A first-frame fingerprint mismatch fails explicitly.
- A model/accelerator fingerprint mismatch is reported but accepted chunks remain fixed, because their latent output is already approved.
- The new output creates a child Session; the input Session is not mutated.

## 8. Audio timeline

H3 video is 24fps and audio latent is 40Hz. Decoded PCM is placed using cumulative integer boundaries:

```text
start_sample = round(cumulative_frames / 24 * sample_rate)
stop_sample  = round(next_cumulative_frames / 24 * sample_rate)
```

This avoids the one-sample drift that can occur when every 119-frame segment is rounded independently.

## 9. Memory model

Full accepted AV latents are comparatively small and stored on CPU. The final decoded IMAGE is large, so V2:

- estimates final float32 IMAGE + one raw chunk + headroom before sampling;
- refuses unsafe jobs before expensive H3 work;
- allocates the final IMAGE exactly once;
- copies each decoded segment into its final range;
- avoids progressive whole-sequence concatenation.

## 10. Compatibility policy

The package checks:

- native `MiniMaxH3Model` class and required attributes;
- `PackedLayout` capability, including transparent `*args/**kwargs` wrappers;
- H3 temporal grid `(1,4,4,4,4)`;
- APPLY_MODEL and DIFFUSION_MODEL wrapper APIs;
- NestedTensor support;
- real PackedLayout row placement through the installer self-test.

Marked Continuum payload failures never silently fall back to stock reference placement, because that could render a plausible but semantically wrong join.
