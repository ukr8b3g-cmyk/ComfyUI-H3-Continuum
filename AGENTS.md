# AGENTS.md

## Scope
Native MiniMax H3 audio/video continuation for ComfyUI. V1 supplies manual Join/Finish nodes; V2 integrates N chunks over the same continuation core.

## Non-negotiable rules
- Do not globally replace `PackedLayout`, `MiniMaxH3.extra_conds`, or other ComfyUI classes.
- Keep SageAttention, Sol-Attn, and Spectrum external; integrate through public ComfyUI wrappers and H3 payload contracts.
- Preserve the identity of `layout.position_ids` when changing MM-RoPE coordinates.
- Never silently resize a continuation State or Session to a different resolution.
- Unknown H3 layout contracts must fail clearly instead of rendering a subtly incorrect join.
- State and Session files remain safetensors + JSON and are written atomically.
- UI nodes call reusable non-UI modules. V1 and V2 must use the same temporal, state, continuation, and layout logic.
- V2 must not decode Video/Audio VAE between H3 chunks.
- Accepted full chunk latents remain on CPU; do not accumulate generated chunks in VRAM.
- Spectrum history must remain run-scoped through its public sampler wrappers; never import Spectrum private runtime functions.
- Changes must preserve V1 node identifiers and State schema unless an explicit migration is included.

## Validation

```bash
python -m compileall -q .
pytest -q
```

Runtime installer verification must check native PackedLayout behavior and all registered nodes.

GPU checks must cover Sage only, Sage+Sol, Sage+Spectrum, and Sage+Sol+Spectrum with identical prompts and seeds. V2 must also be compared against the equivalent V1 3×5-second graph.
