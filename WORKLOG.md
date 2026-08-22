# Work Log

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
