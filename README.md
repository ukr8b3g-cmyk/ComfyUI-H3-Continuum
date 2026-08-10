# ComfyUI-H3-Continuum 2.1.4

Integrated long-form continuation for ComfyUI's native MiniMax H3 audio/video model.

**H3 Continuum Sampler V2** runs N native H3 chunks through the proven V1 continuation core, keeps text/image preparation outside the H3-only sampling loop, captures AV latent state before decoding, and decodes/assembles the sequence only after all sampling is complete. All V1 node identifiers remain available.

## V2 highlights

- One integrated N-chunk sampler node
- Native video/audio latent continuation with 5, 22, 39-frame and conservative Auto profiles
- One externally patched MODEL input with an isolated call-local clone per chunk
- Unique prompt conditioning cached before sampling
- One stable `Sequence Prompt` socket with Auto, Fixed, List, and Timeline parsing
- Optional `Clip N Prompt` overrides follow `chunks` from 1–16 and are collapsed by default
- Local latent-preview toggle under `Settings > H3 Continuum > Preview`
- Optional V2.1 Basic seam correction after deferred decode; Off keeps the V2.0.2 path
- CPU-only adaptive cut, bounded color/luma guard, short motion-aware blend, and boundary-local audio crossfade
- No Video/Audio VAE decode between H3 chunks
- Full chunk latents stored on CPU; VRAM does not grow with accepted chunks
- Session resume, branch-safe reroll, atomic safetensors + JSON persistence
- Cumulative 24fps audio boundaries, preventing per-chunk rounding drift
- Single-allocation final image assembly and preflight RAM safety check
- External SageAttention, Sol-Attn, and Spectrum composition
- No global ComfyUI H3 monkey patch and no accelerator private-API dependency
- No additional pip dependencies

See [README_JA.md](README_JA.md) for the complete guide.

## Recommended graph

```text
H3 UNET → SageAttention → Sol-Attn → LoRA → Spectrum
                                              ↓
CLIP / Video VAE / Audio VAE / Sampler / Sigmas
                                              ↓
                              H3 Continuum Sampler V2
                                              ↓
                                  IMAGE + AUDIO → CreateVideo
```

## V2 nodes

- H3 Continuum Sampler V2
- H3 Continuum Prompt Plan
- H3 Continuum Save Session
- H3 Continuum Load Session
- H3 Continuum Session Info

V1 compatibility nodes remain registered: Join, Finish, Assemble, Save State, and Load State.

## Development checks

```bash
python -m compileall -q .
pytest -q
```

## License

GPL-3.0-or-later. This package was independently implemented against public ComfyUI H3 runtime contracts. Optional accelerator source code is not bundled.
## V2.1.4 Feature Summary

- One integrated `H3 Continuum Sampler V2` node generates 1 to 16 sequential chunks.
- `Sequence Prompt` accepts one external Text (Multiline) input.
- Prompt formats: `Auto`, `Fixed`, `List`, and `Timeline`.
- Optional per-clip prompt overrides remain collapsed until needed.
- Native video and audio latents pass directly between chunks without VAE decode/re-encode.
- Continuity presets: `Fast - 5 frames`, `Balanced - 22 frames` (default), and `Strong - 39 frames`.
- Seam Correction provides `Off` and `Basic`; `Basic` is the default safe post-decode correction path.
- Exact total duration and audio continuity are enabled by default.
- SageAttention, Sol-Attn, LoRA, and Spectrum remain external and composable.
- Spectrum Interop API v1 requests a two-step Actual prefix only when continuation context exists.
- Advanced continuation, State, Session, Prompt Plan, reroll, and diagnostic controls are collapsed by default.
- Existing advanced connections automatically reopen the Advanced section.
- V1 and auxiliary nodes remain load-compatible but are marked deprecated and moved to the Legacy category.
- Existing State and Session schemas, output ordering, and saved workflow node identifiers are preserved.
- Repository: https://github.com/ukr8b3g-cmyk/ComfyUI-H3-Continuum
