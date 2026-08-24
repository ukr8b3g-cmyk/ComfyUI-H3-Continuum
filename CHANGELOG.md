# Changelog

## 3.5.0

- Added `H3 Continuum Sampler V3.5` with a Continuum-aware refine-context output while preserving the V3.4 sampler path.
- Added `H3 Continuum Second Pass V3.5` as the advanced bridge for externally processed H3 video latents, including physical-group and Long Terminal Merge preservation.
- Added experimental `H3 Continuum Hi-Res Fix V3.5`, using a bounded pixel/VAE resize round trip before low-denoise Second Pass sampling.
- Added `H3 Continuum Latent Resize V3.5` as an advanced utility; direct high-ratio latent interpolation is not the recommended main Hi-Res Fix path.
- Added `H3 Continuum Assemble + Seam V3.5` with Auto, RAM, and Windows-safe disk-backed video buffers while keeping audio in RAM.
- Added the recommended V3.5 template workflow with optional Hi-Res Fix, Auto assembly, shared still-image megapixel sizing, and separate VHS Video Reference sizing.
- Preserved Exact Duration, seam behavior, physical decode-group ordering, first-pass audio passthrough, and external Core VAE Decode contracts.
- Kept V3.4 nodes and saved-workflow compatibility unchanged.
- Validated a 9.49 GiB final IMAGE with hash-identical RAM/Disk-backed output and approximately 9.50 GiB lower Windows private memory in Disk-backed mode.
- GPU-accepted the integrated 1x5 576-to-1152 Main path and Hybrid/Reference 1x5 paths; documented that the 3x5 2x terminal 77T group exceeds the tested RTX 5060 Ti 16 GiB.

## 3.4.0

- Completed the V3.4 runtime path from the public sampler through V3/V2 to `run_sequence()`.
- Added Driving Audio with absolute-time guide slices while preserving the original source for final output.
- Added persistent Video Reference conditioning with Efficient 0.4 MP, Balanced 0.6 MP, and Match Output modes.
- Included Driving Audio and Video Reference identities in Run Storage contracts.
- Changed malformed or empty prompts to warning-and-fallback behavior instead of stopping generation.
- Removed independent compatibility, model, and upstream-node restrictions that were stricter than ComfyUI Core.
- Added V3.4 runtime, driving-audio, and context diagnostics coverage.

## 3.3.0

- Promoted Timeline Video to a stable public node with chunk-local slicing and a 0.4 MP default.
- Added `H3 Continuum Assemble + Seam` with stable Audio Seam Auto and guarded Video Seam Auto defaults.
- Kept `Auto 2` as an experimental exposure-ramp extension without widening the visible option label.
- Added native Reference Audio conditioning and retained up to three ordered Reference Images.
- Preserved stable sampler Node IDs, Run Storage compatibility, Core VAE decode, and Spectrum Interop API v1 Actual Prefix 2 behavior.
- Added consolidated runtime validation results and documented known Timeline Video and Auto 2 limitations.

## 3.2.4

- Added native MiniMax H3 Reference Audio 1 conditioning with deferred Audio VAE encoding.
- Matched Core's permissive prompt handling by warning instead of stopping on unavailable Picture or Audio tags.
- Matched Core's dynamic Reference behavior by compacting active image inputs into Picture 1 through Picture N.
- Kept Sampling, Continuation, Spectrum Interop, external Core VAE Decode, and assembly semantics unchanged.

## 3.2.3

- Formalized the third ordered Reference Image as a compatibility-preserving extension.
- Kept V3.2.2 zero, one, and two-image Reference Contract JSON unchanged.
- Added Image 3 shape, dtype, exact SHA-256, position, and preprocess metadata only for three-image runs.
- Added Golden Contract and Revision identity regression coverage for V3.2.2 saved runs.
- Kept Sampling, Continuation, Spectrum Interop, Core VAE Decode, and assembly semantics unchanged.

## 3.2.2

- Allowed Ref2VA, FL2VA, and unverified checkpoints with Reference conditioning.
- Kept checkpoint classification as diagnostics without automatic MODEL switching.
- Kept Strict Compatibility for genuinely unsafe or unsupported H3 contracts.

## 3.2.1

- Declared V3.2.1 stable after GitHub Actions, Windows Ref2VA generation, Spectrum Actual Prefix 2, chunk integrity and complete Auto Resume passed.
- Added T2VA, First/Last Frame, FL2VA and persistent two-image Reference conditioning to the production sampler.
- Added crash-safe raw AV Run Storage, automatic resume, deterministic Revisions and partial regeneration.
- Combined ordered upstream graph fingerprints with runtime MODEL/CLIP/VAE weight probes for fail-closed reuse.
- Added per-chunk SHA-256 verification and rejected Regenerate From when Run Storage is disabled.
- Added official MiniMax H3 Sigma Shift graph-contract support.
- Updated CI dependencies, Windows runtime verification and package metadata for V3.2.1.
- Standardized project licensing as MIT.
- Kept sampling, Continuation, Spectrum Interop and external Core VAE decode semantics unchanged.

## 2.1.7

- Added the compact static `H3 Continuum Sampler` facade over the unchanged V2 execution core.
- Added Clip Overrides, Advanced, and Result pack helper nodes.
- Preserved `H3ContinuumSamplerV2` as a Legacy/Core workflow compatibility node.
- Removed the frontend display controller and all dynamic socket, proxy-widget, DOM, resize, and serialization workarounds.
- Kept State, Session, Prompt Plan, Sampling, Native Continuity, and Spectrum Interop contracts unchanged.

## 2.1.6

- Rebuilt the Sampler V2 frontend as one Vue-aware display controller.
- Removed the Individual Clip Overrides accordion; only active Clip Prompt sockets are shown.
- Kept connected out-of-range Clip Prompt sockets visible when chunks is reduced.
- Added one Advanced Settings control; connected advanced sockets stay visible while collapsed.
- Removed fixed node-height handling and all input/output add/remove UI folding.
- Kept backend socket/widget order, types, serialization, State/Session/Prompt Plan schemas, sampling, and Spectrum Interop unchanged.
- Exposed show_preview as a per-node basic control and removed the duplicate global preview setting.

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
