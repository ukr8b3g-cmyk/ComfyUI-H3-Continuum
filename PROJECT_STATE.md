# Public source status

Updated: 2026-10-04 (Japan time).

## Package 3.9.1

This patch stabilizes V3.9 generation and Review without adding LoRA Plan or V4.0. Public V3.9 node IDs and official workflows remain unchanged. V3.8X2 stays available as a separate workflow; historical releases and tags remain available.

The included repairs cover:

- Second Pass audio-only and mixed keyframes, with video-only spatial adaptation.
- Conditioning and Reference inheritance for the actual Review output, including partial output and a single middle chunk.
- Take compatibility using Sampling Contract v6 and Graph Contract v4, including sampler closures and MODEL CFG/wrapper settings.
- Review Driving Audio cropped once from the physical group's natural frame range, sharing the PCM origin for Exact ON/OFF.
- Core-standard audio resampling with the legacy fallback when the API is unavailable.
- The documented Reference Encode Cache limitation for direct weight mutation inside the same VAE object.

## Compatibility

Original v5 Takes and history remain readable and are not deleted or converted. They cannot supply prefixes for v6 generation. Start a new Full Video or use Start again from Chunk 1 when moving an older Run to the repaired runtime.

Run Storage v3 and State/Session formats are retained. Unknown upstream settings can still generate; when their identity cannot be observed safely, automatic Take reuse is disabled.

## Validation and remaining limits

- Full CPU regression: 1,696 passed, 1 skipped, no failures; CUDA initialization attempts: zero.
- Offline verification: native PackedLayout and Fixed 3x5-second planning passed; twelve public nodes registered.
- Targeted GPU checks passed partial-prefix Review, single-middle-chunk Review and complete three-group reuse at 512x512 / 24 fps. Corresponding saved FLAC matched source PCM, and original Take/raw files were retained.
- Integrated generation and Take-reuse GPU checks passed for the repaired runtime.
- Browser save/reload acceptance and full acceptance of the unchanged default workflow remain pending. These targeted results do not establish every accelerator or quality combination.
- Optional latent-upscale doubled outlines are tracked separately in [Issue #27](https://github.com/ukr8b3g-cmyk/ComfyUI-H3-Continuum/issues/27).
- Versioned source downloads are listed in GitHub Releases. Registry publication is separate, and Release publication does not complete the pending acceptance gates.

See README.md, README_JA.md and CHANGELOG.md for user instructions and repair details. Current package records are in PACKAGE_VALIDATION.txt and PACKAGE_INFO_JA.txt; docs/VALIDATION_JA.md separates the current acceptance procedure from historical V2 instructions. Follow-up documentation corrections on main retain the published v3.9.1 tag.
