# Work Log

## 2026-08-24 - V3.5.1 Issue #9 Conditioning Bridge CPU implementation

- Preserved all Issue #10 changes and created accepted pre-change snapshots: `pre-issue9-conditioning-bridge-source-accepted-20260824_190823` (460 files) and `pre-issue9-conditioning-bridge-runtime-w-accepted-20260824_190823` (337 files), excluding top-level `.git` and the pre-existing inaccessible `.pytest_cache`.
- Added `H3ContinuumConditioningBridgeV35` as an Advanced MODEL + CONDITIONING interoperability node. It exposes one aligned pair per Continuum physical group, preserves complete CONDITIONING inner lists, updates target geometry, and explicitly leaves AV LATENT/noise/Audio Lock behavior to the external workflow.
- Extracted shared physical-group preparation from Second Pass. The built-in path consumes each prepared group immediately, so its prior group-by-group sampling order and low-memory behavior remain intact; no V3.4 sampling, conditioning, Terminal Merge, Assembly, Seam, or Run Storage code was changed.
- Added schema, registration, 37T + 77T Terminal Merge alignment, target geometry, context identity, and non-flattening regressions. Focused result: `33 passed`; full source pytest: `442 passed`; only the known `pynvml` FutureWarning remains.
- Synchronized only `nodes.py`, `v3/second_pass.py`, `v3/conditioning_bridge_nodes.py`, and `tools/verify_runtime.py` to ComfyUI_W and verified per-file SHA-256 equality. Runtime verification passed package 3.5.0 registration, native PackedLayout, and Fixed 3x5 planning with the Bridge visible as a current node. The 163-entry distribution Manifest validates completely.
- GPU Basic Guider / external sampler acceptance remains pending. Commit and push were not performed.

## 2026-08-24 - V3.5.1 Issue #10 Reference Audio CPU implementation

- Preserved the V3.4 public schema and added only internal V3.4 forwarding parameters plus two V3.5 optional sockets: `Reference Audio` and `Reference Audio VAE`.
- Reused the existing Production/Core-compatible Reference Audio path without duplicate preparation or encoding. Standalone Reference Audio 1 is the only V3.5.1 scope; generated audio remains final unless the separate Driving Audio path is connected.
- Added regressions for socket append-only compatibility, published V3.5 template routes, unused-VAE behavior, required VAE validation, Run Storage revision separation/restoration, and Reference Audio retention in normal and Terminal Merge refine-context groups.
- Verified snapshots: `pre-v351-reference-audio-source-verified-ee7b993-20260824_171013` (457 files) and `pre-v351-reference-audio-runtime-w-verified-20260824_171013` (336 files), both with zero SHA-256 mismatch. Earlier standard-script attempts are incomplete because the pre-existing `.pytest_cache` ACL denies traversal.
- Source focused regression `62 passed`; full pytest `439 passed`. ComfyUI_W received one preserved-tooltip Production merge plus three related tests; runtime focused result is `41 passed, 1 skipped`, syntax and runtime verifier PASS. The skip is only the public workflow-route test because `examples/workflows` is not installed in that runtime copy.
- GPU tests 1-4 and required normal/Terminal long-form cases remain pending. Package version and public README remain V3.5.0.
- User authorized publication. To avoid pushing the canonical branch's four private/local commits, copied only Production, three regression files, and Manifest into the clean isolated clone at public `origin/main`. Regenerated the 161-entry Manifest from public Git index blobs, correcting 36 pre-existing public-tree hash mismatches. Full isolated-clone pytest remained `439 passed`; commit `a704aa961fc2ba0c19aef6f2ecfdcb46fa9384b2` was pushed and remote-read back exactly.

## 2026-08-24 - V3.5 recommended template workflow

- Added `examples/workflows/MiniMax_H3_Continuum_V35.json` as the recommended V3.5 template while retaining every V3.4 template.
- Verified the V3.5 Sampler -> optional Hi-Res Fix -> Core Video/Audio Decode -> Assemble + Seam V3.5 route, including `refine_context`, Video VAE, Reference Images 1-3, and Video Reference socket placement.
- The template defaults Hi-Res Fix to OFF and Assemble to Auto. First/Last/Reference still images share one 0.3 MP control; VHS Video Reference sizing remains independent.
- Updated English/Japanese README, Changelog, project state, and distribution Manifest. No Production Python or runtime file was changed.
- Validation: JSON parse and semantic route audit PASS; all Manifest hashes PASS; full pytest `430 passed`; ComfyUI_W runtime registration, native PackedLayout, and Fixed 3x5 prompt-plan verification PASS; `git diff --check` PASS.

## 2026-08-22 - E2-8A / E2-8B1 implementation

- Added additive physical-group Second Pass metadata to V3.4 Assembly Plan output.
- Added static validation, target-geometry update, audio passthrough, and namespaced refine-seed helpers.
- Added CPU regression coverage for 24ch, B/T/group preservation, terminal 260f preservation, H/W upscale, prompt policy, and audio passthrough.
- Production Second Pass sampling, LBH integration, GPU validation, UI, and node registration remain unimplemented.
- Validation: Second Pass contract `8 passed`; related V3.4 regressions `94 passed`; full suite `257 passed`.
- Updated two legacy mocked Assembly Plans with required geometry fields; Production generation code was not changed by this test-only correction.

Append concise completed-work records here. Do not paste full console logs or duplicate `PROJECT_STATE.md`.

## 2026-08-20 - Project guidance organization

- Established the three-file structure: `AGENTS.md`, `PROJECT_STATE.md`, and `WORKLOG.md`.
- Added reusable snapshot and validation scripts under `tools`.
- Kept the existing uncommitted Hybrid reference work untouched.
- No tests were run for this documentation and tooling-only change.

## 2026-08-21 - Hybrid FLF Chunk Contract v1

- Replaced the single global FLF sample/split path with a 0.4 MP guide and separately sampled FL2VA chunks.
- Kept Reference Images persistent in the guide and every output chunk.
- Preserved the existing V3.4 UI and non-FLF execution paths.
- GPU behavior remains unverified.

## 2026-08-21 - Restore successful FLF terminal baseline

- Recorded GPU visual baselines: PASS 00029/00031/00032; FAIL 00034/00035.
- Reverted only the FLF terminal strategy from `context_bound_terminal_bridge_v2` to `context_bound_terminal_v1`.
- Removed the synthetic interpolated terminal keyframe; retained the continuation-context boundary anchor and supplied Last Frame anchor.
- No UI, Hybrid presentation, Reference, Run Storage, Driving Audio, Video Reference, or prompt-policy changes.
- Synced the modified `v2/sequence.py` to the active `ComfyUI_W` runtime.
- Runtime GPU retest intentionally pending user execution.

## 2026-08-21 - GPU result 00036 classified FAIL

- User confirmed that 00036 is a full failure, not a partial pass.
- The 5 s boundary was stable, but the sequence failed near 8 s with a bright ghost/flash and discontinuous loss of the reference fox.
- Recorded that whole-sequence continuity is the acceptance criterion.
- Recorded that the `context_bound_terminal_v1` restoration remains unresolved for terminal Hybrid FLF+Reference behavior.
- No code or runtime file was changed for this classification update.

## 2026-08-21 - GPU result 00037 classified FAIL

- Confirmed a second full failure after 00036.
- Embedded workflow: official FL2VA pruned INT8 ConvRot model, FL2V Turbo 8-step LoRA, 8 steps, Euler/simple, Spectrum Off, 2 x 5 s, 640x640, one reference image, Video Reference Efficient 0.4 MP.
- The fox remained stable across the 5 s seam, then became translucent and disappeared with a bright ghost/flash near 7.5-8 s.
- Rollback decision: do not use the immediately previous bridge-v2 implementation because its 00034/00035 results failed; identify and restore the exact accepted 00029/00031 baseline.
- No code or runtime file was changed in this classification step.

## 2026-08-21 - 00038 FAIL; withdrew terminal-v1 restoration

- User classified 00038 as FAIL and requested rollback.
- Confirmed embedded workflow used Ref2VA pruned INT8 ConvRot, FL2V Turbo 8-step LoRA, Euler/simple 8 steps, Spectrum Off, 2 x 5 s, randomized seed, and Video Reference Efficient 0.4 MP.
- Verified repository and ComfyUI_W `v2/sequence.py` matched before modification.
- Snapshotted repository/runtime sequence files plus project records to: 
D:\Codex\_snapshots\ComfyUI-H3-Continuum\pre-rollback-after-00038-fail-20260821_032550
- Restored only `v2/sequence.py` from the exact pre-restoration snapshot `pre-restore-flf-success-baseline-repo-20260821_030316`.
- Synced the restored file to ComfyUI_W. No UI or unrelated feature files were changed.
- The restored bridge-v2 implementation remains unapproved; this action only reverses the failed terminal-v1 restoration.


## 2026-08-21 - Corrected rollback target to exact 00031 state

- User clarified that the rollback target is the code state that generated PASS `MiniMax_H3_Continuum_V31_00031_.mp4`.
- Correlated filesystem times: 00031 completed at 02:32:59; the pre-bridge snapshot was captured at 02:35:53.
- Restored only `v2/sequence.py` from `pre-flf-terminal-bridge-v2-repo-20260821_023553` to the repository and active ComfyUI_W runtime.
- Active FLF strategy is `context_bound_terminal_v1`; bridge v2 is no longer active.
- No UI or unrelated feature files were changed. GPU retest was not run.

## 2026-08-21 - M1 Hybrid diagnostics

- Used ComfyUI_W as the authoritative source after confirming repository/runtime differences.
- Created and verified a runtime snapshot before edits.
- Implemented display-only Hybrid labels and global Picture-number warnings.
- Documented Hybrid Picture numbering and added focused regression tests.
- Runtime generation behavior and public UI were intentionally left unchanged.
- Tests were not run in this implementation step.
## 2026-08-21 - FLF duplicate boundary anchor removal

- Preserved the active ComfyUI_W M3 display-label and M4 Last Frame session checks while synchronizing `v2/sequence.py` to the repository.
- Changed the FLF contract to `context_bound_terminal_last_only_v2` so Run Storage cannot reuse chunks produced by the previous strategy.
- Removed only the final-chunk call that duplicated the continuation-context tail as a boundary keyframe.
- Kept the 22-frame continuation context and the single supplied Last Frame anchor retained by `prepare_conditioning()`.
- No UI, public sockets, Assembly, audio, Spectrum, or general continuation behavior changed.
- Automated and GPU validation were not run in this implementation step.

- 2026-08-22 00:49:57 Terminal Merge Physical Seed v2 implemented locally after snapshot pre-change-20260822_004423. Changed v2/sequence.py and run_storage.py; added seed and revision regressions. No commit or push.

- 2026-08-22 00:51:45 Validation: 220 passed, 1 pre-existing failure in test_v2_sequence_orchestration because conditioning_display_label is absent from conditioning.py. All Physical Seed v2 and Run Storage revision tests passed. GPU generation not run.


## 2026-08-22 - Terminal Merge staged diagnostics

- Snapshot: D:\Codex\_snapshots\ComfyUI-H3-Continuum\pre-terminal-merge-diagnostics-20260822_020527
- Added tests-only deterministic capture/comparison helpers for stages A-E.
- Added unit coverage for noise, PackedLayout/position_ids, sampled-stage ordering, numerical tolerance, and bit-exact 243f Terminal split/recombine.
- No Production code, UI, Conditioning, Seed v2, Terminal Merge, Assembly, or Seam behavior changed.
- Commit/push not performed.

## 2026-08-22 - Standalone Core vs Continuum GPU diagnostics
- Added a standalone diagnostic node without changing Production runtime semantics.
- Added capture helpers and regression tests.
- Installed to ComfyUI_W as a separate custom node and verified source/runtime SHA-256 equality.
- Registration import: PASS (`H3CoreContinuumGpuDiagnostic`).
- Targeted tests: 6 passed.
- Full suite: 232 passed, 1 pre-existing unrelated failure (`conditioning_display_label` missing for unfinished M3 wiring).
- GPU execution: not run.
- Commit/push: not performed.
## 2026-08-22 - Terminal Merge physical decode groups

- Preserved logical chunks for Session and Run Storage.
- Recombined terminal logical AV latent slices bit-exactly before external Core VAE Decode.
- Added assembly_plan.decode_groups so one terminal physical sample is decoded once.
- Assembly hardening and Video Seam now operate at physical decode-group boundaries.
- Sampling, Physical Seed v2, Conditioning, UI, sockets, and Run Storage schema were unchanged.
- Synced implementation to ComfyUI_W.
- Pending validation: targeted pytest, full pytest, and GPU Core-vs-Continuum decode comparison.

## 2026-08-22 - Long Terminal Merge prompt pairing

- Snapshots: `pre-long-terminal-merge-repo`, `pre-long-terminal-merge-comfyui-w`, and `pre-long-terminal-merge-comfyui-wan` under `D:\Codex\_snapshots\ComfyUI-H3-Continuum`.
- Removed only the final-prompt-hash equality gate from Terminal Merge eligibility.
- Added a scoped physical prompt policy: identical prompts remain byte-identical; distinct final logical prompts are rebased to `[0-5s]` / `[5-10s]` for one terminal physical sample.
- Added scoped Run Storage execution semantics and 3-logical-to-2-physical decode-group regression coverage.
- No UI, public sockets, model selection, Spectrum, Assembly, Seam, or global Run Storage schema changes.
- Focused regression result: 22 passed; GPU generation not yet run for the new 3x5 path.
- Runtime correction: `run_storage.py` was also synchronized to ComfyUI_W and ComfyUI_WAN after the first GPU attempt exposed an old `RunStorageController.prepare()` signature. Run Storage plus Terminal Merge regressions: 47 passed.
- GPU PASS: `MiniMax_H3_Continuum_V31_00008_.mp4` exercised 3x5s FL2VA with `terminal_pair=2-3`, `physical_frames=260`, `sampling_passes=1` for the pair, `paired_timeline_v1`, two physical decode groups, and final 360 frames / 15.000 seconds.
- Core comparison `MiniMax_H3_00005_.mp4` reproduced the same short terminal still period. Long Terminal Merge was formally accepted; terminal stillness is Core-equivalent FL2VA convergence and is not a Continuum repair target.
- Final release validation: full pytest `249 passed`; `tools/verify_runtime.py --comfy-root D:\StabilityMatrix\Data\Packages\ComfyUI_W` passed V3.4 registration, native PackedLayout, and Fixed 3x5s prompt-plan checks. GPU acceptance is recorded above.

## 2026-08-23 - E2-8C experimental T2VA Second Pass

- Snapshots: `pre-change-20260823_004307` for the repository and `comfyui-w-before-e2-8c-20260823_004341` for the active runtime files.
- Added a generic physical-group Second Pass node; LBH remains an external upstream latent upscaler.
- Reused the existing prompt encoder and ComfyUI-native `sample_chunk()` path with workflow-supplied SIGMAS.
- One namespaced refine seed is used per physical group; temporary refined audio is discarded and first-pass audio objects are returned unchanged.
- Existing V3.4 Sampling, Terminal Merge, Assembly, Seam, Run Storage, and public Sampler sockets were not changed.
- CPU regression and GPU 1x5 T2VA acceptance remain pending after implementation.

## 2026-08-23 - E2-8C Second Pass GPU acceptance

- E2-8C is formally PASS after 1x5 T2VA, 3x5 T2VA, and 3x5 FL2VA Long Terminal Merge GPU runs.
- Final acceptance artifact: `E2-8B2_01_1x5_T2VA_LBH3D_00011_.mp4`; embedded workflow used three 5-second timeline prompts, supplied First/Last images, the FL2VA INT8 ConvRot model, no enabled LoRA, `res_multistep`, First Pass `simple` 20 steps / denoise 1.0, external LBH FP16 CUDA upscale from 640x640 to 768x768, and Second Pass `simple` 4 steps / denoise 0.3. Execution time was 17 minutes 44 seconds.
- Long Terminal Merge preserved `37T + 77T` and two physical groups: group 1 logical `[1]`; group 2 logical `[2,3]` with `paired_timeline_v1`. Each physical group ran exactly one Second Pass sampling call with its own reported refine seed.
- Final media was 768x768, 360 frames, 24 fps, and 15.000 seconds. First-pass audio LATENT objects were returned bit-exact; Core Video/Audio Decode and Assemble completed successfully.
- The 5-second and 10-second boundaries had no major flash, ghosting, jump, or temporal collapse. The final approximately 0.5-second low-motion interval was accepted as natural Last Frame convergence.
- V3.4 Sampling, Terminal Merge, Assembly, Seam, and Run Storage were unchanged. No code or runtime file was modified during GPU acceptance classification.
- Final validation after documentation update: full pytest `260 passed in 4.41s`.

## 2026-08-23 - V3.5 Continuum Latent Resize

- Snapshots: `pre-v35-latent-resize-repo-20260823_153334` (345 files) and `comfyui-w-before-v35-latent-resize-20260823_153336` (308 files).
- Added `H3ContinuumLatentResizeV35`, a list-aware thin wrapper over ComfyUI Core `common_upscale` for the standard Continuum Hi-res fix path.
- The node exposes Core nearest-exact, bilinear, area, bicubic, and bislerp interpolation plus `scale_by`; it preserves LATENT metadata, physical-group order, and B/C/T while changing only spatial H/W.
- LBH and other learned latent upscalers remain optional external alternatives. No upscaler was embedded into Continuum.
- Updated runtime registration verification to include the existing V3.5 Second Pass and the new Latent Resize node.
- Synced only `nodes.py` and `v3/latent_resize_nodes.py` to ComfyUI_W and verified SHA-256 equality.
- Validation: Latent Resize tests `5 passed`; full pytest `265 passed in 5.09s`; ComfyUI_W runtime registration, native PackedLayout, and Fixed 3x5s prompt-plan verification passed. GPU generation with the new resize node remains pending.
- V3.4 Sampling, Terminal Merge, Conditioning, Assembly, Seam, Run Storage, and public Sampler sockets were unchanged. Commit/push not performed.

## 2026-08-23 - V3.5 one-node Hi-Res Fix

- Snapshots: `pre-v35-hires-fix-repo-20260823_174946` (349 files) and `comfyui-w-before-v35-hires-fix-20260823_174947` (310 files).
- Added `H3ContinuumHiResFixV35` as the normal Main workflow: ON performs Core-compatible spatial resize followed by the existing physical-group Second Pass; OFF returns the exact first-pass video/audio LATENT lists and original Assembly Plan object.
- MODEL/CLIP/SAMPLER/SIGMAS are lazy inputs, so the node does not request Second Pass dependencies while disabled.
- Preserved `H3ContinuumSecondPassV35` as the Advanced external-latent bridge required by Issue #8 and `H3ContinuumLatentResizeV35` as a standalone Utility. Removed only the `(Experimental)` suffixes from their display names.
- No V3.4 Sampling, Conditioning, Terminal Merge, Assembly, Seam, Run Storage, or Sampler socket behavior changed.
- Validation: V3.5 focused tests `13 passed`; full pytest `270 passed in 3.82s`; ComfyUI_W runtime registration, native PackedLayout, and Fixed 3x5 prompt-plan verification passed. GPU execution through the new wrapper remains pending. Commit/push not performed.

## 2026-08-23 - V3.5 Second Pass audio-lock candidate

- Snapshots: `pre-v35-second-pass-audio-lock-repo-20260823_203840` (357 files) and `comfyui-w-before-v35-second-pass-audio-lock-20260823_203843` (312 files). The earlier 45-file repository snapshot was incomplete after a `.pytest_cache` permission error and is not the accepted snapshot.
- Added `v3/refine_sampling.py` and switched only V3.5 Second Pass to direct Core sampling with seed-derived random video noise/mask 1 and zero audio noise/mask 0. No inverse noise scaling or manual sigma compensation is applied.
- Kept V3.4 `sample_chunk()`, UI sockets, Conditioning, Terminal Merge, Assembly, Seam, and Run Storage unchanged. First/Last/Reference conditioning remains out of scope.
- Validation: V3.5 focused tests `19 passed`; Core minimal-mask expansion PASS for representative 37T video and H3 audio shapes; ComfyUI_W venv full pytest `273 passed in 3.98s` using a writable dedicated basetemp (`pynvml` FutureWarning only).
- GPU A/B against the fixed 00015 artifact condition remains pending. This CPU result does not establish that audio re-noise was the artifact's primary cause. Commit/push not performed.

## 2026-08-23 - V3.5 no-resize Second Pass GPU isolation

- Snapshot: `pre-v35-resize-bypass-diagnostic-workflow-verified-20260823_211203` (356 repository files excluding the inaccessible `.pytest_cache`, plus the SHA-256-verified 00017 source MP4).
- Created `MiniMax_H3_Continuum_V35_NoResize_SecondPass_Diagnostic.json` by replacing the Hi-Res Fix wrapper with a direct `H3ContinuumSecondPassV35` connection and adding a status preview. No Production code or runtime file was changed.
- Reused the exact cached 576x576 first-pass latent from the 00017 condition. Second Pass remained `res_multistep`, `simple` 10 steps / denoise 0.35, refine seed 42; only spatial resize and 1152x1152 re-entry were removed.
- GPU execution succeeded as prompt `aa1faf7f-7353-49bd-8efb-23b1cf9c2462`. The report confirmed video random noise/mask 1, audio zero noise/mask 0, shape `(1, 24, 37, 36, 36)`, one physical group, one sampling pass, and first-pass audio LATENT passthrough.
- Output `V35_NoResize_SecondPass_Diagnostic_00001_.mp4` is 576x576, 120 frames, 24 fps, and 5.000 seconds. Twenty representative frames were visually clean with none of 00017's persistent cyan/orange/white line or plate artifacts.
- Result: audio-lock does not repair the 2x artifact and random audio re-noise is not its primary cause. The direct Second Pass path passes; the remaining failure is scoped to the 2x spatial-resize/high-resolution re-entry path. Interpolation method versus scale/resolution remains to be isolated.
- Commit/push not performed.

## 2026-08-23 - V3.5 spatial method/resolution GPU isolation

- Held the cached 576x576 first-pass latent, `res_multistep`, `simple` 10 steps / denoise 0.35, refine seed 42, prompt, audio, and Assembly Plan fixed. Only resize method or target H/W changed.
- FAIL `V35_NearestExact2x_Diagnostic_00001_.mp4` (`c35f5c9d-e1b7-43aa-8b09-7f4994aa6225`): nearest-exact 2x, 1152x1152, latent `(1, 24, 37, 72, 72)`. The same persistent colored line/plate artifact family remained, so bilinear-specific channel mixing is not the primary cause.
- PASS `V35_NearestExact_576to768_Diagnostic_00001_.mp4` (`676b23cb-79c8-4d03-9e24-0ecfa2288128`): nearest-exact 4/3x, 768x768, latent `(1, 24, 37, 48, 48)`. Twenty representative frames were clean.
- PASS `V35_Bilinear_576to768_Diagnostic_00001_.mp4` (`9a7b7383-06dd-4972-bb6c-82c010e64b1e`): bilinear 4/3x, 768x768, latent `(1, 24, 37, 48, 48)`. The target artifact did not recur.
- FAIL `V35_Bilinear_576to1024_Diagnostic_00001_.mp4` (`b0530d14-fb2c-42d4-b62c-08d73ec13c8d`): bilinear 16/9x, 1024x1024, latent `(1, 24, 37, 64, 64)`. Persistent line/plate artifacts returned across the sequence.
- Every run completed Core Decode and Assemble as 120 frames / 24 fps / 5.000 seconds with the audio-locked report and first-pass audio LATENT passthrough. Visual acceptance, not execution validity, separates PASS from FAIL.
- ComfyUI Core source defines H3 `BASE_SHORT_EDGE = 768` and `MAX_PIXELS = 768 * 1344`. The observed square boundary is consistent with the native canvas: 768 passed; 1024 and 1152 failed. The exact transition between 768 and 1024 remains untested.
- Added four importable diagnostic workflow JSON files under `D:\Codex\_test_workflows\ComfyUI-H3-Continuum`. No Production code, runtime file, V3.4 Sampling, Conditioning, Terminal Merge, Assembly, Seam, or Run Storage behavior changed.
- Commit/push not performed.

## 2026-08-23 - V3.5 H3 native-canvas Auto default

- Snapshots: `pre-v35-native-canvas-auto-repo-20260823_215429` (356 files, excluding the inaccessible `.pytest_cache`) and `pre-v35-native-canvas-auto-comfyui-w-20260823_215429` (309 files). Relevant source/runtime files matched by SHA-256 before the change.
- Preserved the existing `H3ContinuumHiResFixV35` node ID, sockets, widget order, and saved-workflow behavior. The new defaults are `bilinear` and `scale_by=0.0`; zero means H3 native-canvas Auto, while every positive value retains the previous manual scale multiplier.
- Auto calls ComfyUI Core `adapt_canvas()` and uses an exact-target resize helper so non-square Core targets do not depend on a rounded uniform multiplier. It never shrinks an already-larger latent. Manual targets beyond Core native canvas emit a status warning only; no clamp or hard stop was introduced.
- Added exact-target, multi-group metadata, native target, no-shrink, landscape 1024x576 -> 1344x768, manual-compatibility, and warning coverage. V3.5 focused tests: `28 passed`; full pytest: `277 passed` with only the known `pynvml` FutureWarning.
- Synchronized only `v3/hires_fix_nodes.py` and `v3/latent_resize_nodes.py` to ComfyUI_W and verified SHA-256 equality. Runtime registration reported `upscale_method=bilinear`, `scale_by=0.0`, and minimum 0.0 after restart.
- GPU acceptance prompt `26a7709d-0e4a-4c3f-ad34-3424e3dc7c69` produced `V35_NativeAuto_576to768_Acceptance_00001_.mp4`. The report selected 576x576 -> 768x768, sampled one `(1, 24, 37, 48, 48)` physical group once, retained first-pass audio bit-exact, and completed Core Decode/Assemble as 120 frames / 24 fps / 5.000 seconds.
- Ten-frame visual review found none of the 1024/1152 colored line/plate artifacts. Decoded video matched the accepted manual bilinear 576 -> 768 run exactly (`PSNR = inf`). The importable acceptance workflow is `D:\Codex\_test_workflows\ComfyUI-H3-Continuum\MiniMax_H3_Continuum_V35_NativeAuto_576to768_Acceptance.json`.
- V3.4 Sampling, Conditioning, Terminal Merge, Assembly, Seam, Run Storage, and public Sampler sockets were unchanged. Commit/push not performed.

## 2026-08-24 - V3.5 context-aware conditioning implementation and GPU isolation

- Verified snapshots before modification: `pre-v35-refine-context-repo-verified-20260823_233600` (356 repository files excluding `.git` and the inaccessible `.pytest_cache`) and `pre-v35-refine-context-comfyui-w-verified-20260823_233632` (309 runtime files with the same exclusions).
- Added runtime-only `v3/refine_context.py`, a new public `H3ContinuumSamplerV35`, physical-group capture immediately before First Pass sampling, and optional `refine_context` / `video_vae` inputs on Second Pass and Hi-Res Fix. V3.4 retains its original five outputs; V3.5 appends context as output six after Driving Audio.
- Context-aware Second Pass validates the capture against the Assembly Plan, re-encodes target First/Last keyframes through the Video VAE, resizes only marked Continuum video context, bypasses prompt re-encoding, and uses one call-local Continuum MODEL clone per physical group. Missing, incomplete, or target-adaptation-unavailable context warns and uses the legacy prompt-only path; corrupt typed context remains a contract error.
- Kept the existing direct refine sampling contract unchanged: video random noise/mask 1, audio zero noise/mask 0, workflow SIGMAS once, one derived seed and sampling call per physical group, and the original first-pass audio LATENT objects returned unchanged.
- Review found no P0/P1 integration defect. Known non-blocking risks are CPU RAM growth from immutable conditioning copies for long/reference-heavy runs, bilinear context resize when an Advanced external learned upscaler is used, and a still-required CLIP socket even when complete context bypasses prompt encode.
- Validation: targeted integration `40 passed`; full pytest `293 passed`; `git diff --check` PASS; source runtime verifier and ComfyUI_W runtime registration/native PackedLayout/Fixed prompt-plan checks PASS. Only the known `pynvml` warning remained.
- Synced the changed production files to ComfyUI_W after the verified snapshot. Eight files match source by SHA-256. `v3/driving_nodes.py` differs only by the pre-existing runtime Video Reference tooltip addition, which was deliberately preserved; runtime `py_compile` and registration passed.
- Context-aware GPU A/B prompt `0adff3b7-1552-47e9-a167-7b6e4010b0a5` used the same FL2VA 1x5 inputs and seeds as the prior artifact run, 576x576 -> 864x864 bilinear 1.5x, `res_multistep`, `simple` 10 steps / denoise 0.35, refine seed 42. Report: one physical group, `conditioning_source=refine_context`, two target keyframes VAE re-encoded, `(1, 24, 37, 54, 54)`, audio passthrough. `V35_ContextAware_FL2VA_576to864_d035_00001_.mp4` still shows the colored line/plate artifact family, so conditioning mismatch is not the primary cause.
- Resize-only prompt `75249bbe-306a-45f9-a139-a79c0b17e536` reused the cached First Pass and produced `V35_ResizeOnly_FL2VA_576to864_bilinear_00001_.mp4`. It is 864x864 / 120 frames / 24 fps / 5.000 seconds; colored lines are absent, but severe temporal/person/background ghosting proves that direct spatial interpolation is not a valid general H3 latent-upscale backend.
- Pixel/VAE roundtrip prompt `2a03a1d4-2355-4d5a-a237-0ec3e0c09761` used First Pass Core Decode -> pixel Lanczos 864x864 -> H3 Video VAE Encode -> the same context-aware denoise 0.35 Second Pass. Sampling, Core Decode/Audio Decode, and Assemble succeeded. `V35_PixelRoundtrip_FL2VA_576to864_d035_00001_.mp4` is 864x864 / 120 frames / 24 fps / 5.000 seconds and is visually clean: no colored lines, plates, or resize ghosting, with the orange jacket, subject identity, motion, and terminal composition retained.
- Pixel/VAE roundtrip 2x prompt `de11e383-8b3d-4d8a-806f-1ac3550091f1` used the same cached First Pass, pixel Lanczos 1152x1152, H3 Video VAE Encode, context-aware `res_multistep` / `simple` 10-step denoise 0.35 Second Pass, and refine seed 42. It completed without OOM on the 16 GiB GPU. Report: one physical group, `(1, 24, 37, 72, 72)`, one sampling pass, two target keyframes VAE re-encoded, first-pass audio passthrough, then successful Core Decode/Audio Decode and Assemble. `V35_PixelRoundtrip_FL2VA_576to1152_d035_00001_.mp4` is 1152x1152 / 120 frames / 24 fps / 5.000 seconds and is visually clean across twelve representative time points: no colored lines/plates, resize ghosting, or temporal collapse, with subject identity, orange clothing, motion, and composition retained.
- Result: retain the Advanced external-latent Second Pass bridge for Issue #8; do not promote plain Latent Resize as the Main Hi-res backend. The evidence-backed next code phase is a low-memory sequential pixel/VAE roundtrip inside Hi-Res Fix, one physical group at a time, followed by the existing context-aware Second Pass. That backend change is pending explicit approval. Commit/push not performed.

## 2026-08-24 - V3.5 Main safe Pixel/VAE Hi-res Fix implementation and GPU acceptance

- Pre-change snapshots: `pre-v35-pixel-vae-main-repo-20260824_004310` (159 files / 3,817,668 bytes) and `pre-v35-pixel-vae-main-comfyui-w-20260824_004310` (132 files / 1,660,144 bytes). Source/runtime hashes matched for the relevant pre-existing production files before modification.
- Added `v3/pixel_vae_resize.py` and changed only the V3.5 Main `H3ContinuumHiResFixV35` path to perform one physical group at a time as H3 Video VAE Decode -> bounded 8-frame CPU pixel resize -> same H3 Video VAE Encode -> existing context-aware Second Pass. Default Main controls are Lanczos and `scale_by=2.0`; zero remains native-canvas Auto.
- Enabled Main execution requires the lazy Video VAE and has no direct-latent interpolation fallback. OFF remains exact video/audio/Assembly Plan identity and does not evaluate VAE or sampling dependencies. Advanced Second Pass and the standalone Latent Resize Utility were not changed.
- The first integrated GPU attempt (`46f775ca-093c-4c1f-b5ce-1aa9a8f8616f`) stopped at the explicit output-shape contract before Second Pass. Root cause: passing `[B,F,H,W,C]` directly to Core `VAE.encode()` makes Core's 4D IMAGE crop path treat F as a spatial axis. The helper now calls Encode per B with `[F,H,W,C]`, validates each `[1,C,T,H,W]` result before concatenation, and restores B explicitly. No latent fallback ran during the failed attempt.
- Validation after the Core-boundary correction: focused pixel/VAE and Hi-Res tests are covered by the full `308 passed`; `py_compile`, `git diff --check`, and the ComfyUI_W runtime verifier all pass. Independent review found no remaining P0/P1/P2 defect. Runtime `v3/pixel_vae_resize.py` matches source SHA-256 `B7C4A35A5E73F528492BC6946B97B687C412F1D3F5F976C19D45C6DC20288C9A` after restart.
- Integrated Main GPU acceptance prompt `c5dbe55c-c846-47e8-9f49-8bb167887236` used FL2VA 1x5, 576x576 -> 1152x1152 pixel Lanczos, context-aware `res_multistep`, `simple` 10 steps / denoise 0.35, and refine seed input 42. Report: one physical group, one sampling pass, `(1, 24, 37, 72, 72)`, two target keyframes re-encoded, and first-pass audio LATENT passthrough. Core Video/Audio Decode and V3.4 Assemble+Seam completed in 14:18.
- `V35_MainSafePixelVAE_Core4D_FL2VA_576to1152_d035_00001_.mp4` is 1152x1152 / 120 frames / 24 fps / 5.000 seconds with 32 kHz stereo audio. All decoded video and audio frame hashes exactly match the accepted external Decode -> Lanczos -> Encode -> Second Pass baseline. Visual contact-sheet review found none of the prior colored line/plate or resize-ghosting artifacts. The shared still interval from 3.666667 seconds is the same FL2VA Last Frame convergence in both outputs.
- Host-memory use remains material: observed peak was about 47.7 GiB working set / 61.3 GiB private bytes, with about 7.3 GiB system RAM available during the run. The Main backend is accepted for this 1x5 FL2VA 2x condition only; 3x5 Terminal Merge 2x remains pending separate GPU/resource acceptance.
- V3.4 Sampling, Conditioning, Terminal Merge, Assembly, Seam, Run Storage, public V3.4 sockets, Advanced Second Pass, and Latent Resize Utility were unchanged. Commit/push not performed.

## 2026-08-24 - Phase 2A P2-0 Windows file-backed Tensor PoC

- Verified pre-change snapshot: `D:\Codex\_snapshots\ComfyUI-H3-Continuum\pre-phase2a-p2-0-backend-poc-verified-20260824_022242` (374/374 source files, SHA-256 mismatch 0, revision `d77a467796c048908f8b7b83736e226e736e0f98`). The earlier `pre-phase2a-p2-0-backend-poc-20260824_022217` attempt is incomplete because the repository `.pytest_cache` ACL denied traversal and is not the accepted snapshot.
- Added only the unregistered standalone PoC `tools/p20_file_backed_tensor_poc.py` and its tests. Production nodes and ComfyUI_W/ComfyUI_WAN runtime packages were not modified.
- Selected `torch.from_file(shared=True)` and implemented strict backing-path/sidecar validation, alias-aware Storage lifetime, a process-global manager, retryable deletion, dead-process stale cleanup, live/young retention, root-scoped thread/process locking, and fail-closed invalid metadata handling.
- Independent review reproduced and drove fixes for Windows sharing-violation retry, dropped unpublished allocations, allocation/cleanup races, GC/root-lock re-entry, cross-thread ABBA lock inversion, and close-after-cancel fd reuse. Finalizers now enqueue only; actual cleanup uses root-lock -> manager-lock ordering.
- Validation: ComfyUI_W focused `26 passed`; full repository `334 passed`; standalone probe PASS (`bit_exact=true`, 480/480 bytes, alias-live deferred=1, final-alias reclaimed=1, managed files remaining=0). ComfyUI_WAN independently passed the same 26 tests and probe under Python 3.12.12 / PyTorch 2.13.0+cu130. Only the known `pynvml` FutureWarning was emitted.
- Deferred by design: Production Assemble integration, real ComfyUI cache/requeue and VHS/Save compatibility, RAM/Disk full-assembler equivalence, cross-process application integration, and representative 9-15 GiB sequential-write/RSS acceptance. These remain P2-2 through P2-5 gates; P2-1 Memory Attribution is next.
- Commit/push not performed.

## 2026-08-24 - Phase 2A P2-1 through P2-3 CPU/static acceptance

- Verified the authoritative source and both runtime copies, preserved all prior uncommitted work, and created `pre-phase2a-p2-1-memory-attribution-20260824_030858` followed by the accepted implementation snapshot `D:\Codex\_snapshots\ComfyUI-H3-Continuum\pre-phase2a-p2-2-disk-backed-20260824_032923` (166/166 source files, zero SHA-256 mismatch, revision `d77a467796c048908f8b7b83736e226e736e0f98`).
- Completed P2-1 with fail-soft, read-only V3.5 Memory Attribution at sequence start/before CPU commit/after CPU commit/completion, including deduplicated retained AV/refine-context storage, projected final IMAGE sizes, RSS/system RAM, and CUDA allocated/reserved values. No synchronization, peak reset, cache clear, forced GC, model unload, or V3.4 default change was added.
- Completed P2-2 with the Production adapter `v3/file_backed_buffer.py`: manual RAM/Disk-backed selection only, no Auto and no fallback, process-global alias-aware lifetime management, lazy root-first stale cleanup, and Video-only mapping while Audio stays in RAM.
- Completed P2-3 with independent V3.5 assembly/seam modules. The final target IMAGE is allocated once and receives physical decode groups in order through direct trim/pad/final-anchor spans. Exact Duration and Terminal Merge contracts are retained without a final full IMAGE `cat`, `stack`, `clone`, or `contiguous` materialization.
- Reused the existing V3.4 Video Seam analysis and math while limiting temporary copies to the affected 1-4 boundary frames and anchors. Preserved Audio Seam and cumulative sample alignment in RAM. Disk-backed publication is delayed until late Driving Audio/report validation completes; regressions cover early/late abort, alias lifetime, and dead-process stale recovery.
- CPU regressions cover RAM/Disk bit-exact output; Seam Off/Analyze/Auto/Auto 2; Exact ON/OFF; trim, pad, and preserved final frame; 1x5, 2x5 Terminal Merge, and 3x5 Long Terminal Merge; 32 kHz rounding; Audio Seam; physical ordering; Auto rejection; and error/lifetime paths.
- Final canonical validation: full pytest `412 passed` with only the known `pynvml` FutureWarning; changed Production `py_compile` PASS; `git diff --check` PASS. ComfyUI_W runtime verification passed node registration, native PackedLayout, and Fixed 3x5 prompt plan; focused runtime regression `141 passed`.
- Synchronized only 19 P2-related source-or-preserved-merge files to primary ComfyUI_W and verified every SHA-256 comparison. Preserved its pre-existing Video Reference tooltip delta. ComfyUI_WAN was left unchanged rather than receiving a broken partial V3.5 dependency set.
- Stopped at the requested P2-3 boundary. Still pending for P2-4/P2-5: real cache/requeue lifetime, Preview/VHS/Save, ESC cancel, 9-15 GiB stress/RSS, downstream copy behavior, GPU generation, long-duration GPU acceptance, and Auto backend. Commit/push not performed.

## 2026-08-24 - Phase 2A P2-4 ComfyUI cache/downstream integration

- Accepted verified snapshots: source `pre-phase2a-p2-4-comfy-integration-source-verified-20260824_101909` (415 files, SHA-256 mismatch 0, revision `d77a467796c048908f8b7b83736e226e736e0f98`) and ComfyUI_W `pre-phase2a-p2-4-comfy-integration-comfyui-w-verified-20260824_101938` (324 files, mismatch 0). The two standard-script attempts and one intermediate verification attempt are incomplete because the existing `.pytest_cache` ACL denies traversal and are not accepted snapshots.
- Added bounded 8-frame interrupt polling to only the V3.5 direct IMAGE writer. ComfyUI's normal interrupt is checked after Disk-backed allocation and between copy batches, so immediate or mid-copy ESC uses the unpublished-allocation cleanup path. RAM/Disk output equality is unchanged; focused interrupt/P2-3 regression was `47 passed`.
- Added the reusable headless integration probe `tools/p24_comfy_integration_probe.py`. It registers deterministic decoded CPU fixtures only, then executes the real installed ComfyUI_W `PromptExecutor` CLASSIC cache, Core Save/Preview nodes, VHS h264-mp4, Core interrupt handling, and separate-process stale cleanup. No model/VAE/sampler/CUDA/GPU path is used.
- Actual cache evidence: an intentional downstream failure retains the completed mapped IMAGE; unchanged requeue reports assembler node 2 cached and leaves one backing pair; Save/Preview/VHS requeue reports nodes 1/2/4/5/6 cached without rewriting outputs; cache eviction followed by replacement allocation keeps pair count bounded at one; final pair count is zero.
- Downstream evidence: Core Save 120 PNGs, Core Preview 120 PNGs, and VHS H.264/AAC succeeded. `ffprobe` verified 16x16, 120 frames, 24/1 fps, 5.000-second video/container duration, and 32 kHz audio. Core interrupt produced `execution_interrupted` with zero unpublished files. Crash child left one pair; clean-start child removed it.
- Final runtime artifacts: `D:\Codex\_test_results\ComfyUI-H3-Continuum\P24-runtime-W-final-20260824_1105\p24_result.json`, `p24_prompt_graphs.json`, and `output\P24\VHS_00001-audio.mp4` (39,006 bytes). The expected intentional downstream-error traceback is part of the probe and not a failure.
- Final validation: full pytest `415 passed`; ComfyUI_W P2-focused `89 passed`; runtime verifier, `py_compile`, `git diff --check`, and source/runtime SHA-256 checks pass. Synced only `v3/assembly_v35.py`, the P2-4 probe, and its test. The known `pynvml` FutureWarning is unchanged.
- P2-4 is formally PASS and work stops here. P2-5 still covers representative 9-15 GiB/RSS stress, full-resolution and long-duration GPU execution, manual UI cancellation under large I/O, downstream memory peaks, and any future Auto backend policy. Commit/push not performed.

## 2026-08-24 - V3.5 compact UI parity

- Verified source/runtime `web/project_id.js` equality, preserved all existing uncommitted work, and accepted snapshots `pre-v35-compact-ui-source-verified-20260824_104010` (420 files) and `pre-v35-compact-ui-runtime-w-verified-20260824_104048` (330 files), both with zero SHA-256 mismatch. Standard snapshot attempts failed only on the pre-existing inaccessible `.pytest_cache`.
- Added the V3.5 Sampler and Assemble+Seam class IDs to the existing frontend compact/settings integration. This hides Report Detail/debug/preview/strict compatibility and the internal Auto Resume ID, while retaining the existing conditional Run Name/Regenerate/Variation Nonce behavior.
- `strict_compatibility` was not removed from the backend schema; legacy loading remains possible, while the frontend continues to force the ignored value to `false`. No backend or generation behavior changed.
- Added `tests/test_v35_compact_ui_frontend.py`. Dedicated regression `2 passed`, JavaScript module syntax PASS, and canonical full pytest `417 passed` using a fresh writable basetemp. Only the known `pynvml` and repository pytest-cache warnings remain.
- Synchronized only the frontend file and dedicated regression test to ComfyUI_W; both source/runtime SHA-256 comparisons match, and the runtime-side dedicated regression is `2 passed`.
- P2-5 was not started. Commit/push not performed.

## 2026-08-24 - Phase 2A P2-5 long-output acceptance

- Preserved every existing uncommitted change and accepted verified snapshots `pre-phase2a-p2-5-gpu-acceptance-source-verified-20260824_105605` (422 files) and `pre-phase2a-p2-5-gpu-acceptance-runtime-w-verified-20260824_105626` (331 files), both with zero SHA-256 mismatch after excluding the pre-existing inaccessible `.pytest_cache`.
- Added the reusable source-side `tools/p25_gpu_acceptance_probe.py` and focused tests. The probe runs ComfyUI_W headlessly through its installed `PromptExecutor`, reconstructs the accepted 3x5 FL2VA Long Terminal Merge physical decode groups from Run Storage revision `1e30d8bf2154bbe7`, and uses the installed Core Video/Audio VAE Decode and Production V3.5 assembler. No UI automation or new model/sampler generation was used.
- Fresh-process RAM/Disk 640x640 A/B passed: 3 logical chunks, 2 physical groups (`37T + 77T`), 360 frames at 24 fps / 15.000 seconds, 32 kHz stereo audio, identical Exact Duration `362 -> 360` and audio correction `-2667`, identical Seam Auto report, finite output, identical video SHA-256 `95d5479bc5fee9c235ece7996c7c88dcc60981625dbedc330344403016ca9b9d`, and identical audio SHA-256 `eec0c6ff378c5bfcc3e71d02bab14230dea02a57e18ce1212f1dc1be4c88a3f9`.
- Core Save/Preview each consumed 360 mapped frames. VHS H.264/AAC was verified as 640x640, 360 frames, 24 fps, 15.000 seconds, and 32 kHz. Same-input requeue cached every node through assembler/digest without growing beyond one backing pair; cache release reclaimed it.
- A post-allocation Core interrupt produced `execution_interrupted` and left zero managed files. The P2-4 crash/restart probe was rerun in the P2-5 environment: one crash-stale pair was created and the next process removed it on first manager access. Downstream-error retention/recovery and final cache pair count also remained correct.
- Ran a 1536x1536x360 float32 stress producing a 10,192,158,720-byte / 9.49 GiB final IMAGE. RAM and Disk-backed outputs were hash-identical and finite. Disk-backed retained one file only while cached and zero after release.
- Corrected the measurement contract: Windows RSS includes resident file-mapped pages, so stress RSS was about 10.44 GiB for both backends and is not a valid standalone proof of commitment savings. RAM private/USS measured 13,322,362,880 / 11,045,199,872 bytes; Disk-backed measured 3,122,954,240 / 855,834,624 bytes. The mapped backend therefore reduced anonymous private commitment by about 9.50 GiB and USS by about 9.49 GiB, matching the output size.
- Validation: focused acceptance regression `58 passed`; full pytest `420 passed`; probe `py_compile` and `git diff --check` PASS. The first pytest attempt failed only because the inherited default temp/cache roots denied access; reruns used fresh `D:\Codex\_pytest_temp` bases with cacheprovider disabled. Only the known `pynvml` FutureWarning remains.
- P2-5 is formally PASS for manual RAM/Disk-backed V3.5 Assembly. Auto backend, arbitrary downstream full-copy behavior, new 3x5 sampler/model generation, and 3x5 Main Hi-res Fix 2x GPU/resource acceptance remain separate. No Production runtime file required synchronization. Commit/push not performed.

## 2026-08-24 - Phase 2A P2-6 Auto Buffer Backend

- Preserved all existing uncommitted work and accepted snapshots `pre-phase2a-p2-6-auto-source-verified-20260824_112744` (426 files) and `pre-phase2a-p2-6-auto-runtime-w-verified-20260824_112744` (331 files), both with zero SHA-256 mismatch after excluding the pre-existing inaccessible `.pytest_cache`.
- Added `Auto` to only the independent V3.5 Assemble backend. New V3.5 assembler nodes default to Auto; saved manual `RAM` and `Disk-backed` values remain compatible. V3.4 paths and sockets were not changed.
- Fixed policy: RAM requires final IMAGE `<= 4 GiB` and available physical memory `>= final IMAGE + max(4 GiB, 10% total RAM)`. Otherwise Auto selects Disk-backed. Missing memory counters select Disk-backed. Disk requires final IMAGE plus a 2 GiB reserve; measurement/capacity/allocation failure is explicit with no RAM fallback.
- Added detailed decision reporting and CPU regression for safe RAM choice, size-limit Disk choice, memory-pressure Disk choice, missing counters, disk shortage, manual compatibility, actual selected writer, bit-exact output, and backing lifetime.
- Synchronized only `v3/file_backed_buffer.py`, `v3/assembly_v35.py`, and a preserved-runtime merge of `v3/driving_nodes.py` to ComfyUI_W. The first two match source SHA-256; the third matches the prepared merge exactly and retains the pre-existing runtime Video Reference tooltip addition.
- Headless real acceptance `P26-auto-ram-long-terminal-20260824_113400` used accepted 3x5 FL2VA Long Terminal Merge physical latents plus Core GPU Video/Audio Decode. Auto selected RAM for the 1,769,472,000-byte final IMAGE and reproduced the accepted P2-5 640x640 / 360f / 15.000s video/audio hashes exactly.
- Headless stress acceptance `P26-auto-disk-stress-20260824_113610` selected Disk-backed for the 10,192,158,720-byte / 9.49 GiB final IMAGE, reproduced the accepted stress hashes, retained one pair only while cached, and reclaimed all managed files after release.
- Validation: focused regression `66 passed`; full pytest `428 passed`; source/runtime `py_compile`, runtime verifier, and `git diff --check` PASS. Only the known `pynvml` FutureWarning remains. Commit/push not performed.

## 2026-08-24 - V3.5 release-candidate preparation

- Preserved all existing uncommitted changes and accepted verified snapshots `pre-v35-release-preparation-source-verified-20260824_115858` (426 files) and `pre-v35-release-preparation-runtime-w-verified-20260824_115858` (331 files), both with zero SHA-256 mismatch.
- Updated `version.py`, `pyproject.toml`, `metadata.ini`, Changelog, package information/validation, and English/Japanese README to `3.5.0`. Added an automated metadata-consistency regression.
- Promoted the prior local Hi-Res connection memo to `docs/V35_HIRES_FIX.md`. The public guide distinguishes standard integrated Pixel/VAE Hi-Res Fix from the external-latent Advanced Second Pass Bridge, documents workflow-side SIGMAS, and warns that direct high-ratio latent interpolation is not the accepted Main path.
- Classified public artifacts. Production modules, applicable CPU tests, the public guide, and Production-required `tools/p20_file_backed_tensor_poc.py` are included in `MANIFEST.sha256`. Generated media/results and diagnostic workflows are excluded; P2-4/P2-5 probes remain repository-only validation tools.
- Targeted release/V3.5 regression is `75 passed`; canonical full pytest is `430 passed`. Source and synced ComfyUI_W runtime verifier both report V3.5.0, native PackedLayout PASS, Fixed 3x5 prompt-plan PASS, and expected node registration. Only the known `pynvml` FutureWarning remains.
- Synchronized only release metadata, READMEs, Manifest, the public V3.5 guide, and its metadata regression to the already snapshotted ComfyUI_W runtime, with per-file SHA-256 equality. Runtime-specific Production differences were not overwritten.
- Representative release GPU revalidation used the accepted Long Terminal Merge revision through Core GPU Decode and Assemble V3.5 Auto. Result: PASS, 3 logical / 2 physical groups (`37T + 77T`), 640x640, 360f, 24 fps, 15.000s, exact accepted video/audio hashes, finite outputs, and zero managed backing files after release. Evidence: `D:\Codex\_test_results\ComfyUI-H3-Continuum\V35-release-candidate-auto-long-terminal-20260824\p25_backend_result.json`.
- Main Hi-Res Fix remains Experimental because 3x5 2x and Reference/Hybrid-specific GPU acceptance are pending. Commit/push not performed.

## 2026-08-24 - V3.5 pending GPU acceptance

- Preserved all uncommitted work. Verified pre-documentation snapshots are `pre-v35-pending-gpu-results-source-verified-20260824_130824` (431 files) and `pre-v35-pending-gpu-results-runtime-w-verified-20260824_130824` (334 files), excluding `.git` and the pre-existing inaccessible `.pytest_cache`.
- Started ComfyUI_W headlessly on `127.0.0.1:8188` and submitted workflows through its HTTP API. Test GPU was an NVIDIA GeForce RTX 5060 Ti with 16,311 MiB VRAM. No Production code was changed.
- Main Hi-Res Fix 3x5 FL2VA 2x used 576x576 First Pass, Lanczos 1152x1152 target, `res_multistep`, and workflow `simple / 10 steps / denoise 0.35`. First Pass retained the Long Terminal Merge contract: 3 logical chunks, 2 physical groups (`37T + 77T`), logical `[2,3]` shared terminal sample, and 362 pre-assembly frames. The 37T Second Pass group completed 10/10; the terminal 77T group failed at its first Second Pass inference with CUDA OOM (15.93 GiB limit, 10.04 GiB allocated, 1.49 GiB requested). Result: FAIL on the tested 16 GiB GPU; prompt id `e6042730-1618-4967-9e3b-06125ff8ee35`.
- Hybrid FL2VA + Reference 1x5 integrated Main Hi-Res Fix 2x passed. It used one captured context-aware physical group, one Second Pass sampling call, Lanczos 576-to-1152, actual refine seed `2946484852083492747`, and bit-exact first-pass audio LATENT passthrough. Core Decode / Assemble produced 1152x1152, 120 frames, 24 fps, 5.000 seconds, 32 kHz stereo. Visual contact-sheet inspection found no persistent colored line/plate artifact, flash, or temporal collapse. Output `V35_RC_HybridReference_MainHiRes_1x5_576to1152_d035_00001_.mp4`, SHA-256 `E5B27CABCD5FBC1422F169AC6E75570EF4D54010CD04A3439852D8DED15C1384`; prompt id `c48dd1de-dd45-4896-b39e-45478d971194`.
- Direct `H3ContinuumSecondPassV35` Hybrid/Reference 1x5 also passed independently at 576x576. It reported `conditioning_source=refine_context`, actual refine seed `5765580629374593532`, `(1, 24, 37, 36, 36)`, one sampling pass, temporary refined audio discard, and bit-exact first-pass audio passthrough. Core Decode / Assemble produced 120 frames / 5.000 seconds; visual inspection was clean. Output `V35_RC_HybridReference_MainHiRes_1x5_576to1152_d035_00002_.mp4` (filename retained from the reused workflow prefix), SHA-256 `67311A797CD812584B4E2CCC21D7DF83AE8C1F1D72AB8BF5FA1C142D00894D2D`; prompt id `01b8a2a6-245d-4d29-bc4d-0e92426308d2`.
- The Hybrid prompt omitted angle brackets around `Picture 3`, generating a non-blocking H3C-P103 warning. Connected Reference conditioning remained active; this is accepted for execution/transport but not a warning-free public prompt example.
- Final validation after documentation synchronization: full canonical pytest `430 passed`; ComfyUI_W runtime verification passed package 3.5.0 registration, native PackedLayout, and Fixed 3x5 planning; `git diff --check` passed. README English/Japanese, the V3.5 guide, package validation, and Manifest match ComfyUI_W by SHA-256.
- Remaining acceptance: Main 3x5 2x on more than 16 GiB VRAM or a lower-memory terminal 77T implementation, and Reference/Hybrid durations longer than 1x5. Hi-Res Fix remains Experimental. Commit/push not performed.

## 2026-08-24 - V3.5.0 formal README and release publication

- Preserved all accumulated uncommitted V3.4 Terminal Merge, E2-8, Phase 2A, V3.5, test, and release-preparation work. Verified snapshots are `pre-v35-formal-readme-release-source-verified-20260824_141358` (431 files) and `pre-v35-formal-readme-release-runtime-w-verified-20260824_141359` (334 files), excluding `.git` and the pre-existing inaccessible `.pytest_cache`.
- Reorganized English/Japanese README around the two V3.5 additions: Continuum-aware Second Pass / experimental integrated Hi-Res Fix, and low-memory Assemble + Seam. Added concise wiring, the workflow-side SIGMAS baseline, OFF/no-Hi-Res performance behavior, 16 GiB GPU acceptance limits, and an explicit V3.4 saved-workflow compatibility statement.
- Added separate Hi-Res Fix and Second Pass node images without BasicScheduler, wires, or group labels. The Hi-Res image uses the accepted `lanczos / 2.00` setting. Image generation/editing was limited to isolating the supplied UI and aligning that displayed option; README text remains authoritative for connections and SIGMAS.
- Added the validated 9.49 GiB stress numbers to both READMEs: private memory 12.41 -> 2.91 GiB and USS 10.29 -> 0.80 GiB, with hash-identical RAM/Disk output. Explicitly documented that this is host-RAM/private-commitment reduction, not sampler VRAM reduction, and that Disk-backed can affect final assembly I/O rather than model sampling speed.
- Updated Changelog, package information, package validation, V3.5 guide wording, and the 159-entry Manifest. Full canonical pytest is `430 passed`; every Manifest hash, `git diff --check`, and ComfyUI_W runtime verification pass. Nine changed public files/assets were synchronized to ComfyUI_W with per-file SHA-256 equality.
- User explicitly authorized committing and pushing the complete V3.5.0 release state to `origin/main`.

## 2026-08-24 - V3.5.1 Last Queued Seed reuse frontend fix

- Preserved all existing Issue #9/#10 and earlier uncommitted work. The standard snapshot script was attempted first and failed only on the known ACL-inaccessible top-level `.pytest_cache`; accepted SHA-256-verified snapshots are `pre-v351-last-queued-seed-fix-source-accepted-20260824_210526` (467 files) and `pre-v351-last-queued-seed-fix-runtime-w-accepted-20260824_210526` (339 files), excluding `.git` and `.pytest_cache`, both with zero mismatch at source revision `ee7b9937dc9bda5b4e55b012e8e725b7afc5f3aa`.
- Added session-only V3.5 sampler Seed state in `web/last_queued_seed.js`: `last_queued_seed`, `auto_updated_seed`, `previous_control_mode`, and `auto_update_pending`. `beforeQueuePrompt` captures the submitted Seed; `Randomize -> Fixed` restores it only when the displayed value still equals the exact ComfyUI automatic After Generate update. A manual Seed edit clears pending restoration. Linked/missing Seed inputs clear the capture.
- No Workflow JSON state, new widget, backend change, cache manipulation, Run Storage relaxation, Sampling/Second Pass/Terminal Merge/Assembly/Seam change, V3.4 behavior change, Node ID change, or display-name change was introduced. Seed restoration only restores normal cache eligibility; an absent cache regenerates normally with the same Seed.
- Added `tests/test_v351_last_queued_seed_frontend.py` with an actual Node.js module harness covering automatic restore, manual override, consecutive Randomize queues, Before Generate/no-update behavior, Fixed baseline, and linked Seed cancellation. Focused frontend regression is `5 passed`; JavaScript syntax passes; canonical full pytest is `445 passed` with only the known `pynvml` FutureWarning; source Manifest has 165 entries with zero missing or mismatched hashes; `git diff --check` passes.
- Synchronized only `web/project_id.js` and new `web/last_queued_seed.js` to ComfyUI_W; both match source SHA-256. The runtime-specific Manifest received only the matching frontend entry updates; its pre-existing unrelated divergence from the canonical source Manifest was not normalized or overwritten. Runtime JavaScript syntax, compact-UI regression (`2 passed`), package registration, native PackedLayout, and Fixed 3x5 planning pass. Real `Randomize -> Fixed -> Second Pass ON` browser/cache acceptance remains pending; ComfyUI_W was not restarted or reloaded. Commit/push not performed.

## 2026-08-24 - V3.5.1 Hi-Res Fix Core canvas alignment

- Preserved all existing Issue #9/#10/Seed Fix working-tree changes. The standard snapshot script again encountered only the known top-level `.pytest_cache` ACL denial; accepted SHA-256-verified snapshots are `pre-v351-hires-core-alignment-source-accepted-20260824_213303` (470 files) and `pre-v351-hires-core-alignment-runtime-w-accepted-20260824_213303` (340 files), excluding `.git` and `.pytest_cache`, with zero mismatch at source revision `ee7b9937dc9bda5b4e55b012e8e725b7afc5f3aa`.
- Diagnosed the GPU failure `shape '[1, 24, 1, 1, 21, 2, 21, 2]' is invalid for input of size 44376`: manual `576x576 * 1.2` used `round(36 * 1.2) = 43`, while Core H3 requires a 32-pixel canvas grid / even latent dimensions for its `2x2` spatial patchifier.
- Added Core-derived manual target alignment in `v3/hires_fix_nodes.py`. The failing case now produces `704x704` / `44x44`; rectangular `1024x576 * 1.2` produces `1216x704` / `76x44`. No Sampling, Conditioning adaptation, Terminal Merge, Assembly, Seam, Run Storage, node schema, ID, or display name changed.
- Added direct and integrated square/rectangular regressions. Focused Hi-Res/Second Pass result is `48 passed`; full source pytest is `448 passed` with only the known `pynvml` FutureWarning. An initial full run's 97 setup errors were solely the existing inaccessible global pytest temp root and disappeared with an explicit writable `--basetemp`.
- Synchronized only `v3/hires_fix_nodes.py` to ComfyUI_W and verified exact SHA-256 equality. Runtime verifier passed package registration, native PackedLayout, and Fixed 3x5 planning. The running ComfyUI process was not restarted, so GPU re-acceptance remains pending after a deliberate restart. The attempted Seed cache run was not valid because its second prompt was queued before the first completed; logs show First Pass `20/20` ran again. Commit/push not performed.

## 2026-08-25 - V3.5.1 Reference Audio conditional UI and naming

- Preserved all existing Issue #9/#10/Seed/Hi-Res working-tree changes. The standard snapshot attempt failed only on the known ACL-inaccessible top-level `.pytest_cache`; accepted SHA-256-verified snapshots are `pre-v351-reference-audio-conditional-ui-source-accepted-20260824_230702-ee7b993` (470 files) and `pre-v351-reference-audio-conditional-ui-runtime-w-accepted-20260824_230702` (340 files), excluding `.git` and `.pytest_cache`, with zero mismatch.
- Added `web/reference_audio_ui.js`. V3.5 Reference Audio sockets default to `Hidden` when unlinked, can be restored with `Show`, retain their original input positions, auto-open for connected saved workflows, and cannot be hidden while linked. No graph link is removed. The UI widget is attached only after Core graph configuration and removed from serialized Workflow widget values to avoid reload shifts.
- Clarified only human-facing labels/tooltips: `Video Guide Frames`, `Driving Audio`, `Driving Audio VAE`, `Reference Audio (Optional)`, and `Reference Audio VAE (Optional)`. Backend input keys, ordering, types, Node IDs, conditioning paths, Sampling, Terminal Merge, Assembly, Seam, and Run Storage contracts are unchanged.
- Live Chrome/ComfyUI testing on the already-running `127.0.0.6:8188` instance found and corrected two integration-specific issues that the initial mock did not expose: current Core keeps widget descriptors after the Reference Audio sockets in `node.inputs`, and UI injection before graph configuration can shift saved widget values. Final live acceptance passed `Hidden`, `Hidden -> Show -> Hidden`, original-position restoration, connected auto-`Show`, and linked hide protection. Temporary workflows were closed without saving; the template workflows were not modified.
- Added/updated real JavaScript harness coverage for Core-style non-terminal inputs, disconnected `-1`, workflow serialization, labels, show/hide, link protection, callback chaining, and absent-input recovery. Focused validation is `20 passed`; canonical full pytest is `450 passed`; JavaScript syntax, `git diff --check`, and ComfyUI_W runtime verification pass with only the known `pynvml` FutureWarning.

## 2026-08-25 - V3.5.1 release documentation and naming

- Renamed the displayed video-guide inputs to `Video Guide Frames` and `Video Guide Size`; backend keys, input order, Node IDs, graph links, and saved-workflow compatibility remain unchanged.
- Expanded English/Japanese README guidance for V3.5.1 Reference Audio, Conditioning Bridge, Last Queued Seed Reuse, and the distinct roles of still Reference Images, Video Guide Frames, Driving Audio, and Reference Audio.
- Updated package version metadata, Changelog, package information, package validation, release tests, project state, and distribution Manifest for V3.5.1.
- User explicitly authorized committing and pushing the complete V3.5.1 release state after validation. The supplied screenshots still showed the old display label, so no stale screenshot was added to the release documentation.
- Replaced the initially supplied stale/shifted screenshots with three user-approved normal-state images showing `Video Guide Frames`, `Reference Audio Inputs: Hidden`, and `Show`; both README editions reference the same assets.
- Final release checks: canonical ComfyUI_W-root pytest `450 passed` with only the known `pynvml` warning; JavaScript syntax and `git diff --check` pass; all 172 Manifest entries and README image/workflow references verify.
- Added the user-supplied LBH + Conditioning Bridge workflow as a separate public connection example and a lightweight SVG flow chart to both README editions. The recommended template remains unchanged, and Core nodes retain their standard display titles.
- Synchronized only the relevant implementation/tests to ComfyUI_W and verified per-file SHA-256 equality. No ComfyUI process was started or stopped. Commit/push not performed.
