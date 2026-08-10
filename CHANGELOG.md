# Changelog

## 2.1.4

- Make the integrated V2 sampler the only primary Continuum workflow node.
- Mark V1 building blocks and auxiliary plan/state nodes as deprecated Legacy nodes while preserving saved-workflow identifiers.
- Collapse continuation, session, prompt-plan, diagnostics, and advanced generation controls by default.
- Automatically expose Advanced settings when an existing workflow has an advanced connection.
- Preserve output ordering, State/Session schemas, sampling, and accelerator behavior.

## 2.1.3

- Added one stable external `Sequence Prompt` STRING socket for the complete sequence.
- Added `Auto / Fixed / List / Timeline` Prompt Format selection without changing socket connections.
- Added deterministic Auto detection for `---` lists and `[0-5s]` / `[Chunk 1]` timeline sections.
- Kept individual `Clip N Prompt` inputs as optional overrides, collapsed by default while preserving connected legacy sockets.
- Preserved connected Prompt Plan and saved prompt widget fallbacks without changing Prompt Plan schema.

## 2.1.2

- Added fail-closed Native Continuity preflight for raw AV tails, native video-cycle phase, signed 40/24 audio-grid placement, finite Context tensors, and packed Context/Target row separation.
- Added branch-local immutable PackedLayout signatures on native Actual calls while allowing Spectrum Forecast calls to bypass native layout execution.
- Added per-chunk MODEL copy-on-write isolation so Spectrum runtime history, archives, and disable state cannot leak between chunks.
- Added read-only Spectrum Interop API v1 hints only when a valid previous Context exists; initial chunks emit no hint.
- Added Spectrum-compatible Actual Prefix 2 requests with strict metadata types, invalid/unknown fail-open behavior, total-step clamping, and no prefix during offline replay.
- Preserved State, Session, Prompt Plan, Seam Correction, node identifiers, and the raw-latent-only continuation path.

## 2.1.0

- Added opt-in `Seam Correction: Off / Basic` while preserving the complete V2.0.2 decode path for `Off`.
- Added normalized CPU-only video seam scoring and conservative adaptive cuts from 0 to 3 frames before the legacy boundary.
- Added bounded luminance gain, chroma bias, and motion-aware 0–2 frame cosine blending with score-based rollback.
- Added boundary-local stereo-safe audio correlation alignment, level/DC guards, and 10–60ms equal-power crossfades without shifting the following clip.
- Added legacy, cut, and corrected seam scores plus video/audio decisions to Basic and Full diagnostics.
- Added boundary-level fallback without changing Sampling, Context, State, Session, Prompt Plan, V1 nodes, or accelerator composition.

## 2.0.2

- Added external `Clip N Prompt` STRING inputs for 1–16 chunks, intended for ComfyUI's `Text (Multiline)` node.
- Made the visible prompt inputs follow the `chunks` widget while preserving the internal Fixed/List/Timeline values as a legacy fallback.
- Added deterministic per-clip prompt overrides with regenerated prompt hashes and unchanged Prompt Plan schema.
- Added `Settings > H3 Continuum > Preview > Show latent preview`, enabled by default.
- Kept latent-preview control out of the sampler UI and passed the setting to the existing sampling callback without changing final AV output.
- Added regression coverage for selective external prompt overrides, hashes, and the 16 connectable prompt inputs.
- Preserved all V1/V2 node identifiers and State, Session, and Prompt Plan schemas.

## 2.0.1

- Fixed the bundled V2 example workflow widget serialization for `base_seed` with `control_after_generate`.
- Added an in-memory migration guard for the malformed 2.0.0 example where later widgets were shifted by one slot (`diagnostics` arrived as `0`).
- Preserved valid 2.0.0 workflows and all V1/V2 node identifiers and schemas.
- Added regression coverage for the legacy shifted-widget signature.

## 2.0.0

- Added production **H3 Continuum Sampler V2** for integrated N-chunk generation.
- Kept the V1 continuation algorithm and all V1 node identifiers unchanged.
- Added Fixed, List, and Timeline prompt planning plus a connectable Prompt Plan node.
- Cached each unique Qwen prompt conditioning before H3 sampling.
- Reused one externally accelerator-patched MODEL, sampler, and sigma schedule across all chunks.
- Deferred Video/Audio VAE decoding until every H3 chunk finished.
- Captured full raw AV chunk latents and next-state tails on CPU before decoding.
- Removed the second device-to-host state transfer by deriving next-state tails from committed CPU entries.
- Added conservative latent-motion Auto Context selection with 5/22/39-frame profiles.
- Added deterministic independent 64-bit per-chunk seeds and reroll nonces.
- Added V2 Session resume, accepted-prefix reuse, branch-safe reroll, and atomic safetensors/JSON persistence.
- Added exact cumulative audio sample-boundary assembly to prevent long-chain rounding drift.
- Added exact total-duration correction.
- Added single-allocation decoded IMAGE assembly and preflight RAM safety checks.
- Added Basic and Full diagnostics, including video overlap MAE/PSNR and audio correlation/boundary jump.
- Added optional V1 State entry point and V2 Session-to-V1 State conversion.
- Added V2 public API modules and regression/orchestration tests.
- Updated installer runtime verification for all ten registered nodes.

## 1.0.1

- Fixed a false strict-compatibility failure when Sol-Attn wraps MiniMax H3
  `PackedLayout.__init__` with `*args` / `**kwargs` for Morton/span tracking.
- Strict checking still fails closed when the native H3 constructor genuinely
  removes required positional or keyword capabilities.
- Added regression tests for the native signature, Sol-Attn forwarding wrapper,
  and a genuinely incompatible constructor.

## 1.0.0

- Added **H3 Continuum Join** for initial and continuation clips.
- Added direct native video/audio latent state capture with 5/22/39-frame profiles.
- Represented continuation history as one native H3 `video` / `video_audio` reference block.
- Added Finish, Assemble, atomic State Save/Load, signed audio-grid offsets, in-place MM-RoPE adjustment, strict compatibility tests, and accelerator composition.
