# AGENTS.md

## Scope
MiniMax H3 Continuum V3.6.0 for ComfyUI. Treat V3.6 as the current Production baseline; preserve V3.5.3/V3.4 node IDs, public contracts, and saved-workflow loading without letting legacy controls change current behavior.

## Non-negotiable rules
- Follow ComfyUI Core behavior for user-facing validation. Continuum-only prompt restrictions, model allowlists, compatibility gates, and policy-based execution stops are prohibited.
- Do not implement a new user-facing hard stop. If execution is structurally impossible or continuing risks corrupting stored data, document the exact broken internal contract and obtain explicit approval before changing the stop.
- Prompt content must never block execution. Empty, malformed, incomplete, or unknown prompt syntax falls back to a Fixed prompt and is passed through as entered. Valid Timeline/List/JSON syntax is still parsed normally.
- Keep warnings diagnostic-only unless execution cannot continue safely. Hard stops are limited to corrupt internal contracts such as invalid latent/layout topology, incompatible Assembly Plan data, broken stored revision schema/hash, unusable required payloads, or decode formats that cannot be assembled.
- Unknown upstream nodes, models, wrappers, or merged models must not be rejected solely because they are unknown.
- Keep legacy `strict_compatibility` inputs loadable for old workflows, but ignore their value. They must never enable blocking behavior.
- Before every change, run `tools\snapshot.ps1` against the authoritative source. Preserve the compact V3.4 UI unless the user explicitly approves a UI change.
- In public templates, connection examples, screenshots, and documentation, keep ComfyUI Core nodes on their standard display titles. Do not assign custom titles to Core nodes, because users must be able to distinguish Core nodes from Continuum and third-party custom nodes immediately.
- Runtime tests must record the workflow, prompt, media inputs, model/LoRA/sampler/step settings, dimensions, chunk count/duration, elapsed time, and observed result. Inspect embedded workflow metadata when present.
- Do not globally replace `PackedLayout`, `MiniMaxH3.extra_conds`, or other ComfyUI classes.
- Keep SageAttention, Sol-Attn, and Spectrum external; integrate through public ComfyUI wrappers and H3 payload contracts.
- Preserve the identity of `layout.position_ids` when changing MM-RoPE coordinates.
- Never silently resize a continuation State or Session to a different resolution.
- Unknown H3 layout contracts must fail clearly instead of rendering a subtly incorrect join.
- State and Session files remain safetensors + JSON and are written atomically.
- UI nodes call reusable non-UI modules. Legacy nodes and V3.4 must share temporal, state, continuation, and layout logic where their contracts overlap.
- V2 must not decode Video/Audio VAE between H3 chunks.
- Accepted full chunk latents remain on CPU; do not accumulate generated chunks in VRAM.
- Spectrum history must remain run-scoped through its public sampler wrappers; never import Spectrum private runtime functions.
- Changes must preserve V1 node identifiers and State schema unless an explicit migration is included.

## Project files

- `AGENTS.md`: durable rules and prohibitions only.
- `PROJECT_STATE.md`: current paths, version, active direction, and known gaps.
- `WORKLOG.md`: append-only summaries of completed work and evidence.
- Do not duplicate long history across these files. Update `PROJECT_STATE.md` when facts change and append one concise entry to `WORKLOG.md` after completed work.

## Validation

```bash
powershell -ExecutionPolicy Bypass -File tools\validate.ps1
```

Runtime installer verification must check native PackedLayout behavior and all registered nodes.

GPU checks must cover Sage only, Sage+Sol, Sage+Spectrum, and Sage+Sol+Spectrum with identical prompts and seeds. V2 must also be compared against the equivalent V1 3×5-second graph.

## Reusable local environment

- Source repository: `D:\Codex\_git_push_work\ComfyUI-H3-Continuum`
- Primary tested runtime: `D:\StabilityMatrix\Data\Packages\ComfyUI_W\custom_nodes\ComfyUI-H3-Continuum`
- Secondary runtime: `D:\StabilityMatrix\Data\Packages\ComfyUI_WAN\custom_nodes\ComfyUI-H3-Continuum`
- Reuse the repository's existing pytest configuration and helper scripts instead of rediscovering paths on every task.
- Read this file before each task. Record durable project decisions, paths, commands, failure causes, and validation methods here so later work reuses them instead of restarting from zero.
- GitHub authentication for this repository is already configured. Do not request a new login or token unless an actual authentication command fails.
- Commit and push only when the user explicitly requests publication.
