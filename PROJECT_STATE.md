# Public source status

## KJ Preview Override profile — source update

Add the audited audio-scale lookup implementation identified by
`kj-preview-audio-scale-23f4979-phase-a`. Existing profiles, Take reuse checks,
storage formats and official workflow files are preserved. The bounded KJ
profile passed CPU and JavaScript checks. Two isolated GPU queues verified
that a new v6 Take could continue to Chunk 2 with the original Chunk 1 raw
payload intact. Runtime restart confirmed registration and the installed code
matched the tested adapter. Package version remains 3.10.2.

## F1/F2/F3 repairs — source update

Per-Run OS exclusion covers stale owner recovery and the complete writer lifetime.
Reconnect distinguishes empty accepted output IDs from optional submission targets.
Legacy State sidecar fallback applies only to missing embedded metadata.
Sampling v6 / Graph v4, stored formats and workflow files are unchanged.
Windows owner checks also distinguish an exited process from a retained monitor
handle, while preserving unknown/alive owners. Full CPU/JavaScript regression:
2,267 passed, 2 skipped, zero failures and zero CUDA initialization attempts.
Review JavaScript: 95 cases passed; the same tests reproduce the empty-target
failure against the original source. Real State I/O: 10 cases passed.
Local runtime deployment matched all 516 source files. Installed CPU checks:
23 passed; installed Review JavaScript: 95 passed. After restart, twelve public
nodes and matching frontend source were confirmed. Chrome checks covered normal
Sampler display and existing Manager Project/trial/savepoint browsing, with
saved data and workflows unchanged. Take adoption/Continue execution and GPU
generation were not exercised. Package version remains 3.10.2; no new Release
or Registry submission accompanies this source update.

## Second Pass documentation — Issue #37

Current Second Pass guides: docs/SECOND_PASS_GUIDE.md and SECOND_PASS_GUIDE_JA.md.
Version scope is package 3.10.2 / V3.9; product code and registered schemas are
unchanged. README and user-guide links point to these source documents.
Documentation-only publication does not imply new browser/GPU acceptance,
a new Release, or inclusion in the existing 3.10.2 release assets. Existing Takes and
workflow files remain unchanged.

## 3.10.2 — Review history and regeneration hotfix

Protect finalized Take history through separate working storage revisions and
atomic status/provenance publication. Validate capped Review reachability,
preserve linked Run Storage intent, provide secure UUID fallback and keep
accepted Second Pass video on CPU. Sampling v6 / Graph v4, stored schemas and
official workflow bytes are unchanged. CPU/JavaScript: 2,248 passed / 2 skipped /
zero failures; zero CUDA initialization attempts. Offline twelve-node/native
layout checks passed. No new browser/GPU acceptance or runtime deployment.
Prepare the authorized GitHub-only hotfix; Registry resubmission remains held
pending the 3.10.0 manual review. See docs/RELEASE_NOTES_V3102.md.

## 3.10.1 — Project Manager refusal messages

Identify actual revision conflicts with `project_revision_conflict`; other
HTTP 409 refusals retain the server's specific reason. Refusal checks, retry
behavior, sampling contracts and saved schemas are unchanged.
CPU/JavaScript: 2,214 passed / 2 skipped / zero failures or expected failures,
zero CUDA initialization attempts. Manager subset: 66 pytest cases; 38 panel
JavaScript cases are included through wrappers, not added to the total.
Live Chrome/backend checks in English and Japanese distinguished actual revision
conflicts from duplicate Run attachment. The same repaired modules were deployed
for those checks before the version bump. All 184 protected data/settings files
and 21 official workflows retained their hashes. No new GPU generation.
Prepare package 3.10.1 for GitHub-only publication. The automatic release job has
no Registry build/upload. The separate manual 3.10.0 Registry workflow remains
unchanged and is not dispatched; resubmission is held pending manual review.
See docs/RELEASE_NOTES_V3101.md.

## 3.10.0 — Project / Take Manager V1.2

Optional default-OFF panel with independent management metadata. Named Projects,
trials and fixed Take endpoints prepare the original Review controls without
Queue submission. Sampling and storage identity contracts remain unchanged.
CPU/JavaScript: 2,210 passed / 2 skipped / zero failures; CUDA initialization attempts: zero.
This final full run includes the browser follow-up guard for reopening a
host-detached panel. All 24 actual-JavaScript panel cases pass; the Manager's
57 distinct JavaScript cases are included through pytest wrappers, not added
to the full-suite total.
Chrome dedicated-workflow save/reload and targeted four-Queue GPU acceptance
passed: Manager OFF Chunk 1, saved-prefix Chunk 2, alternate Chunk 2, independent
new-Run Chunk 1. Original raw/Takes were preserved; all four AV files decoded.
Manager V1.2 is prepared for publication in package 3.10.0. These are
targeted management checks, not general video-quality acceptance.
See docs/PROJECT_TAKE_MANAGER_V12.md and docs/RELEASE_NOTES_V3100.md.

## Unreleased — portable CPU regression tests

Pin memory probe values only in small assembly/buffer correctness tests. Explicit
low-memory and unavailable-counter tests still exercise the production guard.
Replace the test-time Git/HEAD lookup with a SHA-256-checked model-signature
fixture extracted from the actual v3.9.1 source, with commit/blob provenance.
ZIP-based test runs no longer need Git metadata. Product RAM safety, generation,
Take identity/storage and official workflows are unchanged. No new release.

Validation: the original snapshot reproduced 44 RAM-reserve failures and one
Git-metadata failure under a simulated 1 GiB memory probe without .git. The same
203 cases passed after this test-only repair. Full CPU/JavaScript regression in
an identical ZIP-extracted source copy: 2,148 passed / 2 skipped / zero failures;
CUDA initialization attempts: zero. Targeted results overlap the full total.



## 3.9.12 — Reference Plan Inspector refresh (2026-10-22)

Fix stale verified Reference Plan text after the Sampler UI is reconfigured,
including workflow save/reload. Changing Reference assignments now invalidates
the old Inspector display; the next backend result supplies the verified plan.
Refresh callbacks do not accumulate, and Inspector text is not saved as workflow data.

CPU/JavaScript: **2,148 passed / 2 skipped / 0 failures or expected failures**.
Chrome save/reload checks passed. After actual GPU sampling, unchecking the
Reference assignment changed the visible Inspector heading from **runtime verified**
to **Configured only — Queue has not verified...**, without another Queue.
The 140 protected existing files and all three files of the new Run remained
hash-identical. This is targeted UI acceptance, not video-quality acceptance.

Update through Manager or replace the existing custom-node package, then
**restart ComfyUI and hard-refresh the browser (Ctrl+F5)**. Existing Takes and
workflows can be kept; no rewiring, deletion or new Run is required for this UI fix.
[Validation conditions and limits](docs/RELEASE_NOTES_V3912.md).

## 3.9.11 — Spectrum code audit stability

Supplement the legacy code audit only for code-digest differences in the two
already-audited Spectrum implementations on Python 3.12/3.13. Preserve the old
provider metadata, persisted identity, safe Take reuse and unknown-code rejection.
CPU/JS: 2,139 passed / 2 skipped / 2 known Inspector expected failures. Targeted
Spectrum + Kitchen browser/GPU Review continuation passed with Chunk 1 preserved
and one reused / one new chunk. Existing workflows and stored Takes are unchanged.
Publication and asset integrity are verified separately; see docs/RELEASE_NOTES_V3911.md.

## 3.9.10 — Spectrum reuse and Reference assignment display

Normalize Spectrum CRLF source auditing and add fixed Python 3.12 profiles while
preserving the existing 3.13 profiles, valid Sampling v6 identities, old Takes
and official workflows. Correct the Reference assignment display for externally
connected Chunks without changing generation count or saved selectors.

Full local CPU/JS: 2,096 passed / 2 skipped / 2 known expected Inspector failures.
Python 3.12 component: 112 passed / 1 skip; 24 independent storage cases and
actual-JS checks passed. Reference browser checks passed. No new GPU acceptance
is claimed. Restart ComfyUI and refresh the browser; use a new Run for newly
supported configurations. See docs/RELEASE_NOTES_V3910.md.

## 3.9.9 — KJ Preview Override / Review continuation

Fix new-Run v6 read-only with the separately audited upstream KJ profile, and
show saved reasons when reuse is unavailable. Keep the original local profile,
Sampling v6 guards, old Takes and official workflow bytes.

CPU: **2,075 passed / 2 skipped / 2 known expected failures**, plus overlapping
90-case JS coverage. Upstream KJ GPU and normal-ComfyUI browser Continue both
passed: **Chunk 1 preserved, Chunk 2 generated, one reused / one new**; all four
AV outputs fully decoded. Browser checks used the existing local KJ profile.
These are targeted repair checks, not general quality or all-provider acceptance.

Restart ComfyUI and hard-refresh after updating. On Preview Override, disconnect
optional VAE/Audio VAE and set Tiny VAE `none`; retain generation VAEs. Correct
unsupported settings before starting a new Run. Old unsafe/v5 Takes remain
readable and are not automatically made reusable. No workflow rewiring or Take
deletion is required. [Full release notes](docs/RELEASE_NOTES_V399.md).


## V3.9 Turbo Sample on main

Add the user-supplied sample separately: Auto, 2 x 8s, multiline image-anchored
dance prompt, fixed background/camera, Thai rap and one enabled Turbo LoRA.
Preserve the supplied 6-step/Draft settings and document their unverified pairing
with the 4-step/768p LoRA. Fresh workflow/project IDs avoid user Run identity reuse;
remove misleading auto-download metadata for the saved custom model. Standard
workflows, existing Takes and runtime code stay unchanged. No new GPU validation,
runtime deployment, release or Registry publication is included.

Updated: 2026-10-16 (Japan time).

## Japanese README organization (documentation only)

The Japanese README follows the English quick-start structure. Japanese detail
and images remain in docs/USER_GUIDE_JA.md and docs/README_HISTORY_JA.md.
Downloads, model folders, provider links, history safety and limited acceptance
scope are retained. English documentation, runtime and published assets are unchanged.

## README organization (documentation only)

The English README is a compact entry point. Detailed operating instructions and
screenshots remain in docs/USER_GUIDE.md; release and older implementation notes
remain in docs/README_HISTORY.md. Version-specific acceptance statements retain
their historical context. Japanese README, product code, official workflows and
published v3.9.8 assets are unchanged; this is not a new runtime or release version.

## Published v3.9.8 GPU recheck (2026-10-16)

The exact published tag `58fbd855` was deployed and restarted in normal ComfyUI; all 464 release files and the live startup/adapter identity matched. Two new Runs / four Core-API Queues passed PyTorch/KJ and Kitchen INT8 + audited local Spectrum/KJ Chunk 1 to 2 continuation, unchanged prefix/contracts and complete AV decoding. Existing Takes/workflows stayed hash-identical. README and docs/RELEASE_NOTES_V398.md record conditions and unverified scope. The later documentation-only main commit does not replace the release tag, GitHub assets or Registry package.

## 3.9.8 — KJ Preview Override Phase A (2026-10-16)

A bounded adapter identifies the audited KJ Preview Override source and loaded helpers, preserves fixed settings and wrapper execution order, and excludes its reviewed transient image list. VAE/Audio VAE must be disconnected, KJ Tiny VAE must be `none`, and Core approximate-VAE preview is outside this phase. Unknown implementations remain non-reusable. Sampling v6, old Takes and official workflows are unchanged. Full real-Core CPU gate: 1,995 passed / 3 skipped / 2 existing Inspector expected failures / zero unexpected failures and CUDA initialization attempts; the 48 dedicated KJ tests passed without skips. Normal ComfyUI GPU acceptance passed four Core-API Queues: PyTorch and Comfy Kitchen INT8 + the audited local Spectrum implementation, each with separate-Queue Chunk 1 to 2 continuation and held preview images. Both second Queues reused one chunk and generated one; original Chunk 1 bytes and contracts were unchanged. All four video/audio outputs fully decoded. See docs/KJ_PREVIEW_OVERRIDE_V398.md for exact support and limits. Release and Registry state are verified separately.

## 3.9.7 — external-input regeneration cache

Fix automatic Full Run variations when Chunks or Variation Nonce come from external nodes. Unresolved linked inputs no longer let Core skip an explicitly requested regeneration. Earlier accepted chunks, existing Takes, public inputs and official workflows are preserved. Update the custom nodes, restart ComfyUI and refresh the browser; no workflow changes or history deletion are required. See docs/RELEASE_NOTES_V397.md for targeted validation and limits.

## 3.9.6 — regeneration selection and automatic variations

Package 3.9.6 preserves saved regeneration selections and routes explicit Full Run automatic variations through Run Storage on every Queue. The full CPU gate and targeted normal-runtime browser/GPU acceptance passed; scope and update steps are in docs/REGENERATE_INTENT_V396.md. Sampling v6 safety, public inputs, official workflows and stored Takes are preserved. Release assets and Registry service status are verified separately.

## 3.9.5 — Issue #31 Attention and Spectrum identity repair

Finite loaded-implementation signatures identify the Core PyTorch/Kitchen attention overrides and explicit Spectrum profiles, including upstream 0.2.29. Existing normal v6 contracts without the targeted override remain unchanged; original unsafe/v5 history and official workflows are preserved. Validation and compatibility limits are recorded in docs/ISSUE31_SAMPLING_SIGNATURES.md. GitHub assets and Registry service status are verified separately.

## GitHub and Registry publication status

**Latest package: 3.10.2.** Use the fixed-version GitHub downloads below. Registry publication is verified separately. Current patch validation is recorded in docs/RELEASE_NOTES_V3102.md.

| Version | Release | Custom-node ZIP | SHA-256 checksum |
| --- | --- | --- | --- |
| 3.10.2 | [Release](https://github.com/ukr8b3g-cmyk/ComfyUI-H3-Continuum/releases/tag/v3.10.2) | [ZIP](https://github.com/ukr8b3g-cmyk/ComfyUI-H3-Continuum/releases/download/v3.10.2/ComfyUI-H3-Continuum-v3.10.2.zip) | [SHA256SUMS.txt](https://github.com/ukr8b3g-cmyk/ComfyUI-H3-Continuum/releases/download/v3.10.2/SHA256SUMS.txt) |
| 3.10.1 | [Release](https://github.com/ukr8b3g-cmyk/ComfyUI-H3-Continuum/releases/tag/v3.10.1) | [ZIP](https://github.com/ukr8b3g-cmyk/ComfyUI-H3-Continuum/releases/download/v3.10.1/ComfyUI-H3-Continuum-v3.10.1.zip) | [SHA256SUMS.txt](https://github.com/ukr8b3g-cmyk/ComfyUI-H3-Continuum/releases/download/v3.10.1/SHA256SUMS.txt) |
| 3.10.0 | [Release](https://github.com/ukr8b3g-cmyk/ComfyUI-H3-Continuum/releases/tag/v3.10.0) | [ZIP](https://github.com/ukr8b3g-cmyk/ComfyUI-H3-Continuum/releases/download/v3.10.0/ComfyUI-H3-Continuum-v3.10.0.zip) | [SHA256SUMS.txt](https://github.com/ukr8b3g-cmyk/ComfyUI-H3-Continuum/releases/download/v3.10.0/SHA256SUMS.txt) |
| 3.9.12 | [Release](https://github.com/ukr8b3g-cmyk/ComfyUI-H3-Continuum/releases/tag/v3.9.12) | [ZIP](https://github.com/ukr8b3g-cmyk/ComfyUI-H3-Continuum/releases/download/v3.9.12/ComfyUI-H3-Continuum-v3.9.12.zip) | [SHA256SUMS.txt](https://github.com/ukr8b3g-cmyk/ComfyUI-H3-Continuum/releases/download/v3.9.12/SHA256SUMS.txt) |
| 3.9.8 | [Release](https://github.com/ukr8b3g-cmyk/ComfyUI-H3-Continuum/releases/tag/v3.9.8) | [ZIP](https://github.com/ukr8b3g-cmyk/ComfyUI-H3-Continuum/releases/download/v3.9.8/ComfyUI-H3-Continuum-v3.9.8.zip) | [SHA256SUMS.txt](https://github.com/ukr8b3g-cmyk/ComfyUI-H3-Continuum/releases/download/v3.9.8/SHA256SUMS.txt) |
| 3.9.7 | [Release](https://github.com/ukr8b3g-cmyk/ComfyUI-H3-Continuum/releases/tag/v3.9.7) | [ZIP](https://github.com/ukr8b3g-cmyk/ComfyUI-H3-Continuum/releases/download/v3.9.7/ComfyUI-H3-Continuum-v3.9.7.zip) | [SHA256SUMS.txt](https://github.com/ukr8b3g-cmyk/ComfyUI-H3-Continuum/releases/download/v3.9.7/SHA256SUMS.txt) |
| 3.9.6 | [Release](https://github.com/ukr8b3g-cmyk/ComfyUI-H3-Continuum/releases/tag/v3.9.6) | [ZIP](https://github.com/ukr8b3g-cmyk/ComfyUI-H3-Continuum/releases/download/v3.9.6/ComfyUI-H3-Continuum-v3.9.6.zip) | [SHA256SUMS.txt](https://github.com/ukr8b3g-cmyk/ComfyUI-H3-Continuum/releases/download/v3.9.6/SHA256SUMS.txt) |
| 3.9.5 | [Release](https://github.com/ukr8b3g-cmyk/ComfyUI-H3-Continuum/releases/tag/v3.9.5) | [ZIP](https://github.com/ukr8b3g-cmyk/ComfyUI-H3-Continuum/releases/download/v3.9.5/ComfyUI-H3-Continuum-v3.9.5.zip) | [SHA256SUMS.txt](https://github.com/ukr8b3g-cmyk/ComfyUI-H3-Continuum/releases/download/v3.9.5/SHA256SUMS.txt) |
| 3.9.4 | [Release](https://github.com/ukr8b3g-cmyk/ComfyUI-H3-Continuum/releases/tag/v3.9.4) | [ZIP](https://github.com/ukr8b3g-cmyk/ComfyUI-H3-Continuum/releases/download/v3.9.4/ComfyUI-H3-Continuum-v3.9.4.zip) | [SHA256SUMS.txt](https://github.com/ukr8b3g-cmyk/ComfyUI-H3-Continuum/releases/download/v3.9.4/SHA256SUMS.txt) |
| 3.9.3 | [Release](https://github.com/ukr8b3g-cmyk/ComfyUI-H3-Continuum/releases/tag/v3.9.3) | [ZIP](https://github.com/ukr8b3g-cmyk/ComfyUI-H3-Continuum/releases/download/v3.9.3/ComfyUI-H3-Continuum-v3.9.3.zip) | [SHA256SUMS.txt](https://github.com/ukr8b3g-cmyk/ComfyUI-H3-Continuum/releases/download/v3.9.3/SHA256SUMS.txt) |
| 3.9.2 | [Release](https://github.com/ukr8b3g-cmyk/ComfyUI-H3-Continuum/releases/tag/v3.9.2) | [ZIP](https://github.com/ukr8b3g-cmyk/ComfyUI-H3-Continuum/releases/download/v3.9.2/ComfyUI-H3-Continuum-v3.9.2.zip) | [SHA256SUMS.txt](https://github.com/ukr8b3g-cmyk/ComfyUI-H3-Continuum/releases/download/v3.9.2/SHA256SUMS.txt) |

The original [3.9.2 GitHub source archive](https://github.com/ukr8b3g-cmyk/ComfyUI-H3-Continuum/archive/refs/tags/v3.9.2.zip) remains available from its unchanged tag. This custom-node package ZIP is distinct from the official workflow ZIPs.

Registry 3.9.3 was uploaded; its retrieved ZIP omitted one declared document and included three undeclared prompt-authoring files. Package 3.9.4 corrects the file selection. Registry scan status is reported by the service; source publication alone does not establish scan approval.

## 3.9.4 — Registry packaging repair (2026-10-14)

Include the declared Review restoration guide and exclude repository-only prompt-authoring files from the Registry ZIP. The publishing workflow now builds the actual package and checks its exact file set, CRC and every Registry Manifest hash before uploading. Runtime behavior, twelve public node IDs, workflows and saved Runs/Takes are unchanged. GitHub Releases 3.9.3 and 3.9.2 remain available.

## Package 3.9.3 — temporary storage settings

The current source adds a server-side scratch folder setting for Finalize and Decode Cache, storage usage/free-space reporting and conservative unused-file cleanup. Manual buffer capacity checks retain the existing Auto policy. Node schemas, official workflow bytes, generation identity and saved Runs/Takes are preserved.

Frontend follow-up improves missing/empty-response diagnostics and storage candidate initialization. The Core request address/profile handling is retained, and no automatic mutation retries are added.

The new setting is available under Settings → H3Continuum → Storage. Validation and platform limitations are recorded in PACKAGE_VALIDATION.txt. Source publication does not imply a new GitHub Release/tag or Registry publication.

## Previous package 3.9.2 — Issue #30 frontend hotfix

This package includes three minimal frontend changes: skip Review snapshots without a comparison baseline, notify connected Samplers once per Reference selection, and skip unchanged node dimensions when resizing. Review baseline monitoring, synchronous Take/Queue checks and generation/storage contracts are retained; package metadata is 3.9.2.

CPU/JavaScript regression checks passed 1,703 cases, with 2 skips and 2 explicit expected failures for the separate Inspector reconfigure bug. Offline twelve-node/runtime checks, isolated Chromium checks and the actual Core/frontend/LiteGraph desktop smoke passed without GPU generation. The live smoke covers native assignment graph serialization/reload and upstream edit/restore using synthetic nodes; UI file-save and stored-Take acceptance remain separate. DOM rebuilds remain; real ComfyUI browser save/reload, mobile freeze resolution and full workflow acceptance are still pending. No delayed update timer is added. See GitHub Releases for the published version; Registry publication is separate.

## Previous package 3.9.1 — generation stability history

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
