# ComfyUI-H3-Continuum 3.4.0

> **V3.4 hotfix notice:** The initial V3.4 repository package was incomplete. Although the public V3.4 nodes were present after the first hotfix, their parent sampler and sequence runtime did not yet accept the new Driving Audio and Video Reference contracts. We apologize for the incomplete release. The complete V3.4 runtime has now been synchronized. If you installed V3.4 earlier, run `git pull` or reinstall the node, then restart ComfyUI.

Long-form MiniMax H3 video generation for ComfyUI with restartable chunks, persistent references, Driving Audio, Video Reference, seam correction, and optional Spectrum interoperability.

![H3 Continuum V3.4 workflow overview](docs/images/v34-workflow-overview.png)

> V3.4 is the current stable release. V3.3 legacy nodes remain available for existing workflows.

## What's new in V3.4

V3.4 focuses on the two reference workflows that are most useful in normal production:

- **Driving Audio**: use an existing audio source as the preserved final audio while it guides the H3 generation across chunks.
- **Video Reference**: use an existing video as persistent visual reference for appearance, motion, framing, and timing without treating it as a frame-by-frame copy.
- **Hybrid FLF + Reference**: use First Frame, Last Frame, and persistent Reference Images together without adding a separate mode or model allowlist.
- **Restartable chunks**: reuse completed chunks with Run Storage and regenerate only the selected part when the generation contract remains compatible.
- **Core compatibility**: remove Continuum-only rejection of unknown upstream/custom nodes and remove the obsolete `strict_compatibility` control.
- **Spectrum interoperability**: use the official H3 Continuum Interop API v1 when Spectrum is installed; Spectrum remains optional.
- **Simpler public interface**: Timeline Video and the earlier timeline-audio paths are hidden from the V3.4 public sampler interface rather than being presented as stable production features.

### Direction change: from timeline generation to preserved references

Earlier development explored Timeline Video and timeline-audio conditioning. Those paths can be useful for experiments, but they are not the default production behavior: chunk boundaries can change visual content, and generated audio can diverge from a supplied song, dialogue, or effects track.

V3.4 therefore prioritizes:

1. **Driving Audio** for cases where the supplied audio should remain the final audio stream.
2. **Video Reference** for cases where the supplied video should guide the generated result without requiring exact frame reproduction.
3. **Chunked generation and Run Storage** for practical retries and long-form work.

This is a usability and reliability decision, not a claim that the experimental timeline paths are impossible. They are hidden from the stable interface while the public workflow stays focused on predictable user-controlled inputs.

## Example workflows

- [V3.4 standard](examples/workflows/MiniMax_H3_Continuum_V34.json)
- [V3.4 Turbo](examples/workflows/MiniMax_H3_Continuum_V34_turbo.json)

The templates include optional external nodes such as Spectrum, Video Helper Suite, rgthree, EasyUse, and RTX Video Super Resolution. Install, replace, connect, or bypass them according to your installation. Media and acceleration choices remain under user control.

## What's new in V3.4

### Driving Audio

Driving Audio is the primary V3.4 audio path.

- Source audio guides each chunk at its absolute sequence position.
- The original effective stream is preserved for final output.
- Generated audio and Audio Seam processing are bypassed while Driving Audio is active.
- Audio is not independently rewritten at every chunk boundary.
- Perfect lip sync is not guaranteed; results still depend on H3, source material, prompts, and sampling.

### Video Reference

Video Reference provides a persistent native H3 video reference across all chunks.

- It guides motion, framing, timing, and appearance.
- It is not a direct pixel-copy or deterministic identity-transfer system.
- Video and audio are independent. Route a loader's IMAGE output to Video Reference and AUDIO output to Driving Audio.
- Source decoding and frame-rate conversion remain loader responsibilities. Continuum does not impose an unnecessary forced 24 fps conversion.

| Video Reference Size | Purpose |
|---|---|
| Efficient - 0.4 MP | Default; lower token cost and faster iteration. |
| Balanced - 0.6 MP | More detail at a higher compute cost. |
| Match Output | Largest reference input; potentially much slower and heavier. |

### Hybrid First/Last Frame + Reference Images

V3.4 supports First Frame, Last Frame, and persistent Reference Images in the same Continuum run. The public sockets and controls are unchanged: connect the inputs that the selected H3 model supports.

- Pure FL2VA and pure Ref2VA identity contracts remain unchanged.
- The combined path receives a distinct hybrid identity so Run Storage does not reuse incompatible chunks.
- Prompt/reference mismatches produce guidance warnings rather than a Continuum-only execution stop.
- No model-name allowlist or automatic model replacement is used.

Local checks passed with the B2049 hybrid variant. FL-only models could run, but showed less reliable transitions when FLF and Reference Images were combined; a hybrid-capable model is therefore recommended for this path.

### Core-first, permissive execution

V3.4 removes or relaxes Continuum-only rejection rules that blocked otherwise runnable Core H3 experiments.

- Prompt problems prefer warnings and fallback behavior instead of stopping.
- Unknown upstream/custom wrapper classes are not blanket-rejected.
- There is no model allowlist and no automatic model replacement.
- The obsolete strict_compatibility control is removed from the V3.4 interface.
- Current Core PackedLayout behavior is supported without requiring the removed legacy frame_count argument.

Hard stops remain only for states that cannot execute safely, including corrupt latent topology, incompatible assembly data, invalid persisted revisions, or unusable mandatory payloads.

### Cleaner interface

The public nodes focus on normal production controls. Developer diagnostics and detailed reports are available through ComfyUI settings.

![V3.4 sampler, Spectrum, and assembler](docs/images/v34-sampler-spectrum-assemble.png)

### Timeline paths

Experimental Timeline Video and earlier timeline-audio paths are no longer public V3.4 inputs. They are hidden rather than destructively removed. Existing V3.3 workflows can continue through legacy nodes, but new stable workflows should use Driving Audio and Video Reference.

## Installation

### Updating an existing installation

For a Git checkout, run the update from the custom-node directory:

```powershell
cd ComfyUI/custom_nodes/ComfyUI-H3-Continuum
git pull --ff-only origin main
```

Restart ComfyUI after the update. If the node was installed with ComfyUI Manager, use its **Update** action instead of running `git pull` manually. Do not mix Manager updates and a separate Git checkout for the same installation.

Search for H3 Continuum or Continuum in ComfyUI Manager, or install manually:

~~~bash
cd ComfyUI/custom_nodes
git clone https://github.com/ukr8b3g-cmyk/ComfyUI-H3-Continuum.git
~~~

Restart ComfyUI after installation or update.

## V3.4 nodes

### H3 Continuum Sampler V3.4

Main inputs:

- model, clip, video_vae, sampler, sigmas
- Sequence Prompt
- first_frame, last_frame
- reference_image_1 through reference_image_3
- Video Reference
- driving_audio, audio_vae

Outputs:

- video_latents, audio_latents
- assembly_plan, status
- driving_audio

Visible controls:

- Prompt Format, chunks, chunk_seconds
- width, height, continuity
- base_seed, control after generate
- audio_continuity
- Run Storage
- Reference Size
- Video Reference Size

### H3 Continuum Assemble + Seam V3.4

Inputs: images, audio, assembly_plan, and driving_audio.

Controls: Audio Seam and Video Seam.

When Driving Audio is connected, preserved source audio is selected for final output and generated audio seam processing is bypassed.

## Connection order

~~~text
H3 model / CLIP / Video VAE / sampler / sigmas
                         |
                         v
              H3 Continuum Sampler V3.4
                 |       |        |
          video_latents  |   assembly_plan
                         |
                  audio_latents

video_latents -> Core VAE Decode ------- images --+
audio_latents -> Core VAE Decode Audio -- audio  --+--> H3 Continuum Assemble + Seam V3.4
assembly_plan -------------------------------------+
driving_audio -------------------------------------+
~~~

For a source video with sound:

~~~text
Video loader IMAGE -> Video Reference
Video loader AUDIO -> driving_audio
~~~

The supplied templates use Video Helper Suite for this split. Any compatible IMAGE/AUDIO loader may be substituted.

## Prompt formats

Timeline:

~~~text
[0-5s] First section: action, camera movement, and scene progression.
[5-10s] Continue from the exact final state of the previous section.
[10-15s] Continue naturally without resetting the scene.
~~~

List prompts use --- separators. Fixed reuses one prompt for every chunk. Auto detects the available structure. If a timeline cannot be parsed, V3.4 reports a warning and uses an applicable fallback rather than rejecting an otherwise runnable workflow.

## Run Storage

Run Storage preserves completed chunks and can reuse them after restarting ComfyUI. Regenerate From selects the first chunk to regenerate; earlier compatible chunks remain unchanged.

![Regenerate From](docs/images/v34-regenerate-from.png)

- Use a fixed seed for reproducible resume.
- Changing persistent models, LoRAs, references, prompts, resolution, or sampling settings can create a new revision.
- Unknown upstream node classes no longer cause rejection by themselves; reuse still depends on compatible observable contracts and hashes.

## Spectrum interoperability

Spectrum is optional. Current Spectrum releases officially support H3 Continuum Interop API v1.

- Chunk 1 uses the normal initial path.
- Chunk 2 and later request Actual Prefix 2.
- Successful continuation logs accepted H3 Continuum API v1, actual prefix=2.
- Unsupported Spectrum versions fall back without a private patch.

See [Spectrum v0.2.15 H3 Continuum interoperability](https://github.com/xmarre/ComfyUI-Spectrum-MiniMax-H3#v0215-h3-continuum-interoperability).

Turbo LoRA and Spectrum are not mutually exclusive. Quality and speed remain workflow-dependent.

## Issue and pull-request response

### Issue #3

V3.4 removes blanket rejection of unknown upstream/custom class names. Run Storage evaluates the observable generation contract instead of treating an unfamiliar wrapper as automatically incompatible.

See [Issue #3](https://github.com/ukr8b3g-cmyk/ComfyUI-H3-Continuum/issues/3).

### Issue #4

V3.4 follows the current Core H3 layout contract and no longer requires the legacy frame_count parameter. The old strict-compatibility toggle is not part of the public interface.

See [Issue #4](https://github.com/ukr8b3g-cmyk/ComfyUI-H3-Continuum/issues/4).

### Issue #7

V3.4 allows First Frame, Last Frame, and Reference Images to be used together without requiring the separate BigStationW node or introducing a model allowlist. Hybrid presentation ordering and Run Storage identity are handled by Continuum while pure FL2VA and pure Ref2VA behavior remain unchanged.

The combined path was exercised locally with the B2049 hybrid variant. FL-only models were less consistent for this specific combination, so the README recommends a hybrid-capable model rather than rejecting other models in code.

See [Issue #7](https://github.com/ukr8b3g-cmyk/ComfyUI-H3-Continuum/issues/7).

### Pull request #1 and #2

These older partial pull requests were superseded by the consolidated [Pull request #5](https://github.com/ukr8b3g-cmyk/ComfyUI-H3-Continuum/pull/5). V3.4 selectively includes the compatibility direction needed for the current Core H3 contract, while the broader upstream synchronization and release-automation scope remains a separate upstream review.

The older pull requests are not represented as merged V3.4 changes.

### Pull request #5

PR #5 is the consolidated upstream-to-fork proposal covering current H3 compatibility, reference-input handling, assembly memory behavior, exact-duration handling, continuation-reference interoperability, and CI/release automation. V3.4 already contains the user-facing stability decisions described above; the PR remains an upstream review item and is not claimed as merged here.

## V3.4 input connection patterns

V3.4 separates the visual reference input from the driving-audio input. Choose the connection pattern that matches your source material.

### 1. Audio only

Connect `Load Audio` to `driving_audio`. Use this when an existing song, dialogue track, or sound effect should remain the final audio. A `Video Reference` is not required.

![Driving Audio connection](docs/images/v34-driving-audio-connection.png)

### 2. Video with its own audio

Connect `Load Video (Upload)` `IMAGE` to `Video Reference`. If the uploaded video contains the audio you want to preserve, connect its `AUDIO` output to `driving_audio` as well.

![Video Reference and embedded audio connection](docs/images/v34-video-reference-with-audio.png)

### 3. Video and audio from separate sources

Connect `Load Video (Upload)` `IMAGE` to `Video Reference`, then connect a separate `Load Audio` node to `driving_audio`. Use this when the visual reference video and the final audio source are different files.

![Separate Video Reference and Driving Audio connection](docs/images/v34-video-reference-separate-audio.png)

Both inputs are optional. Connect `Video Reference` when visual guidance is needed, and connect `driving_audio` when the supplied audio should be preserved in the final output.

### Video Reference frame rate

Use a 24 fps source for `Video Reference`. `Load Video (Upload)` may accept files recorded at 25 fps or another frame rate, but acceptance alone does not guarantee correct temporal alignment with H3. For a non-24 fps source, set `force_rate` to `24` in `Load Video (Upload)`, or convert the file to 24 fps before loading it. If the source is already 24 fps, leave `force_rate` at its default and do not resample it.

## Current validation status

V3.4 has been exercised locally with:

- 1, 2, and 3 chunks
- standard and Turbo paths
- Spectrum enabled and disabled
- I2VA, Reference, and selected FL2VA configurations
- Hybrid FLF + Reference with the B2049 hybrid variant
- Driving Audio with short, exact-length, and longer sources
- Video Reference with source audio routed separately
- 0.4 MP and 0.6 MP reference sizing
- Run Storage reuse and selected-chunk regeneration
- Core VAE Decode and final assembly

No OOM was observed in the cited recent local V3.4 checks, including two-chunk 800 x 800 runs. This is not a universal memory guarantee. Model precision, LoRAs, source resolution, optional nodes, GPU, and RAM affect memory use.

## Limits

- Continuation does not guarantee frame-perfect identity or motion.
- Video Reference guides H3; it does not reproduce every source frame.
- Driving Audio preserves selected audio, but visual lip synchronization remains model-dependent.
- Match Output can be substantially slower than 0.4 MP or 0.6 MP.
- Seam correction may keep the native boundary when a proposed correction is not safer.
- Optional template nodes must be installed, replaced, or bypassed by the user.

## License

See [LICENSE](LICENSE).
