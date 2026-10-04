# Changelog

## 3.9.1 — stability fixes (2026-10-04)

- Preserve audio-only and mixed Second Pass keyframes while spatially adapting only video.
- Use Sampling Contract v6 / Graph Contract v4 for safe Take reuse, including sampler closures and MODEL CFG/wrappers. Keep v5 history readable without adopting its prefixes into v6 generation or rewriting old manifests.
- Slice Review Driving Audio once from physical-group natural time; use Core resampling and document explicit Reference Encode Cache invalidation for direct VAE weight mutation.
- Match V3.9 partial Review conditioning and Reference routes to actual output-group identities before Second Pass. Preserve complete-run behavior, original audio LATENT objects and saved Takes.
- The repaired runtime passed 1696 CPU cases (1 skipped) and three targeted 512×512 Review Second Pass GPU cases. Browser acceptance remains pending. Optional latent-upscale doubled outlines are tracked separately in Issue #27 and are not a required gate for this stabilization.
- Bump package metadata to 3.9.1 while preserving V3.9 public node IDs, widget order and official workflows. Restart ComfyUI and refresh the browser after updating. Keep historical V3.8 releases untouched; this patch adds no LoRA Plan. Versioned source downloads are provided through GitHub Releases; Registry publication is separate.

## 3.9.0 — V3.9 source on main (2026-09-29)

- Publish the separate V3.9 Sampler and nine-slot Reference Images V3.9 helper with fixed `@R1`–`@R9` identities and All / Per chunk assignments. V3.8X2 keeps its existing Sampler and Reference connections; saved Runs/Takes are not automatically migrated.
- Ship the user-selected V3.9 workflow JSON unchanged, a V3.9-only workflow ZIP, and a combined V3.8X2/V3.9 workflow ZIP. The ComfyUI Templates gallery exposes both separate workflows.
- Promote package metadata and startup version to `3.9.0`. Keep historical Releases/tags untouched. This main-source commit is not a new GitHub Release or Registry publication; browser save/reload and the unchanged default template's GPU acceptance remain separate gates.

## V3.9 development history — Reference Images in-node UI (2026-09-27)

- Add a separate nine-slot Reference Images V3.9 helper with fixed `@R1`–`@R9` IDs, in-node All chunks / Per chunk table, and one typed connection to the V3.9 Sampler. Both choices use the existing group-effective routing engine; disconnected or unassigned slots do not renumber later images.
- Supply a separate V3.9 workflow JSON/ZIP and user guide. V3.8 Sampler and V38X2 workflow JSON/ZIP remain unchanged. Older V3.9 prototype graphs require manual rewiring and saved Runs/Takes do not migrate automatically.
- Local CPU `1530 passed / 1 skipped / 0 failed`, frontend Reference Images and Review Queue contracts, and standalone runtime verification passed. Live-browser and GPU acceptance of this new helper/UI remain pending. No commit, push, Release or Registry publication.
- Rebase the separate V3.9 JSON/ZIP on the supplied V38X2+Decode Cache Helper workflow, preserving its appended Repeat Reference video setting, media loader values, Image bypass and Decode Cache Helper. Route Reference Images 1–9 through the new helper; keep all other graph nodes and settings unchanged. Restart ComfyUI fully after updating to load the new node schema.

## Prior local prototype — V3.9 Reference Routing RR-R6B (2026-09-25)

- Add a separate V3.9 Sampler ID with default All (unchanged V3.8 Reference path) and opt-in Custom R1–R9 per-chunk selectors. Keep the V3.8 schema/widget order and official V3.8X2 workflow files unchanged.
- Carry the frozen RR-R5 group contract to a read-only, post-Queue Plan Inspector. Pending groups remain configured/unverified; accepted groups display backend-verified generated/reused status, effective Picture mapping, SHA and warnings.
- Capture matching group-local routed conditioning in same-Queue Refine Context; Second Pass distinguishes verified Reference inheritance from prompt-only fallback. No cross-session reconstruction is claimed.
- Local full CPU: `1524 passed / 1 skipped / 0 failed`. RR-R6 GPU/API integration passed 11 Queues, including Review Q1–Q3, Second Pass, and the Sage/Sol/Spectrum wrapper matrix. The subsequent real-browser B0–B5 Review, completion, and save/reload gate passed using a corrected Ref2V 8-step LoRA / eight-step workflow; this is not a six-step rerun. Subjective identity and long-form image quality remain ungraded.
- V3.8X2 workflow JSON/ZIP and the V3.8 Sampler remain available. V3.9 `All` uses the V3.8 shared-reference path; changing to V3.9 `Custom` is a manual workflow change and does not automatically migrate an accepted Run or Take.
- The planned separate V3.8X2 tag/Release and `release/3.8x2` maintenance branch have not been created. V3.9 workflow, commit, push, Release, and Registry publication remain pending.

## Experimental on main — Unified Timeline Video (2026-09-22)

- Opt-in Follow Timeline / legacy-compatible Repeat Reference on the existing IMAGE input.
- Per-physical-group reference selection; source-end fallback; distinct interval VAE keys and local prompt caches.
- Local acceptance passed: full CPU `1424 passed / 1 skipped / 0 failed`, browser save/reload, and Follow/Repeat `2 × 5 s` GPU runs at 704×416/24fps with synchronized 10-second audio/video, mode separation, and no OOM/NaN/crash. This remains Experimental and is not a frame-perfect motion-copying or long-video RAM-optimization claim.

## Unreleased — Loader persistence repair (2026-09-21)

- Repair Issue #23 by delegating inherited native mode accessors; preserve Enable Image and remove draw/save-time widget collection replacement.
- Switch the two paired official V3.8X2 workflows to Core Load Audio and Core Load Video plus an Enable-free H3 Continuum Video Adapter using the existing FPS converter.
- Keep old Audio/Video IDs as deprecated compatibility nodes. Preserve other workflow nodes, settings and output contracts; regenerate matching ZIPs and integrity hashes.
- Add store-backed loader and converter regressions. Windows/browser acceptance remains a separate pending check; no Release/tag/Registry publication.


## 3.8.3 — V3.8X2 release preparation (2026-09-19)

- Vendor the previously standalone Decode Cache Helper implementation into Continuum as a separate `H3DecodeCacheHelper` public node. Preserve its node ID, inputs, outputs, list behavior, native Core Decode delegation, and process-local cache behavior.
- Add `H3 Continuum Reference Images` for optional Reference Images 4–9 while retaining the Sampler's direct Reference Images 1–3 and existing 0–3 image workflows.
- Keep Sampler, Finalize, Assembly Plan, Core Decode and existing V3.8X widget/socket contracts unchanged.
- Add the accepted workflow under two official distribution names: `MiniMax_H3_Continuum_V38X2` and `MiniMax_H3_Continuum_V38X2+Decode_Cache_Helper`. The files contain the same graph and are not separate workflow variants.
- Document the nine-reference GPU/RAM gate and recommend pre-scaling large reference sources to about 0.30 MP when using all nine on a 16 GB GPU.
- Clarify that Decode Cache Helper speeds only repeated Decode of unchanged latents. It does not speed Sampling, a first MISS may be slower, and the measured 20%+ reductions are configuration-specific rather than a general guarantee.

## 3.8.1 — V3.8X release candidate (2026-09-15)

- Promote the accepted R0–R6 Runtime Redesign and final local GPU Functional Gate to the V3.8X (`3.8.1`) release candidate.
- Rename the current supplied Spectrum workflow to `MiniMax_H3_Continuum_V38x.json` and its matching ZIP. The JSON and ZIP remain byte-for-byte paired; the graph is unchanged.
- Preserve old V3.8.0 installation through the existing `v3.8.0` Git tag. Do not mix its workflow with V3.8X; use the matching tag/package for an older saved workflow.
- No new public node, socket, widget-order, Sampling, Review, or Run Storage contract is introduced by this release label.
- Compatibility note: validated V3.8X with external ComfyUI-Spectrum-MiniMax-H3 v0.2.27 in a Sage + Spectrum 3 x 5-second run. It completed without the previous `aimdo memory compile error`; decoded video/audio integrity and chunk-boundary checks passed. This relies on Spectrum's own v0.2.25+ AimDo malloc-graph fix; Continuum does not vendor or modify Spectrum.

## Unreleased — V3.8.x release hygiene (2026-09-14)

- Updated the canonical V3.8 workflow to remove both `easy cleanGpuUsed` nodes. First Image now connects directly to the Sampler, and Core Create Video connects directly to Core Save Video; ComfyUI-Easy-Use is no longer a workflow dependency.
- Fixed the shipped legacy `v3.reference_video` module to import the shared temporal helper from the package root.
- Hardened the Windows installer: validate and copy only the Registry Manifest payload, and move previous installations to a backup directory outside `custom_nodes`.
- No Sampling, Review, or Run Storage behavior is changed by these release-hygiene repairs.

## 3.8.0 — Review UI hotfix on main (2026-09-08)

- Withdraw stale Continue/Retry/Finish actions after local or connected generation inputs change. A stale queued Retry falls back to normal backend compatibility/reuse checks instead of targeting an incompatible saved review.
- Add the frontend-only `Start again from Chunk 1` action: use existing non-destructive branch controls, preserve saved Takes, and consume the restart selection once after Queue.
- Preserve explicit Regenerate From boundaries instead of resetting them when a Review action is clicked. Preserve normal continuation, completed review, history and serialized widget order.
- No sampling, audio, continuation transport, workflow or public Python schema change. The separate 15-second Review static/noise report remains unresolved. This main-branch hotfix is not a new Registry publication or release asset.

## 3.8.0

### Added

- Established the seven-node V3.8 public surface: Sampler V3.8, Finalize, Load Image, Load Audio, Load Video, Second Pass, and the modular Reference Audios helper. Unreleased Easy facade prototypes remain in source but are not registered.
- Added `H3 Continuum Sampler V3.8` with shared `Draft` 0.30 MP, `Balanced` 0.60 MP, `Native 768`, and `Custom MP` resolution presets.
- Added `Review Each Chunk`, `Continue / Next`, `Regenerate Current`, and `Finish Remaining` controls backed by Run Storage review branches and canonical-head recovery.
- Publish one user-supplied V3.8 Spectrum workflow as matching JSON and ZIP. It requires Spectrum, rgthree, and KJNodes; the same graph can be switched to a task-matched LightX2V Turbo LoRA.
- Added Continuum Image, Audio, and Video loaders with explicit native bypass behavior for optional workflow inputs.
- Added `H3 Continuum Reference Audios`, which bundles up to three ordered Core-native standalone audio references behind one appended V3.8 Sampler socket while preserving the legacy single-reference path.
- Replaced the Main `Landscape / Portrait / Square` choice with a two-path `Size Source`: preserve the connected First Image aspect at the selected preset, or enter an exact aligned Manual Width and Height.

### Improved

- Integrated Driving Audio with Review, Smart Regenerate, Finish Remaining, and restart persistence.
- Preserved FL2VA Long Terminal Merge as one atomic physical review unit, including Smart Regenerate of the complete terminal pair.
- Reused one resolution resolver across Easy and normal V3.8 samplers while leaving the V3.7 schema and Production path unchanged.
- Extended Run Storage with Review lifecycle metadata, prefix reuse, nonce branches, and latest canonical-head restoration without changing the sampling identity contract.
- Added a frontend-only `Basic / Production` node property for Sampler V3.8. It changes presentation only and preserves the Python schema, widget order and values, backend inputs, Sampling identity, and Run Storage identity.
- Added Registry packaging rules that exclude tests, tools, diagnostics, Labs assets, and historical workflows while retaining all runtime-imported implementation modules.
- Kept the old V3.8 Aspect input as a hidden compatibility field. Saved Auto workflows migrate to First Image, while saved Landscape, Portrait, and Square workflows migrate to the same resolved Manual canvas.

### Notes

- Second Pass / `refine_context` is not supported on a partial Review sequence. Complete Review before running Second Pass.
- The 16GB GPU Gate passed with small headroom: Strict Minimal peaked at `14.96 GiB`, and complex accepted gates reached about `15.5-15.6 GiB`. Results vary by environment and are not a universal 16GB guarantee.
- Still Image Guide remains Experimental. V3.7 and earlier Node IDs are not exported by V3.8; workflows using them can appear with unknown nodes and should be opened with the matching historical Release/tag.

## 3.7.0

- Added `H3 Continuum Sampler V3.7` with one optional Still Image Guide input while preserving the V3.6 required-input schema, Production defaults, and saved-workflow compatibility.
- Generalized the Second Pass Conditioning Adapter so First/Last images, continuation context, and an owned Still Image Guide can be rebuilt at target latent geometry. Physical-group and Long Terminal Merge ownership remain intact.
- Added the internal schema-v1 `RefineSchedule` contract with `External`, `Full`, `Tail`, and `Partial` modes. Existing SIGMAS input remains compatible, and Tail/Partial use exact ranges from the source schedule.
- GPU-validated the internal Tail 6 suffix at 704×704 against the prior external Tail 6 path, with decoded Video SSIM `0.982936` and bit-exact decoded Audio PCM.
- Completed a 1152×1152 Conditioning correctness gate in which the original Still Image Guide source was reencoded at target geometry without changing the first-pass Audio contract.
- Added explicit source-role ownership so a Still Guide sharing the same frame as First/Last is not replaced by the endpoint image, and restricted Still Image Guide input to exactly one IMAGE.
- Added V3.7 compact-frontend parity for project identity, hidden internal widgets, Run Storage controls, queue normalization, diagnostics, and permanent Reference Audio sockets.
- Kept Still Image Guide **Experimental / Production HOLD**. Core hard-anchor semantics can cause an abrupt trajectory change at the Guide frame and redirect later motion; it is not a smooth transition control.
- Preserved V3.6/V3.5/V3.4 node IDs, public Second Pass schemas, Core PackedLayout/RoPE construction, Run Storage compatibility, and Production generation defaults.

## 3.6.1

- Canonicalized an absent Last Frame hash as `""` and added a narrowly scoped compatibility path for V3.6.1 caches whose old final chunk stored `"none"`. Extending a normal no-Last-Frame run from two to three chunks now reuses both stored chunks, while a real Last Frame and Long Terminal Merge still invalidate/regenerate their required sampling units.
- When Run Storage is turned Off, the compact frontend now resets hidden `Regenerate From` to `Auto` and `Variation Nonce` to `0`; the backend rejection remains as a non-UI safety check.
- Added non-blocking mixed Prompt syntax diagnostics. Timeline mode now ignores standalone `---` separator lines with `H3C-P105`, while preserving existing uncovered-chunk fallback and Fixed-prompt fail-open behavior.
- Prevented V3.6 Standard continuation from stopping when Audio Continuity is enabled with Fast 5, Strong 39, or Auto. These modes now resolve to the accepted Reference Context transport before Run Storage identity is created; Balanced 22 continues to use Masked AV.
- Kept Standard with Audio Continuity disabled on Masked Video, and kept Compatibility on Reference Context for every Continuity mode.
- Added explicit resolved-transport diagnostics without rewriting the user's Backend or Continuity selections.
- Preserved V3.5.3/V3.4 nodes, Sampling, Terminal Merge, Assembly, Seam, Run Storage schema, and saved-workflow compatibility.

## 3.6.0

- Added `H3 Continuum Sampler V3.6` with Standard Masked AV continuation. Prior finalized Video/Audio prefixes are preserved inside the next H3 target with Core noise masks instead of being appended as duplicate Reference rows.
- Retained `Compatibility` as an Advanced fallback to the V3.5 `Reference Context` transport. Internal transport identifiers are not exposed in the public UI, and all V3.4/V3.5 node IDs and saved workflows remain loadable.
- Scoped Run Storage identity and Sampling Contract execution semantics by nondefault continuation backend, preventing Reference and Masked chunks from being mixed while preserving legacy Reference revision identity.
- Preserved Long Terminal Merge as one physical sample during resume and `Regenerate From`; logical chunks `[2,3]` are never split or partially reused.
- Extended the shared V2/V3 `chunk_seconds` range to 4–30 seconds with a 5-second default and 0.1-second step. The 5–15 second range remains recommended and validated; longer high-resolution chunks can substantially increase VRAM and runtime.
- GPU-accepted T2VA, I2VA, Reference Image + Reference Audio, Balanced 22f/37T Joint AV, and 3×5-second FL2VA Long Terminal Merge Masked continuation. Protected Video/Audio prefixes finalize bit-exact, and the accepted PIG-3 audio output passed subjective listening.
- Measured the accepted FL2VA Terminal Group 2 path at 8.01% fewer packed rows and a 4.06% lower median Sampling time than Reference Context in the tested paired runs. These are environment-specific measurements, not universal speed guarantees.
- Preserved V3.5 Second Pass, Hi-Res Fix, Conditioning Bridge, disk-backed Assembly, Prompt/CLIP cache, Video Guide optimization, V3.4 compatibility, and existing Audio/Video Seam algorithms.

## 3.5.3

- Repaired the public Conditioning Bridge workflow's Width/Height input slots and added serialization-integrity checks for every published workflow.
- Removed stale orphan link IDs from the public V3.4, V3.4 Turbo, and V3.5 workflow files.
- Corrected Hybrid First/Last + Reference warning messages so public `<Picture N>` numbering remains absolute and matches the accepted runtime behavior.
- Losslessly re-encoded one unreferenced legacy PNG that strict image decoders could not read.
- Preserved all V3.5.2 generation, Sampling, Conditioning, Terminal Merge, Assembly, Seam, Run Storage, Prompt/CLIP cache, Video Guide optimization, and V3.4 compatibility contracts.

## 3.5.2

- Added a conservative V3.5-only Prompt/CLIP cross-run LRU cache for unchanged T2VA, I2VA, and FL2VA conditioning. Reference, scheduled, tokenizer-option, and hook-modified CLIP paths bypass the cache; V3.4 is unchanged.
- Verified cache HIT execution with `encode_calls=0` and bit-identical decoded video and audio PCM. The optimization removes repeated Prompt/CLIP work only; Sampling still runs normally.
- Reduced long Video Guide preprocessing memory by hashing and finite-checking the complete source in eight-frame CPU chunks while retaining only the prefix required by H3 conditioning.
- Preserved the exact Video Guide source SHA-256, Run Storage identity, `17k+5` frame alignment, final-frame padding, VAE input, Qwen input, Sampling seed, decoded video, and decoded audio.
- Measured the deterministic CPU comparison at approximately 71% lower additional peak RSS (`396.8 MiB` to `114.7 MiB`) and 59% lower retained storage (`225 MiB` to `93 MiB`) with effectively unchanged preprocessing time.
- Completed the Phase 3/4 performance and feature-overhead audit. No speculative Sampling, Driving Audio lazy-decode, Audio hash, Assembly, Seam, Session, or V3.4 optimization was adopted.
- Preserved all V3.4/V3.5 node IDs, backend socket keys, saved-workflow compatibility, Sampling, Conditioning, Terminal Merge, Assembly, Seam, and Run Storage contracts.

## 3.5.1

- Added `H3 Continuum Conditioning Bridge V3.5`, exposing one complete Core-compatible MODEL and CONDITIONING object per Continuum physical group without flattening CONDITIONING entries.
- Added optional standalone Reference Audio conditioning to Sampler V3.5. Its two Python-defined sockets remain permanently present; the frontend no longer adds/removes them or serializes a visibility-only widget, preserving workflow widget alignment on save/reload.
- Removed the experimental Last Queued Seed override and restored standard ComfyUI `control after generate` behavior for the V3.5 sampler.
- Renamed the displayed video-guide inputs to `Video Guide Frames` and `Video Guide Size` to distinguish a video loader's IMAGE frame batch from still Reference Images. Backend input keys and saved-workflow links are unchanged.
- GPU-accepted Conditioning Bridge generation, Reference Audio/Image retention, and the V3.5 Second Pass/Hi-Res paths while preserving physical-group, Terminal Merge, Run Storage, and audio contracts.

## 3.5.0

- Added `H3 Continuum Sampler V3.5` with a Continuum-aware refine-context output while preserving the V3.4 sampler path.
- Added `H3 Continuum Second Pass V3.5` as the advanced bridge for externally processed H3 video latents, including physical-group and Long Terminal Merge preservation.
- Added experimental `H3 Continuum Hi-Res Fix V3.5`, using a bounded pixel/VAE resize round trip before low-denoise Second Pass sampling.
- Added `H3 Continuum Latent Resize V3.5` as an advanced utility; direct high-ratio latent interpolation is not the recommended main Hi-Res Fix path.
- Added `H3 Continuum Assemble + Seam V3.5` with Auto, RAM, and Windows-safe disk-backed video buffers while keeping audio in RAM.
- Added the recommended V3.5 template workflow with optional Hi-Res Fix, Auto assembly, shared still-image megapixel sizing, and separate Video Guide Frames sizing.
- Preserved Exact Duration, seam behavior, physical decode-group ordering, first-pass audio passthrough, and external Core VAE Decode contracts.
- Kept V3.4 nodes and saved-workflow compatibility unchanged.
- Validated a 9.49 GiB final IMAGE with hash-identical RAM/Disk-backed output and approximately 9.50 GiB lower Windows private memory in Disk-backed mode.
- GPU-accepted the integrated 1x5 576-to-1152 Main path and Hybrid/Reference 1x5 paths; documented that the 3x5 2x terminal 77T group exceeds the tested RTX 5060 Ti 16 GiB.

## 3.4.0

- Completed the V3.4 runtime path from the public sampler through V3/V2 to `run_sequence()`.
- Added Driving Audio with absolute-time guide slices while preserving the original source for final output.
- Added persistent Video Guide Frames conditioning with Efficient 0.4 MP, Balanced 0.6 MP, and Match Output modes.
- Included Driving Audio and Video Guide Frames identities in Run Storage contracts.
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
