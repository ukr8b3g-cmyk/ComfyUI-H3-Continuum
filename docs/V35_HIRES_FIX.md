# V3.5 Hi-Res Fix and Second Pass workflow guide

Status: V3.5 public connection guide. The integrated Hi-Res Fix remains Experimental; the Advanced Second Pass Bridge is the accepted Issue #8 path.

## Most important correction

The accepted Second Pass scheduler values are:

```text
BasicScheduler
  scheduler = simple
  steps     = 10
  denoise   = 0.35
```

This means **10 steps and denoise 0.35**. It does not mean denoise 10.

`H3 Continuum Hi-Res Fix V3.5` does not contain its own steps or denoise value. It receives the exact `SIGMAS` produced by the workflow-side `BasicScheduler`, so this connection controls how strongly and how many steps the resized latent is refined.

The values above are the GPU-accepted baseline, not a claim that they are universally optimal for every model, sampler, resolution, or prompt.

## Standard Main connection

Normal users should use the two V3.5 nodes below:

```text
H3 Continuum Sampler V3.5
        │
        ├─ video_latents ───────┐
        ├─ audio_latents ───────┤
        ├─ assembly_plan ───────┤
        └─ refine_context ──────┤
                                ▼
                    H3 Continuum Hi-Res Fix V3.5
                                │
                                ├─ video_latents ──→ Core Video VAE Decode
                                ├─ audio_latents ──→ Core Audio VAE Decode
                                └─ updated_assembly_plan → Assemble + Seam V3.5
```

Additional connections to `H3 Continuum Hi-Res Fix V3.5`:

| Hi-Res Fix input | Connect from |
|---|---|
| `model` | The same final H3 MODEL used by First Pass |
| `clip` | The same MiniMax H3 CLIP |
| `sampler` | Second Pass `KSamplerSelect`; accepted test used `res_multistep` |
| `sigmas` | A separate Second Pass `BasicScheduler`; accepted test used `simple`, 10 steps, denoise 0.35 |
| `video_latents` | `H3 Continuum Sampler V3.5.video_latents` |
| `audio_latents` | `H3 Continuum Sampler V3.5.audio_latents` |
| `assembly_plan` | `H3 Continuum Sampler V3.5.assembly_plan` |
| `refine_context` | `H3 Continuum Sampler V3.5.refine_context` |
| `video_vae` | The same H3 Video VAE used by First Pass/Core Decode |

Accepted Main controls:

```text
enabled        = true
upscale_method = lanczos
scale_by       = 2.0
refine_seed    = 42 in the acceptance run
```

The node derives one actual refine seed per physical group from `refine_seed`; the report shows that derived sampling seed.

When `enabled=false`, the node returns the original video/audio LATENT objects and Assembly Plan unchanged. Sampling and VAE dependencies are lazy and are not evaluated.

## First Pass scheduler versus Second Pass scheduler

There are normally two independent scheduler roles:

```text
First Pass BasicScheduler
  → H3 Continuum Sampler V3.5.sigmas

Second Pass BasicScheduler
  → H3 Continuum Hi-Res Fix V3.5.sigmas
```

The accepted GPU run used:

```text
First Pass:  simple / 20 steps / denoise 1.0
Second Pass: simple / 10 steps / denoise 0.35
```

Only the Second Pass values describe the Hi-Res Fix refinement strength.

## What Hi-Res Fix does internally

```text
First Pass physical video latent
  → H3 Video VAE Decode
  → CPU pixel resize (Lanczos in the accepted run)
  → same H3 Video VAE Encode
  → context-aware physical-group Second Pass
  → refined video latent
```

Audio is not adopted from the temporary Second Pass result. The original First Pass audio LATENT objects are returned bit-exact.

The Main node never falls back to direct 24-channel latent interpolation. If the required Video VAE is missing or the VAE contract is violated, it raises an explicit error.

## Advanced external-upscaler connection

Use `H3 Continuum Second Pass V3.5` directly only when an external latent processor such as LBH is used:

```text
H3 Continuum Sampler V3.5.video_latents
  → LBH / external H3 latent processor
  → H3 Continuum Second Pass V3.5.video_latents

Second Pass BasicScheduler.SIGMAS
  → H3 Continuum Second Pass V3.5.sigmas
```

Also connect the Sampler's original `audio_latents`, `assembly_plan`, and `refine_context`, plus the same MODEL, CLIP, sampler, and Video VAE.

Do not place `H3 Continuum Hi-Res Fix V3.5` and a separate `H3 Continuum Second Pass V3.5` in series for the standard path. Hi-Res Fix already performs one Second Pass internally; chaining both would refine twice.

## Latent Resize Utility

`H3 Continuum Latent Resize V3.5` changes only the H/W of the 24-channel video latent. It does not sample and is not the standard Main backend.

Direct 2x latent interpolation to 1024/1152 square produced persistent artifacts in testing. Therefore standalone Latent Resize `nearest-exact / scale_by=2.0`, or Main Hi-Res Fix `bislerp / scale_by=2.0`, must not be described as the accepted Main 2x configuration. The accepted Main 2x configuration is the Pixel/VAE path with pixel Lanczos.

## GPU-accepted Main condition

```text
Mode:                 FL2VA, 1 chunk × 5 seconds
First Pass canvas:    576 × 576
Hi-Res target:        1152 × 1152
Pixel resize:         Lanczos
Second Pass sampler:  res_multistep
Second Pass SIGMAS:   simple / 10 steps / denoise 0.35
Output latent:        (1, 24, 37, 72, 72)
Physical groups:      1
Sampling passes:      1
Final media:          1152 × 1152, 120 frames, 24 fps, 5.000 seconds
```

This integrated Main output matched every decoded video and audio frame of the accepted external Decode -> Lanczos -> Encode -> Second Pass reference.

Additional GPU results:

- Hybrid FL2VA + Reference `1 x 5s` passed through the integrated 576-to-1152 Lanczos Main path. Context-aware conditioning used the captured `refine_context`, each physical group sampled once, first-pass audio was returned bit-exact, and Core Decode / Assemble produced 120 frames at 24 fps / 5.000 seconds without persistent line or plate artifacts.
- The same Hybrid/Reference input also passed through the direct Advanced Second Pass node at 576x576, confirming the public bridge node independently of the integrated wrapper.
- Main `3 x 5s` at 576-to-1152 is not accepted on the tested RTX 5060 Ti 16 GiB. The 37T group completed its 10-step Second Pass, then the terminal 77T group failed at its first inference with CUDA OOM (`15.93 GiB` device limit, `10.04 GiB` already allocated, `1.49 GiB` requested).

Still unverified:

- Main `3 x 5s` 2x on a GPU with more than 16 GiB VRAM, or a lower-memory implementation for its terminal 77T group
- Reference/Hybrid cases longer than `1 x 5s`
- Main 2x `bislerp` quality; it was not the accepted Lanczos test
