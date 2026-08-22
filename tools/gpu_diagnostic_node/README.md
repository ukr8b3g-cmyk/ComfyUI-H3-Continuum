# H3 Core vs Continuum GPU Diagnostic

This is a standalone diagnostic node. It does not change or register through the
production H3 Continuum package.

## Install for ComfyUI_W

Run from the repository root:

```powershell
.\tools\install_gpu_diagnostic_node.ps1
```

Restart ComfyUI and search for `H3 Core vs Continuum GPU Diagnostic`.

## Connections

- Connect the same direct MODEL used by both tests. Keep Spectrum off.
- Connect the same CLIP, Video VAE, Audio VAE, sampler, and sigmas.
- Connect the exact same First Frame and Last Frame.
- Use 640x640, seed 42, 8 steps, Euler/simple for the baseline comparison.
- Run Storage and Session are not used by this node.

One queue executes Core FL2VA at 243 frames, then Continuum Terminal Merge 2x5s.
Results are written below:

```text
ComfyUI/output/h3_continuum/diagnostics/<timestamp>/
```

The report identifies the first difference across pre-sampler data, first H3
MODEL call, sampled physical latent, split/recombine, and decode/assembly.
