# AGENTS.md

## Scope
Native MiniMax H3 audio/video continuation for ComfyUI. V1 supplies manual Join/Finish nodes; V2 integrates N chunks over the same continuation core.

## Non-negotiable rules
- Follow ComfyUI Core behavior for user-facing validation. Do not add Continuum-only input restrictions or compatibility stops without documenting and obtaining approval for the exception.
- Prompt content must never block execution. Empty, malformed, incomplete, or unknown prompt syntax falls back to a Fixed prompt and is passed through as entered. Valid Timeline/List/JSON syntax is still parsed normally.
- Keep warnings diagnostic-only unless execution cannot continue safely. Hard stops are limited to corrupt internal contracts such as invalid latent/layout topology, incompatible Assembly Plan data, broken stored revision schema/hash, unusable required payloads, or decode formats that cannot be assembled.
- Unknown upstream nodes, models, wrappers, or merged models must not be rejected solely because they are unknown.
- Keep legacy `strict_compatibility` inputs loadable for old workflows, but they must not enable Continuum-only blocking behavior.
- Before code changes, create a snapshot of the active local runtime. Preserve the current compact V3.4 UI unless the user explicitly approves a UI change.
- Runtime tests must record the workflow, prompt, media inputs, model/LoRA/sampler/step settings, dimensions, chunk count/duration, elapsed time, and observed result. Inspect embedded workflow metadata when present.
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

## Reusable local environment

- Source repository: `D:\Codex\_git_push_work\ComfyUI-H3-Continuum`
- Active ComfyUI runtime: `D:\StabilityMatrix\Data\Packages\ComfyUI_WAN\custom_nodes\ComfyUI-H3-Continuum`
- Reuse the repository's existing pytest configuration and helper scripts instead of rediscovering paths on every task.
- GitHub authentication for this repository is already configured. Do not request a new login or token unless an actual authentication command fails.
- Commit and push only when the user explicitly requests publication.
