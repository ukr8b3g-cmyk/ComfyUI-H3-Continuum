# ComfyUI-H3-Continuum 2.1.7

Long-form native MiniMax H3 audio/video continuation for ComfyUI.

**H3 Continuum Sampler** generates 1–16 H3 chunks in one compact facade, carries the previous raw video/audio latent directly into the next chunk, stores accepted chunks on CPU, and defers VAE decode until sampling is complete.

## V2.1.7 Stable Facade UI

V2.1.7 replaces the dynamic V2.1.6 display controller with a small static facade. It uses standard ComfyUI rendering and delegates generation to the fully compatible `H3ContinuumSamplerV2` execution core.

- `H3 Continuum Sampler` contains only the normal sequence controls and three optional pack inputs.
- `H3 Continuum Clip Overrides` supplies per-clip prompts through one static pack socket.
- `H3 Continuum Advanced` contains resume/session inputs and infrequent settings.
- `H3 Continuum Result` expands `last_state`, `session`, and `report` only when needed.
- The old `H3ContinuumSamplerV2` identifier remains registered as a Legacy/Core compatibility node.
- No dynamic sockets, proxy widgets, DOM hiding, MutationObserver, widget-size overrides, or `widgets_values` reconstruction.
- State, Session, Prompt Plan, Sampling, Native Continuity, and Spectrum Interop contracts are unchanged.

## Core features

- Native raw H3 video/audio latent continuation; no decode/re-encode between chunks.
- 5 / 22 / 39-frame context profiles plus conservative Auto.
- Native H3 17k+5 temporal grid and signed 40/24 audio-grid alignment.
- Call-local MODEL clone per chunk; Spectrum runtime/history does not leak across chunks.
- Spectrum Interop API v1 requests Actual Prefix 2 only when valid continuation context exists.
- `Sequence Prompt` with Auto / Fixed / List / Timeline parsing and per-clip overrides.
- Seam Correction: `Auto / Off / Basic`.
- Session resume and branch-safe reroll.
- Exact cumulative audio boundaries and exact total-duration correction.
- No additional pip dependencies beyond the normal ComfyUI environment.

## Recommended graph

```text
H3 UNET -> SageAttention -> Sol-Attn -> LoRA -> Spectrum
                                                  |
CLIP / Video VAE / Audio VAE / Sampler / Sigmas  |
                                                  v
                                    H3 Continuum Sampler
                                      |         |
                                    IMAGE      AUDIO
```

Recommended first validation: `chunks=2`, `chunk_seconds=5`, `Balanced — 22 frames`, `Seam Correction=Off` for native-continuity A/B, then test Auto separately.

## Install

Copy the extracted `ComfyUI-H3-Continuum` folder into `ComfyUI/custom_nodes/` and restart ComfyUI, or run `install_windows.bat`.

If replacing the older `ComfyUI-H3-Continuum-Join` folder, remove or rename the old folder so both packages are not loaded at once. The included installer backs up both old and new destination names.

## Development checks

```bash
python -m compileall -q .
pytest -q
```

## License

GPL-3.0-or-later. External accelerator source code is not bundled.
