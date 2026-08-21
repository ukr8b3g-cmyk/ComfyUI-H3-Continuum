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
