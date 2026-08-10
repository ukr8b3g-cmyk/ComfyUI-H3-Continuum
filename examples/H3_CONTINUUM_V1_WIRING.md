# H3 Continuum Join V1 — Manual Wiring

## Clip 1

```text
MiniMax H3 Image to Video ── conditioning/latent ─┐
H3 model → Sage → Sol ───────────────────────────┼→ H3 Continuum Join (state empty)
                                                 └→ Spectrum → Basic Guider → Sampler
Sampler output → Video VAE Decode / Audio VAE Decode
             └────────────────────────────────────→ H3 Continuum Finish
                                                     └→ STATE 1
```

## Clip 2

Duplicate the H3 conditioning/sampling group and connect `STATE 1` to the next `H3 Continuum Join.previous_state`. Use another seed for the next clip.

Two conditioning choices are supported:

1. **Identity anchored:** keep the original image connected. Join removes its spatial first-frame keyframe but retains the Qwen visual tokens as identity guidance.
2. **Context only:** disconnect the image from the second MiniMax H3 Image to Video node. The previous AV state becomes the only visual timeline anchor.

## Clip 3+

Repeat the same pattern. State Save/Load is optional when every clip is in one graph. Use numbered state slots when clips are approved across separate runs.

## Recommended accelerator order

```text
MODEL → SageAttention → Sol-Attn → H3 Continuum Join → Spectrum → Basic Guider
```

The order is shown for clarity. Continuum uses `APPLY_MODEL`, Spectrum uses `DIFFUSION_MODEL`, and Sage/Sol remain attention overrides.
