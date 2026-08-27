# Project State

## E2-8 Second Pass contract (2026-08-22)

- V3.4 remains the stable generation contract; UI, sockets, sampling, Run Storage identity, and Assembly behavior are unchanged.
- `assembly_plan.second_pass_contract` is additive V3.5 metadata organized by physical decode group.
- Prompt source is the stored physical prompt; a future Second Pass node must not reparse Sequence Prompt.
- Video B/C/T and physical group count/order are fixed; only latent H/W may be preserved or enlarged.
- Audio output is the original physical audio LATENT passed through bit-exact; refined audio is not adopted in V1.
- E2-8A Contract, E2-8B1 CPU/static validation, E2-8B2 external LBH GPU PoC, and E2-8C Second Pass GPU acceptance are formally PASS. The E2-8C CPU baseline is `260 passed`.
- External LATENT nodes may discard custom dictionary metadata. Identically shaped group reordering therefore cannot be cryptographically detected; count, position, T, geometry, and audio-shape checks are enforced.

Updated: 2026-08-27

## V3.6.0 public release implementation (2026-08-27)

- Added the new public `H3ContinuumSamplerV36` / `H3 Continuum Sampler V3.6` without replacing or redirecting V3.5.3/V3.4 nodes. Its final required widget is `Continuation Backend` with only `Standard` and `Compatibility`; internal transport identifiers are not exposed.
- `Standard` selects accepted Masked AV when Audio Continuity is ON and accepted Masked Video when it is OFF. `Compatibility` selects the original Reference Context route. Existing V3.5.3 remains on Reference Context with its prior schema and widget sequence.
- Added `examples/workflows/MiniMax_H3_Continuum_V36.json` as the recommended template, retaining the V3.5 template unchanged. Version/package metadata and English/Japanese release documentation are updated to 3.6.0; V3.5 Second Pass, Hi-Res Fix, Conditioning Bridge, V3.5 Assembly, and older workflows remain available.
- The public-node GPU Smoke used `H3ContinuumSamplerV36` directly through the normal API, not the private diagnostic node: Standard backend, 2x5-second I2VA + Reference Image + Reference Audio, 384x384, four steps, Audio Continuity ON, Audio Seam Auto. Prompt `1cff2ce7-6587-4d71-903d-b04bb304fdd5` completed successfully in `65.21s`; the report confirms a 22f/37T masked AV target prefix on chunk 2.
- Smoke output is `D:\output\video\comfy_video\video\V36_Release_Smoke_Reference_AV_Standard_00001_.mp4`: finite 384x384, 240 frames, 24 fps, 10.000-second video, and 32 kHz stereo 10.000-second audio. Evidence is `D:\Codex\_test_results\ComfyUI-H3-Continuum\v360-release-smoke\20260827_172835`.
- Source focused release validation is `81 passed`; final full source validation is `527 passed` with only the known `pynvml` FutureWarning. V3.6.0 WAN runtime verifier, JavaScript syntax, changed-file `py_compile`, the 178-entry Manifest, README link validation, and source/runtime SHA-256 equality for 12 Production files all pass. The live API queue is empty and the V3.6 backend remains running.
- Accepted snapshots are `pre-v360-public-release-accepted-20260827_171442` (212 Git-visible source files) and `pre-v360-public-runtime-wan-20260827_172531` (the five runtime files changed for public registration/version/UI). Final repository validation is complete; commit/push/release are the remaining publication actions.

## V3.6 Production Integration Gate (2026-08-27)

- PIG-0 through PIG-5 are complete. The Masked AV backend and V3.6 public/default promotion are **PASS**. During the gate, published/default V3.5.3 remained `reference_context_v1` and no public schema changed; the separately authorized V3.6 UI/version implementation is recorded above. V3.5.3 and V3.4 behavior remains unchanged.
- Run Storage now scopes only nondefault continuation transports. `reference_context_v1` retains its exact legacy identity/revision behavior, while `masked_av_prefix_22_v1` records `continuation_transport` in both the identity and Sampling Contract. Reference and Masked chunks therefore cannot be mixed.
- The integration gate also found and fixed a pre-existing resume defect: temporary Run Storage Sessions did not restore Terminal Merge `execution_semantics`, so an apparently valid prefix was discarded before Sampling. Resume Sessions now carry the stored execution semantics, and the reported reuse count is synchronized after atomic terminal-pair pruning.
- Real-cache PIG-2 PASS evidence is under `D:\Codex\_test_results\ComfyUI-H3-Continuum\v36-production-integration\v36_pig2_masked_20260827_164303`. Initial Save used `0 reused / 3 generated`; Auto Resume used `3 / 0` with zero Sampling calls; Regenerate From Chunk 2 and Chunk 3 each used `1 / 2` and exactly one `77T Video / 433T Audio` terminal physical Sampling call. Neither request reused or sampled only one logical half of the terminal pair.
- PIG-1 CPU coverage proves that Reference Image and standalone Reference Audio remain present exactly once in every normal and Terminal physical group under Masked AV, with no old continuation Reference block. PIG-3 then completed a representative 2x5-second I2VA + Reference Image + Reference Audio GPU run at 384x384 / 4 steps. Both physical groups contained image/audio references, protected Video/Audio prefixes finalized bit-exact, and the final output is finite 240 frames / 24 fps / 10.000 seconds with 10.000-second stereo audio.
- PIG-3 evidence is `D:\Codex\_test_results\ComfyUI-H3-Continuum\v36-production-integration\pig3-reference-masked`; output video is `D:\output\video\comfy_video\video\V36_PIG3_Reference_Image_Audio_Masked_AV_00001_.mp4`. At the retained 124-frame boundary with existing Audio Seam Auto, the sample jump is `0.004261`, below the local median (`0.005129`) and only `0.0876x` the local p99; PCM is finite. This representative numeric gate is PASS, but prior R2 seeds show mixed Seam-Auto improvement, so no universal click-removal claim is made without listening/generalization.
- PIG-5 policy is fixed: V3.6 uses Masked AV as the standard continuation backend and retains Reference Context only as an Advanced compatibility fallback. Raw transport implementation names are not exposed in the UI. Run Storage identity remains transport-scoped, Terminal Merge regeneration remains atomic per physical group, and Audio Seam Auto remains an independently evaluated post-Sampling feature. This gate preceded the separately recorded V3.6 public UI/default implementation above.
- The accepted PIG-3 output passed subjective listening: no click, dropout, unnatural stereo positioning, or other audible boundary defect was reported. PIG-5 and V3.6 public-promotion eligibility are therefore **PASS** without reopening the completed structural, cache, Reference, Terminal Merge, or Audio Seam numeric gates.
- Final validation is `61 passed` focused and `521 passed` full pytest with only the known `pynvml` FutureWarning. Changed-file `py_compile`, V3.5.3 WAN runtime verification, source/runtime SHA-256 equality for `run_storage.py`, `v2/sequence.py`, and the diagnostic node, `git diff --check`, and empty API queue all pass.
- Accepted pre-change snapshots are `pre-v36-production-integration-pig0-accepted-20260827_161517` and `pre-v36-production-integration-pig2-diagnostic-accepted-20260827_162943`. Commit/push were not performed, and the ComfyUI_WAN backend remains running.

## V3.6-R2 FL2VA Long Terminal Merge multi-seed GPU gate (2026-08-27)

- The shortened final gate is **PASS for the private GPU research path**. Published/default V3.5.3 remains `reference_context_v1`; no public node/schema, saved-workflow contract, V3.4 behavior, Sampling implementation, Assembly, Seam, or Run Storage behavior changed.
- Accepted evidence consists of Seed `238985343135606` full Gate A, Seed `238985343135607` full `reference_context_v1` versus `masked_av_prefix_22_v1` comparison plus cache-only Audio Seam OFF derivatives, and Seed `238985343135608` Masked AV structure/practical acceptance. The redundant Seed 608 Reference run was intentionally omitted.
- Every measured run retained 3 logical chunks and 2 physical groups. Group 1 is `124f / Video 37T / Audio 207T`; Terminal Group 2 is logical `[2,3]`, `paired_timeline_v1`, `terminal_merged=true`, trim `22f`, `260f / Video 77T / Audio 433T`. Physical seeds were `15439951268068580545`, `4181078118376080811`, and `6961917749643595863` for Seeds 606–608. Final outputs are finite `640x640`, `360f`, `24fps`, `15.000s`, with 15.000-second audio.
- Seed 606 and 607 Group 1 Video/Audio hashes are identical between Reference and Masked routes. For all three Masked runs, Core raw protected-prefix drift was at most `2.384185791015625e-07` Video and `5.960464477539063e-08` Audio; scoped final restore produced bit-exact 7T Video and 37T Audio prefixes with SHA-256 equality and maximum difference `0`. Generated regions were not restored.
- Terminal Group 2 PackedLayout was `35,865` rows for Reference and `32,991` for Masked, removing exactly `2,874` Reference rows (`8.01%`). CUDA-synchronized Group 2 Sampling was `574.134 -> 529.933s` for Seed 606 and `560.782 -> 544.413s` for Seed 607. Both paired comparisons favor Masked; paired percentage median is `5.31%`. Reference/Masked time medians are `567.458s` and `544.413s`, respectively (`4.06%` lower by median comparison). Seed 608 Masked was `549.704s`.
- Across the five main runs, monitored process peak RSS median was `9.674 GiB`. Maximum observed whole-device usage was `15.646 GiB`; this is an order-sensitive device-used monitor, not only Continuum allocation. Terminal-group CUDA allocator peak was about `4.06 GiB` for Reference versus `3.80 GiB` for Masked. No OOM, NaN/Inf, or retained-GPU-prefix regression occurred.
- Contact sheets covering nominal 5/10/15-second positions and actual retained boundaries `124f/243f` show no obvious flash, pose collapse, direction reversal, or temporal break in Seeds 606–608. Decoded audio is finite, exactly 15 seconds, and has no >=200 ms dropout below -50 dB. Existing Audio Seam Auto strongly improved Seed 606 Masked jumps (`0.035014 -> 0.002018` at 124f; `0.004495 -> 0.003130` at 243f), but Seed 607 was mixed (`0.059640 -> 0.133805` at 124f; `0.021297 -> 0.019704` at 243f). Therefore no universal click-removal claim is made from numerical jump alone.
- Final validation is `516 passed` with only the known `pynvml` FutureWarning, after rerunning with a fresh writable basetemp because the inherited global pytest temp root denied access. V3.5.3 WAN runtime verification, source/runtime SHA-256 for seven synchronized Production/diagnostic files, `git diff --check`, and empty API queue pass. The backend remains running as requested.
- **Production promotion: HOLD.** FL2VA/Terminal Merge structure, multi-seed execution, integrity, and performance are accepted, but Reference conditioning variants, Run Storage/resume identity, public UI/default-policy decisions, and broader audible Audio Seam acceptance remain outside this gate. Evidence: `D:\Codex\_test_results\ComfyUI-H3-Continuum\v36-fl2va-combined-20260826\gate-a` and `...\r2-short`. Pre-change snapshot: `pre-v36-r2-short-gate-20260827_000840`. Commit/push were not performed.

## V3.6 shared chunk-duration range (2026-08-27)

- V3 Production, V3.4/V3.5 inherited schemas, the V2 compatibility sampler/facade, and Prompt Plan Preview now share `chunk_seconds`: default `5.0`, minimum `4.0`, maximum `30.0`, step `0.1`.
- One `chunk_seconds` value still applies to every logical chunk. Per-chunk variable durations were not added; Assembly, Timeline, Continuation, and Run Storage retain the shared-duration contract and existing workflow inputs remain compatible.
- `5–15s` remains the recommended and validated range. `15–30s` is usable rather than hidden/experimental, with a shared tooltip warning that high resolution can substantially increase VRAM use and processing time.
- Prompt Plan creation and validation accept `30.0` and reject values above it. Timeline mapping was verified for `[0-30s]` / `[30-60s]`. Temporal extension tests now cover the complete `4.0–30.0s` UI range and preserve the existing native H3 `17k+5` grid.
- The only remaining `max: 15.0` is the separate legacy V1 `H3ContinuumJoin.extend_seconds` control; it is not `chunk_seconds`, is not used by the V2/V3 Production path, and was intentionally left unchanged.
- CPU/static acceptance is PASS: focused duration and inherited-schema validation `89 passed`; canonical full pytest `516 passed`; changed-file `py_compile`, `git diff --check`, runtime verifier, source/WAN SHA-256, live API schema, and empty queue all pass. ComfyUI_WAN was restarted with Sage Attention and `--disable-pinned-memory` and remains running.
- A validation-only GPU launch used one T2VA chunk, `chunk_seconds=30.0`, `384x384`, one Sampling step, and fixed seed `238985343135609`. API prompt `9e665f85-b32f-4b17-9734-219fb284e087` was accepted with no node errors and entered H3 model initialization/Sampling without duration, shape, Prompt Plan, immediate OOM, or NaN/Inf errors. Per user scope, it was interrupted after `31.87s` rather than decoded or saved; this is an execution-entry smoke PASS, not a completed 30-second quality/performance acceptance. Queue returned to `0/0`.
- The previously prepared FL2VA joint multi-seed run was cancelled at the user's request. Only its one-step cache warm-up completed; the first measured run was interrupted before node execution and is not acceptance evidence.
- Accepted snapshots are `pre-v36-chunk-duration-30-source-20260826_234716` (209 Git-visible source files, zero missing/mismatch) and `pre-v36-chunk-duration-30-wan-runtime-20260826_235423` (four exact runtime files). Commit/push were not performed.

## V3.6-R2-2 Balanced 22f / 37T Joint AV GPU gate (2026-08-26)

- R2-2 is **PASS as a one-seed GPU structure/performance gate with the existing Audio Seam Auto path**, not a Production promotion. The accepted pair used T2VA 2x5 seconds, 640x640, Balanced 22, Audio Continuity ON, fixed seed `238985343135605`, Prompt/CLIP cache HIT, CUDA synchronization, Sage Attention, `--disable-pinned-memory`, Exact Duration ON, and no First/Last/Reference/Video Guide/Run Storage/Spectrum/Sol/Video Seam.
- Added only the private `masked_av_prefix_22_v1` research transport. It preserves the existing Balanced contract: Video prefix `22f = 7T = 0.916667s`, Audio prefix `37T = 0.925s`, an intentional mask-boundary asymmetry of `1/120s = 8.333ms`, target `141f / Video 42T / Audio 235T`, trim `22f`, and net new `119f`. Public V3.5.3/V3.4 schemas and defaults remain unchanged.
- Masked finalization is exact: source Video tail and finalized target Video prefix are bit-exact with max diff `0`; the same holds for the Audio 37T tail/prefix. Core raw output before the scoped restore differed by at most `2.384185791015625e-07` for Video and `5.960464477539063e-08` for Audio. Only the protected prefix regions are restored; generated regions remain sampler-owned.
- Reference continuation used `20,205` packed rows (`2,800` video-reference rows plus `74` audio-reference rows); Masked AV used `17,331` rows with no reference block or old Spectrum interop hint. The `2,874`-row reduction is `14.22%`. Synchronized continuation Sampling was `226.373s -> 206.437s`, an `8.81%` reduction; whole API time was `435.907s -> 420.752s`, a `3.48%` reduction. This is one-seed evidence, not a universal performance claim.
- Both routes produced finite `640x640`, `240f`, `24fps`, `10.000s` outputs. Eight-frame boundary contact sheets show no obvious pose snap, direction reversal, camera collapse, NaN/Inf, or masked-prefix visual regression.
- With Audio Seam OFF, Reference boundary jump was `0.082725`; Masked AV was worse at `0.268163` (`7.57x` its local p99 and the `99.9989` file-wide percentile). Reassembling the same cached Masked latents with existing Audio Seam Auto took `7.10s` without Sampling and reduced the jump to `0.029944` (about `88.83%` lower, `0.86x` local p99, `94.31` percentile). RMS ratio also moved `1.12196 -> 0.97724`. R2 adds no new Audio Seam algorithm; raw Seam-OFF 22f/37T is not accepted as click-free.
- Evidence root: `D:\Codex\_test_results\ComfyUI-H3-Continuum\v36-r2-gate2-20260826`; accepted MP4s and the cached Audio-Seam-Auto derivative are under `D:\output\video\comfy_video\video`. Focused tests are `24 passed`; final full pytest is `510 passed`; changed-file `py_compile`, `git diff --check`, source/runtime SHA-256, runtime verifier, and empty queue all pass. Production remains **HOLD** pending multi-seed/audio listening generalization, Reference/FL2VA/Terminal Merge/Run Storage integration, public UI decisions, and final Production acceptance.

## V3.6-R2-0 Joint AV masked-prefix CPU/static gate (2026-08-26)

- R2-0 is implemented as a private research transport, `masked_av_prefix_39_v1`; the public/default V3.5.3 transport remains `reference_context_v1`. No public widget, Node ID, saved-workflow schema, `v2/sampling.py`, seed, Plan, trim, Decode, Assembly, Seam, Run Storage, or V3.4 contract changed.
- The exact-duration research case uses Strong 39-frame Continuity. A 39-frame video tail maps to 12 video latent slots, and the same 1.625-second duration maps to 65 audio latent ticks. The next physical target is 158 frames / video `47T` / audio `263T`, trims 39 frames, and retains 119 new frames.
- The target copies the prior finalized video tail into video `[0:12]` and audio tail into audio `[0:65]`. Full masks preserve those prefixes with zero and generate only video `[12:47]` / audio `[65:263]` with one. Old Context Reference conditioning and the Spectrum reference-context hint are not emitted. The original First Image remains attached only to chunk 1.
- After Sampling, Continuum restores only the protected video and audio prefixes from the normalized pre-sampling target. CPU regressions require bit-exact video/audio prefix equality and prove that generated video/audio regions are not restored or overwritten.
- The 39f and 65T durations are equal, but the native H3 audio grid can retain a signed source phase offset. The validated 124-frame source is `+1/3` audio tick (about `+8.33 ms`) and a 158-frame target is `-1/3` tick; this is recorded explicitly rather than described as zero-phase alignment.
- CPU/static R2-0 is **PASS**: focused masked/temporal validation `21 passed`, canonical full pytest `507 passed`, and changed-file `py_compile` pass with only the known `pynvml` FutureWarning. GPU R2-1 (`Reference Context 39f` versus `Masked AV Prefix 39f`), audio-boundary measurements, runtime synchronization, and Production promotion remain pending.
- Accepted pre-change snapshots are `pre-v36-r2-0-joint-av-source-accepted-20260826_203022` (571 files, SHA-256 mismatch 0, source revision `67a0d80117bd8332d2768d093dff343001c87d60`) and `pre-v36-r2-0-joint-av-wan-runtime-accepted-20260826_203022` (three exact runtime files). Commit/push were not performed.

## V3.6-R2-1 39f / 65T Joint AV GPU structure gate (2026-08-26)

- R2-1 is **PASS as a GPU structure/interoperability gate**. It is not a Production promotion. The accepted pair used T2VA 2x5 seconds, 640x640, Strong 39, Audio Continuity ON, the same fixed prompt/seed `238985343135604`, Prompt/CLIP cache HIT, CUDA synchronization around each Sampling call, `--disable-pinned-memory`, Sage Attention, and no First/Last/Reference/Video Guide/Run Storage/Spectrum/Sol/Video Seam. Reference ran before Masked after one excluded warm-up.
- `reference_context_v1` emitted Core's combined `video_audio` Reference block. Its continuation PackedLayout was `24,317` rows: target text `61`, audio `526`, video `18,800`, plus `4,800 ref_img` and `130 ref_audio` rows. `masked_av_prefix_39_v1` emitted no old refs/interop and used `19,387` rows: the identical target rows only. The measured reduction is exactly `4,930` rows / `20.27%` relative to Reference.
- CUDA-synchronized Chunk 2 host/Sampling time was `332.460s` for Reference and `241.888s` for Masked (`27.24%` lower). API wall time was `556.058s` versus `465.925s` (`16.21%` lower). This one-seed Gate is an explanatory performance signal, not a generalized speed claim.
- Masked target construction and masks passed on GPU: Video `[0:12]=0`, generated Video `[12:47]=1`, Audio `[0:65]=0`, generated Audio `[65:263]=1`; source tails matched both target prefixes. Core raw integration differed by at most `2.384185791015625e-07` for Video and `5.960464477539063e-08` for Audio. The finalized physical-group prefixes are bit-exact by SHA-256 and maximum difference `0` for both streams; generated regions are not restored.
- Both outputs are finite `640x640`, 240 frames, 24 fps, and 10.000 seconds. Boundary contact sheets at frames `112,118,123,124,125,130,136,148,160` show no gross snap, collapse, persistent artifact, or identity/background discontinuity in either route.
- With Audio Seam OFF, the exact decoded boundary sample is the global maximum single-sample jump for both routes: Reference `0.352289`, Masked `0.287521`. Masked is better but the raw hard boundary is not accepted as intrinsically click-free. The same cached Masked AV latents reassembled with the existing Audio Seam Auto in `7.23s` without re-running Sampling; boundary jump fell to `0.005774` (about `98.0%` lower and only the `37.4` percentile of file-wide sample differences), while DC jump fell `0.002789 -> 0.001103`. Therefore the existing Production seam path resolves the observed hard cut; R2 adds no new Audio Seam algorithm.
- Chunk 2 allocator peak was lower for Masked (`2,407,722,872` allocated / `2,785,017,856` reserved bytes) than Reference (`2,950,494,614` / `3,590,324,224`). Whole-process/device monitor peaks are order-sensitive and are not accepted as a memory claim from this one pair.
- Evidence root: `D:\Codex\_test_results\ComfyUI-H3-Continuum\v36-r2-gate1-20260826`; accepted MP4s are `V36_R2_Gate1_reference_39f_seed238985343135604_00001_.mp4`, `V36_R2_Gate1_masked_av_39f_65t_seed238985343135604_00001_.mp4`, and the cached Audio-Seam-Auto derivative under `D:\output\video\comfy_video\video`. The backend remains running. R2-2 22f / 37T, multi-seed/audio-quality generalization, References, Terminal Merge, Run Storage, public UI, and Production promotion remain pending.

## V3.6-R1 masked video-prefix continuation PoC (2026-08-26)

- V3.6-R1 is a private experimental continuation transport only. The published V3.5.3 path remains `reference_context_v1`; no public widget, Production Node ID, saved-workflow schema, V3.4 contract, Sampling implementation, seed derivation, Plan, trim, Decode, Assembly, Seam, or Run Storage contract was changed.
- `masked_video_prefix_v1` copies the previous chunk's normalized 22-frame / 7T video tail into the next 42T video target, applies a full video mask with prefix `0` and generated region `1`, leaves the 235T audio target empty with an all-`1` mask, emits neither the old `minimax_refs` video context nor the Spectrum reference-context hint, and retains the existing 141-frame physical / 22-frame trim / 119-frame net contract.
- Core v0.34.0 honors the zero-mask prefix during model calls, but its raw final integrated float32 sampler output differed from the input prefix by up to `2.38418579101562e-07`. Continuum therefore restores only the protected target prefix after Sampling. The finalized physical latent is bit-exact (`torch.equal`, maximum absolute difference `0`, and SHA-256 match); generated video and audio regions are not overwritten.
- CPU/static acceptance is PASS: focused validation `8 passed`; canonical full pytest `500 passed` with only the known `pynvml` FutureWarning; changed-file `py_compile` and `git diff --check` pass.
- GPU Gate 1 and Gate 2 ran three fixed-seed A/B pairs through the normal ComfyUI_WAN API at `127.0.0.1:8188`: 2x5-second T2VA, 640x640, 20 steps, Balanced 22, Audio Continuity OFF, Run Storage OFF, no First/Last/Reference/Video Guide, Spectrum/Sol OFF, Seam OFF, and Sage Attention enabled globally. Every run preserved two physical samples (`124f` then `141f`, trim `22`, net `119`), matching derived seeds and chunk-1 video/audio hashes. All six outputs are finite 640x640 / 240-frame / 24 fps / 10.000-second MP4s.
- All masked runs report prefix exactness, zero/one video mask regions, all-one audio mask, empty second-group `minimax_refs`, and no old interop hint. API elapsed A/B pairs were `432.67/412.73`, `409.98/386.09`, and `408.62/386.56` seconds; these single ordered pairs are diagnostic observations, not an accepted speed claim.
- The initial 2x5 T2VA contact-sheet review found no clear pose snap, direction reversal, persistent artifact, or temporal collapse in either transport, but also no consistent visual superiority. The later 3x5 Strong Motion I2VA Stress Gate adds a positive signal without yet justifying a public/default replacement.
- Before the formal I2VA gate, diagnostics found that the private masked branch reapplied the original I2VA First Image on continuation chunks while `reference_context_v1` correctly removed it under `POLICY_REPLACE`. Those preliminary runs are invalid and excluded. The private branch now attaches the First Image only to chunk 1, so the accepted A/B differs only in continuation transport.
- Formal Stress Gate conditions were 3x5-second I2VA, 640x640, Balanced 22, three fixed seeds, Audio Continuity/Run Storage/Spectrum/Sol/Seam OFF, Prompt/CLIP cache HIT, `--disable-pinned-memory`, and alternating order `R->M`, `M->R`, `R->M`. All six normal runs are finite 640x640 / 360-frame / 24 fps / 15.000-second MP4s.
- Masked continuation was faster for all three seeds. API reductions were `6.185%`, `7.491%`, and `5.544%` (paired median `6.185%`). Continuation Sampling reductions were `9.471%`, `12.029%`, and `8.309%` (paired median `9.471%`; reference `466.424s`, masked `426.798s`). A separate CUDA-synchronized seed pair still reduced continuation Sampling from `464.97s` to `437.10s` (`5.995%`), proving that the signal is not only asynchronous host timing.
- Actual Core packed layouts explain the result: continuation `reference_context_v1` is `20,569` rows (`2,800` `ref_img` rows), while `masked_video_prefix_v1` is `17,769` rows with no `cond` or `ref_img` rows. This is `2,800` fewer rows / `13.61%` below the reference layout. Peak process RSS and observed device memory remained comparable; no memory regression was accepted or claimed.
- Every masked boundary retained the finalized 7T prefix bit-exact by SHA-256 and maximum difference `0`. Boundary contact sheets found no gross snap, direction reversal, persistent artifact, or collapse. At the second boundary, automated optical-flow jerk and absolute luma/saturation drift were lower for Masked in all three seeds; flow-magnitude continuity was mixed, so this is an improvement signal rather than proof of universal visual superiority.
- R1 Stress Gate is therefore **PASS**, while Production promotion remains **HOLD**. It opened the separately specified R2 Audio-prefix research gate; the later R2-0 CPU/static result is recorded above. Feathering, References, Terminal Merge, public UI, Run Storage integration, and GPU R2 acceptance remain unimplemented V3.6 research.
- Stress evidence: `D:\Codex\_test_results\ComfyUI-H3-Continuum\v36-r1-stress-gate-20260826\normal_fair` and `sync_fair`; `analysis.json` and `contact_sheets` contain the aggregate metrics and boundary frames. Invalid pre-fairness runs under the sibling `normal` directory are retained only as diagnostic history and must not be cited. Accepted Stress snapshots are `pre-v36-r1-stress-gate-source-accepted-20260826_174839`, `pre-v36-r1-stress-gate-wan-diagnostics-accepted-20260826_174839`, and `pre-v36-r1-stress-i2va-fairness-wan-runtime-20260826_182905`.
- Final validation after the Stress Gate is `500 passed`; changed-file `py_compile`, V3.5.3 runtime verification, `git diff --check`, source/runtime SHA-256 for four R1 Production files plus the diagnostic node, and empty API queue all pass. The ComfyUI_WAN backend intentionally remains running after acceptance.
- Reusable private A/B workflow: `D:\Codex\_test_workflows\ComfyUI-H3-Continuum\MiniMax_H3_Continuum_V36_R1_MaskedPrefix_AB.json` (22 nodes, 24 links, three annotated groups, SHA-256 `0964D55DDE1671E0BB0CA04FD3DD1F0AF82A4173FB9E6D9CE75900FC9B6981CE`). It is a simplified derivative of the user-supplied V3.5 workflow and requires the ComfyUI_WAN-only diagnostic node; it is not a public template.

## V3.5.3 maintenance hotfix (2026-08-26)

- V3.5.3 is a distribution-integrity maintenance hotfix over published V3.5.2. Sampling, Conditioning payloads, Terminal Merge, Assembly, Seam, Run Storage, Prompt/CLIP caching, Video Guide optimization, V3.4 compatibility, node IDs, and backend socket keys are unchanged.
- Repaired the public Conditioning Bridge workflow links `349`/`350` so the shared Width/Height controls target Sampler V3.5 input slots `16`/`17`; removed stale output link IDs `171`/`172`/`173` from the public V3.4, V3.4 Turbo, and V3.5 workflows.
- `validate_reference_prompts()` now preserves absolute public `<Picture N>` numbers for Hybrid First/Last + Reference warnings. This matches the previously accepted ComfyUI_W behavior and changes report text only.
- Re-encoded the unreferenced legacy `docs/images/v31b-auto-resume.png` without changing any displayed pixel. All 19 packaged PNG files pass strict Pillow verification.
- Added regressions for all eight public workflow graphs and the Hybrid warning numbers. Focused validation is `30 passed`; canonical full pytest is `495 passed`, and the source/runtime V3.5.3 verifier passes native PackedLayout, Fixed 3x5 planning, and complete node registration.
- The release Manifest now contains 173 files and verifies every recorded SHA-256, including the new public-workflow integrity regression.
- Production files `reference.py`, `version.py`, and `metadata.ini` are synchronized to ComfyUI_W with exact SHA-256 equality. ComfyUI_WAN is excluded because that secondary runtime is an incomplete older copy and must not be partially relabeled as V3.5.3.
- Accepted snapshots are `pre-v353-maintenance-hotfix-source-accepted-20260826_030732` (199 tracked files, revision `70cbbcd`) and `pre-v353-maintenance-hotfix-comfyui-w-accepted-20260826_030731` (14 present target files). The maintenance release was published as commit `67a0d80117bd8332d2768d093dff343001c87d60`.

## V3.5.2 final release gate (2026-08-26)

- V3.5.2 is the release-candidate baseline for the Stabilization & Optimization Update. It adds no generation mode and preserves all V3.5.x workflow contracts plus V3.4 Node IDs/backend socket keys.
- Phase 3-1 Prompt/CLIP cross-run cache and Phase 4-6A Video Guide memory optimization are the only adopted Production optimizations. Sampling, Conditioning payloads, Terminal Merge, Assembly, Seam, Run Storage, and standard ComfyUI Seed behavior remain unchanged.
- Final pre-release T2VA API smoke at 576x576 / 1x5 seconds / 20 steps confirmed MISS `encode_calls=1` and HIT `encode_calls=0`; Prompt/CLIP time changed from `8.454306s` to `0.000038s`. Both runs used derived Sampling seed `5684542245315818407` and produced identical decoded video MD5 `40e378d7c80e6bebd9d64b322c13e677` and audio PCM MD5 `4fb0a699227c4f834f7a52ba4d395ae8`.
- The accepted Video Guide GPU A/B remains the Phase 4-4 result: full source SHA-256, identity, 124-frame prefix, VAE/Qwen inputs, Sampling seed, decoded video MD5, and audio PCM MD5 all match exactly between old and optimized preprocessing.
- Final post-sync gate is PASS: `485 passed`, compileall exit `0`, V3.5.2 runtime verifier PASS, all 172 Manifest hashes valid, `git diff --check` exit `0`, required node registration complete, and the API queue empty. ComfyUI_W restarted with `H3 Continuum 3.5.2 loaded`; source, ComfyUI_W, and ComfyUI_WAN hashes match for `version.py`, `metadata.ini`, and the accepted `reference_video.py`.
- Public result image is `docs/images/v352-stabilization-optimization.png`, copied bit-exact from the user-supplied `D:\SD_PIC\Neo\Clip_91.png` (SHA-256 `0c1dfd5acff349b98ecdfb57ae50941f6da26a462dfd2aaa9b7c7b0a34abf304`). README text is the canonical environment description where the supplied image contains a different ComfyUI minor-version label.
- Exact release-preparation snapshot: `pre-v352-release-preparation-exact-20260826_022016`, revision `b8ab766eb364063f8af88781e7be70ee7286fba0`, 198 source files plus the four active runtime metadata files.

## V3.5.1 stabilization Phase 4-6A Video Guide memory optimization (2026-08-26)

- Phase 4 Feature Tax & Redundancy Audit is PASS. No evidence-backed Production speed optimization was selected. Driving Audio generated-audio Decode/Assembly and same-rate Audio hashing remain documented `SIMPLIFY` candidates below the 1% adoption threshold; Sampling, Session/State validation, Refine Context, Run Storage, Assembly Plan validation, and V3.4 remain unchanged.
- Phase 4-6A is formally PASS, including Phase 4-4 GPU acceptance. `reference_video.py` now normalizes, finite-checks, and hashes the complete Video Guide in eight-frame CPU float32 RGB chunks while retaining only the prefix used by the one-chunk H3 conditioning contract. Full source shape/dtype/raw-byte order and SHA-256 remain exact, so unused-tail changes and non-finite values still affect identity/validation.
- The primary ComfyUI_W runtime contained a pre-existing uncommitted Video Guide preprocess v3 that was newer than the repository v2. With explicit approval, its H3 `17k+5` frame alignment and final-frame padding behavior was integrated into the authoritative source before applying the memory optimization. The active v3 contract, source SHA-256, combined hash, frame count, and Run Storage identity are preserved by dedicated regressions.
- Deterministic 300x256x256 RGB / 124-frame-prefix comparison against the pre-change ComfyUI_W v3 produced the same `source_sha256` and complete contract. Preprocessing peak RSS above the already allocated input fell from `396.758 MiB` to `114.695 MiB`; retained Video Guide storage fell from `225.0 MiB` / 300 frames to `93.0 MiB` / 124 frames. Host time was `0.246672s` versus `0.257602s`, so this is accepted as a memory optimization rather than a speed claim.
- Dedicated Video Guide plus existing Driving Audio regressions are `17 passed`; canonical full pytest is `485 passed`. Source runtime verification, 171 Manifest hashes, syntax, and `git diff --check` pass. Only the known `pynvml` and inaccessible repository pytest-cache warnings remain.
- Phase 4-4 compared the pre-change v3 implementation and the optimized implementation through the normal ComfyUI API with the same 15-second / 360-frame 800x800 Video Guide, V3.5 one-chunk 5-second workflow, 576x576 output, 20 steps, seed input `46001`, and Hi-Res Fix disabled. Both resolved the guide to 640x640 / 124 frames, used one physical group and the same derived Sampling seed `3288707263902886519`, and assembled 124->120 frames at 24 fps / 5.000 seconds with 32 kHz stereo audio.
- The actual VHS-loaded source SHA-256 is `ea03aa0cb216213b3a7320f7fa262f226e8e9075d31f69bdb184eec7ea189f5d`; old/new combined identity, 124-frame prefix, 640x640 VAE input, and Qwen input are byte-identical. Decoded video MD5 is `53cd381aff184c2f8aa5910ab62be342` and decoded audio PCM MD5 is `3653c0ec89947a928075d4ba056ff624` on both paths. Representative frames show no gross artifact or collapse. Runtime was restored to the optimized file and its SHA-256 matches source (`a0266ab4434b8e9844219d2b6dd8a168d198dd8f142775be01a39b81dc196b91`).
- Accepted pre-change snapshot is `pre-phase4-6a-video-guide-memory-exact-20260826_012227` (6 exact source/runtime files, revision `b8ab766eb364063f8af88781e7be70ee7286fba0`). The standard full snapshot attempt stopped only on the known ACL-inaccessible `.pytest_cache`.

## V3.5.1 stabilization Phase 3-2 synchronized GPU rebaseline (2026-08-26)

- Phase 3-2 is formally PASS and is measurement-only. No Production node, schema, Sampling/Conditioning payload, Terminal Merge, Assembly, Seam, Run Storage, or V3.4 behavior changed. Diagnostics run from repository tools against the normal ComfyUI API and are not installed into `custom_nodes`.
- After one excluded warm-up and with the Phase 3-1 Prompt/CLIP cache already hot (`encode_calls=0`), the three-run API medians are `168.069s` for 1x5 T2VA at 576x576 and `379.765s` for 3x5 FL2VA Long Terminal Merge at 640x640. Synchronized in-process medians are respectively `166.986s` / `378.107s`, with Sampling `120.516s` / `295.216s`, Video VAE Decode `19.154s` / `51.634s`, Audio VAE Decode `0.466s` / `1.040s`, Assemble + Seam `0.130s` / `0.619s`, and MP4 save `2.583s` / `7.248s`.
- True whole-workflow PyTorch CUDA allocator peaks are `1.456 GiB` T2VA and `4.129 GiB` FL2VA. They are allocator observations, not total device VRAM usage and do not include every model-weight, ComfyUI staging, driver, or external allocation. Separate per-node peak runs confirm Sampling as the CUDA maximum; Video VAE Decode peaks are `0.290 GiB` / `0.319 GiB`. Whole-workflow Windows RSS/private peaks are about `29.15/45.53 GiB` T2VA and `30.82/46.18 GiB` FL2VA. These process peaks include Core/model staging and mapped/output pages and are attribution data, not Continuum-retained memory claims.
- T2VA external-attention API medians are: Sage `168.069s`; Sage + Sol-Attn `162.090s` (`-3.56%`); Sage + Spectrum `124.830s` (`-25.73%`); Sage + Sol-Attn + Spectrum `121.147s` (`-27.92%`). Sol's sparse Triton kernel was verified active with zero fallback after moving its writable cache to the test evidence root. Spectrum emitted its Continuum API acceptance marker. These routes may change floating-point results and are not bit-exact Continuum A/B claims.
- The fastest combined route also passed one measured FL2VA Long Terminal Merge run at `288.548s` API (`-24.02%` versus the Sage median): 3 logical / 2 physical groups (`[1]`, `[2,3]`), terminal seed/trim contract intact, 640x640, 360 frames, 24 fps, 15.000s, and audio present. All measured T2VA routes produced 576x576, 120 frames, 24 fps, 5.000s, and audio. Representative contact-sheet review found no gross line/plate artifact or collapse; this does not turn the external plugins into Continuum-owned quality guarantees.
- The new rebaseline leaves no evidence-backed Continuum Production optimization candidate for Phase 3-3. Sampling is dominant but contract-sensitive; Video/Audio VAE Decode and MP4 encoding are external Core/downstream work; Assemble + Seam is below the 1% adoption threshold. Phase 3-1 remains frozen rather than broadening its cache scope.
- Reusable diagnostics are `tools/p32_profile_server.py`, `tools/p32_api_runner.py`, and `tools/p32_gpu_profile_probe.py`. Accepted evidence is under `D:\Codex\_test_results\ComfyUI-H3-Continuum\stabilization-phase3-2-20260825`. The accepted pre-change snapshot is `pre-stabilization-phase3-2-profile-accepted-20260825_220920` (479 files, revision `b8ab766eb364063f8af88781e7be70ee7286fba0`).
- Phase 3-2 focused validation is `13 passed`; canonical full pytest is `480 passed`. Diagnostic-file `py_compile`, all 170 Manifest hashes, source runtime verification, and `git diff --check` pass. Only the known `pynvml` FutureWarning remains.

## V3.5.1 stabilization Phase 3-1 Prompt/CLIP cross-run cache (2026-08-25)

- V3.5 now enables one private, bounded Prompt/CLIP conditioning cache. V3.4 public schema and execution remain unchanged. The cache belongs to the exact CLIP object, holds at most 16 LRU entries, and keys prompt text, exact resized First/Last image fingerprints, Last Frame presence, CLIP patch UUID, and CLIP layer.
- Reference Image, Reference Audio, Video Reference, Timeline Video, CLIP schedules, tokenizer options, and hook-modified CLIP states conservatively bypass the cache. Any cache error falls back to a normal encode and does not stop generation. Cached tensor payloads may be shared, but mutable metadata containers are copied for every consumer. CUDA-resident conditioning is never stored.
- Detailed Report records `hits`, `misses`, `bypasses`, and the actual Prompt/CLIP `encode_calls`. CPU regressions cover bit-exact payloads, mutable metadata isolation, every key invalidation, special-state bypass, CUDA-output rejection, fail-soft behavior, and 17th-entry LRU eviction.
- GPU/API 1x5 T2VA at 576x576 passed. MISS was `encode_calls=1`, Prompt/CLIP `5.898398s`; HIT was `encode_calls=0`, Prompt/CLIP `0.000028s`. Both same-seed outputs contain the same 120 decoded frame MD5 sequence and identical decoded audio PCM MD5. A separate base-seed-only change also remained a HIT with `encode_calls=0`, produced a different derived Sampling seed, and completed at 120 frames / 5.000s.
- GPU/API 3x5 FL2VA Long Terminal Merge at 640x640 passed with 3 logical / 2 physical groups (`[1]`, `[2,3]`). MISS was `encode_calls=4`, Prompt/CLIP `21.642687s`; HIT was `encode_calls=0`, Prompt/CLIP `0.007128s`. Both same-seed outputs contain the same 360 decoded frame MD5 sequence, identical decoded audio PCM MD5, and 15.000s duration. A separate base-seed-only change also retained four HITs / zero encode calls and the same physical grouping with newly derived physical seeds.
- No retained CUDA regression was observed: HIT completion CUDA allocated was lower than the adjacent MISS in both cases, and retained Refine Context GPU / observed GPU storage remained zero. The warm FL2VA HIT completed with about 21.3 MiB higher RSS than the adjacent MISS, consistent with the intentionally retained four-entry CPU conditioning cache and bounded by the 16-entry LRU.
- Focused CPU/static validation is `25 passed`; canonical full pytest is `467 passed`. Syntax, source/runtime verifier, source/runtime SHA-256 equality for the five changed Production files, and `git diff --check` pass. Accepted evidence is under `D:\Codex\_test_results\ComfyUI-H3-Continuum\stabilization-phase3-1-20260825`.

## V3.5.1 stabilization Phase 2-2 Conditioning attribution (2026-08-25)

- Extended the existing V3.5 Detailed Report timing only; no node, socket, UI, Sampling, Conditioning payload, Terminal Merge, Assembly, Seam, or Run Storage contract changed. Basic/Off reports and every V3.4 path remain unchanged.
- Conditioning is now split into First/Last image VAE, Reference Image VAE, Reference Audio VAE, Driving Audio VAE, Video Reference VAE, Timeline Video VAE, and Prompt/CLIP. Unconnected paths report `n/a`, and counts distinguish an absent path from a measured near-zero path. Timing remains `time.perf_counter()` only with no CUDA synchronization or allocator mutation.
- CPU/static validation is `29 passed` focused and `453 passed` full. The first full run was blocked only by the existing Windows ACL on pytest's default temp root; the clean rerun with an explicit writable `--basetemp` passed. The remaining warnings are the known `pynvml` deprecation and inaccessible repository `.pytest_cache` cache-write warning.
- Accepted GPU/API 1x5 T2VA at 576x576 took 158.701s API / 135.970s Sampler host wall. Conditioning was 6.004392s, of which Prompt/CLIP was 6.004374s; identity video VAE was 0.000006s. A preceding warm-up independently measured 6.283131s Conditioning / 6.283109s Prompt/CLIP. A cached 3.398s replay is explicitly excluded.
- Accepted 3x5 FL2VA Long Terminal Merge at 640x640 took 410.727s API / 346.197s Sampler host wall and preserved 3 logical / 2 physical groups (`[1]`, `[2,3]`), 360 frames, 15.000s, and Exact Duration `362 -> 360`. Conditioning was 23.644903s: Prompt/CLIP 22.873708s (96.7%) and First/Last image VAE 0.771176s (3.3%). Sampling remained dominant at 322.335226s.
- No optimization is adopted. The measured Continuum bookkeeping remains negligible, and Prompt/CLIP time is required Core model encoding across the distinct physical prompts, including the Terminal Merge prompt. Reference-specific paths are instrumented but were not connected in these accepted runs, so their GPU cost remains unmeasured rather than assumed.
- Accepted evidence is under `D:\Codex\_test_results\ComfyUI-H3-Continuum\stabilization-phase2-2-20260825`.

## V3.5.1 stabilization Phase 2-1 performance attribution (2026-08-25)

- Added measurement-only host timing to the existing V3.5 Detailed Report path. V3.4, Basic/Off reports, node schemas, UI, Sampling inputs/outputs, Terminal Merge, Assembly, Seam, and Run Storage contracts are unchanged.
- The report records total Preparation with Conditioning as an identified subset; each physical group's preparation, Sampling, CPU commit/finite validation, and Refine Context capture; plus Finalization and total host wall time. Terminal Merge is reported in physical order, so a 3-logical FL2VA run remains two measured groups: `[1]` and `[2,3]`.
- Timing uses `time.perf_counter()` only. It does not call `torch.cuda.synchronize()`, reset allocator peaks, clear caches, or change the normal asynchronous execution contract. Sampling values are host-observed elapsed time, not CUDA-event kernel timing.
- Core Video/Audio VAE Decode remains external and is not attributed to the Sampler. V3.5 Assembly continues to report its existing workflow elapsed time separately.
- CPU/static validation is `27 passed` focused and `451 passed` full with only the known `pynvml` FutureWarning. Runtime verification and source/runtime hashes pass.
- GPU/API measurement is PASS on the RTX 5060 Ti 16 GB system. Warm 1x5 T2VA at 576x576 took 143.888s API wall time; Sampler host wall was 134.736s, including 128.737s Sampling (95.5%), 5.963s Conditioning (4.4%), 0.013s CPU commit/finite validation, and 0.001s Refine Context capture. Output is 576x576, 120 frames, 5.000s, 32 kHz.
- The 3x5 FL2VA Long Terminal Merge run took 396.477s API wall time and retained 3 logical / 2 physical groups (`[1]`, `[2,3]`). Sampler host wall was 348.047s: 323.835s Sampling (93.0%), 24.003s Conditioning (6.9%), 0.050s CPU commit/finite validation, and 0.010s Refine Context capture. Output is 640x640, 360 frames, 15.000s, 32 kHz.
- The 1x5 Hi-Res Fix 1.2x run took 330.005s and produced 704x704, 120 frames, 5.000s, 32 kHz. Against the warm non-Hi-Res baseline, the integrated Resize/Second Pass/Decode path added about 186.1s, 0.49 GiB peak Working Set, and 1.34 GiB peak Private Bytes. Global observed VRAM usage was about 15.4-15.6 GiB in all three runs and is not a per-node allocator measurement.
- No optimization has been selected or implemented. Sampling dominates and the measured CPU commit, finite validation, Refine Context, and group preparation paths are rejected as optimization targets. Conditioning exceeds the 1% investigation threshold but must be split into CLIP/VAE/reference subphases before any change is justified.
- Accepted evidence is under `D:\Codex\_test_results\ComfyUI-H3-Continuum\stabilization-phase2-20260825`. The first 1x5 attempt reached an older already-running ComfyUI process and is retained only as excluded diagnostic evidence; all accepted runs used the restarted updated listener.

## V3.5.1 stabilization Phase 0 CI portability candidate (2026-08-25)

- V3.5.1 is feature-frozen for stabilization. Speculative performance changes and broad refactors are excluded; only measured bottlenecks may proceed after the remaining acceptance work closes.
- The P2-5 process-memory regression is platform-aware without changing the probe or any Production path: RSS is required everywhere, USS is checked when the platform exposes it, and Windows private commit is tested only on Windows.
- Local focused validation is `4 passed`; full Windows validation is `453 passed` with only the known `pynvml` FutureWarning. Syntax and `git diff --check` pass. Remote GitHub Actions remains to be confirmed before publication or updating the public validation count.

## V3.5.1 Issue #9 Conditioning Bridge candidate (2026-08-24)

- Added `H3ContinuumConditioningBridgeV35` / `H3 Continuum Conditioning Bridge V3.5` under `MiniMax H3/Continuum/Advanced`.
- The Bridge accepts externally processed physical-group video LATENTs plus the matching Assembly Plan and required V3.5 refine context. It returns one paired MODEL and one complete ComfyUI CONDITIONING object per physical group, plus a target-geometry Assembly Plan and status.
- The fixed list contract is `OUTPUT_IS_LIST = (True, True, False, False)` and `len(group_models) == len(conditioning) == physical group count`. CONDITIONING entries are appended as one inner object and are never flattened into the outer physical-group list.
- Second Pass and Bridge share the same context validation, target adaptation, prompt fallback, MODEL clone, and geometry update helper. Built-in Second Pass still samples groups sequentially and retains responsibility for Nested AV, video noise, Audio Lock, and audio passthrough; the Bridge deliberately leaves AV LATENT construction, noise, Audio Lock, and external sampling to the workflow.
- CPU coverage includes the 3-logical / 2-physical Terminal Merge shape (`[1] / 37T`, `[2,3] / 77T`), MODEL/CONDITIONING alignment, non-flattening, schema/registration, and existing Reference Image/Audio/context adaptation regressions. Focused validation is `33 passed`; full source pytest is `442 passed` with only the known `pynvml` FutureWarning.
- Only `nodes.py`, `v3/second_pass.py`, `v3/conditioning_bridge_nodes.py`, and `tools/verify_runtime.py` were synchronized to ComfyUI_W; every source/runtime SHA-256 matches. Runtime registration, native PackedLayout, and Fixed 3x5 prompt planning pass with the new Bridge registered as a non-legacy node.
- GPU acceptance through Basic Guider and an external sampler passed for three `1 x 5s` runs: LBH `1.2x` with `simple / 4 steps / denoise 0.3` produced 704x704 twice, and LBH `1.5x` with `simple / 10 steps / denoise 0.3` produced 864x864. Every run kept one MODEL and one complete CONDITIONING for one physical group, completed external sampling/Core decode/Assembly, and produced finite 120-frame/5.000-second video with 32 kHz stereo audio. The existing Issue #10 Reference Audio working-tree changes were preserved without reset or reorganization.

## V3.5.1 Issue #10 Reference Audio candidate (2026-08-24)

- Target version is V3.5.1. The optional `reference_audio_1` and `reference_audio_vae` sockets remain permanently present in their Python-defined input order and are displayed as `Reference Audio (Optional)` and `Reference Audio VAE (Optional)`.
- The earlier frontend-only `Reference Audio Inputs` dropdown and all dynamic socket add/remove behavior were removed by the compatibility hotfix. Workflow serialization now contains only the Python-defined widgets, preserving positional widget-value alignment across save/reload.
- Related display labels are now `Video Guide Frames`, `Driving Audio`, and `Driving Audio VAE`. Input keys, order, types, Node IDs, and runtime contracts remain unchanged.
- This exposes the existing Core-compatible standalone Reference Audio 1 path; it adds no new audio encoding, strength control, model allowlist, source-audio copy, or lip-sync guarantee.
- V3.4 input keys/order/types, Node ID, sockets, and behavior remain unchanged; only the human-facing labels/tooltips are clarified. Its internal `run()` accepts the two values only so V3.5 can forward them to the existing Production path.
- Reference Audio conditions generated video/audio and leaves generated audio as final. Driving Audio remains the separate timeline-guide path whose original source is selected as final output.
- CPU integration confirms Reference Audio survives every normal physical group and the FL2VA Terminal Merge group (`logical [2,3]`, `paired_timeline_v1`) in `refine_context`. Run Storage ignores an unused Reference Audio VAE, separates changed audio contracts, and restores the disconnected revision identity.
- Final canonical validation after the conditional UI change is `450 passed` with only the known `pynvml` FutureWarning. JavaScript syntax, `git diff --check`, ComfyUI_W registration/native PackedLayout/Fixed 3x5 verification, and source/runtime SHA-256 equality for synchronized implementation files pass.
- The earlier conditional-visibility UI acceptance is superseded: a saved/reloaded workflow exposed positional widget corruption under the current frontend. The permanent-socket hotfix removes that frontend mutation path without changing Reference Audio execution.
- The CPU-validated public feature files were previously published from the isolated clone as `a704aa961fc2ba0c19aef6f2ecfdcb46fa9384b2`. GPU acceptance is now complete and package metadata plus public documentation are being formalized as V3.5.1.
- The pre-hotfix V3.5.1 release baseline was `450 passed`. Hotfix validation is `452 passed` with explicit workflow save/reload widget-alignment coverage and only the known `pynvml` FutureWarning. JavaScript syntax and `git diff --check` pass. The two frontend files are synchronized to ComfyUI_W by SHA-256; live save/reload acceptance remains pending.
- The public LBH/Conditioning Bridge connection example is `examples/workflows/MiniMax_H3_Continuum_V351_LBH_Conditioning_Bridge.json`; its README chart is `docs/images/v351-lbh-conditioning-bridge-flow.svg`. It is a separate example and does not replace or modify the recommended V3.5 template.

## V3.5.1 standard ComfyUI Seed behavior (2026-08-25)

- The experimental Last Queued Seed frontend override was withdrawn after repeated real-browser failures. Static callback and simulated-event tests did not reproduce the active ComfyUI Frontend lifecycle reliably.
- `H3 Continuum Sampler V3.5` now uses the same native `control after generate` behavior as ComfyUI Core. Continuum does not wrap seed callbacks, intercept Randomize/Fixed transitions, monitor widgets, or rewrite submitted seed values.
- This removal is limited to the Last Queued Seed experiment. V3.4/V3.5 node schemas, Reference Audio UI, compact UI settings, Sampling, Second Pass, Terminal Merge, Assembly, Seam, Run Storage, and all other frontend behavior remain unchanged.
- Focused unaffected-UI validation is `8 passed`; full source pytest is `450 passed` with only the known `pynvml` FutureWarning.

## V3.5.1 Hi-Res Fix Core canvas alignment (2026-08-24)

- A real `576x576`, `scale_by=1.2` run exposed an invalid `43x43` H3 video/conditioning latent. Core MiniMax H3 patchifies spatial latents in `2x2` blocks and exposes pixel dimensions in 32-pixel steps, so the odd latent failed in Core with `24 * 43 * 43 = 44376` elements.
- Manual Hi-Res Fix targets now use ComfyUI Core's `CANVAS_MULTIPLE` and preserve-or-enlarge each axis on that grid. The failing case resolves to `704x704` / `44x44`; a `1024x576` source at `1.2x` resolves to `1216x704` / `76x44`. The Pixel/VAE, conditioning adaptation, and Second Pass paths remain unchanged.
- Focused Hi-Res/Second Pass validation is `48 passed`; full source pytest is `448 passed`. `v3/hires_fix_nodes.py` is synchronized to ComfyUI_W by SHA-256, and runtime registration/native PackedLayout/Fixed 3x5 verification passes. GPU acceptance after a ComfyUI process restart remains pending.

## V3.5 recommended template workflow (2026-08-24)

- `examples/workflows/MiniMax_H3_Continuum_V35.json` is the recommended V3.5 starting workflow.
- Hi-Res Fix is disabled by default and `H3 Continuum Assemble + Seam V3.5` uses Auto backend selection.
- First Frame, Last Frame, and Reference Images 1-3 share one 0.3 MP control. Video Guide Frames remains independently sized.
- Reference Images 1-3 and Video Guide Frames are routed to their matching V3.5 sampler sockets; `refine_context` and `video_vae` are connected to the integrated Hi-Res Fix path.
- V3.4 standard and Turbo templates remain available for saved-workflow compatibility.

## Baseline

- Published baseline: V3.5.3 maintenance hotfix (`67a0d80117bd8332d2768d093dff343001c87d60`)
- Authoritative working repository: `D:\Codex\_git_push_work\ComfyUI-H3-Continuum`
- Primary tested runtime: `D:\StabilityMatrix\Data\Packages\ComfyUI_W\custom_nodes\ComfyUI-H3-Continuum`
- Secondary runtime: `D:\StabilityMatrix\Data\Packages\ComfyUI_WAN\custom_nodes\ComfyUI-H3-Continuum`
- Old checkout to keep synchronized with published `main`: `D:\Codex\ComfyUI-H3-Continuum`

## Active direction

- Driving Audio preserves the supplied audio as final output while conditioning every chunk.
- Video Guide Frames is persistent across chunks and supports selectable guide sizing.
- Prompt syntax is permissive: invalid or empty input warns and falls back instead of blocking generation.
- Unknown models, wrappers, merged models, and upstream nodes are not rejected merely because they are unknown.
- Legacy `strict_compatibility` remains loadable only for workflow compatibility and must not enforce a stop.
- Keep the compact V3.4 interface and preserve all public sockets and node identifiers unless a UI/API change is explicitly approved.

## Current working tree

The authoritative repository may contain active, uncommitted Hybrid reference work. Preserve it. Never reset, overwrite, or publish it without explicit instruction.

## Standard procedure

1. Read `AGENTS.md` and this file.
2. Inspect `git status -sb` and confirm the authoritative source/runtime.
3. Run `tools\snapshot.ps1` before edits.
4. Make the smallest relevant change.
5. Run `tools\validate.ps1` only when validation is requested or publication is authorized.
6. Append the result and remaining gaps to `WORKLOG.md`.
7. Commit or push only when explicitly requested.

## Validation boundary

Static checks do not replace a real GPU generation. Record workflow, prompt, media, model/LoRA, sampler, steps, dimensions, chunks, elapsed time, and observed result for GPU tests.

## Active FLF implementation

- Hybrid FLF Chunk Contract v1 is implemented locally in `v2/sequence.py`.
- It replaces the previous single global sample/split strategy with a 0.4 MP full-sequence guide, intermediate boundary anchors, and separately sampled FL2VA chunks.
- Reference Images remain persistent in the guide and every output chunk.
- Real GPU generation is still required before this path can be considered stable.

## FLF GPU regression baseline (2026-08-21)

- PASS `MiniMax_H3_Continuum_V31_00029_.mp4`: pure FLF skateboard sequence; visual continuity accepted.
- PASS `MiniMax_H3_Continuum_V31_00031_.mp4`: Hybrid model plus Reference Image; visual result accepted.
- PASS `MiniMax_H3_Continuum_V31_00032_.mp4`: standard Ref2VA model; visual result accepted.
- FAIL `MiniMax_H3_Continuum_V31_00034_.mp4`: Hybrid FLF+Reference; visible jumps near 5 s and 9 s.
- FAIL `MiniMax_H3_Continuum_V31_00035_.mp4`: Ref2VA model plus FL2V Turbo 8-step LoRA; two visible flashes/jumps.
- Current FLF candidate is `context_bound_terminal_last_only_v2`: the final chunk keeps its 22-frame continuation context and the single Last Frame anchor retained by `prepare_conditioning()`, without adding a duplicate context-tail boundary keyframe.
- GPU verification of this candidate is pending; it is not yet a stable baseline.
- `context_bound_terminal_bridge_v2` is withdrawn because its synthetic intermediate latent correlated with the later terminal flash regression.
- Preserve Hybrid/Reference support, Run Storage identity, UI, audio paths, and permissive prompt handling when repairing FLF.

## FLF GPU regression update: 00036 (2026-08-21)

- FAIL `MiniMax_H3_Continuum_V31_00036_.mp4`.
- Workflow: Hybrid B20-49, FL2V Turbo 8-step LoRA, 8 steps, Euler/simple, Spectrum Off, 2 x 5 s, 640x640, Video Reference Efficient 0.4 MP, randomized seed.
- The 5 s chunk boundary was visually stable, but a bright ghost/flash and discontinuous disappearance of the reference fox occurred near 8 s.
- Project acceptance requires whole-sequence continuity; a clean chunk seam alone is insufficient. This run is not a partial pass.
- Restoring `context_bound_terminal_v1` did not resolve the terminal Hybrid FLF+Reference discontinuity and is not accepted as the final repair.

## FLF GPU regression update: 00037 (2026-08-21)

- FAIL `MiniMax_H3_Continuum_V31_00037_.mp4`.
- Workflow: official FL2VA pruned INT8 ConvRot model, FL2V Turbo 8-step LoRA, 8 steps, Euler/simple, Spectrum Off, 2 x 5 s, 640x640, one reference image, Video Reference Efficient 0.4 MP, randomized seed.
- The 5 s chunk boundary remained visually stable, but the reference fox became translucent and disappeared with a bright ghost/flash near 7.5-8 s before the Last Frame composition.
- This reproduces the terminal discontinuity seen in 00036 and is a whole-sequence failure.
- Do not roll back merely to terminal bridge v2: 00034 and 00035 already failed there. Restore only an exact baseline associated with the accepted 00029/00031 behavior.

## FLF GPU regression update: 00038 and rollback (2026-08-21)

- FAIL `MiniMax_H3_Continuum_V31_00038_.mp4` by user visual evaluation.
- Embedded workflow: Ref2VA pruned INT8 ConvRot model, FL2V Turbo 8-step LoRA, Euler/simple, 8 steps, Spectrum Off, 2 x 5 s, randomized seed, Video Reference Efficient 0.4 MP.
- The initial rollback after 00038 temporarily returned to bridge v2, but the user clarified that the required target is the exact code state used for PASS 00031.
- `00031` completed at 2026-08-21 02:32:59; `pre-flf-terminal-bridge-v2-repo-20260821_023553` was captured immediately afterward and before bridge v2 was introduced.
- Current FLF strategy is restored exactly from that snapshot: `context_bound_terminal_v1`. Bridge v2 is withdrawn and is not active.

## M1 Hybrid diagnostics (2026-08-21)

- Canonical implementation source: ComfyUI_W runtime.
- Runtime pre-change snapshot: D:\Codex\_snapshots\ComfyUI-H3-Continuum\pre-m1-comfyui-w-canonical-20260821_172324.
- Added display-only Hybrid conditioning labels; the stored/runtime conditioning mode remains unchanged.
- Hybrid reference warnings now use the actual global Qwen <Picture N> numbering.
- Added README numbering guidance and focused CPU-only regression tests.
- No Sampling, Conditioning payload, Run Storage contract, UI socket, or model-selection behavior changed.
- Tests were added but not executed in this implementation step.

## Terminal Merge Physical Seed v2 (2026-08-22 00:49:57)
- Terminal Merge uses one physical seed per merged pair; an initial 2x5s pair uses base_seed directly when reroll is inactive.
- Later terminal pairs derive once from the zero-based pair-start index; both logical entries store that same physical seed.
- Run Storage distinguishes the scoped terminal_merged_10s_seed_v2 / physical_window_seed_v2 execution semantics without changing the global schema version.


## Terminal Merge diagnostic harness (2026-08-22)

- Production generation semantics remain unchanged; diagnostics live under tests only.
- Diagnostic stages are ordered A Pre-Sampler, B First MODEL Call, C sampled physical AV, D split/recombine, E decode/assembly.
- Tensor identity uses shape, dtype, and SHA-256 of contiguous CPU raw bytes; numerical mismatch also records max/mean absolute difference and allclose.
- Terminal split/recombine requires bit-exact equality.
- Real Core vs Continuum GPU capture remains pending; this unit-test phase does not load checkpoints.

## GPU Core/Continuum diagnostic runner (2026-08-22)
- Source: `tools/gpu_diagnostic_node/`
- Installer: `tools/install_gpu_diagnostic_node.ps1`
- Runtime: `D:\StabilityMatrix\Data\Packages\ComfyUI_W\custom_nodes\H3_Continuum_GPU_Diagnostics`
- Node: `H3 Core vs Continuum GPU Diagnostic`
- Production Continuum files and generation semantics are not modified by this diagnostic plugin.
- Captures A: pre-sampler, B: first MODEL call, C: physical sampled AV latent, D: terminal split/recombine, E1: decode comparison, E2: common 243-to-240 adjustment.
- Artifacts: JSON manifest plus safetensors under the configured ComfyUI output diagnostics directory.
- Pre-change snapshot: `D:\Codex\_snapshots\ComfyUI-H3-Continuum\pre-gpu-core-continuum-diagnostic-runner-20260822_022625` (138/138 files verified).
- GPU comparison has not yet been executed.

## Long Terminal Merge for distinct timeline sections (2026-08-22)

- For FL2VA with 3 or more 5-second logical chunks, the final two chunks may now share one physical Terminal Merge sample even when their prompt sections differ.
- Distinct final prompts are rebased to a local physical timeline (`[0-5s]` and `[5-10s]`); identical prompts retain the accepted 2x5 Core-equivalent prompt path unchanged.
- Expected 3x5 execution: 3 logical chunks, 2 physical sampling passes, and 2 physical VAE decode groups; the terminal group is 260 frames with a 22-frame decoded prefix trim and 238 retained frames.
- Timeline Video remains excluded from Terminal Merge. UI, public sockets, Conditioning payload construction, Physical Seed v2, Assembly, and Seam semantics are otherwise unchanged.
- GPU acceptance passed for `MiniMax_H3_Continuum_V31_00008_.mp4`: 3 logical chunks, 2 physical sampling passes, decoded groups of 124 and 238 retained frames, 362-to-360 exact-duration adjustment, and 15.000-second output.
- Core comparison `MiniMax_H3_00005_.mp4` showed the same short terminal still period. This is accepted as normal FL2VA Last Frame convergence, not a Continuum-specific defect.
- Long Terminal Merge is formally adopted. Do not retune Conditioning, Physical Seed v2, physical decode grouping, or terminal prompt pairing without new contrary regression evidence.

## V3.5 Hi-res Fix and Second Pass (2026-08-23)

- The original V3.5 Main candidate was first-pass physical video latents -> lightweight Core spatial resize -> low-sigma Second Pass -> Core Decode -> Assemble + Seam. The 2026-08-24 GPU isolation below rejects plain latent interpolation as the general Main backend; the Advanced Second Pass bridge remains valid.
- E2-8A and E2-8B1 established additive `assembly_plan.second_pass_contract` metadata and static physical-group validation without changing V3.4 generation semantics.
- E2-8B2 GPU PoC is accepted: LBH 3D Upscaler preserved H3 24-channel physical groups, including the 3x5 FL2VA 124f + 260f Terminal Merge layout.
- E2-8C adds an experimental T2VA-only physical-group Second Pass node. It reads prompts from the plan, uses workflow-supplied SIGMAS, derives one refine seed per physical group, adopts refined video, and returns first-pass audio LATENT objects unchanged.
- `H3ContinuumLatentResizeV35` is the standalone lightweight Utility. It delegates to ComfyUI Core `common_upscale`, exposes the same nearest-exact/bilinear/area/bicubic/bislerp methods and a scale multiplier, preserves physical-group order and B/C/T, and changes only latent H/W. It is not an accepted general-purpose Main Hi-res backend.
- The final V3.5 node layout keeps three distinct roles: `H3ContinuumHiResFixV35` is the normal one-node Main path, `H3ContinuumSecondPassV35` is the Advanced entry for LBH or other externally processed latents, and `H3ContinuumLatentResizeV35` remains a standalone Utility.
- Hi-Res Fix ON performs an H3 Video VAE Decode -> CPU pixel resize -> same H3 Video VAE Encode for each physical group, then calls the existing context-aware physical-group Second Pass helper. Hi-Res Fix OFF returns the exact first-pass video/audio LATENT lists and original Assembly Plan object; all sampling and VAE inputs remain lazy and are not requested by the node.
- Second Pass itself has no enable switch and no duplicate first-pass input. Its public display name is `H3 Continuum Second Pass V3.5`; the Utility display name is `H3 Continuum Latent Resize V3.5`.
- E2-8C GPU acceptance is formally PASS for 1x5 T2VA, 3x5 T2VA, and 3x5 FL2VA Long Terminal Merge.
- The accepted FL2VA run preserved two physical groups as `37T + 77T`: group 1 mapped logical `[1]`, and group 2 mapped logical `[2,3]` with `paired_timeline_v1`. Each physical group was sampled exactly once by Second Pass.
- Final output was 768x768, 360 frames at 24 fps, and 15.000 seconds. First-pass audio LATENT passthrough, Core Video/Audio Decode, and Assemble succeeded; the 5-second and 10-second boundaries had no major discontinuity.
- The final approximately 0.5-second low-motion interval is accepted as natural Last Frame convergence, not temporal collapse.
- V3.4 Sampling, Terminal Merge, Assembly, Seam, and Run Storage were not changed by E2-8C.
- First/Last, Reference, Hybrid, Run Storage, and embedded LBH integration remain outside E2-8C.
- The current V3.5 working tree uses a Second Pass-only direct-sampling contract: video receives seed-derived random noise with mask 1, while first-pass audio receives zero noise with mask 0. Core applies workflow SIGMAS once; no external AddNoise, inverse noise scaling, or `audio / (1-sigma0)` compensation is used.
- This path is isolated in `v3/refine_sampling.py`; V3.4 `v2/sampling.py::sample_chunk()` remains unchanged. The Assembly Plan records execution as `t2va_physical_groups_audio_locked_v2` and audio sampling as `zero_noise_mask_locked`.
- CPU validation is `277 passed`. Core `reshape_mask` also expands the minimal video `[B,1,1,1,1]` and audio `[B,1,1,1]` masks correctly for real H3 stream shapes.
- The audio-locked v2 path is now GPU-confirmed for direct no-resize Second Pass: `V35_NoResize_SecondPass_Diagnostic_00001_.mp4` used the cached 576x576 first-pass latent, `res_multistep`, `simple` 10 steps / denoise 0.35, and refine seed 42. Its report confirmed video random noise/mask 1, audio zero noise/mask 0, one 37T physical group, and one sampling pass.
- The direct no-resize result is visually clean across the full 120-frame / 5.000-second output. The cyan/orange/white line and plate artifacts remain in the otherwise matched one-node Hi-Res Fix run `E2-8B2_01_1x5_T2VA_LBH3D_00017_.mp4`, which used bilinear 2x from 576x576 to 1152x1152.
- The fixed-condition GPU isolation therefore rejects random audio re-noise as the primary artifact cause and validates the basic direct Second Pass re-noise path. The remaining cause is scoped to the 2x spatial-resize/high-resolution re-entry path; this result alone does not yet distinguish interpolation method from scale/resolution.
- ComfyUI_W registration, native PackedLayout, and Fixed 3x5 prompt-plan verification passed before this isolation. The one-node Hi-Res Fix wrapper executes successfully on GPU, but its bilinear 2x path is visually rejected and is not an accepted standard Hi-res Fix path.
- Resolution/method isolation used the same cached first-pass latent, `res_multistep`, `simple` 10 steps / denoise 0.35, and refine seed 42 throughout. Both nearest-exact and bilinear were clean at 576x576 -> 768x768 (`36x36 -> 48x48` latent), while bilinear failed at 1024x1024 (`64x64`) and both bilinear and nearest-exact failed at 1152x1152 (`72x72`).
- This rejects bilinear-specific channel mixing as the primary cause within the direct interpolated-latent path. The tested safe square target for that legacy path is 768x768; its exact failure threshold between 768 and 1024 was not mapped. ComfyUI Core's H3 implementation independently defines `BASE_SHORT_EDGE = 768` and `MAX_PIXELS = 768 * 1344`, consistent with the observed direct-re-entry boundary. These limits do not describe the later Pixel/VAE roundtrip result.
- The current `H3ContinuumHiResFixV35` defaults to pixel Lanczos and `scale_by=2.0`; zero retains the H3 native-canvas Auto option and positive values retain manual multiplier semantics. Enabled execution requires the lazy `video_vae` input and never falls back to direct latent interpolation. Disabled execution does not evaluate the VAE or sampling inputs.
- Manual mode is not clamped or stopped when it exceeds the Core native canvas; the status reports the target as informational and execution continues through the Pixel/VAE backend. No V3.4 constraint or independent target policy was added.
- `V35_NativeAuto_576to768_Acceptance_00001_.mp4` remains historical evidence for the former direct interpolated-latent backend only. Main Hi-Res Fix no longer uses that backend; the explicit `H3ContinuumLatentResizeV35` Utility remains available separately.
- The earlier recommendation to move all 2x delivery to a post-decode video upscaler is superseded for Main Hi-res Fix by the validated Pixel/VAE roundtrip in the next section. Issue #8's external-latent Second Pass bridge remains valid independently.

## V3.5 context-aware Hi-res isolation (2026-08-24)

- Added `H3ContinuumSamplerV35` without changing the V3.4 public contract. Its first five outputs are byte-for-byte ordered like V3.4 (`video_latents`, `audio_latents`, `assembly_plan`, `status`, `driving_audio`); output six is runtime-only `H3_CONTINUUM_REFINE_CONTEXT`.
- The context captures the exact pre-sampling conditioning once per physical group, including Terminal Merge logical mapping, physical clip index, context frames, prepared First/Last images, and source H3 latent geometry. It is never stored in Assembly Plan, Session, logical entries, or Run Storage.
- A complete context is adapted to target H/W by re-encoding First/Last keyframes with the connected Video VAE and resizing only marked Continuum video-context latents. Ordinary MiniMax references, text conditioning, and all audio conditioning remain unchanged. Incomplete Run Storage capture falls back to the legacy prompt-only path with a warning; a corrupt typed context is a contract error.
- Second Pass now creates one call-local Continuum MODEL clone per physical group. The audio-lock contract remains video random noise/mask 1, audio zero noise/mask 0, one workflow SIGMAS application, one refine seed and one sampling call per physical group, and bit-exact first-pass audio LATENT passthrough.
- CPU/static validation after integration is `293 passed` with only the known `pynvml` FutureWarning. Runtime registration exposes `H3 Continuum Sampler V3.5` with six outputs. V3.4 Sampling, Terminal Merge, Assembly, Seam, Run Storage, and its five-output UI contract remain unchanged.
- GPU A/B `0adff3b7-1552-47e9-a167-7b6e4010b0a5` used the fixed FL2VA 1x5 condition, 576x576 -> 864x864 bilinear 1.5x, `res_multistep`, `simple` 10 steps / denoise 0.35, and refine seed 42. The report confirmed `conditioning_source=refine_context`, two keyframes re-encoded at target H/W, shape `(1, 24, 37, 54, 54)`, and first-pass audio passthrough. Output `V35_ContextAware_FL2VA_576to864_d035_00001_.mp4` still contains the persistent cyan/orange/white line and plate artifacts. Context mismatch is therefore not the primary cause.
- Resize-only GPU isolation `75249bbe-306a-45f9-a139-a79c0b17e536` decoded a plain bilinear 576x576 -> 864x864 latent as `V35_ResizeOnly_FL2VA_576to864_bilinear_00001_.mp4`. It removed the colored lines but produced severe person/background ghosting, confirming that channel-wise interpolation creates an invalid H3 video-latent representation even before refinement.
- Pixel/VAE roundtrip GPU isolation `2a03a1d4-2355-4d5a-a237-0ec3e0c09761` used First Pass Decode -> pixel Lanczos 864x864 -> H3 Video VAE Encode -> the same context-aware denoise 0.35 Second Pass. `V35_PixelRoundtrip_FL2VA_576to864_d035_00001_.mp4` completed at 864x864, 120 frames, 24 fps, 5.000 seconds with no colored-line artifacts or resize ghosting while retaining the orange jacket, subject identity, motion, and terminal composition.
- Pixel/VAE roundtrip 2x GPU acceptance `de11e383-8b3d-4d8a-806f-1ac3550091f1` used the same cached First Pass, pixel Lanczos 1152x1152, H3 Video VAE Encode, context-aware `res_multistep` / `simple` 10-step denoise 0.35 Second Pass, and refine seed 42. It completed without OOM on the 16 GiB GPU as `(1, 24, 37, 72, 72)`, one physical group / one sampling pass, two target keyframes VAE re-encoded, first-pass audio passthrough, Core Decode/Audio Decode, and Assemble. `V35_PixelRoundtrip_FL2VA_576to1152_d035_00001_.mp4` is 1152x1152, 120 frames, 24 fps, and 5.000 seconds; twelve representative time points are visually clean with no colored lines/plates, resize ghosting, or temporal collapse, while subject identity, orange clothing, motion, and composition remain coherent.
- The evidence-backed Main backend is implemented as a sequential Pixel/VAE roundtrip per physical group followed by the existing context-aware Second Pass. Pixel resize uses bounded 8-frame CPU batches; VAE Encode matches Core's 4D IMAGE contract by encoding each Continuum batch as `[F,H,W,C]` and then restoring B. Plain interpolated latent is never used as a Main fallback. `H3ContinuumSecondPassV35` remains the Advanced external-LBH/learned-upscaler bridge, and `H3ContinuumLatentResizeV35` remains an explicit Utility.
- CPU/static validation after the Main backend implementation is `308 passed`; ComfyUI_W runtime registration, native PackedLayout, Fixed 3x5 prompt-plan verification, `py_compile`, and `git diff --check` pass. The only test-environment messages are the known pytest cache permission warning and `pynvml` FutureWarning.
- Integrated Main GPU acceptance prompt `c5dbe55c-c846-47e8-9f49-8bb167887236` used FL2VA 1x5, 576x576 -> 1152x1152, pixel Lanczos, context-aware `res_multistep` / `simple` 10-step denoise 0.35 Second Pass, and refine seed input 42. It completed in 14:18 as one physical group / one sampling pass with `(1, 24, 37, 72, 72)`, two target keyframes re-encoded, and first-pass audio LATENT passthrough.
- `V35_MainSafePixelVAE_Core4D_FL2VA_576to1152_d035_00001_.mp4` is 1152x1152, 120 frames, 24 fps, and 5.000 seconds with 32 kHz stereo audio. Its decoded 120 video-frame hashes and all decoded audio-frame hashes are exactly identical to the accepted external four-node Pixel/VAE baseline. The prior colored line/plate and resize-ghosting artifacts are absent. Both baselines enter the same FL2VA Last Frame still interval at 3.666667 seconds; this is not an integrated-node regression.
- This acceptance is limited to the 1x5 FL2VA 2x case. Peak observed host use was approximately 47.7 GiB working set / 61.3 GiB private bytes with about 7.3 GiB system RAM still available; 3x5 Terminal Merge 2x remains a separate GPU/resource acceptance. V3.4 Sampling, Conditioning, Terminal Merge, Assembly, Seam, Run Storage, Advanced Second Pass, and the Latent Resize Utility were not changed by this Main backend implementation.

## Phase 2A P2-0 file-backed Tensor backend PoC (2026-08-24)

- P2-0 is accepted as a source-only Windows backend/lifetime PoC. It is not imported or registered by the Production node package, and neither ComfyUI_W nor ComfyUI_WAN runtime files were changed.
- The selected candidate is `torch.from_file(shared=True)`: it returns a contiguous CPU Tensor backed by a dedicated file while preserving the normal `IMAGE` Tensor contract.
- Backing files use strict allocation IDs plus JSON ownership sidecars. Cleanup is serialized per root across threads/processes, fails closed for invalid ownership metadata, retains live/cache-referenced storage, retries sharing violations, and removes dead-process stale files or eligible orphans.
- Storage lifetime is alias-aware through PyTorch `StorageWeakRef`. Future Production integration must use the process-global `get_process_lifetime_manager()`; a node-local manager is not an accepted integration contract.
- GC finalizers only enqueue cleanup intent. Filesystem I/O uses a consistent root-lock-before-manager-lock order, so cleanup/collect/finalizer interleavings cannot form the reproduced ABBA deadlock. Cancellation cleanup also protects a numeric file descriptor that has already been closed and reused by unrelated code.
- Primary validation: 26 focused tests and the standalone probe pass under ComfyUI_W Python/PyTorch; full repository validation is 334 passed. Secondary validation passes the same 26 tests and probe under ComfyUI_WAN Python 3.12.12 / PyTorch 2.13.0+cu130. Both probes are bit-exact, defer cleanup while an alias is alive, reclaim after the final alias is released, and leave zero managed backing files.
- This P2-0 acceptance does not claim end-to-end low-memory assembly. Real ComfyUI cache/requeue, Preview/VHS/Save consumption, RAM-vs-Disk assembler equivalence, and 9-15 GiB sequential-write/RSS behavior remain explicit later gates (P2-4/P2-5). Invalid sidecar quarantine/manual recovery is also not yet a public policy.
- P2-0 is now consumed by the independent V3.5 Production path described below. V3.4 remains fixed.

## Phase 2A P2-1 through P2-3 CPU acceptance (2026-08-24)

- P2-1 Memory Attribution is complete. V3.5 sequence reports capture chronological start, before CPU commit, after CPU commit, and completion snapshots; deduplicated retained AV/refine-context CPU/GPU bytes; projected natural/exact IMAGE bytes; process RSS/system availability; and read-only CUDA allocation/reservation counters. Collection is fail-soft and does not synchronize CUDA, reset peaks, clear caches, or alter V3.4 default behavior.
- P2-2 added `v3/file_backed_buffer.py`, backed by the accepted P2-0 `torch.from_file(shared=True)` lifetime contract. P2-6 now exposes `Auto` plus the original manual `RAM` and `Disk-backed` choices; there is still no silent Disk-to-RAM fallback. The first manager access performs root-scoped stale cleanup while live mappings remain protected by the ownership/lock contract.
- P2-3 adds the independent `v3/assembly_v35.py` and `v3/video_seam_v35.py` path used by `H3ContinuumAssembleSeamV35`. Video alone may be file-backed; Audio remains in RAM and preserves the V3.4 seam/sample-alignment result.
- Exact Duration allocates the final target-frame IMAGE shape first and writes trim, pad, and optional preserved final-frame spans directly. The assembler does not construct the final IMAGE with full-tensor `cat`, `stack`, `clone`, or `contiguous` copies. Audio remains intentionally RAM-backed and may use separate natural/target RAM buffers.
- Physical `decode_groups` retain their original order and terminal-prefix trim contract. Video Seam reuses the V3.4 analysis/formula/action semantics but copies only the affected 1-4 boundary frames plus required anchors; an analysis/patch error falls back transactionally to native frames.
- Disk-backed publication occurs only after assembly, reporting, and Driving Audio validation succeed. Unpublished early/late errors abort the backing pair. A published IMAGE remains valid while any Tensor/storage alias is retained, and the backing file becomes cleanup-eligible only after the final alias is released.
- P2-3 CPU acceptance covers RAM/Disk bit-exact output, Seam Off/Analyze/Auto/Auto 2, Exact Duration ON/OFF, trim/pad/preserve-final behavior, 1x5, 2x5 Terminal Merge, 3x5 Long Terminal Merge, 32 kHz cumulative audio rounding, Audio Seam, physical order/trim, file lifetime, stale recovery, and error cleanup. Its original Auto-rejection gate is superseded by the accepted P2-6 policy below.
- Canonical full validation is `412 passed` with only the known `pynvml` FutureWarning. `py_compile` and `git diff --check` pass. The ComfyUI_W runtime verifier passes registration, native PackedLayout, and Fixed 3x5 prompt-plan checks; its focused P2 regression is `141 passed`.
- Pre-change snapshots are `pre-phase2a-p2-1-memory-attribution-20260824_030858` and `pre-phase2a-p2-2-disk-backed-20260824_032923`; the latter contains 166/166 source files with zero SHA-256 mismatch at revision `d77a467796c048908f8b7b83736e226e736e0f98`, plus both runtime copies.
- Only the P2-1 through P2-3 target files were synchronized to primary ComfyUI_W; all 19 source-or-preserved-merge comparisons match SHA-256. Its pre-existing Video Reference tooltip addition was preserved. ComfyUI_WAN was deliberately not partially synchronized because its prior V3.5 dependency set is incomplete.
- P2-4 and the assembler-focused P2-5 acceptance are accepted below. Auto backend selection remains deliberately unimplemented; no new sampler/model generation acceptance is claimed by P2-5.

## Phase 2A P2-4 ComfyUI integration acceptance (2026-08-24)

- P2-4 is formally PASS using ComfyUI_W's installed `PromptExecutor` with the default CLASSIC `HierarchicalCache`, Core `SaveImage`/`PreviewImage`, and installed Video Helper Suite `VideoCombine`. The deterministic fixture is decoded CPU IMAGE/AUDIO only; no model, VAE, sampler, media input, CUDA allocation, or GPU generation is involved.
- `v3/assembly_v35.py` now polls ComfyUI's normal interrupt flag between bounded 8-frame direct-copy batches and immediately after the provisional output allocation. This changes only the independent V3.5 writer; V3.4 Assembly/Seam remains untouched. RAM and Disk-backed outputs remain bit-exact.
- A completed Disk-backed IMAGE remains alive after an intentional downstream error because the actual Core cache retains it. Requeue with unchanged assembler inputs reuses the same cached output and creates no additional backing pair. After cache eviction, the next allocation reclaims the released pair before creating its replacement, so managed pair count remains bounded; final managed files are zero.
- Core Save wrote 120 PNG frames and Core Preview wrote 120 temporary PNG frames from the mapped IMAGE. VHS streamed H.264 plus AAC from the same IMAGE/AUDIO. `ffprobe` verified 16x16, 120 frames, 24 fps, 5.000 seconds, and 32 kHz audio; this small geometry is intentional for compatibility/lifetime isolation.
- Core interrupt propagation is accepted: the probe raises the same `InterruptProcessingException` path used by ESC, PromptExecutor reports `execution_interrupted`, and the unpublished Disk-backed pair is removed. Separate-process crash/restart simulation leaves one stale pair and the next process removes it on first manager access.
- Reusable probe: `tools/p24_comfy_integration_probe.py`. Final runtime evidence is under `D:\Codex\_test_results\ComfyUI-H3-Continuum\P24-runtime-W-final-20260824_1105` (`p24_result.json`, exact prompt graphs, 120 Save frames, 120 Preview frames, and the VHS MP4).
- Validation: full canonical pytest `415 passed`; P2-focused ComfyUI_W runtime pytest `89 passed`; runtime registration/native PackedLayout/Fixed 3x5 prompt-plan verification, changed-file `py_compile`, and `git diff --check` pass. Only the known `pynvml` FutureWarning remains.
- Accepted pre-change snapshots are `pre-phase2a-p2-4-comfy-integration-source-verified-20260824_101909` (415 files, zero SHA-256 mismatch, revision `d77a467796c048908f8b7b83736e226e736e0f98`) and `pre-phase2a-p2-4-comfy-integration-comfyui-w-verified-20260824_101938` (324 files, zero mismatch). The standard snapshot script attempts failed only because the pre-existing `.pytest_cache` ACL denies traversal; those incomplete attempts are not accepted snapshots.
- Only `v3/assembly_v35.py`, the P2-4 probe, and its test file were synchronized to ComfyUI_W; source/runtime SHA-256 matches. P2-4 does not claim RAM-pressure/LRU cache modes, arbitrary downstream nodes, large-output memory behavior, manual browser UI interaction, or GPU/long-duration acceptance.

## V3.5 compact UI parity (2026-08-24)

- `web/project_id.js` now applies the established V3.4 compact/runtime-settings path to `H3ContinuumSamplerV35` and `H3ContinuumAssembleSeamV35`. No Python schema, socket, Sampling, Conditioning, Assembly, Seam, or Run Storage behavior changed.
- Sampler `Report Detail`, `debug`, and `show_preview` remain hidden widgets controlled by the existing H3-Continuum Settings entries. `strict_compatibility` remains loadable for legacy workflows but is hidden and forced `false` before queueing.
- `Auto Resume ID Override` remains always hidden and internally generated. `Run Name (Optional Override)` and `Regenerate From` are visible only when Run Storage is `Save + Auto Resume`; `Variation Nonce` is visible only for an explicit stored-chunk regeneration.
- The V3.5 assembler's `Report Detail` and `Exact Duration` controls use the same hidden Settings/fixed-contract path as V3.4.
- Accepted snapshots: source `pre-v35-compact-ui-source-verified-20260824_104010` (420 files, SHA-256 mismatch 0, excluding `.git` and inaccessible `.pytest_cache`) and ComfyUI_W `pre-v35-compact-ui-runtime-w-verified-20260824_104048` (330 files, mismatch 0, excluding `.pytest_cache`). The standard snapshot attempts are incomplete because that existing cache ACL denies traversal.
- Validation: dedicated frontend regression `2 passed`, JavaScript module syntax PASS, and full canonical pytest `417 passed`. The initial full-test attempts stopped only at inaccessible default pytest temp/cache paths; the canonical run used a fresh writable `D:\Codex\_test_temp` base. P2-5 is accepted below.
- Synchronized only `web/project_id.js` and its dedicated regression test to ComfyUI_W. Source/runtime SHA-256 matches (`EA79AF984EB7D615F0D79384C8B505442AF2B00CF7BABFD53E82DA2733927BCC` and `8B75C23DCCFD1AC302596187F2FBBD1C9B71FDDCB5E666AA4F9EEDFD8B5B4B93`).

## Phase 2A P2-5 long-output acceptance (2026-08-24)

- P2-5 is formally PASS for the manual `RAM` / `Disk-backed` V3.5 Assembly path. Testing was headless through ComfyUI_W's installed `PromptExecutor`; no browser, mouse, or front-end automation was used.
- The real 3x5 FL2VA Long Terminal Merge fixture reuses accepted Run Storage revision `1e30d8bf2154bbe7`: 3 logical chunks, 2 physical decode groups (`37T + 77T`), Core Video/Audio VAE Decode on GPU, 640x640, 360 frames, 24 fps, 15.000 seconds, and 32 kHz stereo audio. No new sampler/model generation was run.
- Independent fresh-process RAM and Disk-backed results are bit-exact. Final video SHA-256 is `95d5479bc5fee9c235ece7996c7c88dcc60981625dbedc330344403016ca9b9d`; audio SHA-256 is `eec0c6ff378c5bfcc3e71d02bab14230dea02a57e18ce1212f1dc1be4c88a3f9`. Exact Duration applies `362 -> 360` frames and `-2667` audio samples identically; Seam Auto and physical group order/trim match.
- Real-size Core Save and Preview each consumed all 360 mapped frames. VHS produced H.264/AAC at 640x640, 360 frames, 24 fps, 15.000 seconds, and 32 kHz. Disk-backed downstream peak RSS was about 12.10 GiB versus about 11.70 GiB for Assemble/hash alone; no catastrophic full-output duplicate was observed.
- Same-input requeue reports every node through assembler/digest cached, retains exactly one backing pair, and creates no additional pair. Cache release removes managed `.bin`/`.json` files. Core interrupt raised after backing allocation follows `execution_interrupted` and leaves zero managed files. A separate crash/restart recheck leaves one stale pair and removes it on first manager access in the next process.
- The 9.49 GiB stress uses a deterministic 1536x1536x360 float32 IMAGE while preserving the accepted two-group Long Terminal Merge plan. RAM and Disk-backed video/audio hashes are bit-exact; both are finite; Disk-backed holds one 10,192,158,720-byte file while cached and leaves zero managed files after release.
- On Windows, RSS/working set is not the acceptance metric for file-backed savings because resident mmap pages are counted in RSS. At the stress digest boundary, RAM and Disk-backed RSS were both about 10.44 GiB. The correct commitment metrics show the benefit: RAM private/USS were 13,322,362,880 / 11,045,199,872 bytes, while Disk-backed private/USS were 3,122,954,240 / 855,834,624 bytes. File backing therefore removed about 9.50 GiB of anonymous private commitment and about 9.49 GiB of unique resident commitment for a 9.49 GiB output.
- Reusable probe: `tools/p25_gpu_acceptance_probe.py`; focused P2-5/P2-4/P2-3 regression is `58 passed`, and full canonical pytest is `420 passed` with only the known `pynvml` FutureWarning. `py_compile` and `git diff --check` pass.
- Accepted snapshots are `pre-phase2a-p2-5-gpu-acceptance-source-verified-20260824_105605` (422 files, mismatch 0) and `pre-phase2a-p2-5-gpu-acceptance-runtime-w-verified-20260824_105626` (331 files, mismatch 0). P2-5 changed only the source-side probe, its tests, and project records; no Production runtime sync was required.
- Primary evidence roots: `P25-long-terminal-ab-20260824_110031`, `P25-downstream-disk-20260824_110515`, `P25-interrupt-disk-20260824_110815`, `P25-cache-requeue-disk-20260824_111126`, `P25-stress-1536-disk-private-20260824_111836`, `P25-stress-1536-ram-private-20260824_111907`, and `P25-lifetime-recheck-20260824_111947` under `D:\Codex\_test_results\ComfyUI-H3-Continuum`.
- Auto backend is accepted in P2-6 below. Arbitrary downstream nodes may still materialize their own full copies. New 3x5 sampler/model generation and 3x5 Main Hi-res Fix 2x GPU/resource acceptance remain separate work; P2-5 validates the assembler using already accepted physical latents and real Core GPU Decode.

## Phase 2A P2-6 Auto Buffer Backend acceptance (2026-08-24)

- P2-6 is formally PASS. `H3ContinuumAssembleSeamV35` now offers `Auto`, `RAM`, and `Disk-backed`; `Auto` is the default for newly created V3.5 assembler nodes. Existing saved string values for either manual backend remain valid and retain their exact manual behavior.
- Auto selects RAM only when the final IMAGE is at most 4 GiB and available physical memory is at least `final IMAGE + max(4 GiB, 10% of total physical RAM)`. Larger outputs or insufficient headroom select Disk-backed. If memory counters are unavailable, Auto chooses Disk-backed rather than assuming RAM is safe.
- A Disk-backed Auto decision requires free space for the final IMAGE plus a fixed 2 GiB disk reserve. Capacity-probe failure, insufficient disk, or allocation failure is explicit and never falls back to RAM. Users may still select manual RAM when they independently know it is safe.
- The V3.5 report records requested/resolved backend, final IMAGE bytes, available/total RAM, computed RAM reserve, 4 GiB RAM limit, disk free/reserve values, and the decision reason. Manual paths do not query or change Auto policy.
- Real headless acceptance `P26-auto-ram-long-terminal-20260824_113400` reused the accepted 3x5 FL2VA Long Terminal Merge revision and Core GPU Decode. The 1,769,472,000-byte output selected `Auto -> RAM` with about 39.2 GiB available and a 6.39 GiB RAM reserve. Its 640x640 / 360f / 15.000s video and 32 kHz audio hashes exactly match P2-5.
- Large-output acceptance `P26-auto-disk-stress-20260824_113610` used the 10,192,158,720-byte / 9.49 GiB IMAGE fixture and selected `Auto -> Disk-backed` because the final IMAGE exceeded 4 GiB. It retained one backing pair while cached, returned the accepted stress video/audio hashes, and left zero managed files after release.
- Focused Auto/P2 regression is `66 passed`; full canonical pytest is `428 passed`; changed-file and runtime `py_compile`, runtime registration/native PackedLayout/Fixed 3x5 verification, and `git diff --check` pass. Only the known `pynvml` FutureWarning remains.
- Accepted snapshots are `pre-phase2a-p2-6-auto-source-verified-20260824_112744` (426 files, mismatch 0) and `pre-phase2a-p2-6-auto-runtime-w-verified-20260824_112744` (331 files, mismatch 0), excluding the pre-existing inaccessible `.pytest_cache`. Only `v3/file_backed_buffer.py`, `v3/assembly_v35.py`, and the Auto portion of `v3/driving_nodes.py` were synchronized to ComfyUI_W; its pre-existing Video Reference tooltip addition remains preserved.
- V3.4 Sampling, Conditioning, Terminal Merge, Assembly, Seam, Run Storage, and every V3.4 socket remain unchanged. Auto does not guarantee that arbitrary downstream nodes avoid their own full copies. New 3x5 sampler/model generation and 3x5 Main Hi-res Fix 2x resource acceptance remain separate.

## V3.5 release-candidate preparation (2026-08-24)

- Public package version, Python package metadata, `metadata.ini`, Changelog, English/Japanese README, package information, and validation text now identify `3.5.0` consistently.
- Public scope is explicit: Sampler V3.5 refine-context, Advanced Second Pass Bridge, and Assemble + Seam V3.5 are release paths; integrated Main Hi-Res Fix remains Experimental. The standalone Latent Resize node is documented as an advanced utility rather than the recommended Main 2x backend.
- Added `docs/V35_HIRES_FIX.md` with standard Main and external-upscaler wiring, separate First/Second Pass scheduler roles, the accepted `simple / 10 steps / denoise 0.35` baseline, OFF passthrough, audio behavior, and current GPU limits. No diagnostic UI workflow is published as an accepted V3.5 template.
- Distribution Manifest includes the V3.5 Production modules, CPU regressions, release metadata test, public guide, and the Production-imported P2-0 backend. P2-4/P2-5 runtime probes remain repository validation tools rather than distribution Manifest payloads. No credentials or generated test media are included.
- Release metadata regression and targeted V3.5 tests pass (`75 passed`). Full canonical pytest is `430 passed`; only the known `pynvml` FutureWarning remains. Source and ComfyUI_W runtime verifier both report package `3.5.0`, native PackedLayout PASS, Fixed 3x5 prompt-plan PASS, and the complete expected node registry.
- Representative headless GPU revalidation `V35-release-candidate-auto-long-terminal-20260824` is PASS. Accepted 3x5 FL2VA Long Terminal Merge latents decoded through Core GPU Video/Audio VAE and Assemble V3.5 Auto as 3 logical / 2 physical groups (`37T + 77T`), 640x640, 360 frames, 24 fps, 15.000 seconds. Auto selected RAM for 1,769,472,000 bytes; video/audio SHA-256 exactly match P2-5/P2-6, all outputs are finite, and managed backing files after release are zero.
- Remaining publication limits: Main Hi-Res Fix 3x5 2x and Reference/Hybrid-specific Second Pass GPU acceptance are pending; arbitrary downstream full IMAGE copies are outside Continuum's guarantee. Existing V3.4 workflows remain supported.
- Verified release-preparation snapshots are `pre-v35-release-preparation-source-verified-20260824_115858` (426 files, mismatch 0) and `pre-v35-release-preparation-runtime-w-verified-20260824_115858` (331 files, mismatch 0). Commit/push remain pending explicit user instruction.

## V3.5 pending GPU acceptance closure (2026-08-24)

- Real ComfyUI API acceptance used an NVIDIA GeForce RTX 5060 Ti with 16,311 MiB VRAM. Production code was not changed.
- Main Hi-Res Fix `3 x 5s` FL2VA, 576x576 to 1152x1152 Lanczos, `res_multistep`, workflow `simple / 10 steps / denoise 0.35`, preserved 3 logical chunks and 2 physical groups (`37T + 77T`). First Pass and the 37T group's 10-step Second Pass completed. The terminal logical `[2,3]` / 77T group failed at its first Second Pass inference with CUDA OOM: 15.93 GiB device limit, 10.04 GiB allocated, 1.49 GiB requested, zero CUDA free. This condition is formally not accepted on the tested 16 GiB GPU; it is a resource boundary, not evidence that physical grouping changed.
- Hybrid FL2VA + Reference `1 x 5s`, 576x576 to 1152x1152, passed the integrated Main Hi-Res Fix. The node used `conditioning_source=refine_context`, one physical group / one sampling pass, actual refine seed `2946484852083492747`, output latent `(1, 24, 37, 72, 72)`, temporary refined audio discard, and bit-exact first-pass audio LATENT passthrough. Core Decode / Assemble produced 1152x1152, 120 frames, 24 fps, 5.000 seconds with 32 kHz stereo audio; visual inspection found no persistent colored line/plate artifact, flash, or temporal collapse. Output SHA-256 is `E5B27CABCD5FBC1422F169AC6E75570EF4D54010CD04A3439852D8DED15C1384`.
- The same Hybrid/Reference input also passed the public `H3ContinuumSecondPassV35` node directly at 576x576: `conditioning_source=refine_context`, actual refine seed `5765580629374593532`, shape `(1, 24, 37, 36, 36)`, one sampling pass, bit-exact first-pass audio passthrough, Core Decode / Assemble 120 frames / 5.000 seconds, and clean contact-sheet inspection. Output SHA-256 is `67311A797CD812584B4E2CCC21D7DF83AE8C1F1D72AB8BF5FA1C142D00894D2D`.
- The Hybrid prompt used the plain text `Picture 3` instead of the recommended explicit `<Picture 3>` tag, so preflight emitted a non-blocking H3C-P103 warning. The connected reference still participated in First Pass conditioning; the run proves transport/execution acceptance, not a warning-free public prompt example.
- Evidence root: `D:\Codex\_test_results\ComfyUI-H3-Continuum\V35-pending-gpu-acceptance-20260824`. Remaining limits are Main 3x5 2x on larger VRAM or a lower-memory terminal-group implementation, and Reference/Hybrid durations longer than 1x5.
- Pre-documentation snapshots are `pre-v35-pending-gpu-results-source-verified-20260824_130824` (431 files) and `pre-v35-pending-gpu-results-runtime-w-verified-20260824_130824` (334 files), excluding `.git` and the pre-existing inaccessible `.pytest_cache`.

## V3.5.0 formal release documentation (2026-08-24)

- V3.5.0 is the current formal release. The public README now leads with the two major additions: Continuum-aware Second Pass / experimental integrated Hi-Res Fix, and low-memory Assemble + Seam V3.5.
- V3.4 node IDs remain registered intentionally for saved-workflow compatibility. V3.5 does not replace V3.4 Sampling, Conditioning, Terminal Merge, Assembly, Seam, Run Storage, or public sockets; existing V3.4 workflows can continue unchanged.
- Added separate public node images `docs/images/v35-hires-fix-node.png` and `docs/images/v35-second-pass-node.png`. BasicScheduler is omitted visually but the README explicitly requires workflow-side SIGMAS and records the accepted `res_multistep`, `simple / 10 steps / denoise 0.35` baseline. The Main image shows the accepted Lanczos 2x selection.
- Public memory claims are limited to measured Windows host-memory behavior: for the 9.49 GiB 1536x1536x360 stress IMAGE, Disk-backed reduced private memory by about 9.50 GiB and USS by about 9.49 GiB while preserving exact video/audio hashes. No sampler GPU-VRAM reduction is claimed.
- Public GPU limits now distinguish accepted 1x5 576-to-1152 Main and Hybrid/Reference paths from the unaccepted 3x5 2x RTX 5060 Ti 16 GiB condition, which failed at the terminal 77T group's first Second Pass inference after the 37T group completed.
- Final source validation is `430 passed`; all 159 Manifest entries verify by SHA-256; `git diff --check` passes. ComfyUI_W runtime verifier passes package 3.5.0 registration, native PackedLayout, and Fixed 3x5 planning. Nine changed public documentation/assets match the snapshotted runtime by SHA-256.
- Verified pre-release snapshots are `pre-v35-formal-readme-release-source-verified-20260824_141358` (431 files) and `pre-v35-formal-readme-release-runtime-w-verified-20260824_141359` (334 files), excluding `.git` and the pre-existing inaccessible `.pytest_cache`.

## Issue #11 documentation clarification (2026-08-25)

- `Reference Size` and `Video Guide Size` are existing V3.5 controls, not missing inputs. Compact UI reveals them only after a corresponding Reference Image or Video Guide Frames connection.
- `Video Guide Size` is the V3.5.1 display name for the earlier `Video Reference Size`; the backend key and saved-workflow compatibility are unchanged.
- Reference Images and Video Guide Frames are resized internally before VAE encoding. External resize remains optional for deliberate crop, forced source upscaling, or a custom algorithm; loader-side decoding and frame-rate conversion remain unchanged.

## V3.5.1 public-state cleanup (2026-08-25)

- Project instructions now identify V3.5.1 as the current public baseline while retaining V3.4 node IDs, public contracts, and saved-workflow compatibility.
- The later real-browser acceptance superseded the earlier simulated Last Queued Seed result; that experiment is withdrawn and standard ComfyUI Seed behavior is restored.
- GitHub Issues #9, #10, and #11 received implementation guidance and are closed as completed. Issue #11 was closed after the conditional-UI/internal-resize README clarification reached public `main`.

## GitHub Actions dependency/stub repair (2026-08-25)

- The public V3.5.1 Actions failure was limited to the isolated CI environment: three P25 tests lacked `psutil`, and two Hi-Res Fix tests lacked ComfyUI Core's `comfy_extras.nodes_minimax_h3` module.
- `psutil` is now an Actions-only test dependency. Runtime `requirements.txt` remains dependency-free.
- `tests/test_v35_hires_fix.py` provides a file-local `comfy_extras.nodes_minimax_h3` stub containing only Core's `CANVAS_MULTIPLE = 32`. Production Core imports and Hi-Res Fix behavior are unchanged.
- Focused Hi-Res Fix/P25 validation is `16 passed`; full validation is `450 passed` with only the known `pynvml` FutureWarning. The first full local run encountered only the existing Windows global pytest temp ACL error; the accepted rerun used a dedicated writable `--basetemp`.
