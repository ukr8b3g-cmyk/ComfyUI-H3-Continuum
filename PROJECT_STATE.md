# Project State

Updated: 2026-08-20

## Baseline

- Current public baseline: V3.4.0
- Authoritative working repository: `D:\Codex\_git_push_work\ComfyUI-H3-Continuum`
- Primary tested runtime: `D:\StabilityMatrix\Data\Packages\ComfyUI_W\custom_nodes\ComfyUI-H3-Continuum`
- Secondary runtime: `D:\StabilityMatrix\Data\Packages\ComfyUI_WAN\custom_nodes\ComfyUI-H3-Continuum`
- Old checkout to keep synchronized with published `main`: `D:\Codex\ComfyUI-H3-Continuum`

## Active direction

- Driving Audio preserves the supplied audio as final output while conditioning every chunk.
- Video Reference is persistent across chunks and supports selectable reference sizing.
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
- Current FLF baseline is `context_bound_terminal_v1`: final-chunk context-tail and Last Frame anchors only.
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
