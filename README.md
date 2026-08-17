# ComfyUI-H3-Continuum 3.3.0
<img width="5250" height="2020" alt="workflow (8)" src="https://github.com/user-attachments/assets/58bc27d7-cab4-4f7d-9f58-ed94bdad4a1d" />



Native long-form MiniMax H3 video and audio continuation for ComfyUI.

**Stable release:** V3.3.0. It adds chunk-local Timeline Video and guarded decoded-video seam correction while preserving the stable sampler, Run Storage contracts, and Spectrum Interop API v1.

https://github.com/user-attachments/assets/bfa8c683-fc9d-48f1-9cdb-477ca110cdf2

**H3 Continuum Sampler V3.3** generates 1 to 16 linked H3 chunks, carries raw video/audio latent context between chunks, supports T2VA, I2VA, FL2VA, multi-image Reference conditioning, and optional Timeline Video, and can resume completed chunks from disk.

V3 delegates video and audio decoding to normal **ComfyUI Core VAE Decode nodes**. No model weights or third-party accelerator code are bundled.

## Sample workflows

- [Standard workflow](examples/workflows/MiniMax_H3_Continuum_V33.json) - quality-oriented `res_multistep` profile with Spectrum enabled.
- [Turbo workflow](examples/workflows/MiniMax_H3_Continuum_V33_turbo.json) - 8-step `euler` profile with Spectrum bypassed.

Download a JSON file and drag it onto the ComfyUI canvas. The examples use optional external custom nodes and local image/audio inputs; replace or bypass unavailable assets for your environment.

Turbo weights are available from [LightX2V MiniMax H3 Turbo](https://huggingface.co/lightx2v/Minimax-h3-Turbo/tree/main).

## Key features

- Raw paired video/audio latent continuation without decode/re-encode between chunks.
- One production sampler UI with normal controls first and infrequent controls marked Advanced.
- T2VA, First Frame, Last Frame, First + Last Frame, and Reference conditioning.
- Up to eight active Reference images across every chunk, compacted in Core connection order; reference inputs auto-expand as they are connected.
- One native Reference Audio item across every chunk.
- Disk-backed Run Storage with automatic resume and compatible Revision reuse.
- Fixed, List, and Timeline prompts through one Sequence Prompt input.
- ComfyUI Core Video/Audio VAE Decode and a separate Continuum Assemble stage.
- Chunk-local Timeline Video conditioning with an efficient 0.4 MP default.
- Guarded Audio Seam and Video Seam correction after Core decode.
- Optional Spectrum Actual Prefix 2 interoperability.
- External SageAttention, LoRA, Turbo, and Spectrum MODEL chains remain composable.
- Existing legacy node identifiers remain registered for saved-workflow compatibility.

## Installation

### ComfyUI Manager

Open **ComfyUI Manager**, search for **H3 Continuum** or **Continuum**, and select **Install**.

![H3 Continuum in ComfyUI Manager](docs/images/comfyui-manager-h3-continuum.png)

Restart ComfyUI after installation, then search for **H3 Continuum Sampler V3.3** in the node menu.

### Manual installation

From `ComfyUI/custom_nodes/`:

```bash
git clone https://github.com/ukr8b3g-cmyk/ComfyUI-H3-Continuum.git
```

Restart ComfyUI and search for **H3 Continuum Sampler V3.3**.

For ZIP installation, extract the repository as `ComfyUI-H3-Continuum` under `ComfyUI/custom_nodes/`, then restart ComfyUI.

Use an up-to-date ComfyUI. ComfyUI v0.32.0 or later is recommended for the current MiniMax H3 Core VAE fixes and memory improvements.

## Current and legacy nodes

V3.3 uses two current workflow nodes:

- **H3 Continuum Sampler V3.3** - unified sampler for normal generation and optional Timeline Video conditioning.
- **H3 Continuum Assemble + Seam** - Core-decoded chunk assembly with Audio Seam and guarded Video Seam correction.

The V3.2.4 nodes remain registered only so existing saved workflows continue to load:

- **[Legacy] H3 Continuum Sampler V3.2.4**
- **[Legacy] H3 Continuum Assemble V3.2.4**

New workflows should use the two V3.3 nodes. The legacy Node IDs are preserved, but they do not receive the integrated Timeline Video and current seam workflow surface.

No additional Python package is required beyond a working ComfyUI MiniMax H3 environment.

## Standard connection

```text
H3 MODEL Loader
  -> optional SageAttention
  -> optional Turbo/LoRA
  -> optional Spectrum
  -> H3 Continuum Sampler V3.3.model

MiniMax H3 CLIP/Text Encoder ------> clip
MiniMax H3 Video VAE -------------> video_vae
Sampler --------------------------> sampler
Sigmas ---------------------------> sigmas
Text (Multiline) -----------------> Sequence Prompt
Optional keyframes ---------------> first_frame / last_frame
Optional references -------------> reference_image_1 ... reference_image_8

video_latents --> Core VAE Decode -----------+
audio_latents --> Core VAE Decode Audio -----+--> H3 Continuum Assemble V3
assembly_plan -------------------------------+

H3 Continuum Assemble V3.images/audio --> Create Video
```

The square grid icon on `video_latents` and `audio_latents` means a list of chunk latents. Connect each output to one normal Core decode node; ComfyUI maps the decoder across the chunk list.

The `video_vae` input is used for image conditioning when needed. Continuum does not perform final Video VAE decoding internally.

## Conditioning modes

The sampler selects the mode from connected image inputs.

| Connected images | Mode |
| --- | --- |
| None | T2VA + Continuation |
| First Frame | I2VA + Continuation |
| Last Frame | Last-frame-conditioned + Continuation |
| First + Last Frame | FL2VA + Continuation |
| One to eight Reference images | Reference + Continuation |

Reference images and First/Last Frame are mutually exclusive. They are separate H3 conditioning modes. Use the FL2VA model family for First/Last Frame workflows and the Ref2VA family for Reference workflows. Continuum does not classify or reject MODEL filenames and never switches MODELs automatically.

The node begins with Reference Image 1-3 visible. Connecting the highest exposed Reference input adds the next socket automatically, one at a time, up to Reference Image 8. Disconnecting trailing references removes unused dynamic tail sockets while preserving every connected socket. Active Reference inputs are compacted in connection order; bypassed or absent sockets are ignored, so active images are always numbered contiguously as Picture 1..N.

Reference prompts should identify the images explicitly:

```text
<Picture 1> defines the subject's face and identity.
<Picture 2> defines the subject's clothing, body design, and skateboard.
<Picture 3> optionally defines another ordered identity, object, or environment reference.
```

The same numbering continues through `<Picture 8>` when more references are connected. Reference images persist across all Continuum chunks.

### Reference Size

- **Match Output**: preserve aspect ratio and downscale toward the output pixel area.
- **Max Identity**: retain a larger identity reference, downscaling only when necessary.

Both modes avoid stretching and use crop-free Reference preprocessing.

## Quick start

1. Add **H3 Continuum Sampler V3.3**.
2. Connect MODEL, CLIP, Video VAE, sampler, sigmas, and one Text (Multiline) node.
3. Set `Prompt Format = Auto`.
4. Start with `chunks = 3`, `chunk_seconds = 5.0`, and `Balanced - 22 frames`.
5. Connect the raw latent outputs to Core VAE Decode and Core VAE Decode Audio.
6. Connect decoded outputs and `assembly_plan` to **H3 Continuum Assemble + Seam**.
7. Connect Assemble images/audio to Create Video.

Recommended safe defaults:

| Setting | Starting value |
| --- | --- |
| Prompt Format | Auto |
| Continuity | Balanced - 22 frames |
| Audio Continuity | On |
| Audio Seam | Auto |
| Regenerate From | Auto |
| Run Storage | Off for short tests; Save + Auto Resume for long runs |
| SageAttention | Auto when backend compatibility is unknown |

## H3 Continuum Sampler UI

The V3.3 production node keeps normal generation controls visible and moves developer-only options to ComfyUI Settings. Connection-specific controls appear only when the related input or Run Storage mode is active.

![H3 Continuum V3.3 streamlined sampler and assembler](docs/images/h3-continuum-v33-streamlined-ui.png)

### Main inputs and controls

| Group | Input or control | Purpose |
| --- | --- | --- |
| H3 pipeline | `model`, `clip`, `video_vae`, `sampler`, `sigmas` | Connect the normal MiniMax H3 MODEL, text encoder, Video VAE, sampler, and sigma schedule. |
| Prompt | `Sequence Prompt` | Fixed, List, or Timeline text for the complete Continuum run. |
| Keyframes | `first_frame`, `last_frame` | Optional I2VA, last-frame-conditioned, or FL2VA keyframes. |
| Reference images | `reference_image_1` ... `reference_image_8` | Up to eight ordered Picture references. Inputs auto-expand from the first three as references are connected; bypassed inputs are ignored. |
| Reference audio | `reference_audio_1`, `reference_audio_vae` | Optional native H3 Reference Audio. Connect the Audio VAE only when Reference Audio is used. |
| Duration | `chunks`, `chunk_seconds` | Number of linked chunks and duration of each chunk. Start with `3 x 5.0` seconds. |
| Canvas | `width`, `height` | Output dimensions. Use values compatible with the current H3 Core path, normally multiples of 32. |
| Continuity | `continuity` | Number of previous raw frames carried into the next chunk. `Balanced - 22 frames` is the practical default. |
| Seed | `base_seed` | Base seed used to derive deterministic per-chunk seeds. |

Reference images and First/Last Frame are mutually exclusive. Reference Audio can be combined with either keyframe conditioning or Reference Image conditioning.

### Advanced controls

| Control | Default | Use |
| --- | --- | --- |
| Prompt Format | Auto | Detect Fixed, List, or Timeline prompts. |
| Audio Continuity | On | Carry raw audio context between chunks. |
| Run Storage | Off | Use `Save + Auto Resume` for long or interruptible runs. |
| Run Name | blank | Appears with `Save + Auto Resume`; optionally overrides the automatic storage identity. |
| Regenerate From | Auto | Appears with `Save + Auto Resume`; reuse normally or regenerate from a selected saved chunk. |
| Variation Nonce | 0 | Appears only for explicit chunk regeneration and creates a deliberate alternate revision. |
| Reference Size | Match Output | Appears when a Reference Image is connected. |
| Timeline Video Size | Efficient - 0.4 MP | Appears when Timeline Video is connected. |

### ComfyUI settings

The following package-wide options are available in ComfyUI Settings instead of occupying every sampler and assembler node:

![H3 Continuum settings](docs/images/h3-continuum-v33-settings.png)

| Setting | Default | Use |
| --- | --- | --- |
| H3 Continuum: Sampling Preview | On | Show normal sampling preview/progress information. |
| H3 Continuum: Developer Diagnostics | Off | Enable developer-oriented diagnostics when troubleshooting. |
| H3 Continuum: Detailed Report | Off | Expand sampler and assembly status text. Normal generation does not require it. |

These settings are applied when the workflow is queued. Hidden legacy widgets remain compatible with older saved workflows, while unknown or merged MODEL filenames are not rejected by name.

### Outputs

| Output | Connect to |
| --- | --- |
| `video_latents` | One normal ComfyUI Core Video VAE Decode node. |
| `audio_latents` | One normal ComfyUI Core Audio VAE Decode node. |
| `assembly_plan` | **H3 Continuum Assemble V3**. |
| `status` | Core **Preview as Text** when a readable run report is needed. |

## Sequence Prompt

### Fixed

One prompt is reused for all chunks.

```text
A continuous cinematic shot. Preserve the same subject, camera direction,
lighting, movement, voice, soundscape, and music across every continuation.
```

### List

Separate one prompt per chunk with a line containing three hyphens.

```text
Opening action.
---
Continue seamlessly from the exact previous movement.
---
Complete the action naturally without a cut or pose reset.
```

If fewer sections are provided than `chunks`, the last section is repeated.

### Timeline

```text
[0-5s]
Opening action.

[5-10s]
Continuous middle action.

[10-15s]
Natural ending.
```

`Prompt Format = Auto` detects Fixed, List, or Timeline syntax.

### Local LLM / Qwen prompt generation

MiniMax provides the official [H3 prompt-writing skill](https://github.com/MiniMax-AI/MiniMax-H3/tree/main/skills/h3-prompt-writing) for T2VA, I2VA, FL2VA, L2VA, and Ref2VA. Give a local agent the complete `h3-prompt-writing` folder, not only `SKILL.md`, because the detailed formats and examples are stored under `references/`.

The official skill defines the H3 prompt fields and reference-label rules. H3 Continuum adds one routing requirement: divide the visual progression into one prompt section per Continuum chunk. The currently validated workflow uses 5-second chunks.

For reliable output, use `Prompt Format = Timeline` or `Auto` and require:

- exactly one non-empty section per configured chunk;
- sequential ranges such as `[0-5s]`, `[5-10s]`, and `[10-15s]`;
- shared Ref2VA subject and reference definitions only once, before the first timeline section;
- only labels for active connected inputs, using compact Core numbering;
- a different action, camera, and scene progression for each section;
- no explanatory text outside the final H3 prompt.

If fewer usable sections are produced, Continuum may reuse the previous available section. Matching the requested chunk count is therefore strongly recommended.

Copy-paste system instruction for a local LLM:

```text
You write production prompts for ComfyUI-H3-Continuum V3.3.

Use the complete official MiniMax H3 prompt-writing skill as the authority for
T2VA, I2VA, FL2VA, L2VA, and Ref2VA field order, syntax, and reference labels.

The user will provide:
- generation mode;
- chunk count;
- seconds per chunk;
- active image, video, and audio inputs;
- scene requirements.

Output rules:
1. Output only the final H3 prompt. Do not add explanations or Markdown fences.
2. Produce exactly one non-empty Timeline section per requested chunk.
3. Use sequential headers calculated from the supplied chunk duration. For three
   5-second chunks, use exactly [0-5s], [5-10s], and [10-15s].
4. Every section must describe the action, camera movement, scene progression,
   and relevant sound for that interval. Continue naturally from the previous
   section; do not repeat the first section.
5. Mention only active connected references. Number Picture, Video, and Audio
   labels compactly in ComfyUI Core order. Never mention bypassed, missing, or
   unconnected inputs.
6. For Ref2VA, write subject_definitions, summary, and retention_analysis once
   before the first Timeline header. In each Timeline section, provide that
   chunk's detailed_description, overall_soundscape, and non_diegetic_music.
7. For T2VA, I2VA, FL2VA, and L2VA, each Timeline section must contain the
   official integrated_multimodal_description, overall_soundscape, and
   non_diegetic_music structure for that chunk.
8. Preserve requested dialogue, lyrics, and visible text verbatim and in their
   requested language. Follow the official H3 dialogue and reference syntax.
9. Do not claim guaranteed frame-perfect continuity or exact audio copying.
```

## Run Storage and automatic resume

For long generations:

```text
Run Storage      = Save + Auto Resume
Regenerate From  = Auto
reroll_nonce      = 0
```

![H3 Continuum chunk auto-resume settings](docs/images/v31b-auto-resume.png)

Each completed raw AV chunk is atomically saved. If generation stops, Queue the same compatible workflow again:

```text
Chunk 1 saved
Chunk 2 saved
Chunk 3 interrupted

Next Queue:
Chunk 1 reused
Chunk 2 reused
Chunk 3 generated
```

Run Storage creates deterministic Revisions from the sampling contract. When Run Name and Auto Resume ID are blank, a stable storage ID is derived from the sampler node. It tracks observable inputs including:

- H3 MODEL loader and ordered MODEL patch/wrapper chain.
- LoRA/Turbo enabled state, filename, and strength.
- CLIP/Qwen encoder and Video VAE loaders.
- Sampler, exact sigma schedule, resolution, duration, continuity, seed, and prompts.
- Conditioning mode, First/Last Frame hashes, and Reference image hashes/settings.

Changing FL2VA to Ref2VA, changing LoRA strength, or changing another tracked setting creates or selects a different Revision. Returning to an earlier compatible configuration reuses its earlier Revision.

The upstream graph and runtime MODEL/CLIP/VAE weight probes are both retained. Unknown wrappers or incomplete runtime probes fail safe: chunks may still be saved, but automatic reuse is disabled when identity cannot be established reliably.

Saved chunk files are verified by size and SHA-256 before reuse. Storage schema changes preserve old files but do not automatically reuse unverifiable older chunks.

Even when all sampling chunks are reused, Core VAE Decode and final assembly run again. A reused 15-second test can therefore still take roughly one minute.

### Regenerate from a chunk

Select `Chunk N` in `Regenerate From` to reuse chunks before N and regenerate N onward. Keep `Auto` for normal resume. Chunk regeneration requires `Run Storage = Save + Auto Resume`.

`reroll_nonce = 0` uses automatic Revision behavior. A positive nonce is retained for compatibility and explicit branch selection.

## Spectrum-aware continuation

With [ComfyUI Spectrum MiniMax H3](https://github.com/xmarre/ComfyUI-Spectrum-MiniMax-H3), Continuum requests **Actual Prefix 2** for continuation chunks through Interop API v1. First-class H3 Continuum API v1 interoperability is included upstream in Spectrum v0.2.15 and later, so a current standard Spectrum installation can receive this request without a separate fork. Confirm the acceptance log below during runtime validation.

```text
Chunk 1: normal path
Chunk 2+: inherited raw AV Context
          -> at least two Actual Transformer steps
          -> normal Spectrum forecast schedule
```

This does not add solver steps. It protects the first evaluations after a new continuation Context before forecasting begins.

A compatible receiver logs:

```text
Spectrum H3: accepted H3 Continuum API v1, actual prefix=2
```

Actual Prefix 2 is active only when the Spectrum log reports that the Continuum API request was accepted. Older or incompatible Spectrum versions continue without that receiver behavior.

### Benefits of the upstream Spectrum integration

The Continuum receiver is included in the official Spectrum release, so users no longer need a Continuum-specific Spectrum fork or local patch. Installing or updating Spectrum through its normal distribution path preserves the integration.

- **Automatic handshake:** Continuum emits the request only for continuation chunks, and Spectrum applies Actual Prefix 2 when it recognizes Interop API v1.
- **Safer chunk transitions:** the first two Transformer evaluations after a new raw AV Context are evaluated normally before Spectrum forecasting resumes. This is intended to reduce forecast instability immediately after a chunk boundary; it does not guarantee that every visible seam or flicker will disappear.
- **No additional solver steps:** Actual Prefix 2 changes which existing evaluations are calculated as Actual steps; it does not increase the configured step count.
- **Update-friendly operation:** the receiver becomes part of upstream Spectrum, so a normal Spectrum update does not overwrite a separate local interoperability patch.
- **Optional composition:** Continuum still works without Spectrum. MODEL selection, Turbo/LoRA, SageAttention, and Spectrum remain external workflow choices, and Continuum does not install or switch them automatically.

After updating Spectrum, confirm that Chunk 2 and later print the acceptance log shown above. Its presence is the runtime proof that the upstream receiver is active.

### Standard and Turbo profiles

```text
Quality
  standard approximately 20-step H3 sampling
  Spectrum ON
  Actual Prefix 2 automatic

Fast
  Turbo / 8-step profile
  Spectrum OFF

Experimental
  Turbo + Spectrum
```

Turbo + Spectrum is not the recommended default because local testing showed a higher risk of artifacts. Sol-Attn is also not part of the current recommended continuity profile.

Turbo LoRA files are available from [LightX2V MiniMax H3 Turbo](https://huggingface.co/lightx2v/Minimax-h3-Turbo/tree/main). The ComfyUI-specific FL2VA and Ref2VA variants can be selected in the upstream MODEL/LoRA chain; Continuum does not bundle or switch them automatically.

## Timeline Video

`H3 Continuum Sampler V3.3` includes an optional `timeline_video` input. When connected, the source is sliced per 5-second chunk, resized independently from the output, encoded only for chunks that must be generated, and released after use. When it is not connected, the same node operates as the normal Continuum sampler.

- `Efficient - 0.4 MP` is the default and recommended starting point.
- `Match Output` preserves more source detail but can be substantially slower and heavier.
- Timeline-video audio is not used; connect Reference Audio separately when needed.
- Results still depend on the checkpoint, prompt, source motion, and reference compatibility.

## Assemble + Seam

Connect decoded chunk images, audio, and `assembly_plan` to `H3 Continuum Assemble + Seam`.

- Default: `Audio Seam = Auto`, `Video Seam = Auto`.
- Video modes: `Auto`, `Auto 2`, `Analyze Only`, `Off`.
- `Auto` applies guarded transient and micro-flash correction without frame deletion.
- `Auto 2` additionally enables guarded exposure-ramp correction and remains experimental.
- `Analyze Only` reports the boundary classification without changing images or audio.
## Why Core Decode is external

Continuum owns sampling, continuation planning, chunk metadata, context trimming, audio alignment, exact duration, and final assembly.

ComfyUI Core owns Video/Audio VAE execution, tiled decode behavior, memory strategy, and future H3 VAE improvements.

This allows the normal Core `VAE Decode` to benefit from ComfyUI updates without copying H3 VAE implementation code into Continuum. Use Core `VAE Decode (Tiled)` when the normal decode path is unsuitable for the selected resolution or available memory.

Full raw chunks are decoded before Continuum trims repeated context. Trimming latents before decode would change temporal VAE conditioning.

## Validation summary

V3.3.0 passed the automated suite and Windows runtime checks for the production sampler, Reference Image/Audio, Run Storage, Timeline Video, Spectrum Actual Prefix 2, Audio Seam Auto, and guarded Video Seam Auto.

`Auto 2` is included as an experimental fallback when `Auto` does not sufficiently reduce a boundary exposure ramp. Detailed test conditions, results, and remaining limits are recorded in [docs/VALIDATION_RESULTS.md](docs/VALIDATION_RESULTS.md).
## Diagnostics

`status` is a normal STRING output. Connect it to Core **Preview as Text** when you need the sampling and Run Storage report.

Useful lines include:

```text
Conditioning mode: Reference + Continuation.
interop=emitted actual_prefix=2
3 reused, 0 generated
resume=complete
```

`accelerator markers not detected (informational only)` is not an error. It only means the optional accelerator marker was not observable.

Keep **Detailed Report** and **Developer Diagnostics** disabled normally. Enable them in ComfyUI Settings only when troubleshooting or collecting a diagnostic report.

## Compatibility and scope

- Native MiniMax H3 PackedLayout is preserved.
- Video and audio VAEs are not run between sampling chunks.
- Accepted raw chunk latents are retained on CPU.
- MODEL input is cloned once per chunk; the workflow MODEL is not mutated.
- SageAttention, LoRA/Turbo, Spectrum, and model weights remain external.
- Unknown H3 layout contracts fail clearly.
- Legacy V1/V2/V3 node identifiers remain registered for older workflows but are not the recommended starting point.

Continuum is independently implemented. It does not copy or bundle source code from Spectrum or [H3 Motion Context](https://github.com/NikoDemon80/ComfyUI-H3-Motion-Context).

## Development checks

```bash
python -m compileall -q .
python -m pytest -q
```

The GitHub Actions workflow runs compileall and the full pytest suite with its explicit test dependencies.

## License

MIT. Model files and third-party custom nodes retain their own licenses. MiniMax H3 weights are not redistributed.
