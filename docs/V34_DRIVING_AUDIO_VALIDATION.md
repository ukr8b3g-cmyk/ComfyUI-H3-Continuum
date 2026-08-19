# V3.4 Driving Audio Runtime Validation

This file records the Windows real-generation evidence for the V3.4 Driving Audio path. The MP4 outputs retain their embedded ComfyUI workflow metadata; settings not repeated below should be recovered from that metadata rather than inferred.

## Test environment

- Windows 11, ComfyUI Core, NVIDIA GeForce RTX 5060 Ti 16 GB
- H3 Continuum V3.4.0, I2VA + Continuation
- 800 x 800, 24 fps, 5 seconds per chunk
- Core Video/Audio VAE Decode followed by H3 Continuum Assemble
- Fixed chunk seeds during comparisons
- Driving Audio uses absolute-time guide slices while the original AUDIO stream is selected for final output
- Generated audio and Audio Seam are bypassed for the final Driving Audio stream

## Source assets

- Short source: `Voice_Design_00002_.mp3`, approximately 4 seconds
- Exact two-chunk source: `H3_V34_Driving_Audio_10s_Boundary_Test.wav`, 10 seconds
- Long source: `H3_V34_Driving_Audio_15s_Long_Tail_Test.wav`, 15 seconds used with a 10-second output
- Three-chunk source: `H3_V34_Driving_Audio_15s_Three_Chunk_Test.wav`, 15 seconds, 48 kHz mono
- Three-chunk source structure: one spoken phrase in each 5-second interval with silence around the chunk boundaries

## Results

| Output | Purpose and relevant settings | Result | Time |
|---|---|---|---:|
| `MiniMax_H3_Continuum_V31_00091_.mp4` | 2 x 5 s; short source; existing exact-duration tail policy | Source audio was retained and the 10-second output completed without a custom short-audio rejection. | 14:22.85 |
| `MiniMax_H3_Continuum_V31_00092_.mp4` | 2 x 5 s; exact 10-second boundary source | Boundary timing and original-stream selection passed. Source/output audio PSNR: 165.763 dB. | 14:23.90 |
| `MiniMax_H3_Continuum_V31_00093_.mp4` | 2 x 5 s; 15-second source | Only the requested 10-second output interval was used; the later phrase was excluded naturally. Source/output audio PSNR: 165.731 dB. | 14:23.14 |
| `MiniMax_H3_Continuum_V31_00094_.mp4` | 3 x 5 s; three-phrase source | All three absolute-time intervals and silence positions were retained. Source/output audio PSNR: 165.671 dB. | 22:33.29 |
| `MiniMax_H3_Continuum_V31_00095_.mp4` | Run Storage initial generation | `0 reused / 3 generated`; stored output audio matched `00094` (`inf` dB comparison). | 22:42.63 |
| `MiniMax_H3_Continuum_V31_00096_.mp4` | Immediate unchanged queue | Completed, but this run alone was not accepted as restart-resume evidence because ComfyUI execution caching could apply. | 22:42.63 |
| `MiniMax_H3_Continuum_V31_00097_.mp4` | Restarted ComfyUI; unchanged Run Storage contract | `3 reused / 0 generated`, `resume=complete`; complete resume passed. | 01:36.47 |
| `MiniMax_H3_Continuum_V31_00098_.mp4` | Third prompt changed only | `2 reused / 1 generated`; first regenerated chunk was Chunk 3; output audio remained identical (`inf` dB). | 09:47.09 |
| `MiniMax_H3_Continuum_V31_00099_.mp4` | New portrait and three-section dialogue prompt; 3 x 5 s | User listening/video review passed. Original audio remained 15.000 s at 48 kHz mono; source/output PSNR was 165.671 dB. Silence intervals, mouth closure, face stability, and chunk-local dialogue timing were accepted at practical quality. | 23:05.38 |
| `MiniMax_H3_Continuum_V31_00100_.mp4` | Same Driving Audio test with Spectrum enabled and Video/Audio Seam set to Auto | User review passed. Spectrum and Video Seam completed; final Driving Audio remained the original stream at 15.000 s, 48 kHz mono, PSNR 165.671 dB. Audio Seam diagnostics were produced, but the generated/seamed audio was bypassed for final output. | 15:34.54 reported by workflow; 953.16 s (15:53.16) external observation |
| `MiniMax_H3_Continuum_V31_00101_.mp4` | Turbo LoRA 8-step profile using `res_multistep`; report unavailable | Runtime completed in 662.63 seconds. Recorded as the planned Turbo 8-step Driving Audio comparison and accepted as part of the completed Driving Audio gate. | 11:02.63 |
| `MiniMax_H3_Continuum_V31_00102_.mp4` | Three-section city-pop prompt attempt | Generation and original Driving Audio output completed, but the prompt parser reported `Timeline-like syntax was not recognized` and used one Fixed prompt for all three chunks. This run is retained as parser-fallback evidence and is not accepted as a valid three-section visual-timeline comparison. | 11:24.89 |
| `MiniMax_H3_Continuum_V31_00103_.mp4` | Generic audio-content-independent lip-sync prompt; Turbo LoRA 8-step; `euler` + `simple`; Spectrum disabled; 3 x 5 s | Timeline parsing returned three unique sections. The 40-second, 48 kHz stereo source `audio_ace_step_00003_.mp3` naturally supplied only the requested first 15 seconds. Final source/output PSNR was 169.031 dB left and 169.021 dB right. Original Driving Audio was selected and Audio Seam was bypassed. User listening review passed; a non-vocal passage was interpreted visually as a sound-effect-like event, which is accepted within native H3 behavior without an external Mel-band or dedicated lip-sync controller. | 10:58.09 |

## Acceptance summary

- Original waveform timing and final duration: PASS
- Absolute-time slicing across 5-second chunks: PASS
- Silence and later-phrase placement: PASS
- No unintended generated dialogue in the final audio: PASS
- Short source permissive execution: PASS
- Longer-than-output source handling without a custom pre-trim policy: PASS
- Run Storage complete reuse after restart: PASS
- Run Storage partial regeneration from Chunk 3: PASS
- Spectrum-enabled compatibility: PASS
- Practical mouth movement and listening review: PASS
- Strict phoneme-level lip-sync guarantee: not claimed

## Remaining cleanup

- Driving Audio currently makes final Audio Seam correction unnecessary. Skipping its analysis entirely would reduce confusing diagnostics and avoid unused processing; this is a cleanup item, not a correctness failure.
- Native H3 audio-driven facial motion is not a strict phoneme-level lip-sync contract. External Mel-band or dedicated lip-sync control is outside the accepted V3.4 scope.

## Current verdict

**PASS.** Standard, Spectrum-enabled, Turbo 8-step, Run Storage, partial-regeneration, short-source, long-source, mono, and stereo tests establish that Driving Audio preserves the original final stream and maintains absolute timeline placement across Continuum chunks. Strict phoneme-level lip sync is not claimed.
