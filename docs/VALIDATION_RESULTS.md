# V3.3.0 Validation Results

This file consolidates the release evidence by feature. It is not a claim that every model, LoRA, prompt, resolution, or GPU produces identical visual quality.

## 1. Test environment

- Windows 11 and ComfyUI Core
- NVIDIA GeForce RTX 5060 Ti 16 GB
- MiniMax H3 Ref2VA and FL2VA paths
- Standard approximately 20-step and Turbo 4/8-step profiles
- Core Video/Audio VAE Decode followed by Continuum assembly

## 2. Core continuation

**Purpose:** verify raw paired AV continuation over multiple 5-second chunks.

**Coverage:** 1, 2, 3, and 6 chunks; T2VA, I2VA, FL2VA, and Reference conditioning.

**Result:** sampling, 22-frame context trimming, exact-duration assembly, and external Core VAE decode completed. Three-chunk outputs retained 362 source frames and assembled to 360 frames.

**Verdict:** PASS.

## 3. Reference image and audio

**Coverage:** one to three ordered images, Ref2VA and FL2VA diagnostics, native Reference Audio, and image/audio persistence across chunks.

**Result:** three-image conditioning and native Reference Audio completed. Bypassed image sockets were ignored and active images were compacted in Core order. Reference Audio influences native H3 generation but is not an exact source-audio or strict lip-sync contract.

**Verdict:** PASS with the documented native-model limitation.

## 4. Run Storage and resume

**Coverage:** initial three-chunk save, SHA-256 verification, complete reuse, condition changes, and partial regeneration.

**Representative result:** initial run reported `0 reused / 3 generated`; complete Auto Resume reported `3 reused / 0 generated`. Changed MODEL, prompt, resolution, Reference configuration, and storage conditions did not reuse incompatible chunks.

**Verdict:** PASS.

## 5. Spectrum interoperability

**Coverage:** Spectrum `continuum-interop` PR head `c68f967b47f80a95077a251e91b8ed20098de9e3`, `res_multistep`, 3 x 5 seconds.

**Result:** Chunk 1 emitted no acceptance log. Chunks 2 and 3 each accepted `actual prefix=2` exactly once. All sampling passes, Core VAE Decode, and final assembly completed at 800 x 800 for 15 seconds.

**Verdict:** PASS on the validated PR/Fork receiver. Upstream PR #52 remains pending; verify the runtime acceptance log until merged.

## 6. Timeline Video

**Coverage:** optional Core VIDEO input, omitted/bypassed fallback, chunk-local temporal slicing, 0.4 MP preprocessing, Match Output, Ref2VA/FL2VA, Turbo and standard 20-step Spectrum paths, and one/two-chunk runs.

**Representative outputs:** `MiniMax_H3_Continuum_V31_00035_.mp4`, `MiniMax_H3_Continuum_V31_00039_.mp4`, and `MiniMax_H3_Continuum_V31_00040_.mp4`.

**Result:** chunk-local slices reached sampling and assembly correctly. Efficient 0.4 MP was substantially more practical than Match Output and showed no consistent benefit from the removed 0.6 MP UI preset.

**Verdict:** PASS. Motion, identity, detail, and generated audio remain model-, LoRA-, source-, and prompt-dependent.

## 7. Audio Seam

**Coverage:** Off and Auto on real multi-chunk decoded audio.

**Result:** Auto reduced measured boundary jumps while keeping final duration aligned. Audio and Video Seam remained independently selectable.

**Verdict:** PASS; Auto is the V3.3.0 default.

## 8. Video Seam Auto

**Coverage:** Analyze Only and Auto over real three-chunk outputs with clean boundaries, transient flashes, and micro-flashes.

**Representative outputs:** `MiniMax_H3_Continuum_V31_00047_.mp4`, `00048`, `00053`, `00054`, `00057`, `00058`, `00059`, and `00060`.

**Result:** qualified transient or micro-flash frames were corrected; clean boundaries were retained. Frame count, resolution, dtype, audio payload, and exact-duration assembly were preserved. User visual comparison accepted the flicker reduction.

**Verdict:** PASS; Auto is the stable default.

## 9. Auto 2 status

**Coverage:** deterministic exposure-ramp tests and real-output comparisons including `00062`, `00064`, `00066`, `00070`, and `00071`.

**Result:** the controlled exposure-ramp path is covered and no-op/fallback behavior is safe. Real generations did not reliably produce a qualifying exposure-ramp boundary; in one comparison Auto and Auto 2 were pixel- and audio-identical because no exposure ramp was accepted.

**Verdict:** PARTIAL / EXPERIMENTAL. Use Auto first; try Auto 2 only when Auto leaves a gradual exposure ramp.

## 10. Known limitations

- Continuation improves temporal context but cannot guarantee identity, motion, detail, or audio quality for every checkpoint, LoRA, prompt, or source.
- Timeline Video is computationally expensive at Match Output; 0.4 MP is the recommended default.
- Native Reference Audio is conditioning, not sample-identical audio copying or guaranteed strict lip sync.
- Video Seam correction is deliberately guarded and may preserve a boundary when correction would be riskier.
- Auto 2 real exposure-ramp benefit is not yet broadly validated.
- Spectrum Actual Prefix 2 requires a compatible receiver and an acceptance log.

## 11. Release checks

- Python compileall
- Full pytest suite
- Runtime node-registration verifier
- Windows real-generation and decode/assembly runs listed above

The exact automated test count is recorded by the V3.3.0 release commit and GitHub Actions run.
