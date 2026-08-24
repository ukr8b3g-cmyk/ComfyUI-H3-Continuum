# Project State

## E2-8 Second Pass contract (2026-08-22)

- V3.4 remains the stable generation contract; UI, sockets, sampling, Run Storage identity, and Assembly behavior are unchanged.
- `assembly_plan.second_pass_contract` is additive V3.5 metadata organized by physical decode group.
- Prompt source is the stored physical prompt; a future Second Pass node must not reparse Sequence Prompt.
- Video B/C/T and physical group count/order are fixed; only latent H/W may be preserved or enlarged.
- Audio output is the original physical audio LATENT passed through bit-exact; refined audio is not adopted in V1.
- E2-8A Contract, E2-8B1 CPU/static validation, E2-8B2 external LBH GPU PoC, and E2-8C Second Pass GPU acceptance are formally PASS. The E2-8C CPU baseline is `260 passed`.
- External LATENT nodes may discard custom dictionary metadata. Identically shaped group reordering therefore cannot be cryptographically detected; count, position, T, geometry, and audio-shape checks are enforced.

Updated: 2026-08-25

## V3.5.1 Issue #9 Conditioning Bridge candidate (2026-08-24)

- Added `H3ContinuumConditioningBridgeV35` / `H3 Continuum Conditioning Bridge V3.5` under `MiniMax H3/Continuum/Advanced`.
- The Bridge accepts externally processed physical-group video LATENTs plus the matching Assembly Plan and required V3.5 refine context. It returns one paired MODEL and one complete ComfyUI CONDITIONING object per physical group, plus a target-geometry Assembly Plan and status.
- The fixed list contract is `OUTPUT_IS_LIST = (True, True, False, False)` and `len(group_models) == len(conditioning) == physical group count`. CONDITIONING entries are appended as one inner object and are never flattened into the outer physical-group list.
- Second Pass and Bridge share the same context validation, target adaptation, prompt fallback, MODEL clone, and geometry update helper. Built-in Second Pass still samples groups sequentially and retains responsibility for Nested AV, video noise, Audio Lock, and audio passthrough; the Bridge deliberately leaves AV LATENT construction, noise, Audio Lock, and external sampling to the workflow.
- CPU coverage includes the 3-logical / 2-physical Terminal Merge shape (`[1] / 37T`, `[2,3] / 77T`), MODEL/CONDITIONING alignment, non-flattening, schema/registration, and existing Reference Image/Audio/context adaptation regressions. Focused validation is `33 passed`; full source pytest is `442 passed` with only the known `pynvml` FutureWarning.
- Only `nodes.py`, `v3/second_pass.py`, `v3/conditioning_bridge_nodes.py`, and `tools/verify_runtime.py` were synchronized to ComfyUI_W; every source/runtime SHA-256 matches. Runtime registration, native PackedLayout, and Fixed 3x5 prompt planning pass with the new Bridge registered as a non-legacy node.
- GPU acceptance through Basic Guider and an external sampler passed for three `1 x 5s` runs: LBH `1.2x` with `simple / 4 steps / denoise 0.3` produced 704x704 twice, and LBH `1.5x` with `simple / 10 steps / denoise 0.3` produced 864x864. Every run kept one MODEL and one complete CONDITIONING for one physical group, completed external sampling/Core decode/Assembly, and produced finite 120-frame/5.000-second video with 32 kHz stereo audio. The existing Issue #10 Reference Audio working-tree changes were preserved without reset or reorganization.

## V3.5.1 Issue #10 Reference Audio candidate (2026-08-24)

- Target version is V3.5.1. The backend keeps the optional `reference_audio_1` and `reference_audio_vae` sockets in their existing input order. The frontend presents them as `Reference Audio (Optional)` and `Reference Audio VAE (Optional)` behind the UI-only `Reference Audio Inputs` dropdown.
- New or unlinked nodes default to `Hidden`. `Show` restores both sockets at their original positions. A saved workflow with either socket connected opens in `Show`, and `Hidden` is rejected while either link exists; the UI never removes a graph link. The dropdown is added only after Core graph configuration and is excluded from Workflow JSON widget values, preventing widget-value shifts on reload.
- Related display labels are now `Video Guide Frames`, `Driving Audio`, and `Driving Audio VAE`. Input keys, order, types, Node IDs, and runtime contracts remain unchanged.
- This exposes the existing Core-compatible standalone Reference Audio 1 path; it adds no new audio encoding, strength control, model allowlist, source-audio copy, or lip-sync guarantee.
- V3.4 input keys/order/types, Node ID, sockets, and behavior remain unchanged; only the human-facing labels/tooltips are clarified. Its internal `run()` accepts the two values only so V3.5 can forward them to the existing Production path.
- Reference Audio conditions generated video/audio and leaves generated audio as final. Driving Audio remains the separate timeline-guide path whose original source is selected as final output.
- CPU integration confirms Reference Audio survives every normal physical group and the FL2VA Terminal Merge group (`logical [2,3]`, `paired_timeline_v1`) in `refine_context`. Run Storage ignores an unused Reference Audio VAE, separates changed audio contracts, and restores the disconnected revision identity.
- Final canonical validation after the conditional UI change is `450 passed` with only the known `pynvml` FutureWarning. JavaScript syntax, `git diff --check`, ComfyUI_W registration/native PackedLayout/Fixed 3x5 verification, and source/runtime SHA-256 equality for synchronized implementation files pass.
- Live ComfyUI acceptance passed for unlinked `Hidden`, `Hidden -> Show -> Hidden`, original-position socket restoration, clarified labels, linked-workflow auto-`Show`, and rejection of `Hidden` while linked. The user had already accepted the V3.5.1 generation test categories as all-clear; this UI-only step did not queue another GPU generation.
- The CPU-validated public feature files were previously published from the isolated clone as `a704aa961fc2ba0c19aef6f2ecfdcb46fa9384b2`. GPU acceptance is now complete and package metadata plus public documentation are being formalized as V3.5.1.
- V3.5.1 release validation is `450 passed` from the ComfyUI_W root, JavaScript syntax PASS, `git diff --check` PASS, and all 172 distribution Manifest entries match SHA-256. README English/Japanese use the user-supplied normal-state screenshots for Video Guide Frames and Reference Audio Hidden/Show.
- The public LBH/Conditioning Bridge connection example is `examples/workflows/MiniMax_H3_Continuum_V351_LBH_Conditioning_Bridge.json`; its README chart is `docs/images/v351-lbh-conditioning-bridge-flow.svg`. It is a separate example and does not replace or modify the recommended V3.5 template.

## V3.5.1 Last Queued Seed reuse candidate (2026-08-24)

- The fix is limited to `H3 Continuum Sampler V3.5` frontend state. It does not change V3.4, backend Sampling, Second Pass, Terminal Merge, Assembly, Seam, Run Storage, Node IDs, display names, or public sockets.
- Per-node session-only state is `last_queued_seed`, `auto_updated_seed`, `previous_control_mode`, and `auto_update_pending`. Nothing is serialized into Workflow JSON or carried across a browser/ComfyUI restart.
- `beforeQueuePrompt` records the actual `base_seed` submitted for the V3.5 sampler. After Generate records only the automatic Randomize update. A `Randomize -> Fixed` transition restores the prior queued seed only while the displayed value still equals the recorded automatic update; an intervening manual Seed edit cancels restoration and remains authoritative.
- Restoring the Seed only makes the First Pass inputs eligible for normal ComfyUI cache reuse. If the cache is absent or evicted, First Pass regenerates normally with the same Seed. Run Storage seed contracts remain strict and unchanged.
- The implementation is isolated in `web/last_queued_seed.js` and integrated through the existing `web/project_id.js` extension. JavaScript syntax and focused frontend behavior validation are `5 passed`; full source pytest is `445 passed`. The two Production frontend files match ComfyUI_W by SHA-256, whose runtime verifier and existing compact-UI regression pass. Real UI/cache acceptance remains pending.

## V3.5.1 Hi-Res Fix Core canvas alignment (2026-08-24)

- A real `576x576`, `scale_by=1.2` run exposed an invalid `43x43` H3 video/conditioning latent. Core MiniMax H3 patchifies spatial latents in `2x2` blocks and exposes pixel dimensions in 32-pixel steps, so the odd latent failed in Core with `24 * 43 * 43 = 44376` elements.
- Manual Hi-Res Fix targets now use ComfyUI Core's `CANVAS_MULTIPLE` and preserve-or-enlarge each axis on that grid. The failing case resolves to `704x704` / `44x44`; a `1024x576` source at `1.2x` resolves to `1216x704` / `76x44`. The Pixel/VAE, conditioning adaptation, and Second Pass paths remain unchanged.
- Focused Hi-Res/Second Pass validation is `48 passed`; full source pytest is `448 passed`. `v3/hires_fix_nodes.py` is synchronized to ComfyUI_W by SHA-256, and runtime registration/native PackedLayout/Fixed 3x5 verification passes. GPU acceptance after a ComfyUI process restart remains pending.
- The same attempt did not validate Last Queued Seed cache reuse: the second prompt was queued at `21:24:38` before the first prompt completed at `21:26:02`, and the log shows another First Pass `20/20`. Retry only after the first prompt has completely finished.

## V3.5 recommended template workflow (2026-08-24)

- `examples/workflows/MiniMax_H3_Continuum_V35.json` is the recommended V3.5 starting workflow.
- Hi-Res Fix is disabled by default and `H3 Continuum Assemble + Seam V3.5` uses Auto backend selection.
- First Frame, Last Frame, and Reference Images 1-3 share one 0.3 MP control. Video Guide Frames remains independently sized.
- Reference Images 1-3 and Video Guide Frames are routed to their matching V3.5 sampler sockets; `refine_context` and `video_vae` are connected to the integrated Hi-Res Fix path.
- V3.4 standard and Turbo templates remain available for saved-workflow compatibility.

## Baseline

- Current public baseline: V3.5.1
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
