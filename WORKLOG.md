# Work Log

## 2026-08-30 - V3.7 Tail 6 README and release images

- Used the V3.6 release infographic `D:\SD_PIC\Neo\Clip_95.png` as the style/layout reference to create `docs/images/v37-tail6-second-pass.png`, a 1536x1024 V3.7 infographic covering the exact Tail 6 suffix, `100.27 s -> 64.18 s` (`-36.0%`), Conditioning Adapter, RefineSchedule v1, Audio bit-exactness, V3.6 default compatibility, and Still Image Guide Production HOLD.
- Used `docs/images/v36-sampler-node.png` as the edit reference for `docs/images/v37-sampler-node.png`, updating the title to V3.7 and adding the optional `guide` input. The V3.7 infographic replaces the old remote V3.6 hero in the English README; the V3.7 node UI replaces the V3.6 node image in the later interface section.
- Added the English Tail 6 performance explanation and clarified that RefineSchedule manages the exact range while the speedup comes from six evaluations instead of ten. Both PNGs pass Pillow verification; the 187-entry Manifest has zero missing/mismatch, full regression is `633 passed`, and `git diff --check` passes. Runtime logic, version, release tag, README_JA, commit, and push are unchanged.
- Accepted pre-change snapshots are `pre-v370-readme-tail6-image-source-approved-20260830_025423` (227 files) and `pre-v370-readme-tail6-image-runtime-w-approved-20260830_025423` (170 files), both at revision `093475dba798f0a24a6d8291ae4b42ec90e86c79` with zero SHA-256 mismatch.

## 2026-08-30 - V3.7.0 release publication

- Created verified pre-change snapshots of the authoritative source and ComfyUI_W runtime before release-only edits: `pre-v370-release-metadata-source-approved-20260830_022944` (227 files) and `pre-v370-release-metadata-runtime-w-approved-20260830_022944` (170 files), both at revision `ecc72dae9bad1fb909b8e2a003b8e4e5013f4a09` with zero SHA-256 mismatch.
- Unified `version.py`, `pyproject.toml`, and `metadata.ini` at `3.7.0`; updated English/Japanese release documentation, package information, validation text, and version assertions. The release message centers on the Conditioning Adapter and RefineSchedule foundations and states that Still Image Guide is Experimental / Production HOLD because of hard-anchor trajectory changes.
- Runtime generation logic, public Production defaults, existing workflows, and the untracked PDD workflow were not changed.
- Final local Release Gate passed: `633 passed`, 185 Manifest entries with zero missing/mismatch, Python/JavaScript syntax, `git diff --check`, runtime verification as `3.7.0`, live V3.7/V3.6 schema registration, empty queue, and exact source/runtime SHA-256 for 25 release/Production files. ComfyUI_W restarted as PID `8296`; evidence is `D:\Codex\_test_results\ComfyUI-H3-Continuum\v370-release-runtime-restart-20260830`.
- Published release commit `fe4ff9c20c2cc8bb375625d1534f5673a737d1be` to `origin/main`, created annotated tag `v3.7.0` pointing to that commit, and published the non-draft, non-prerelease GitHub Release `ComfyUI-H3-Continuum v3.7.0`. The tag remains fixed at the validated release commit; this post-publication record is a separate documentation-only main commit.

## 2026-08-30 - V3.7 frontend parity and Still Guide input hardening

- Audited four findings from an older WIP ZIP against the current authoritative source. Confirmed and fixed the V37 compact-frontend class omission and the overly broad Still Guide IMAGE batch contract. The reported Guide/First/Last collision was already fixed by explicit Guide-role priority, and the Reference Audio `Hidden / Show` behavior was an obsolete pre-V3.5.1 expectation rather than a current regression.
- Added `H3ContinuumSamplerV37` to the same setup and queue-normalization paths as V3.6. Enforced exactly one Still Guide image during public payload creation and defensive source preparation. Added regressions for V37 frontend routing, batch sizes 0/2/5, defensive batch validation, and Guide collisions at physical frames 0 and 123.
- Accepted snapshots are `pre-v37-frontend-batch-contract-approved-accepted-20260830_020900` (source, 646 files, zero mismatch, revision `ecc72dae9bad1fb909b8e2a003b8e4e5013f4a09`) and `pre-v37-frontend-batch-contract-runtime-w-approved-accepted-20260830_020901` (ComfyUI_W runtime, 359 files, zero mismatch). Focused validation is `45 passed`; final full regression is `633 passed` with only the known `pynvml` warning. Runtime files were synchronized with exact SHA-256 equality. No GPU rerun, Production-default change, version change, commit, push, or release was performed.

## 2026-08-30 - V3.7 Conditioning Adapter and RefineSchedule pillars

- Added the internal schema-v1 `RefineSchedule` contract and integrated it into context-aware Second Pass without changing public node schemas or the existing SIGMAS socket. External/Full preserve the source tensor, Tail/Partial select exact source ranges, and Second Pass records schedule/hash/noise/audio policy in its contract. First Pass Run Storage reuse remains schedule-independent; schedule differences are identified at the Second Pass contract.
- Added original-source ownership for one Still Image Guide. The owner group alone retains a CPU source clone, source hash, absolute frame, and Guide schema/mode identity; target-resolution Second Pass conditioning reencodes the marked Guide from that source rather than resizing its First Pass latent fallback.
- GPU Gate PASS for correctness: 704x704 internal Tail 6 completed in six evaluations. A final same-Sage comparison against the earlier external `SplitSigmas` Tail 6 baseline produced Video SSIM `0.982936` and identical decoded PCM SHA-256 with matching 120-frame/5-second contracts. The 1152x1152 Guide + Tail 6 run reencoded the 1254x1254 Guide source to 72x72 latent geometry and completed with valid Video and 32 kHz stereo Audio. That Guide output was low-motion/freeze-detected, so the existing Still Image Guide hard-anchor quality and Production HOLD decisions are unchanged.
- Final regression is `626 passed`; compileall, Manifest hashes, runtime source equality, runtime verifier, and `git diff --check` pass. Evidence is under `D:\Codex\_test_results\ComfyUI-H3-Continuum\v37-pillars-gpu-gate-20260830`. No commit, push, release, Production-default change, or public workflow change was performed.

## 2026-08-28 - Sampling layout-validation measurement and no-fast-path decision

- Started from the formally accepted Phase 1 source/runtime snapshots and added Detailed-Report-only instrumentation around the existing full `validate_native_continuity_layout()` call. It records calls, full validations, statuses, wall time including existing D2H/implicit synchronization, physical groups, and per-step contribution without adding explicit CUDA synchronization. Normal diagnostics modes and generation semantics are untouched.
- Focused regression is `43 passed`; canonical full pytest is `570 passed`. All 180 Manifest hashes, changed-file syntax, runtime verifier, source/runtime identity, empty queue, and `git diff --check` pass. The first full-pytest attempt is excluded because its newly named `--basetemp` parent did not yet exist; it produced setup-only errors while 466 tests passed. Re-running after creating the parent produced the accepted all-PASS result.
- GPU matrix PASS on the existing ComfyUI_W Sage backend: 384x384, 2x5-second I2VA + Continuation, Compatibility Reference Context, 4 steps, fixed seed `361040`. Sage: 4 full calls / 1.889 ms total / 0.472 ms per step. Sage+Sol: 4 / 2.122 ms / 0.530 ms. Sage+Spectrum: 8 / 4.658 ms / 1.164 ms. Sage+Sol+Spectrum: 8 / 4.431 ms / 1.108 ms. All routes reported zero failures; no explicit `torch.cuda.synchronize()` was used. Because global `--use-sage-attention` has no observable MODEL marker, controlled prompt configuration plus the backend command line is the authoritative Sage route evidence.
- Representative 576x576 / 20-step Sage PASS: 20 calls, 20 full validations, zero failures, `14.289 ms` total and `0.714 ms/step`. Sampling was `321.632848 s` and API elapsed was `382.055317 s`, so the validator contributes only about `0.00444%` of Sampling and `0.00374%` of API time.
- Rejected the proposed validation cache/fast-path: its theoretical maximum representative gain is only about 14 ms, far below a material Production improvement. No Layout, Sampling, Terminal Merge, Run Storage, UI, metadata, workflow, schema/version, or transport behavior was optimized or changed. Evidence and the reusable live-API runner are under `D:\Codex\_test_results\ComfyUI-H3-Continuum\layout-validation-profile-phase`. Commit and push were not performed.

## 2026-08-28 - G3 FL2VA prefix correctness repair and Phase 1 PASS

- Scoped the G3 repair to the existing post-Run-Storage FL2VA guard. `FLF_STRATEGY` is now required only when Terminal Merge is active; a real-Last-Frame non-Terminal request keeps the compatible prefix already validated by Run Storage. A missing/mismatched Terminal strategy still discards the prefix, and terminal pair atomicity remains unchanged.
- Added three regressions for non-Terminal prefix retention, Terminal missing-strategy rejection, and matching-Terminal retention. Focused result is `63 passed`; canonical full result is `568 passed`. Manifest 180 entries, compileall except the known inaccessible `.pytest_cache` listing notice, runtime verifier, source/runtime SHA-256, Python/JavaScript syntax, empty queue, and `git diff --check` pass.
- Synchronized only `v2/sequence.py` to ComfyUI_W and restarted the same `127.0.0.6:8188` Sage backend with its recorded venv Python and arguments. Verified pre-change snapshots are `pre-g3-fl2va-prefix-correctness-source-accepted-20260828_165400-ecc72da` (632 files) and `pre-g3-fl2va-prefix-correctness-runtime-w-accepted-20260828_165400-ecc72da` (351 files), excluding only `.git` and the known inaccessible `.pytest_cache`, with zero mismatch. Final accepted snapshots are `phase1-correctness-pass-source-accepted-20260828_172802-ecc72da` and `phase1-correctness-pass-runtime-w-accepted-20260828_172802-ecc72da`.
- Formal GPU rerun PASS: G1 current canonical cache `2/1` with Sampling 1; G2 isolated actual legacy V3.6.1 `"none"` cache `2/1` with Sampling 1; G3 real-Last-Frame non-Terminal FL2VA `1/2` with Sampling 2 and no FLF-strategy reset; G4 Terminal Merge `1/2` with one physical `77T/433T` Sampling call; G6 Run Storage Off completed with one Sampling call and no queue error.
- G5 fresh 3-chunk versus matched 2→3 extension retained exact equality for all three Video/Audio latent SHA-256 values, decoded RGB24, decoded PCM, 360 frames, and 480256 PCM samples/channel. Phase 1 G1-G6 is formally **PASS**. Evidence: `D:\Codex\_test_results\ComfyUI-H3-Continuum\phase1-gpu-acceptance-20260828\20260828_170034\gate_summary.json`.
- Public UI, metadata, workflows, schema/version, Reference/Masked transport identity, optimization paths, commit, push, and release were not changed.

## 2026-08-28 - Phase 1 Run Storage GPU Acceptance Gate

- Ran G1-G6 against the already-running ComfyUI_W 0.34.2 backend at `127.0.0.6:8188` on RTX 5060 Ti 16 GiB. G1 current canonical I2VA 2→3 and G2 actual legacy V3.6.1 `"none"` cache both passed at `2 reused / 1 generated`; G4 FL2VA Terminal Merge passed at `1 / 2` with one `77T Video / 433T Audio` physical Sampling call; G6 Run Storage Off completed with one Sampling call and no hidden-value queue error.
- G5 compared a fresh 3-chunk run with the matched 2→3 extension at 576x576, 3x5 seconds, 20 steps, and Variation Nonce 1. All three raw Video latent SHA-256 values and all three Audio latent SHA-256 values matched. Decoded RGB24 and PCM hashes also matched; both outputs are 360 frames and 480256 decoded PCM samples/channel.
- G3 failed the required negative case: real-Last-Frame non-Terminal FL2VA expected `1 reused / 2 generated` but returned `0 / 3` with three Sampling calls. The old/new top-level Last Frame hash and Chunk 1 contract hash are identical, and the report first says `resuming after accepted chunk 1`; the subsequent existing FLF whole-sequence guard clears that prefix because a non-Terminal request has no saved terminal `flf_execution` semantic.
- Overall Phase 1 status is **HOLD**. The G3 finding is outside the absent-hash compatibility implementation and was not repaired because this gate explicitly prohibited Sampling and Terminal Merge contract changes. No optimization, post-acceptance snapshot, commit, push, or release was performed. Evidence: `D:\Codex\_test_results\ComfyUI-H3-Continuum\phase1-gpu-acceptance-20260828\20260828_154951\gate_summary.json`.

## 2026-08-28 - V3.6.1 Run Storage correctness hotfix

- Canonicalized absent Last Frame hashes to `""` and added a strictly limited V3.6.1 cache compatibility comparison: both top-level Last Frames must be absent, and the per-chunk `last_frame_hash` spelling must be the only contract difference. Real Last Frame changes and FL2VA Terminal Merge atomicity remain strict; no schema/version bump or optimization was included.
- Run Storage Off now resets hidden Regenerate From/Variation Nonce widgets to `Auto`/`0` on toggle and graph load, and defensively rewrites the queued API inputs. Backend validation remains unchanged.
- Added regressions for canonical/legacy no-Last-Frame 2→3 reuse, real Last Frame invalidation, unrelated-field rejection, exact resume, Terminal Merge 1/2 atomicity, and frontend toggle/reload/queue serialization. Focused result: `64 passed`; full result: `565 passed`; all 180 Manifest entries, Python/JS syntax, and `git diff --check` pass.
- Synchronized only `run_storage.py` and `web/project_id.js` to ComfyUI_W after accepted source/runtime snapshots `pre-phase1-correctness-hotfix-accepted-20260828_150500-ecc72da` and `pre-phase1-correctness-hotfix-comfyui-w-20260828_150659-ecc72da`. Runtime verifier and source/runtime hashes pass. The first restart attempt used the resolved base CPython and stopped before listening because venv dependencies were absent; the same backend was immediately restored through `ComfyUI_W\venv\Scripts\python.exe`, with no double-start or queued job.
- Actual ComfyUI_W 0.34.2 / RTX 5060 Ti GPU prompt `bf619577-2057-4635-8fef-2537a40295c4` extended an isolated copy of legacy revision `9c35c64b529a5c2c` from 2→3 chunks as `2 reused, 1 generated`; first regenerated Chunk 3, Sampling `169.256391s`, output `D:\output\video\comfy_video\video\MiniMax_H3_00008_.mp4`, and empty final queue. Exact 2-chunk prompt `e593b06a-9a37-4cc1-932c-0d13e55979c1` then passed as `2 reused, 0 generated`, first regenerated `none`, output `MiniMax_H3_00009_.mp4`.

## 2026-08-28 - Current V3.6 sampler README images

- Replaced the English README's obsolete V3.4 combined workflow screenshot with separate current `H3 Continuum Sampler V3.6` and `H3 Continuum Assemble + Seam V3.5` node images, and added the same images to the Japanese recommended-template section.
- Clarified that the current Production path combines the V3.6 sampler with the V3.5 low-memory assembler. No node, workflow, schema, or runtime behavior changed.
- Snapshot: `pre-readme-v36-node-images-20260828_121500-8dec0b7` (219 tracked files, zero missing or SHA-256 mismatches, revision `8dec0b7ceb961102e36de4dfa735eb40c4cfa4c1`).
- Validation: all 180 Manifest entries PASS, all 13 unique README image links resolve, focused README/release/workflow tests `11 passed`, and `git diff --check` PASS.

## 2026-08-28 - Run Storage partial-regeneration README guide

- Expanded the English and Japanese Run Storage documentation with a concrete normal T2VA/I2VA `2 chunks x 5 seconds` procedure: enable `Save + Auto Resume` before the first run, retain the Run Name and generation contract, select `Regenerate From = Chunk 2`, and confirm `1 reused, 1 generated`.
- Documented that Prompt Plan or other contract changes can create a new revision, `Run Storage = Off` cannot be reused retroactively, regeneration operates at chunk boundaries, reassembly reevaluates Seam processing, and FL2VA Long Terminal Merge regenerates its final atomic pair together. No Production code, UI, workflow, or schema changed.
- Snapshot: `pre-readme-run-storage-regenerate-guide-20260828_115840-8dec0b7` (630 files, mismatch 0, revision `8dec0b7ceb961102e36de4dfa735eb40c4cfa4c1`). Validation: 178 Manifest entries PASS, focused README/release/workflow tests `11 passed`, and `git diff --check` PASS.

## 2026-08-28 - README ComfyUI compatibility requirement

- Added a concise English/Japanese installation note: ComfyUI `>=0.32.0` is required, package validation passed on `0.33.3`, V3.6.1 GPU Smoke passed on `0.34.0`, and the latest ComfyUI release is not mandatory.
- Updated the README entries in `MANIFEST.sha256`. Validation passed with `552 passed`, the ComfyUI_W V3.6.1 runtime verifier, native PackedLayout, Fixed 3x5 Prompt Plan, and `git diff --check`. The initial validation attempts were environment-only failures caused by the system Python lacking pytest and the known default pytest temp-directory ACL; the accepted run used the established ComfyUI_W Python and a writable dedicated `--basetemp`.

## 2026-08-27 - V3.6.1 Strong 39 fallback GPU Smoke

- Ran the synchronized ComfyUI_W runtime at `127.0.0.6:8188` on ComfyUI 0.34.0 / RTX 5060 Ti 16 GiB with Sage Attention and `--disable-pinned-memory`. The public V3.6 node used Standard, Audio Continuity ON, Strong 39, T2VA 2x5 seconds, 576x576, 20 steps, fixed seed `361039`, Run Storage OFF, and Detailed Report.
- API prompt `f5d5c36c-fa5b-4031-ba0e-349cf70ff64f` completed in `412.034s`. The report explicitly resolved `Reference Context` before execution with the expected Balanced-22 requirement reason; chunk 2 used 39 frames of fixed Reference Context, and no schema, Sampling, finite-validation, Decode, Assemble, save, OOM, or queue error occurred.
- Output `D:\output\video\comfy_video\video\V361_Strong39_Fallback_Smoke_00001_.mp4` is H.264 `576x576`, `240f`, `24fps`, exactly `10.000s`, with AAC 32 kHz stereo audio of exactly `10.000s`. The queue returned to empty. V3.6.1 GPU Smoke is PASS; commit/push remain pending.

## 2026-08-27 - V3.6.1 mixed Prompt syntax parser hotfix (unreleased)

- Preserved all existing tracked/untracked work and created verified snapshot `pre-v361-prompt-parser-hotfix-accepted-20260827_190257` at revision `0d18e3abe0923502171f47f24769e957057eaf15` (214 files, zero SHA-256 mismatch). The standard snapshot attempt stopped only on the known `.pytest_cache` ACL before any edit.
- Updated only the shared Python Prompt planner and tests: Auto/Timeline now ignore standalone `---` lines when Timeline syntax is active, issue `H3C-P105`, keep following text in the current Timeline section, and preserve `H3C-P101` fallback. Explicit List keeps List parsing with a mixed-syntax warning; Explicit Fixed and invalid-Timeline Fixed fallback remain literal/fail-open.
- Warning reports now lead with `PROMPT PREFLIGHT WARNING` and retain resolved Timeline or List source mappings. Prompt Preview consumes the same plan/report; no Frontend Toast, JavaScript parser duplication, schema bump, or Production Sampling/Masked AV/Reference/Terminal/Assembly/Seam change was introduced.
- Added mixed Auto/Timeline/List/Fixed, shared-preamble separator, five-chunk trailing separator, missing-chunk fallback, report, Preview, invalid fallback, and Run Storage revision-separation regressions. Results: focused `71 passed`, related `94 passed`, full `538 passed`, compileall PASS, V3.6.0 source runtime verifier against ComfyUI_WAN PASS, and `git diff --check` PASS. GPU, runtime synchronization, version metadata, release, commit, and push were intentionally not performed.

## 2026-08-27 - V3.6.0 public release implementation and GPU smoke

- Added `H3 Continuum Sampler V3.6` as a new public Node ID while preserving V3.5.3/V3.4 nodes and widget sequences. Public backend choices are only `Standard` and `Compatibility`: Standard maps to Masked AV or Masked Video according to Audio Continuity, while Compatibility maps to the original Reference Context path. Internal transport names remain private.
- Updated package/version metadata, CHANGELOG, package validation/info, README English/Japanese, compact frontend handling, runtime verifier registration, and a copied V3.6 recommended workflow. The V3.5 workflow remains unchanged. Added public-node/backend/schema/workflow regressions.
- Synchronized only `nodes.py`, `version.py`, `metadata.ini`, `v3/driving_nodes.py`, and `web/project_id.js` to ComfyUI_WAN after snapshot `pre-v360-public-runtime-wan-20260827_172531`; all five hashes matched. Restarted the same Sage + `--disable-pinned-memory` backend and confirmed V3.6 registration with `Standard` default.
- Normal API GPU Smoke using the public node completed in `65.21s`: 2x5-second I2VA + Reference Image + Reference Audio, 384x384, four steps, Standard backend, Audio Seam Auto. Output `V36_Release_Smoke_Reference_AV_Standard_00001_.mp4` is 240f / 24fps / 10.000s with 32 kHz stereo 10.000s audio; the report confirms Masked AV on continuation chunk 2. Evidence: `D:\Codex\_test_results\ComfyUI-H3-Continuum\v360-release-smoke\20260827_172835`.
- Focused release validation is `81 passed`; final full source pytest is `527 passed`; V3.6.0 runtime verifier, JavaScript syntax, changed-file `py_compile`, the regenerated 178-entry Manifest, README link validation, source/runtime SHA-256 equality for 12 Production files, `git diff --check`, and empty API queue all pass. Commit/push/release are the remaining publication actions; the backend remains running.

## 2026-08-27 - V3.6 PIG-5 subjective audio acceptance

- User completed subjective listening of `V36_PIG3_Reference_Image_Audio_Masked_AV_00001_.mp4` and reported **Audio PASS**. No click, dropout, unnatural stereo positioning, or other audible boundary defect was reported.
- PIG-0 through PIG-5 and V3.6 public-promotion eligibility are now formally PASS. This records the gate result only: published V3.5.3, public UI/defaults, version metadata, node schemas, runtime files, and workflows were not changed in this step.
- Pre-change documentation snapshot: `pre-pig5-audio-pass-20260827_171054`. Commit/push were not performed.

## 2026-08-27 - V3.6 PIG-5 policy freeze

- User approved the final Production policy: Masked AV is the standard V3.6 continuation backend; Reference Context remains an Advanced compatibility fallback; raw transport names stay internal; Run Storage identity stays transport-scoped; Terminal Merge regeneration remains atomic per physical group; and Audio Seam Auto continues as an independent evaluation path.
- Public promotion remains HOLD only for subjective listening of the accepted PIG-3 output. A clean result for clicks, dropouts, stereo-positioning anomalies, and other audible boundary defects is sufficient to promote V3.6 without reopening PIG-0 through PIG-4. No UI, runtime, node schema, Sampling, Run Storage, or public default was changed in this policy-recording step.
- Pre-change documentation snapshot: `pre-pig5-policy-freeze-20260827_170808`. Commit/push were not performed.

## 2026-08-27 - V3.6 Production Integration Gate PIG-0 through PIG-4

- Preserved published/default V3.5.3, every accumulated V3.6 change, and all unrelated working-tree edits. Accepted exact snapshots are `pre-v36-production-integration-pig0-accepted-20260827_161517` and `pre-v36-production-integration-pig2-diagnostic-accepted-20260827_162943`; the standard full snapshot stopped only on the known inaccessible `.pytest_cache` before edits.
- Added nondefault `continuation_transport` scoping to Run Storage identity, Sampling Contract execution semantics, and generated Session settings while leaving the default `reference_context_v1` revision identity bit-for-bit compatible. Added normal/Terminal Reference Image + Reference Audio CPU regressions and transport/session/terminal identity tests.
- PIG-2 real-cache testing exposed that Run Storage's temporary resume Session omitted stored `flf_execution`, causing all preserved chunks to be discarded. `run_storage.py` now restores execution semantics into the resume Session, and `v2/sequence.py` synchronizes the reuse count after atomic Terminal-pair pruning. The accepted rerun produced `0/3`, `3/0`, `1/2`, and `1/2` reused/generated counts for Save, Auto Resume, Regenerate From Chunk 2, and Chunk 3; the two regeneration requests each made exactly one Terminal physical Sampling call and never split logical `[2,3]`.
- PIG-3 completed 2x5-second I2VA + Reference Image + Reference Audio through Masked AV at 384x384 / 4 steps. Every physical group retained both Reference kinds, protected Video/Audio prefixes were bit-exact after finalization, and the output is finite 240f / 24fps / 10.000s with 10.000s stereo audio. Existing Audio Seam Auto produced a benign retained-boundary jump (`0.004261`, `0.0876x` local p99); subjective listening remains a separate user check.
- Evidence roots are `D:\Codex\_test_results\ComfyUI-H3-Continuum\v36-production-integration\v36_pig2_masked_20260827_164303` and `...\pig3-reference-masked`. Production integration is PASS; public/default promotion remains HOLD pending explicit UI/default-policy approval and subjective Audio Seam listening. No public UI was added, commit/push were not performed, and the backend remains running.
- Final validation: PIG-focused `61 passed`; canonical full pytest `521 passed`; changed-file `py_compile`, V3.5.3 WAN runtime verifier, three source/runtime SHA-256 comparisons, `git diff --check`, and empty API queue PASS. Only the known `pynvml` FutureWarning remains.

## 2026-08-27 - V3.6-R2 shortened FL2VA Long Terminal Merge final GPU gate

- Preserved published/default V3.5.3 and every accumulated uncommitted V3.6 change. Snapshot `pre-v36-r2-short-gate-20260827_000840` contains the exact runner/docs changed for this gate. Added only `--phase r2-short` scheduling to the private gate runner: Seed 607 full Reference/Masked comparison with cache-only Seam OFF, followed by Seed 608 Masked-only acceptance.
- Combined the existing complete Seed 606 Gate A with the shortened runs. All accepted executions preserve 3 logical chunks, 2 physical groups, Group 2 logical `[2,3]`, `paired_timeline_v1`, terminal seed/trim, and `260f / 77T Video / 433T Audio`. Every main MP4 is finite 640x640, 360 frames, 24 fps, and exactly 15 seconds with 15-second audio.
- Seed 607 Reference/Masked Group 1 Video and Audio SHA-256 values match. Seeds 606–608 Masked finalization restores only protected 7T Video and 37T Audio prefixes to bit-exact equality; raw Core drift remains limited to one-float-scale deltas and generated regions remain sampler-owned.
- Terminal PackedLayout is `35,865 -> 32,991` rows, a `2,874`-row / `8.01%` reduction. Synchronized Group 2 Sampling pairs are `574.134 -> 529.933s` and `560.782 -> 544.413s`; both favor Masked. Paired percentage median is `5.31%`; method medians are `567.458s` Reference and `544.413s` Masked (`4.06%` lower). Seed 608 Masked completed in `549.704s` Group 2 / `801.006s` API wall time.
- Five-run monitored peak RSS median is `9.674 GiB`; maximum observed device use is `15.646 GiB`. Terminal CUDA allocator peak is approximately `4.06 GiB` Reference versus `3.80 GiB` Masked. These whole-process/device values are environment- and order-sensitive; no broad memory guarantee is inferred.
- Inspected Seed 606–608 boundary sheets at nominal 5/10/15-second positions and actual 124f/243f retained boundaries. No obvious flash, collapse, direction reversal, or temporal discontinuity was found. Audio analysis found finite 15-second streams and no >=200 ms -50 dB dropout. Audio Seam Auto materially improved Seed 606 Masked, while Seed 607's 124f instantaneous jump increased despite no dropout or structural failure; the report therefore records mixed numerical seam behavior rather than claiming universal improvement.
- Final checks: canonical full pytest `516 passed` with only the known `pynvml` warning; the first attempt's 98 setup errors were solely the inherited inaccessible Windows pytest temp root and disappeared with a new writable basetemp. WAN runtime verifier, source/runtime SHA-256 for `constants.py`, `v2/nodes.py`, `v2/prompts.py`, `v2/sequence.py`, `v3/nodes.py`, `v3/masked_continuation.py`, and the diagnostic node, `git diff --check`, and empty queue pass.
- Gate result: **PASS**. Production promotion: **HOLD** pending Reference variants, Run Storage/resume identity, public UI/default decisions, and broader audible Audio Seam acceptance. Evidence roots are `D:\Codex\_test_results\ComfyUI-H3-Continuum\v36-fl2va-combined-20260826\gate-a` and `...\r2-short`. Backend PID 15888 remains running per request. Commit/push were not performed.

## 2026-08-27 - V3.6 shared chunk-duration maximum 30 seconds

- Preserved all uncommitted V3.6 R1/R2/FL2VA work and changed only the shared duration range, Prompt Plan validation, documentation, and focused regressions. No per-chunk variable-duration feature, Sampling, Conditioning, `17k+5` temporal math, Assembly, Seam, Run Storage, or saved-workflow socket contract changed.
- Added shared constants for default `5.0`, minimum `4.0`, maximum `30.0`, step `0.1`, and one tooltip. Applied them to all V2/V3 Production-compatible sampler schemas and Prompt Plan Preview. Values above 15 seconds are supported with a high-resolution VRAM/runtime warning; `5–15s` remains the recommended/validated range.
- Prompt Plan creation and connected-plan validation now accept `30.0`, reject `30.1`, and correctly map a two-chunk `[0-30s]` / `[30-60s]` Timeline. Temporal regression covers every tenth from `4.0` through `30.0` for 5/22/39-frame contexts and requires native `17k+5` output shapes.
- The separate legacy V1 `H3ContinuumJoin.extend_seconds` maximum remains 15 seconds by design; the audit found no remaining 15-second cap on `chunk_seconds`.
- Source snapshot `pre-v36-chunk-duration-30-source-20260826_234716` verifies all 209 Git-visible files. Runtime snapshot `pre-v36-chunk-duration-30-wan-runtime-20260826_235423` verifies the four synchronized files. Source/runtime pre-change differences in `constants.py` and `v2/prompts.py` were EOL-only.
- Validation: focused inherited-schema/prompt/temporal suite `89 passed`; final full pytest `516 passed`; changed-file `py_compile`, `git diff --check`, V3.5.3 runtime verifier, source/WAN SHA-256, live API schemas for seven V2/V3 node IDs, and empty queue PASS. The restarted WAN backend uses Sage Attention plus `--disable-pinned-memory` and is intentionally left running. Commit/push were not performed.
- Per the reduced GPU scope, submitted one T2VA `1x30s`, `384x384`, one-step validation prompt. API returned prompt ID `9e665f85-b32f-4b17-9734-219fb284e087` with `node_errors={}`; H3 model initialization/Sampling began without immediate duration/shape/Prompt Plan/OOM error. Interrupted intentionally after `31.87s`; no Decode/Save or 30-second output-quality claim was made. Queue returned empty.
- Cancelled the FL2VA joint multi-seed continuation gate at user request. Its cache warm-up completed, but the first measured condition was interrupted before execution and is excluded from results.

## 2026-08-26 - V3.6-R2-2 Balanced 22f / 37T Joint AV GPU gate

- Preserved the public/default V3.5.3 `reference_context_v1` route and all accumulated R1/R2 work. Added only private `masked_av_prefix_22_v1` handling and diagnostic tooling; no public node/schema, V3.4 behavior, `v2/sampling.py`, seed, Plan, trim, Decode, Assembly, Seam, Run Storage, or saved-workflow contract changed.
- Pre-change exact-file snapshots are `pre-v36-r2-2-balanced-av-source-files-20260826_214033` (9 files, zero mismatch) and `pre-v36-r2-2-balanced-av-wan-runtime-files-20260826_214033` (3 files, zero mismatch) under `D:\Codex\_snapshots\ComfyUI-H3-Continuum`. The initial runtime snapshot copy omitted subdirectories and was corrected before any edit; only the verified snapshot is accepted.
- CPU/static validation established the Balanced target `141f / 42T / 235T`, Video prefix `22f / 7T`, Audio prefix `37T`, trim `22f`, net `119f`, and the `8.333ms` Video/Audio mask-boundary asymmetry. Focused result is `24 passed`; pre-GPU full result is `510 passed` with only known warnings.
- Synchronized only `v2/sequence.py`, `v3/masked_continuation.py`, and private diagnostic `nodes.py` to ComfyUI_WAN with SHA-256 equality. Restarted ComfyUI v0.34.0 with Sage Attention and `--disable-pinned-memory`; node registration and empty queue passed.
- One-seed A/B used T2VA 2x5, 640x640, Balanced 22, Audio Continuity ON, fixed seed `238985343135605`, Prompt/CLIP cache HIT, CUDA synchronization, and Exact Duration ON. Reference packed layout was `20,205` rows; Masked AV was `17,331`, eliminating `2,874` reference rows (`14.22%`). Continuation Sampling was `226.373s -> 206.437s` (`8.81%` lower) and API wall time `435.907s -> 420.752s` (`3.48%` lower). One-seed timing is not generalized.
- Masked source/target Video 7T and Audio 37T prefixes match bit-exactly after scoped final restore. Core raw prefix deltas were only `2.384185791015625e-07` Video and `5.960464477539063e-08` Audio. Both outputs are finite `640x640 / 240f / 24fps / 10.000s`; boundary contact sheets show no obvious visual regression.
- Seam-OFF decoded audio is not intrinsically accepted: Reference jump `0.082725`, Masked jump `0.268163`. Existing Audio Seam Auto reassembled the cached Masked latents in `7.10s`, did not rerun Sampling, and reduced the jump to `0.029944` (`88.83%` lower and below local p99). No new Audio Seam code was added.
- R2-2 status: GPU structure/performance gate **PASS with existing Audio Seam Auto**, raw Seam-OFF audio documented, Production **HOLD**. Final full pytest is `510 passed`; changed-file `py_compile`, `git diff --check`, source/runtime SHA-256, V3.5.3 runtime verifier, and empty queue pass. Evidence is under `D:\Codex\_test_results\ComfyUI-H3-Continuum\v36-r2-gate2-20260826`. Backend remains running; commit/push were not performed.

## 2026-08-26 - V3.6-R2-1 39f / 65T Joint AV GPU structure gate

- Synchronized only `v2/sequence.py`, `v3/masked_continuation.py`, and the private diagnostic `nodes.py` to ComfyUI_WAN after the accepted R2-0 runtime snapshot. All three source/runtime SHA-256 hashes match. Restarted the same ComfyUI v0.34.0 backend with Sage Attention and `--disable-pinned-memory`; the backend is intentionally left running.
- Added reusable `tools/v36_r2_gpu_gate_runner.py`. It removes the I2VA First Image, fixes T2VA 2x5 / 640x640 / Strong 39 / Audio Continuity ON / one seed, excludes optional conditioning and Run Storage, warms Prompt/CLIP once, and measures Reference then Masked with CUDA synchronization. A validation-only stop found Core reports the 39f AV Reference as combined kind `video_audio`; the completed Reference generation remained valid and Masked resumed without repeating it.
- Reference continuation used `24,317` PackedLayout rows (`4,800 ref_img`, `130 ref_audio`); Masked used `19,387` with no Reference rows. The exact reduction is `4,930` rows / `20.27%`. Synchronized Chunk 2 time was `332.460 -> 241.888s` (`27.24%` lower); API wall was `556.058 -> 465.925s` (`16.21%` lower). This is one-seed structural evidence, not a universal performance claim.
- GPU evidence confirmed source-tail/target-prefix equality, Video mask `0:12` protected and `12:47` generated, Audio mask `0:65` protected and `65:263` generated, no old refs/interop, and final Video/Audio Prefix SHA-256 equality. Core raw maximum deltas were `2.384185791015625e-07` Video and `5.960464477539063e-08` Audio; final restored deltas are zero. No generated region is restored.
- Both primary MP4s are finite 640x640 / 240 frames / 24 fps / 10.000 seconds. Nine-frame boundary contact sheets show no gross visual snap, collapse, persistent artifact, or scene discontinuity.
- Added `tools/v36_r2_audio_boundary_analyze.py`. With Audio Seam OFF, the exact 124-frame cumulative boundary is the maximum decoded single-sample jump in both files: Reference `0.352289`, Masked `0.287521`. Masked has smaller DC/RMS/Peak discontinuities but the native hard cut is not described as click-free.
- Added a cache-only Audio Seam Auto probe. It reassembled the accepted Masked latents in `7.23s` without Sampling; boundary jump became `0.005774` (about `98.0%` lower), global rank fell from maximum to `37.4` percentile, and DC jump became `0.001103`. Existing Audio Seam Auto therefore handles the observed cut; no new seam algorithm was added.
- R2-1 status: GPU structure/interoperability **PASS**, raw Seam-OFF audio cut documented, existing Audio-Seam-Auto path PASS, Production still HOLD. R2-2 22f / 37T and broader acceptance remain pending. Evidence is under `D:\Codex\_test_results\ComfyUI-H3-Continuum\v36-r2-gate1-20260826`; commit/push were not performed.

## 2026-08-26 - V3.6-R2-0 Joint AV masked-prefix CPU/static gate

- Preserved all uncommitted V3.6-R1 work and kept V3.5.3 public/default behavior frozen. Added only the private `masked_av_prefix_39_v1` research transport; no public node/schema, `v2/sampling.py`, V3.4, seed, Plan, trim, Decode, Assembly, Seam, or Run Storage contract changed.
- Generalized `v3/masked_continuation.py` so R1 still protects only 22f / 7T video, while R2-0 copies and masks both a 39f / 12T video tail and a duration-matched 65T audio tail. Sampling-finalization restore is limited to the two protected prefixes; generated video and audio regions remain sampler-owned.
- Added a Strong-39-only sequence branch using a 158-frame physical target (`47T` video / `263T` audio), 39-frame trim, and 119-frame net output. It emits neither old Context Reference rows nor the old Spectrum interop hint and does not reapply the initial I2VA First Image after chunk 1.
- Extended the private WAN diagnostic wrapper to capture audio-prefix hashes/equality, audio mask regions, source-tail matching, native audio-grid offset, and final physical-group AV prefix pairs. It remains diagnostic-only and is not a public V3.5.3 node contract.
- Added CPU regressions for exact shapes, zero/one masks, source/target immutability, invalid audio shapes/NaN, protected-prefix restoration, generated-region preservation, First Image isolation, absence of old refs/interop, and the integrated two-chunk sequence path.
- The 39f video window and 65 audio ticks are both 1.625 seconds, but native H3 source/target audio-grid phase is not silently assumed to be zero: 124f / 207T is `+1/3` tick and 158f / 263T is `-1/3` tick.
- Validation: changed-file `py_compile` PASS; focused masked/temporal tests `21 passed`; full pytest `507 passed`; only the known `pynvml` FutureWarning remains. GPU R2-1 and runtime synchronization were deliberately not started in this CPU/static gate.
- Accepted snapshots: `pre-v36-r2-0-joint-av-source-accepted-20260826_203022` and `pre-v36-r2-0-joint-av-wan-runtime-accepted-20260826_203022`. Commit/push were not performed; the existing WAN backend was not stopped.

## 2026-08-26 - V3.6-R1 masked video-prefix continuation PoC

- Kept V3.5.3 `reference_context_v1` as the public/default continuation transport and added only a private V3.6-R1 switch for testing. No public widget or Production node was added; V3.4, public V3.5.3 schemas, Sampling implementation, seeds, Plan, trim, Decode, Assembly, Seam, and Run Storage remain unchanged.
- Added `v3/masked_continuation.py` for 22-frame / 7T video-prefix target construction and mask creation. The masked route copies the video tail into the next 42T target, uses video mask `0` for the seven protected slots and `1` afterward, keeps the 235T audio target empty with an all-one mask, and omits both old Context Reference conditioning and its Spectrum interop hint.
- Found that Core v0.34.0 preserved the prefix inside denoising but the raw final float32 integration introduced a maximum difference of `2.38418579101562e-07`. Added a narrowly scoped post-Sampling restore of the protected prefix only. Finalized prefix equality is exact by `torch.equal`, max difference, and SHA-256; no generated video/audio region is restored.
- Added dedicated CPU regressions, a test-runtime diagnostic node, and `tools/v36_r1_api_runner.py`. Focused validation is `8 passed`; full pytest is `500 passed`; `py_compile` and `git diff --check` pass. Synced only the changed Production/diagnostic files to ComfyUI_WAN and verified source/runtime SHA-256 equality.
- After user-authorized queue clear/interrupt, completed three normal-API A/B pairs at 640x640 / 2x5-second T2VA / 20 steps / Balanced 22. Audio Continuity, Run Storage, Spectrum, Sol, Seam, First/Last, References, and Video Guide were off; Sage Attention was enabled by the server. Every masked run passed 7T prefix exactness, mask/shape/seed/finite checks, empty second-group refs, and absent old interop. All six outputs are 240 frames at 24 fps / 10.000 seconds.
- Contact sheets at frames 112, 118, 122, 123, 124, 125, 128, 136, and 148 show no gross boundary snap, direction reversal, persistent artifact, or collapse for either route. The masked route did not show a consistent visual advantage over the accepted reference-context route across the three seeds. Decision: R1 structure PASS; visual improvement unproven; do not promote it as the Production default.
- Evidence roots: `v36-r1-gate1-postrestore-20260826`, `v36-r1-gate2-seed238985343135587`, `v36-r1-gate2-seed238985343135588`, and `v36-r1-boundary-sheets-20260826` under `D:\Codex\_test_results\ComfyUI-H3-Continuum`. Output MP4s remain under `D:\output\video\comfy_video\video` with `V36_R1_*` names. Commit/push were not performed.
- Derived a simplified, annotated A/B workflow from `MiniMax_H3_Continuum_V35 (3).json`: `D:\Codex\_test_workflows\ComfyUI-H3-Continuum\MiniMax_H3_Continuum_V36_R1_MaskedPrefix_AB.json`. Removed disconnected external AddGuide/Noise Mask/AV split-concat nodes and all non-R1 features; retained the exact Model/SIGMAS/diagnostic Sampler/Core Decode/Assembly/Save route. Static graph validation found 22 unique nodes, 24 reciprocal/type-correct links, three groups, zero errors, registered diagnostic type, and default `masked_video_prefix_v1`. Companion explanation is `V36_R1_WORKFLOW_GUIDE.md`; no GPU generation was rerun for workflow serialization.
- Ran the formal R1 Stress Gate as 3x5-second Strong Motion I2VA at 640x640, Balanced 22, three fixed seeds, Prompt/CLIP cache HIT, Audio Continuity/Run Storage/Spectrum/Sol/Seam OFF, and `--disable-pinned-memory`. The order alternated `Reference -> Masked`, `Masked -> Reference`, `Reference -> Masked`.
- Diagnostics caught an A/B fairness defect before acceptance: the private masked branch reapplied the original First Image on chunks 2/3 while the reference branch removed it. Interrupted/excluded those preliminary runs, restricted First Image to chunk 1 in `masked_video_prefix_v1`, and added CPU coverage. Public V3.5.3 behavior was not changed.
- The accepted normal API pairs were `719.800/675.284s`, `693.449/641.506s`, and `711.800/672.341s` for Reference/Masked. Masked API time was lower by `6.185%`, `7.491%`, and `5.544%`; continuation Sampling was lower by `9.471%`, `12.029%`, and `8.309%`, with paired medians `6.185%` and `9.471%` respectively.
- Added real Core `PackedLayout` capture to the diagnostic node. Reference continuation uses `20,569` rows including `2,800 ref_img` rows; Masked uses `17,769` rows and no continuation `cond`/`ref_img` rows. A CUDA-synchronized pair confirmed continuation Sampling `464.97 -> 437.10s` (`5.995%` faster), so the signal is not a host-asynchrony artifact.
- All six accepted videos are 640x640, 360 frames, 24 fps, and 15.000 seconds. Every masked finalized prefix is bit-exact at both boundaries. Contact sheets show no gross snap, reversal, persistent artifact, or collapse. At the second boundary Masked had lower optical-flow jerk and lower absolute luma/saturation drift for all three seeds; flow-magnitude continuity remained mixed, so the quality result is promising but not universal proof.
- Stress evidence is under `D:\Codex\_test_results\ComfyUI-H3-Continuum\v36-r1-stress-gate-20260826\normal_fair` and `sync_fair`. The sibling `normal` runs are pre-fairness diagnostics and explicitly invalid for acceptance. Added reusable `tools/v36_r1_stress_gate_runner.py` and `tools/v36_r1_stress_gate_analyze.py`.
- Final validation: focused masked-prefix regression `5 passed`; canonical full pytest `500 passed`; changed-file `py_compile`, V3.5.3 runtime verifier, `git diff --check`, source/WAN hashes, and empty queue PASS. R1 Stress Gate is PASS; Production remains HOLD pending separately scoped R2/Reference/Terminal/Run Storage work. The WAN backend was intentionally left running per user instruction. Commit/push were not performed.

## 2026-08-26 - V3.5.3 distribution-integrity maintenance hotfix

- Kept published V3.5.2 generation and optimization behavior frozen; no Sampling, Conditioning payload, Terminal Merge, Assembly, Seam, Run Storage, Prompt/CLIP cache, Video Guide, V3.4, node, or socket contract was changed.
- Created accepted source/runtime snapshots `pre-v353-maintenance-hotfix-source-accepted-20260826_030732` and `pre-v353-maintenance-hotfix-comfyui-w-accepted-20260826_030731` after the standard full snapshot stopped only on the known inaccessible `.pytest_cache`.
- Repaired Conditioning Bridge workflow links `349`/`350` from stale Sampler input slots `14`/`15` to Width/Height slots `16`/`17`; removed orphan output links `171`/`172`/`173` from the public V3.4, V3.4 Turbo, and V3.5 workflows.
- Replaced source-only Hybrid warning renumbering with the accepted absolute public `<Picture N>` behavior already present in ComfyUI_W. Added two regressions covering unavailable and missing Hybrid references.
- Added an eight-workflow serialization-integrity regression covering node/link uniqueness, endpoints, slot bounds, reciprocal input/output references, and types. The focused release/hotfix result is `30 passed`; canonical full pytest is `495 passed` with only the known `pynvml` FutureWarning.
- Regenerated the release Manifest with 173 entries, added the public-workflow integrity regression, and verified every recorded SHA-256.
- Losslessly re-encoded the unreferenced legacy `v31b-auto-resume.png`; strict Pillow verification passes all 19 packaged PNGs and an independent pixel comparison found zero changed pixels.
- Synchronized only `reference.py`, `version.py`, and `metadata.ini` to the primary ComfyUI_W runtime and verified exact source/runtime SHA-256 equality. Runtime verification reports V3.5.3, native PackedLayout PASS, Fixed 3x5 planning PASS, and complete node registration. The incomplete ComfyUI_WAN copy was intentionally not modified.
- No GPU generation was rerun because the only Python behavior change is report warning text and the remaining changes are package/workflow metadata. Commit and push were not performed.

## 2026-08-26 - V3.5.2 README final audit and publication authorization

- Re-audited English/Japanese README chapter order, historical/current-version wording, withdrawn controls, local links, image references, and validation claims before publication.
- Moved the Japanese product summary to the document opening and merged the duplicated English V3.5.1 Hotfix/What's New sections into one chronological `Reference Audio & Compatibility Update` section.
- Explicitly documented that the withdrawn experimental Last Queued Seed override is not included and that V3.5.2 retains standard ComfyUI Seed behavior.
- Kept the user-supplied infographic unchanged and added a precise caption distinguishing its accepted measurement labels from the final ComfyUI 0.33.3 / 172-entry packaging gate.
- Regenerated the 172-entry Manifest and verified all local README links. Post-audit full pytest is `485 passed`; Manifest, runtime verifier, node registration, source/runtime hashes, queue state, and `git diff --check` remain PASS.
- The user explicitly authorized committing and pushing the complete V3.5.2 release state to the main repository after this audit.

## 2026-08-26 - V3.5.2 final release gate

- Completed the final Stabilization & Optimization release gate without adding a generation mode or changing V3.4/V3.5 Sampling, Conditioning payloads, Terminal Merge, Assembly, Seam, Run Storage, or standard ComfyUI Seed behavior.
- Created exact pre-change snapshot `pre-v352-release-preparation-exact-20260826_022016` at revision `b8ab766eb364063f8af88781e7be70ee7286fba0`, containing 198 authoritative files plus the four active ComfyUI_W/ComfyUI_WAN metadata files. The standard snapshot attempt stopped only on the known repository `.pytest_cache` ACL.
- Ran a final 576x576 / 1x5-second / 20-step T2VA API cache smoke before the release metadata change. MISS reported one encode call and `8.454306s` Prompt/CLIP; HIT reported zero encode calls and `0.000038s`. Both used derived seed `5684542245315818407` and produced identical decoded video MD5 `40e378d7c80e6bebd9d64b322c13e677` and audio PCM MD5 `4fb0a699227c4f834f7a52ba4d395ae8`.
- Reused the accepted Phase 4-4 Video Guide GPU A/B because no Production path changed afterward: complete source identity, 124-frame prefix, VAE/Qwen inputs, Sampling seed, decoded video, and audio PCM remain exact between legacy-v3 and optimized preprocessing.
- Bumped package, project, and runtime metadata to `3.5.2`; added the Stabilization & Optimization sections to English/Japanese README and Changelog; removed the stale withdrawn Last Queued Seed claim from package information; and updated package validation to the canonical `485 passed` result.
- Copied the user-supplied infographic `D:\SD_PIC\Neo\Clip_91.png` to `docs/images/v352-stabilization-optimization.png` bit-exact (SHA-256 `0c1dfd5acff349b98ecdfb57ae50941f6da26a462dfd2aaa9b7c7b0a34abf304`) and embedded it near the top of both READMEs.
- Synchronized only `version.py` and `metadata.ini` to ComfyUI_W and ComfyUI_WAN; all four destination hashes match the source. ComfyUI_W restarted successfully and logged `H3 Continuum 3.5.2 loaded` on ComfyUI `0.33.3`.
- Final validation: compileall exit `0`; full pytest `485 passed` with only the known `pynvml` FutureWarning; V3.5.2 runtime verifier PASS; all 172 Manifest hashes PASS; five required V3.5 nodes registered; source/runtime hashes PASS; queue `0/0`; and `git diff --check` PASS. Commit, push, and release were intentionally not performed at this gate.

## 2026-08-26 - Stabilization Phase 4-6A Video Guide memory optimization

- Completed the read-only Phase 4 Feature Tax & Redundancy Audit and selected only Video Guide long-input memory as an implementation candidate. No Production Sampling speed change, Driving Audio lazy Decode, Audio hash special case, Session/State relaxation, Refine Context change, or V3.4 change was adopted.
- The mandatory standard snapshot stopped on the known `.pytest_cache` ACL. Created verified exact snapshot `pre-phase4-6a-video-guide-memory-exact-20260826_012227` with six authoritative/runtime files at revision `b8ab766eb364063f8af88781e7be70ee7286fba0`.
- Pre-change verification found that ComfyUI_W alone contained an unrecorded Video Guide preprocess v3, while the repository and ComfyUI_WAN still had v2-equivalent content. With explicit approval, preserved and integrated the active v3 `17k+5` alignment and final-frame padding behavior into the repository before optimizing memory.
- Replaced whole-source float32 RGB materialization, finite scan, and one-shot `bytes` hashing with eight-frame normalization/validation/hash updates. The source object now owns only the used prefix. The complete normalized source still contributes to the exact same SHA-256 and unused-tail NaN/Inf detection.
- Deterministic 300x256x256 RGB comparison against the original ComfyUI_W v3 retained an identical full contract and hash. Peak RSS above the allocated input changed from `396.758 MiB` to `114.695 MiB`, retained storage from `225.0 MiB` to `93.0 MiB`, and host time from `0.246672s` to `0.257602s`.
- Added five CPU regressions for legacy-v3 hash byte order, full-tail identity, unused-tail finite rejection, prefix ownership, frame alignment/padding, and encoding behavior. Focused result is `17 passed`; full result is `485 passed`. Source runtime verification and all 171 Manifest entries pass.
- Completed Phase 4-4 GPU A/B through the normal API using the same 15-second / 360-frame 800x800 Video Guide, V3.5 one-chunk workflow, 576x576 output, 20 steps, seed input `46001`, Sage Attention, and Hi-Res Fix disabled. Legacy and optimized paths both used one physical group, guide contract 640x640 / 124 frames, derived Sampling seed `3288707263902886519`, exact-duration 124->120 frames, 24 fps / 5.000 seconds, and 32 kHz stereo audio.
- Reloaded the exact VHS input independently and confirmed old/new source SHA-256 and combined identity, retained 124-frame prefix, resized VAE input, and Qwen input are byte-identical. Decoded video MD5 and audio PCM MD5 are also identical (`53cd381aff184c2f8aa5910ab62be342` / `3653c0ec89947a928075d4ba056ff624`). Representative start/middle/end frames show no gross artifact. Phase 4-6A is formally accepted; runtime was restored to the optimized source-identical file and the API queue is empty.

## 2026-08-26 - Stabilization Phase 3-2 synchronized GPU rebaseline

- Phase 3-2 is formally PASS. The accepted decision is to make no speculative Phase 3-3 Production optimization: measured Continuum Assembly is negligible, Core VAE/MP4 work is external, and existing Spectrum/Sol-Attn routes provide materially larger gains without changing Continuum's Sampling contract.
- Final-pass documentation snapshot: `pre-phase3-2-formal-pass-docs-20260826_004900` (2 files, revision `b8ab766eb364063f8af88781e7be70ee7286fba0`).
- Preserved all Phase 3-1 and earlier uncommitted work. Accepted snapshot `pre-stabilization-phase3-2-profile-accepted-20260825_220920` contains 479 files at revision `b8ab766eb364063f8af88781e7be70ee7286fba0`; the standard snapshot attempt stopped only on the known ACL-inaccessible `.pytest_cache`.
- Added repository-only API diagnostics that synchronize CUDA before/after measured nodes, separate true whole-workflow allocator peaks from per-node reset peaks, poll lightweight RSS/private and NVML free VRAM during each interval, and sample USS at interval boundaries. Early probes that queried CUDA from a polling thread or called `memory_full_info()` at 10 Hz measurably slowed Sampling and are explicitly excluded.
- Rebaselined Phase 3-1 cache-HIT Production behavior after an excluded warm-up and three measured runs. API medians are T2VA `168.069s` and FL2VA `379.765s`; synchronized phase medians show Sampling `120.516s` / `295.216s`, Video Decode `19.154s` / `51.634s`, Audio Decode `0.466s` / `1.040s`, Assembly `0.130s` / `0.619s`, and MP4 save `2.583s` / `7.248s`.
- Whole-workflow CUDA allocator peaks are `1.456 GiB` T2VA and `4.129 GiB` FL2VA. Per-node runs independently identify Sampling as the maximum. The FL2VA contract remained 3 logical / 2 physical groups (`[1]`, `[2,3]`), 360 frames, 24 fps, 15.000s; T2VA remained 120 frames / 5.000s.
- Compared external attention routes on T2VA with one warm-up excluded and three-run API medians: Sage `168.069s`; Sage + Sol-Attn `162.090s`; Sage + Spectrum `124.830s`; Sage + Sol-Attn + Spectrum `121.147s`. The initial Sol attempt failed only because the diagnostic process could not write its default Triton cache and was interrupted/excluded. The accepted rerun used a writable test cache, logged active sparse kernels, and had zero fallback.
- The fastest combined route additionally passed one measured FL2VA run at `288.548s` API with 3 logical / 2 physical groups, terminal seed/trim unchanged, 640x640, 360 frames, 24 fps, 15.000s, and audio. `ffprobe` validated every selected output; contact sheets showed no gross persistent artifact. External accelerator outputs are intentionally not required to be MD5-identical.
- No Continuum Production optimization was adopted. Sampling remains contract-sensitive, Core VAE Decode and MP4 save are external, and Assemble + Seam is below the 1% threshold. The diagnostic wrapper was removed from the running process and the normal ComfyUI API was restored at `127.0.0.6:8188` with output `D:\output\video\comfy_video`. No Production runtime synchronization was required. Evidence is under `D:\Codex\_test_results\ComfyUI-H3-Continuum\stabilization-phase3-2-20260825`; commit/push were not performed.
- Focused diagnostics are `13 passed`; full pytest is `480 passed`. Diagnostic `py_compile`, all 170 Manifest hashes, source runtime verification, and `git diff --check` pass with only the known `pynvml` FutureWarning.

## 2026-08-25 - Stabilization Phase 3-1 Prompt/CLIP cross-run cache

- Created exact source/runtime snapshot `pre-stabilization-phase3-1-prompt-cache-20260825_211303` with 19 files and preserved all earlier uncommitted stabilization changes.
- Added a V3.5-only private Prompt/CLIP conditioning cache attached to the exact CLIP object. It is capped at 16 LRU entries and invalidates on prompt, exact resized First/Last pixels/shape/dtype, Last Frame presence, patch UUID, or CLIP layer. V3.4, public schemas, Sampling, Terminal Merge, Assembly, Seam, and Run Storage were not changed.
- Conservatively bypassed Reference Image/Audio/Video/Timeline and CLIP schedule/tokenizer/hook states. Cache exceptions and CUDA-resident outputs fall back to uncached encode. Tensor payloads are shared only when CPU-resident; metadata dict/list/tuple containers are copied per use.
- Added Detailed Report evidence with real `hits/misses/bypasses/encode_calls`. Dedicated and integrated CPU result is `25 passed`; full pytest is `467 passed` with only the known `pynvml` and inaccessible repository pytest-cache warnings.
- Synchronized only `v2/h3_builder.py`, `v2/sequence.py`, `v2/nodes.py`, `v3/nodes.py`, and `v3/driving_nodes.py` to ComfyUI_W; every SHA-256 matched. ComfyUI_W was restarted with its recorded arguments before GPU tests.
- GPU/API T2VA A/B PASS: 576x576, 120 frames / 5.000s. Prompt/CLIP changed from `5.898398s` (`misses=1`, `encode_calls=1`) to `0.000028s` (`hits=1`, `encode_calls=0`). Decoded video frame MD5 sequence and decoded audio PCM MD5 are identical. A separate base-seed-only change produced a new derived Sampling seed while retaining one HIT / zero encode calls.
- GPU/API FL2VA Long Terminal Merge A/B PASS: 640x640, 360 frames / 15.000s, 3 logical / 2 physical groups (`[1]`, `[2,3]`). Prompt/CLIP changed from `21.642687s` (`misses=4`, `encode_calls=4`) to `0.007128s` (`hits=4`, `encode_calls=0`). Decoded video frame MD5 sequence and decoded audio PCM MD5 are identical. A separate base-seed-only change retained four HITs / zero encode calls, changed both normal and terminal physical seeds, and preserved the group contract.
- No CUDA retention regression was observed. FL2VA warm completion RSS was 6095.8 MiB MISS versus 6117.1 MiB HIT, a bounded approximately 21.3 MiB CPU cost for four retained conditioning entries. Evidence is under `D:\Codex\_test_results\ComfyUI-H3-Continuum\stabilization-phase3-1-20260825`. Commit and push were not performed.

## 2026-08-25 - Stabilization Phase 2-2 Conditioning attribution

- Created exact source/runtime snapshot `pre-stabilization-phase2-2-conditioning-20260825_200800` with 15 files including snapshot metadata. Existing uncommitted Phase 2-1 and all prior V3.5.1 work were preserved.
- Split Detailed Report Conditioning timing into identity video VAE, Reference Image/Audio VAE, Driving Audio VAE, Video/Timeline Reference VAE, and Prompt/CLIP. The instrumentation is inactive outside the existing V3.5 Detailed Report path and never synchronizes CUDA.
- Focused validation is `29 passed`; full validation is `453 passed` using a writable explicit pytest `--basetemp`. The initial full attempt produced setup errors only because the default `pytest-of-links` directory is ACL-inaccessible. Manifest, syntax, and related regressions pass.
- Synchronized only `v2/sequence.py`, `v3/memory_attribution.py`, the two related test files, and `MANIFEST.sha256` to ComfyUI_W; source/runtime SHA-256 matched before GPU execution.
- GPU/API 1x5 T2VA accepted result: 576x576, 120 frames / 5.000s, 158.701s API, 135.970s Sampler host wall, 129.935s Sampling, 6.004392s Conditioning, and 6.004374s Prompt/CLIP. Warm-up independently measured 6.283131s Conditioning and 6.283109s Prompt/CLIP. One 3.398s execution-cache replay was excluded.
- GPU/API 3x5 FL2VA Long Terminal Merge accepted result: 640x640, 3 logical / 2 physical groups (`[1]`, `[2,3]`), 360 frames / 15.000s, 410.727s API, 346.197s Sampler host wall, 322.335s Sampling, 23.644903s Conditioning, 22.873708s Prompt/CLIP, and 0.771176s First/Last image VAE. Decode and Assemble completed with Exact Duration `362 -> 360`.
- No optimization was implemented. Prompt/CLIP accounts for effectively all T2VA Conditioning and 96.7% of FL2VA Conditioning; the remaining measured Continuum-side work is not an optimization target. Reference-specific branches remain instrumented but require separate connected GPU evidence before any conclusion.
- Evidence is under `D:\Codex\_test_results\ComfyUI-H3-Continuum\stabilization-phase2-2-20260825`. Commit and push were not performed.

## 2026-08-25 - Stabilization Phase 2-1 performance attribution instrumentation

- Attempted the mandatory full snapshot first; it stopped only on the known ACL-inaccessible `.pytest_cache`. Accepted exact-file snapshot `pre-stabilization-phase2-exact-20260825_190303` contains nine source/runtime target files at revision `b8ab766eb364063f8af88781e7be70ee7286fba0`, with source/runtime Production hashes equal before modification.
- Extended the existing V3.5 Detailed Report collector with non-synchronizing host timings for Preparation/Conditioning, physical-group preparation/Sampling/CPU commit plus finite validation/Refine Context capture, and Finalization. No new node, socket, widget, schema, or normal-report overhead was added.
- Terminal Merge regression confirms exactly two performance group records for logical `[1]` and `[2,3]`. Dedicated tests also prove the collector never calls CUDA synchronization.
- Focused CPU/static validation is `27 passed`; full validation is `451 passed`; only the known `pynvml` FutureWarning remains. Runtime verification, Manifest validation, `py_compile`, `git diff --check`, and source/runtime SHA-256 equality pass.
- The first API run accidentally reached the pre-existing 18:46 ComfyUI listener; the newly started process had exited on port conflict. That result is explicitly excluded. After confirming an empty queue, the exact old listener PID was stopped and the synchronized runtime was restarted with the recorded Stability Matrix arguments.
- Accepted GPU/API measurements: warm 1x5 T2VA 576x576 = 143.888s API / 134.736s Sampler host wall (Sampling 128.737s); 3x5 FL2VA Long Terminal Merge 640x640 = 396.477s API / 348.047s Sampler host wall (Sampling 323.835s, physical `[1]` + `[2,3]`); 1x5 Hi-Res 1.2x = 330.005s and 704x704. All outputs are 24 fps with exact 5.000s or 15.000s duration and 32 kHz audio.
- Warm baseline versus Hi-Res peak Working Set was 6.882 versus 7.374 GiB; peak Private Bytes was 20.655 versus 21.998 GiB. The 3x5 peaks were 9.409 GiB Working Set and 21.159 GiB Private Bytes. Global VRAM used peaked around 15.4-15.6 GiB and is recorded only as a process-external observation.
- Sampling accounts for 93.0-95.5% of measured Sampler time. CPU commit/finite validation, Refine Context, and group preparation are below the adoption threshold and will not be optimized. Conditioning is 4.4-6.9% and is eligible only for finer attribution, not an optimization change. Evidence is under `D:\Codex\_test_results\ComfyUI-H3-Continuum\stabilization-phase2-20260825`.

## 2026-08-25 - Stabilization Phase 0 local CI portability fix

- Froze V3.5.1 feature work and began stabilization with a test-only change. Production Sampling, Layout, Session, Run Storage, Refine Context, UI, and runtime files were not changed.
- Split the P2-5 process-memory assertion by actual platform contract: RSS is universal, USS is validated when present, and the Windows private-commit field is Windows-only.
- Verified snapshot: `pre-stabilization-phase0-ci-platform-test-accepted-20260825_124156` (477 files), revision `cf92ac609341539de95675c86271fea11c85e040`, excluding top-level `.git` and the pre-existing inaccessible `.pytest_cache`. The standard snapshot attempt stopped on that known ACL before any edit.
- Local focused validation is `4 passed`; full validation is `453 passed`; syntax and `git diff --check` pass. Only the known `pynvml` FutureWarning remains. Remote Actions confirmation, commit, and push were not performed.

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

## 2026-08-25 - Issue #11 conditional size-control documentation

- Confirmed that Issue #11 reports a discoverability/documentation gap rather than missing V3.5.1 inputs: Compact UI hides `Reference Size` and `Video Guide Size` until their matching image inputs are connected.
- Added matching English/Japanese README guidance covering the conditional display, the `Video Reference Size` to `Video Guide Size` display-name clarification, internal aspect-preserving resize before VAE encoding, the no-automatic-upscale behavior, and the limited cases where external resize is useful.
- No node schema, backend key, workflow, runtime implementation, Sampling, Conditioning, Terminal Merge, Assembly, Seam, or Run Storage behavior changed.
- Pre-change snapshot: `pre-issue11-readme-clarification-source-accepted-20260825_001938` (478 files), excluding `.git` and the known ACL-inaccessible `.pytest_cache` after the standard snapshot script encountered that existing ACL condition.

## 2026-08-25 - V3.5.1 public-state cleanup

- Updated the project scope rule from the obsolete V3.4 public baseline to V3.5.1, preserving V3.4 node IDs, contracts, and saved-workflow compatibility.
- Aligned `PACKAGE_VALIDATION.txt` with `PROJECT_STATE.md`: Last Queued Seed Reuse has automated frontend validation, while real UI/cache acceptance remains pending.
- Posted implementation answers to GitHub Issues #9, #10, and #11. Closed #9 Conditioning Bridge and #10 Reference Audio as completed; retained #11 as open until its local README clarification is published.
- No implementation code, node schema, workflow, runtime, Sampling, Conditioning, Terminal Merge, Assembly, Seam, or Run Storage behavior changed.
- Pre-change snapshot: `pre-v351-public-state-cleanup-source-accepted-20260825_004006` (478 files), excluding `.git` and the known ACL-inaccessible `.pytest_cache` after the standard snapshot script encountered that existing ACL condition.
- Validation: release metadata `2 passed` with the ComfyUI_W venv, all 172 Manifest entries match SHA-256, and `git diff --check` passes. The system Python lacks pytest; no product-test failure occurred.

## 2026-08-25 - GitHub Actions dependency and Core stub repair

- Kept Production runtime code and `requirements.txt` unchanged. Added `psutil` only to the GitHub Actions test-install command for the P25 probe tests.
- Added a test-file-local `comfy_extras.nodes_minimax_h3` stub with only `CANVAS_MULTIPLE = 32`, allowing manual Hi-Res canvas tests to exercise the real Production import path without installing ComfyUI Core in CI.
- Focused Hi-Res Fix/P25 result is `16 passed`; full result is `450 passed` with only the known `pynvml` FutureWarning. The accepted full run used a dedicated writable `--basetemp` after the known global Windows pytest temp ACL caused setup-only errors.
- No Production runtime contract, Hi-Res Fix algorithm, Node ID, V3.4/V3.5 compatibility path, or runtime dependency changed.
- Pre-change snapshot: `pre-ci-dependency-stub-fix-source-accepted-20260825_005009` (478 files), excluding `.git` and the known ACL-inaccessible `.pytest_cache` after the standard snapshot script encountered that existing ACL condition.
- Confirmed the prior README clarification was already on public `main` and closed GitHub Issue #11 as completed. Issues #9, #10, and #11 are now all closed with implementation answers.

## 2026-08-25 - V3.5.1 Reference Audio permanent-socket compatibility hotfix

- The standard snapshot script stopped only on the known ACL-inaccessible `.pytest_cache`. Accepted snapshots are `pre-v351-reference-audio-permanent-sockets-source-accepted-20260825_024425_613` (478 files) and `pre-v351-reference-audio-permanent-sockets-runtime-w-accepted-20260825_024426_476` (350 files), excluding `.git` and `.pytest_cache` with matching source/destination file counts.
- Removed all frontend `addInput`/`removeInput` behavior for `reference_audio_1` and `reference_audio_vae`, the UI-only `Reference Audio Inputs` Hidden/Show widget, its connection callbacks, and its serialization guard. Both sockets now remain permanently present exactly as defined by `H3ContinuumSamplerV35.INPUT_TYPES`.
- Retained only human-facing label normalization for Video Guide Frames, Driving Audio, and Reference Audio. Node IDs, backend socket keys/order/types, Sampling, Conditioning, Last Queued Seed Reuse, V3.4 behavior, and all other conditional widgets are unchanged.
- Added a real JavaScript save/reload regression that serializes the complete 20-value V3.5 widget sequence, reloads it positionally, and verifies every value remains aligned while both Reference Audio sockets retain their names and order. The bundled LBH/Conditioning Bridge example now has the same aligned 20-value sequence and both permanent sockets. Focused validation is `13 passed`; full validation is `452 passed`; JavaScript syntax and `git diff --check` pass. The only warning is the known `pynvml` FutureWarning.
- Synchronized only `web/project_id.js` and `web/reference_audio_ui.js` to ComfyUI_W and verified exact source/runtime SHA-256 equality. The two matching runtime Manifest entries were updated without normalizing its pre-existing unrelated 30 missing/divergent entries. No ComfyUI process was started, stopped, or restarted; live workflow save/reload acceptance is left to the already-running user environment.
- Removed the obsolete Hidden/Show comparison article and its two screenshots. Replaced the input overview with the user-supplied permanent-socket view and added the user-supplied full sampler view showing the corrected widget alignment.

## 2026-08-25 - Optional Windows pinned-memory README tip

- Added a short English-only optional tip for `--disable-pinned-memory` near the measured memory section. It records the local RTX 5060 Ti 16 GB / RAM 64 GB `0.4 MP, 2 x 5s` result (`5m 23s`, approximately 6.1 GB sampler RSS and 8.6 GB after assembly) without presenting the flag as a default, universal crash fix, or guarantee against Shared GPU Memory use.
- Pre-change snapshot: `pre-readme-pinned-memory-tip-source-accepted-20260825_031002_500` (477 files), excluding `.git` and the known ACL-inaccessible `.pytest_cache`.

## 2026-08-25 - Last Queued Seed promptQueued observer candidate

- Replaced the unsuccessful widget callback, `afterQueued`, and `onWidgetChanged` wrapping approach instead of stacking another mechanism on top. `beforeQueuePrompt` now stages the V3.5 Randomize seed, the official `promptQueued` event accepts it after a successful queue, and a pending-only 50 ms observer reads current `node.widgets` until it restores the accepted seed on `Fixed` or cancels on a manual seed change.
- Queue validation failures cannot update `last_queued_seed`; a later single-queue attempt replaces any unaccepted candidate. Restoration changes the visible widget value directly and never mutates the API prompt behind the UI.
- Accepted exact-file snapshots are `pre-last-seed-observer-source-files-20260825_175117` (4 files), `pre-last-seed-observer-runtime-files-20260825_175117` (2 files), `pre-last-seed-observer-docs-20260825_175652` (2 files), and `pre-last-seed-observer-runtime-manifest-20260825_175724` (1 file). The standard full snapshot attempt stopped only on the known ACL-inaccessible `.pytest_cache` before any edit.
- Focused frontend/compact-UI validation is `9 passed`; full source pytest is `453 passed` with only the known `pynvml` FutureWarning. JavaScript syntax passes, and `web/last_queued_seed.js` plus `web/project_id.js` match ComfyUI_W by SHA-256. Live UI transition and First Pass cache reuse remain pending; commit/push were not performed.

## 2026-08-25 - Last Queued Seed experiment withdrawn

- Real-browser Randomize-to-Fixed pairs repeatedly submitted different base seeds, including `00043` (`432308459616145`, Randomize) and `00044` (`238985343135586`, Fixed). Each file's Workflow/UI seed matched its submitted Prompt seed, proving that the restoration itself failed rather than metadata being stale.
- Removed only the Last Queued Seed frontend integration, its dedicated module, and its simulated regression. `H3 Continuum Sampler V3.5` again delegates Seed and `control after generate` entirely to ComfyUI. Reference Audio UI, compact UI settings, and all unrelated Production paths are unchanged.
- GitHub review found a valid alternative pattern in rgthree's dedicated Seed node: it removes the native control, finalizes the Prompt/Workflow seed immediately before queueing, and exposes an explicit `Use Last Queued Seed` button. That design is materially different from transparently intercepting an existing Sampler's Randomize-to-Fixed transition and was not added to Continuum.
- Accepted exact-file snapshots are `pre-remove-last-queued-seed-source-files-20260825_184039` (10 files) and `pre-remove-last-queued-seed-runtime-files-20260825_184039` (4 files). The standard snapshot attempt stopped only on the known ACL-inaccessible `.pytest_cache` before any edit.
- Focused compact/reference-audio/release validation is `8 passed`; full source pytest is `450 passed` with only the known `pynvml` FutureWarning. JavaScript syntax and runtime verification pass; the seed-only removal is synchronized to ComfyUI_W. Commit/push were still pending at this checkpoint.

## 2026-08-27 - V3.6.1 non-Balanced Audio Continuity fallback

- Confirmed the public V3.6 contract mismatch: Standard selected the 22-frame-only Masked AV transport whenever Audio Continuity was ON, while Fast, Strong, and Auto could resolve to 5 or 39 frames and reach an internal contract stop; Strong 39 also had an explicit Long Terminal Merge rejection.
- Added pre-execution routing in `v3/driving_nodes.py`: Balanced 22 stays Masked AV, Audio Continuity OFF stays Masked Video, and Fast 5 / Strong 39 / Auto with Audio Continuity ON use accepted Reference Context from the start. Compatibility is unchanged. Status and tooltip diagnostics describe the resolved transport without rewriting UI values.
- Added routing, report, unchanged-path, and legacy Reference Run Storage identity regressions. Focused validation is `108 passed`; final full source pytest is `543 passed`; all 178 Manifest entries, compileall, and `git diff --check` pass. V3.6.1 version/README/CHANGELOG/package metadata now include this fix together with the already-pushed Prompt Parser hotfix.
- Pre-change snapshots are `pre-v361-continuity-fallback-source-accepted-20260827_194154-e626053` (598 source files) and `pre-v361-runtime-w-sync-accepted-20260827_195452` (350 runtime files). Synchronized `v2/prompts.py`, `v3/driving_nodes.py`, and `version.py` match ComfyUI_W by SHA-256; the V3.6.1 runtime verifier passes. Representative GPU Smoke remains pending; commit/push were not performed.

## 2026-08-27 - Issue #13 contrast / oily drift investigation

- Preserved all existing V3.6.1 release/fallback changes. The standard snapshot attempt encountered only the known ACL-inaccessible `.pytest_cache`; accepted source snapshot is `pre-issue13-drift-investigation-accepted-20260827_204413-e626053` with 598 files at revision `e62605389302192394446645cf3483fff08dfbf2`.
- Added two non-Production diagnostic tools: `tools/issue13_drift_gate_runner.py` for matched five-case ComfyUI API execution and `tools/issue13_drift_analyze.py` for 25-frame-per-chunk color metrics and a contact sheet. They are not imported or registered by the package.
- GPU matrix completed on ComfyUI_W 0.34.0 / RTX 5060 Ti 16 GB: Fixed Standard, same-text List Standard, same-text Timeline Standard, varied List Standard, and Fixed Compatibility. Every case produced 600 frames / 25 seconds at 384x384 without execution error, NaN/Inf, or OOM.
- Fixed, same-text List, and same-text Timeline are decoded-stream bit-identical and use identical resolved prompt hashes. Prompt Format itself and repeating the same text through a different parser mode are rejected as the cause.
- Compatibility / Reference Context reproduced cumulative contrast and high-saturation-tail growth; Standard Masked AV did not. This supports legacy Reference Context visual self-conditioning as the most likely cause under the controlled condition. The exact reporter workflow is still unavailable, and model/sampler/seed generality was not claimed.
- Evidence is under `D:\Codex\_test_results\ComfyUI-H3-Continuum\issue13-drift-20260827_204827`, including `ISSUE_13_INVESTIGATION_REPORT.md`, five-case prompts/histories, `analysis.json`, `chunk_metrics.csv`, and `contact_sheet.png`.
- Diagnostic `py_compile` passes; full pytest is `543 passed` with only the known `pynvml` FutureWarning; the ComfyUI_W V3.6.1 runtime verifier and `git diff --check` pass. Production, frontend, schema, version, commit, push, and release were unchanged.

## 2026-08-27/28 - Audio Continuity Research Gate

- Preserved all existing V3.6.1 working-tree changes and created accepted snapshot `pre-audio-continuity-research-gate-accepted-20260827_231806-e626053` (602 files, excluding `.git` and the inherited ACL-inaccessible `.pytest_cache`).
- Added tests for 24 fps / 40 Hz grid offsets, cumulative PCM boundaries, 39f/65T State retention, Audio40 end alignment, and non-mutating Seam diagnostics. No Production implementation was changed.
- Added private research-only Audio40 routing to the diagnostic node plus API/output analysis tools. Ran six 3x5-second GPU outputs: music, dialogue, and ambient, each at 37T and 40T with fixed seed, 576x576, 20 steps, Balanced 22, Audio Continuity ON, and Seam OFF.
- All outputs completed and retained 360f / 15.000s / 32 kHz stereo contracts with finite latents. 40T added only six packed rows but did not improve audio boundaries consistently: Ambient improved, Dialogue was mixed, and Music immediate jumps worsened. Production remains at Audio37T.
- Generated machine-readable summaries, finalized-output metrics, boundary contact sheets, and 12 listening clips under `D:\Codex\_test_results\ComfyUI-H3-Continuum\audio-continuity-research-20260827_2335`. The detailed report is `AUDIO_CONTINUITY_RESEARCH_REPORT.md`.
- Final validation: focused `33 passed`, related `115 passed`, full `552 passed`; compileall, V3.6.1 ComfyUI_W runtime verifier, diagnostic source/runtime SHA-256, empty queue, and `git diff --check` PASS. No commit/push/version/release was performed; ComfyUI_W remains running.
