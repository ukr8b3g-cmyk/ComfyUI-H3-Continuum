# ComfyUI-H3-Continuum 3.0.0

Long-form native MiniMax H3 video and audio continuation for ComfyUI.

V3 is a latent-first workflow. It samples several manageable H3 chunks, carries raw video and audio context into each continuation chunk, and sends the complete raw chunks to ComfyUI Core VAE nodes for decoding. **H3 Continuum Assemble V3** then trims decoded context, aligns audio, and produces the final video frames and audio.

## V3 highlights

- Generate 1 to 16 native H3 chunks as one continuous sequence.
- Preserve raw paired video/audio latent context without decode and re-encode between chunks.
- Keep accepted full chunk latents on CPU instead of accumulating them in active VRAM.
- Use ComfyUI Core **VAE Decode** or **VAE Decode (Tiled)** for video.
- Use ComfyUI Core **VAE Decode Audio** for audio.
- Trim decoded overlap and assemble the final result with cumulative audio sample alignment.
- Optionally accelerate sampling with external SageAttention and Spectrum nodes.
- Automatically request Spectrum Actual Prefix 2 for continuation chunks.
- Preserve V1/V2 node identifiers and State/Session schema compatibility.

## Standard V3 connection

```text
H3 MODEL
  -> optional SageAttention
  -> optional Spectrum
  -> H3 Continuum Sampler V3.model

CLIP / text encoder ----------------------> Sampler V3.clip
MiniMax H3 Video VAE --------------------> Sampler V3.video_vae
Sampler ---------------------------------> Sampler V3.sampler
Sigmas ----------------------------------> Sampler V3.sigmas
Text (Multiline) ------------------------> Sampler V3.Sequence Prompt
Scaled source image ---------------------> Sampler V3.first_frame

Sampler V3.video_latents ---------------> Core VAE Decode.samples
MiniMax H3 Video VAE --------------------> Core VAE Decode.vae

Sampler V3.audio_latents ---------------> Core VAE Decode Audio.samples
MiniMax H3 Audio VAE --------------------> Core VAE Decode Audio.vae

Core VAE Decode.IMAGE -------------------> Assemble V3.images
Core VAE Decode Audio.AUDIO -------------> Assemble V3.audio
Sampler V3.assembly_plan ----------------> Assemble V3.assembly_plan

Assemble V3.images ----------------------> Create Video.images
Assemble V3.audio -----------------------> Create Video.audio
```

The grid marker on `video_latents` and `audio_latents` means that each output is a chunk list. ComfyUI automatically maps the Core VAE Decode nodes across that list. You do not need to duplicate the decode nodes for every chunk.

`video_vae` remains connected to the sampler because V3 uses it to encode first-frame and optional last-frame conditioning. V3 does not use it for output decoding.

## Main nodes

### H3 Continuum Sampler V3

Runs H3 sampling and native continuation, then outputs:

| Output | Purpose |
| --- | --- |
| `video_latents` | Full raw video latent chunks for Core VAE Decode |
| `audio_latents` | Full raw audio latent chunks for Core VAE Decode Audio |
| `assembly_plan` | Context trim and exact-duration contract for Assemble V3 |
| `result` | Optional packed State, Session, and sampler report |

### H3 Continuum Assemble V3

Receives all externally decoded chunks and:

- validates chunk counts against the assembly plan;
- trims the decoded continuation context;
- aligns audio using cumulative frame boundaries;
- optionally applies **Audio Seam Auto** without changing video frames;
- adjusts the final output to the requested exact duration.

### H3 Continuum Advanced V3

Optional pack for Session/State input, reroll controls, diagnostics, audio continuity, strict compatibility, and sampling preview control. Leave it disconnected for normal defaults.

### H3 Continuum Clip Overrides

Optional sparse per-clip prompt replacement. Unspecified clips continue using the main Sequence Prompt.

### H3 Continuum Result

Optional helper that exposes `last_state`, `session`, and the sampler report from the packed `result` output.

## Recommended starting settings

| Setting | Starting value |
| --- | --- |
| Prompt Format | `Auto` |
| Chunks | `2` or `3` for the first run |
| Chunk seconds | `5.0` |
| Continuity | `Balanced - 22 frames` |
| Audio Seam | `Off` |
| Exact total duration | `true` |
| Report Detail | `Basic` |
| Resolution | Approximately `0.5 MP` for practical detail |

Use approximately `0.3 MP` first when testing longer sequences or limited hardware. For a 3:2 landscape source, typical rounded sizes are approximately:

```text
0.3 MP -> 672 x 448
0.5 MP -> 864 x 576
0.6 MP -> 960 x 640
```

Resolution, model precision, ComfyUI offload behavior, and other loaded nodes determine the actual memory limit.

## Prompt formats

Connect one **Text (Multiline)** node to **Sequence Prompt**.

- **Fixed**: one prompt is used for every chunk.
- **List**: separate one prompt per chunk with a line containing `---`.
- **Timeline**: use sections such as `[0-5s]`, `[5-10s]`, or `[Chunk 1]`.
- **Auto**: detects Fixed, List, or Timeline syntax and is the recommended default.

Example List prompt:

```text
The skateboarder begins moving through the city in one continuous shot.
---
She continues the same motion and camera direction without a cut or reset.
---
She completes the action naturally while preserving identity and environment.
```

## Spectrum interoperability

Spectrum is optional. Continuum does not import Spectrum private runtime code.

When valid previous context exists, Continuum adds a small read-only API v1 hint requesting at least two Actual Transformer evaluations at the beginning of that continuation chunk. A compatible Spectrum build reports:

```text
Spectrum H3: accepted H3 Continuum API v1, actual prefix=2
```

Actual Prefix 2 does not add solver steps. It changes the early Actual/Forecast schedule for continuation chunks. Chunk 1 emits no hint, and unsupported Spectrum versions ignore it and continue normally.

A practical accelerated starting point is:

```text
Spectrum enabled          = true
warmup_steps              = 1
tail_actual_steps         = 1
bootstrap_first_forecast  = true
offline_smoothing_replay  = true
audio_blend_weight        = 0.00
```

SageAttention and Spectrum remain external and optional. Sol-Attn and Turbo LoRA are not required by the current tested V3 profile.

## Current tested baseline

The current local V3 baseline was tested on:

- NVIDIA GeForce RTX 5060 Ti 16GB
- 64GB system RAM
- MiniMax H3 INT8 ConvRot workflow
- SageAttention plus Spectrum
- no Sol-Attn and no Turbo LoRA
- `Balanced - 22 frames`
- `Audio Seam: Off`

Observed long-form run:

```text
6 x 5-second chunks
672 x 448 (approximately 0.3 MP)
24 fps / 720 frames / 30.0 seconds
Spectrum Actual Prefix 2 accepted for chunks 2-6
Total execution time: 12 minutes 48 seconds
```

This is one validated local baseline, not a universal performance guarantee. A 60-second run and higher-resolution long-form profiles are still pending validation.

Development and A/B notes are available in [docs/AB_TEST_LOG_JA.md](docs/AB_TEST_LOG_JA.md).

## Installation

From the ComfyUI `custom_nodes` directory:

```bash
git clone https://github.com/ukr8b3g-cmyk/ComfyUI-H3-Continuum.git
```

Restart ComfyUI and search for:

```text
H3 Continuum Sampler V3
H3 Continuum Assemble V3
H3 Continuum Advanced V3
```

No additional Python package is required beyond a working ComfyUI MiniMax H3 environment. Model files and external accelerator nodes are not bundled.

If an older `ComfyUI-H3-Continuum-Join` folder exists, remove or rename it before starting ComfyUI. Do not load both package folders at the same time.

## Compatibility and legacy workflows

- Existing V1 and V2 node identifiers remain registered as Legacy nodes.
- State, Session, and Prompt Plan schema versions remain unchanged.
- Unknown or unsafe native H3 layout contracts fail clearly.
- The workflow input MODEL is not mutated; each chunk uses a call-local clone.
- Full continuation chunks are decoded before overlap trimming to preserve VAE temporal context.

New workflows should use the V3 sampler, ComfyUI Core VAE Decode nodes, and Assemble V3.

## Current limitation and roadmap

V3.0 keeps raw chunk latents on CPU and delegates decoding to ComfyUI Core, which substantially improves VRAM flexibility. Decoded IMAGE tensors still remain in system RAM until Assemble V3 runs, so system RAM can become the limit for very long or high-resolution output.

Planned work:

- V3.0.x: contract validation, diagnostics, and ownership/lifetime hardening without changing sampling semantics.
- V3.1: disk-backed chunks, chunk-wise decode/release, and streaming assembly for longer sequences.

## Development checks

Use the same Python environment as ComfyUI:

```bash
python -m compileall -q .
pytest -q
```

## License

GPL-3.0-or-later. External model weights and accelerator packages retain their own licenses.
