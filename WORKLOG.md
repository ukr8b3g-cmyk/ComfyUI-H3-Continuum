# Public development log

## 2026-11-28 — Issue #42 GPU verification

Added an audited KJ Preview Override profile for Core 0.46.0 and 0.46.2. Disconnected the Turbo Sample’s preview VAE inputs. See the [release notes](docs/RELEASE_NOTES_V3104.md) for CPU, JavaScript and two-queue GPU results.

## 2026-11-18 — Review preflight and inactive reference slots

Reproduced the wired-seed Review stop and the stale, disconnected reference assignment on the previous main. Tested wired and unwired seeds, inactive selectors, and validation after reconnect. See the [3.10.3 release checks](docs/RELEASE_NOTES_V3103.md) for the CPU and GPU results.

## 2026-11-18 — Four local regression repairs

Correlate Reference Inspector results with their submitted prompt and handle
results that arrive before the Queue response. Exercise assignment edits,
overlapping submissions, graph replacement and nested execution IDs in the
JavaScript fixture. Cover duplicate Run refusals and real revision conflicts
in both Manager locales. Compare overlapping chunk selectors with valid
adjacent ranges and check that recovery edits only the selected image.
Exercise State and V2 Session loading with real CPU safetensors, malformed
JSON mirrors and invalid authoritative metadata.

## 2026-11-17 — KJ Preview Override profile update

Audit the exact audio-scale lookup source and its unchanged KJ and Core
dependencies. Admit it through a separate profile while retaining the earlier
profiles and the existing source, loaded-code and runtime-state checks. Cover
profile collisions, altered code, unsupported preview VAE settings, old
read-only history, and passthrough through the real wrapper on CPU. Existing
provider contracts and revision IDs match their previous values. JavaScript
Review checks also exercise the saved reusable and read-only Take data.

With an isolated GPU backend, generate Chunk 1 in Review Each Chunk, then
explicitly select its Take with Continue From Here. Both Takes are reusable
under Sampling v6. The second queue reuses Chunk 1 and generates only Chunk 2,
preserving the first raw payload's SHA-256. Both queues use the same KJ wrapper
and the original preview frames do not change its signature. The test uses
512×512, 24 fps, two 5-second chunks, Euler/simple at eight steps and PyTorch
attention. Both audio/video outputs decode fully. The installed variant uses
identical adapter/profile bytes, and its subsequent startup registers the
existing twelve Continuum nodes.

## 2026-10-29 — F1/F2/F3 repairs (source update)

Limit production changes to Run lock recovery/lifetime, reconnect accepted-target
filtering and legacy State metadata fallback. Keep the JSON owner marker and add
a stable per-Run OS guard; do not unify Manager/scratch lock policies. Preserve
old metadata-free states while rejecting corrupt embedded JSON. Review's normal
pre-submit empty-target behavior remains intact.
Targeted results: 40 lock/history/transaction CPU cases, 95 Review JS cases and
10 State I/O CPU cases passed. Windows process-exit coverage terminates the actual
owner recorded by the lock, including when Python starts through a venv launcher.
The real process-exit test exposed a Windows owner probe that counted exited PIDs
with retained handles as alive. Query exit status too; unknown status remains
protected. Lock/PID regression: 12 passed. Full CPU/JavaScript: 2,267 passed,
2 skipped, zero failures, zero CUDA initialization attempts. CPU registration
disables GPU availability probing only during Core import; real KJ and Spectrum
provider fixtures are configured. These checks do not validate GPU kernels.
Deploy the reviewed source to the existing local runtime: all 516 source files
matched, with 23 installed CPU checks and 95 Review JavaScript cases passed.
After the user's restart, confirm twelve public node registrations and matching
frontend source. Chrome checks cover normal Sampler display, existing Manager
Project/trial/savepoint browsing and the enabled preparation control without
applying it. Protected Run/Take, settings and workflow hashes remain unchanged.
Take adoption/Continue execution and GPU generation are not part of this browser
check. Publish source changes only; retain package version 3.10.2 and existing
Release/Registry artifacts.

## 2026-10-27 — Issue #37 Second Pass guide (documentation-only)

Check the registered Second Pass and V3.9 Sampler against existing documents.
Add bilingual diagrams and exact connections, list/physical-group requirements,
explicit Second Pass MODEL/LoRA choice, context validation/fallback, low-denoise
SIGMAS and external upscaling constraints. Update README entry points and old
V3.8-specific blanket restrictions. Publish the source documentation separately
from the existing 3.10.2 Release; verify public guide links before replying to
Issue #35. No product code, saved Takes or workflows change. No deployment,
Queue, new Release or Registry submission.
Targeted CPU regression: 63 passed, zero CUDA initialization attempts.
Sixteen guide links and two diagram structures checked; no browser rendering.
Source/Registry manifests matched; product code and workflow bytes unchanged.

## 2026-10-24 — Package 3.10.2 hotfix

Protect sealed Take history with copy-on-write storage revisions and atomic
finalization of status/provenance. Cover failures before/after a raw commit,
atomic seal failure, project-index failure and abrupt child-process exit.
Keep existing schema, signatures, raw references and immutable saved endpoints.
Add narrow reachability validation for capped Review, linked Run Storage intent
coverage, cryptographic Manager UUID fallback and CPU retention of refined video.
Preserve normal CPU object identity and exact First Pass audio passthrough.
This work does not refactor unrelated runtime paths or change official workflows.
Final CPU/JavaScript: 2,248 passed / 2 skipped / zero failures in 310.55 seconds.
CUDA initialization attempts: zero. Review Queue 90, linked-storage 42 and
Manager panel 46 JavaScript cases are included through pytest wrappers, not
added to that total. Offline twelve-node/native-layout checks passed.
GPU testing requires separate approval.
Prepare the authorized GitHub commit, push and hotfix Release with matching
metadata, bilingual README, release notes and the existing verified release job.
No runtime deployment. Registry resubmission remains held pending manual review.

## 2026-10-23 — Package 3.10.1: Manager refusal messages

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

## 2026-10-23 — Package 3.10.0 publication preparation

Prepare the authorized Manager V1.2 feature and illustrated bilingual README
for package 3.10.0, retaining V3.9 workflow identity and the 3.9.12 historical
release. Include the previously approved test portability repair; production
RAM guards stay unchanged. Align metadata, installation guidance and release
automation. Add Manager storage/API/JavaScript coverage to Windows CI. Existing
Takes, workflow bytes and safe reuse contracts remain unchanged. Publication
follows the final CPU gate, remote tree verification and successful CI.

Final versioned source gate: 2,210 passed / 2 skipped / zero failures in 290.86
seconds, with zero CUDA initialization attempts. Offline native-layout and
twelve-node registration passed. All 21 official workflow files and protected
existing Takes remain unchanged; six screenshots and source/package manifests
were checked before committing. Remote CI and publication are checked separately.

## 2026-10-23 — Illustrated Manager walkthrough

Add six actual Chrome screenshots and step-by-step English/Japanese README
instructions for enabling the panel, selecting a Sampler, creating a Project,
attaching a Run, naming a Take, preparing continuation, starting an independent
trial, archiving/restoring and resolving unavailable actions. Capture only
relevant UI regions, without local paths or model selections. Separate browsing,
preparation and Queue submission; describe savepoints as references, not backups
or whole-workflow restores. This documentation stage changes no product code,
stored Takes or existing workflow files, and submits no GPU Queue. No publication.

## 2026-10-23 — Manager V1.2 final regression and documentation

Freeze the candidate including the host-detached panel reopening repair. Full
CPU/JavaScript regression: 2,210 passed, two skips, no failures or expected
failures, one pytest import-rewrite warning; zero CUDA initialization attempts.
The 62 Manager pytest cases include 57 distinct actual-JavaScript cases through
wrappers; do not add those counts to the full-suite total. Document the separate
Chrome save/reload and four-Queue GPU acceptance already completed, its data
preservation evidence and its quality/performance limits. Update both READMEs,
the feature guide and unreleased release notes. Keep package version 3.9.12,
official workflows and tested product code unchanged. No commit or publication.

## Unreleased — Project / Take Manager V1.2 implementation

Implement the agreed optional right-side panel and separate per-Project metadata.
New trials receive an independent Run identity, savepoints pin existing ancestry,
and preparation delegates to the existing Review selection. No Queue wrapper,
new node, Run marker or sampling/storage implementation change is introduced.
Preserve prior test portability work. Fixed-source CPU/JavaScript regression:
2,210 passed / 2 skipped / zero failures; CUDA initialization attempts: zero.
Manager coverage includes 62 pytest cases and 56 distinct actual-JS cases
(the JS cases run inside pytest and are not added to its total). Earlier test-count
failures during fixture additions were corrected before this fixed-source run.
Browser follow-up: guard reopening when a host removes the panel DOM without
its Close callback. Preserve cancellation of obsolete asynchronous work. The
panel's actual-JS gate now has 24 passing cases; the earlier full count above
predates this follow-up and is not a new full-suite result for that guard.

Chrome: dedicated workflow imported, saved and reloaded; default OFF, panel,
target Sampler, named Project, attached Run, fixed Chunk 1 savepoint and new
independent trial were operated through visible controls. Targeted GPU: four
successful Queues at 512x512, 24 fps, two 5-second chunks, 8-step Euler/simple,
Comfy Kitchen, Turbo model-only LoRA, no Spectrum/KJ override/Second Pass.
Chunk 1 raw SHA-256 was unchanged; Chunk 2 variations 1 and 2 and all old Takes
were retained. A fresh UUID with empty Run Name began at Chunk 1. Four MP4s
fully decoded with matching AV durations of 5/10/10/5 seconds. Existing Takes
and workflows were unchanged; only the explicit Manager enable preference and
new dedicated test assets were added. Queue empty; no commit, push or release.
These are functional management checks, not broad quality/performance acceptance.

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

## 3.9.11 — Spectrum loaded-code audit stability

Retain the legacy marshal audit and its four metadata files. If only function
code digests differ, compare complete loaded descriptors using fixed typed-code
profiles for Python 3.12/3.13 and the two already-audited provider source sets.
Validate profile provenance against the original metadata digest and full source
set; do not generate profiles, import providers or learn identities at runtime.
The supplemental audit never enters the stored contract. Preserve safe v6 Take
reuse and unsafe/v5 read-only history, with no workflow or storage migration.
Targeted browser/GPU checks passed with audited local Spectrum + Kitchen
Attention: enabled Review buttons, Chunk 1 retained, Chunk 2 generated, one
reused / one new; both AV outputs fully decoded. Generation completed without
execution errors or OOM. Separate third-party MP4 menu-thumbnail HTTP errors
were avoided by disabling Show Image On Menu, without product code changes.
See docs/RELEASE_NOTES_V3911.md for exact scope and remaining limits.

Full CPU/JS gate: 2,139 passed / 2 skipped / 2 existing Inspector expected failures,
with zero unexpected failures or CUDA initialization attempts. Python 3.12
component checks: 155 passed / 1 skip, excluding 21 tests tied to the older
Core's independent Attention limitation. Real-Core observer/storage fixtures
matched 53 expected reuse/refusal decisions and the production JS predicate.
Four normal pre-repair v6 Takes retained full contracts and reused Chunk 1;
unsafe/v5 histories stayed read-only. Both supplemental profiles reproduced
byte-for-byte with reverse import order. Compile/offline registration passed.

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


## 2026-10-16 — V3.9 Turbo Sample

Add the user-supplied sample separately: Auto, 2 x 8s, multiline image-anchored
dance prompt, fixed background/camera, Thai rap and one enabled Turbo LoRA.
Preserve the supplied 6-step/Draft settings and document their unverified pairing
with the 4-step/768p LoRA. Fresh workflow/project IDs avoid user Run identity reuse;
remove misleading auto-download metadata for the saved custom model. Standard
workflows, existing Takes and runtime code stay unchanged. No new GPU validation,
runtime deployment, release or Registry publication is included.
Local CPU checks: 17 passed, zero CUDA initialization attempts. Workflow link
consistency, gallery/ZIP bytes, saved settings and both manifests were checked.

## 2026-10-16 — Japanese README organization

Align the Japanese README with the compact English entry point, including exact
model/VAE/text-encoder downloads, model folders, external node links and optional
Turbo guidance. Keep current compatibility and known limitations explicit.
Move all former Japanese detail and ten image references into USER_GUIDE_JA.md
and README_HISTORY_JA.md, preserving historical context and rebasing links.
Include these text guides in the Registry selection and update both manifests.
English documentation, product code, images, official workflows and existing
Runs/Takes remain unchanged. This is local documentation work, not a new release.

Local checks: 5 existing tests passed, 95 relative file/heading links resolved,
all ten original image references and original detailed text were retained, and
both manifests matched (464 source entries / 162 Registry entries). The Japanese
README is 247 lines instead of 801. Its 18 external destinations match English.
No CUDA initialization, runtime deployment, commit or push was performed.

## 2026-10-16 — condensed README and retained reference material

Organize the English README as a short installation and operation entry point.
Keep the version heading, fixed-version downloads, getting-started video, Review /
regeneration steps, history safety and bounded v3.9.8 compatibility/known limits.
Move the former detailed controls and screenshots into docs/USER_GUIDE.md, and
release/legacy implementation material into docs/README_HISTORY.md; retain all
original sections and image assets, with rebased links and historical context.
Follow-up: list the template-selected H3 diffusion model, text encoder, Video/Audio
VAEs with provider downloads and ComfyUI model folders. Link Spectrum, KJNodes,
rgthree and optional task-matched LightX2V Turbo LoRAs. Explain the saved INT8
Video VAE versus old FP16 download metadata without altering workflow bytes.

Include the two text references in the Registry selection and update both source
manifests. Product code, Japanese README, official workflows, stored Takes,
release tags/assets and runtime deployment are unchanged by this documentation work.

Local documentation checks: 5 existing tests passed; all 143 relative file/heading
links resolved, all 39 original image references were retained, and both manifests
matched (462 source entries / 160 Registry entries). README is 267 lines, down
from 1,574. No code, workflow, image or Japanese README changes were made.

## 2026-10-16 — published v3.9.8 GPU recheck documentation

Record a fresh GPU recheck after deploying and restarting the exact published tag `58fbd855`: PyTorch/KJ and Comfy Kitchen INT8 + audited local Spectrum/KJ each passed separate-Queue Chunk 1 to 2 continuation. KJ retained images, contracts and original Chunk 1 stayed equal, and all four AV outputs decoded. Existing Takes/workflows were hash-protected. README and Release notes distinguish this published-tag result from the earlier candidate gate and retain exact provider/no-preview-VAE/Tiny-none scope plus browser, quality and performance limits. This is a documentation-only main update; the original v3.9.8 tag and package assets remain unchanged.

## 2026-10-16 — package 3.9.8 / KJ Preview Override Phase A

- Audit the actual KJ Preview Override file, SHA-256 `d07c8e5ff7d7abd3e31acefe2cf29f618b5da5341b3b434e72ec2ac0953230b0`, rather than accepting KJNodes 1.5.2 by version alone. Pin sibling helpers and Core preview/dispatcher source, then compare loaded code/defaults/classes without importing or executing the provider during observation.
- Add a dedicated adapter only at `outer_sample/kj_preview_override`. Preserve all fixed wrapper settings and Core's key/list order. Ignore only the exact builtin transient `frames` list after the provider audit; preserve the generic no-KJ observer and all other reuse guards.
- CPU scope covers real-provider frame changes, reconstruction, fixed-setting/order changes, monkeypatch/source rejection, VAE/Tiny VAE exclusion, combined Attention/Spectrum identities, saved prefix bytes and old unsafe history. Full real-Core CPU gate: 1,995 passed / 3 skipped / 2 existing Inspector expected failures / zero unexpected failures and CUDA initialization attempts; the 48 dedicated KJ tests passed without skips. Normal ComfyUI GPU acceptance passed four Core-API Queues: PyTorch and Comfy Kitchen INT8 + the audited local Spectrum implementation, each with separate-Queue Chunk 1 to 2 continuation and held preview images. Both second Queues reused one chunk and generated one; original Chunk 1 bytes and contracts were unchanged. All four video/audio outputs fully decoded. See docs/KJ_PREVIEW_OVERRIDE_V398.md for exact support and limits. GitHub main/tag CI, Release asset integrity and Registry status are separate publication checks.

## 2026-10-15 — package 3.9.7 / linked-input regeneration cache

- Keep Full Run automatic variations reachable when Core leaves linked Chunks, Nonce, storage, regeneration boundary or generation mode unresolved during cache-key evaluation.
- Validate the actual chunk range at execution, and retain stable caching for known ordinary Full Run, storage OFF and directly specified fixed nonces. An unresolved external nonce conservatively reevaluates the node; Run Storage still owns prefix reuse.
- Keep Sampling Contract v6, Take protection, public schemas and official workflows unchanged. Add direct-input and real-Core cache regressions for both V3.8 and V3.9.

## 2026-10-15 — package 3.9.6 / regeneration intent and automatic variations

- Separate saved manual regeneration intent from the legacy stale Chunk 1 / nonce 0 state. Retain earlier unmarked later-chunk/fixed-nonce settings, and clear intent metadata when Auto or a one-shot restart consumes it. No widget order or API inputs change.
- Bypass Core output caching only for Full Run explicit regeneration with Run Storage on and automatic nonce 0. Run Storage remains the authority for compatible prefixes, interrupted variations and new completed variations; its Sampling v6 checks are unchanged.
- Add restored-workflow Queue cases for both public Samplers and a CPU-only real-Core cache lookup gate. Keep historical unsafe/v5 Takes read-only and official workflow bytes unchanged. Full CPU gate: 1,908 passed / 2 skipped / 2 known Inspector expected failures; zero unexpected failures and CUDA initialization attempts. Normal ComfyUI browser save/reload retained Chunk 2 / nonce 5 and Chunk 1 / nonce 0 after history loading. Five new-Run GPU queues passed continuation, Chunk 2 regeneration and two identical Full Run / nonce 0 submissions; earlier Chunk 1 bytes were preserved. GPU scope: PyTorch, Spectrum OFF, 512x512, 8-step Turbo; all five media outputs fully decoded. See docs/REGENERATE_INTENT_V396.md. GitHub main/tag CI, Release asset integrity and Registry status are verified separately during publication.

## 2026-10-15 — package 3.9.5 / Issue #31 publication

Main Linux/Windows CI passed. Correct the tag-presence probe to branch on the API exit status: a missing-ref error body must not be treated as an existing commit SHA. Product code and accepted GPU signatures are unchanged.

Consolidate the Attention fix and finite Spectrum binding adapter on the exact 3.9.4 public source tree. Add a separate audited upstream Spectrum 0.2.29 profile without changing existing local-provider identities. Keep old unsafe history, public node IDs, contracts and all official workflows. CPU/GPU and publication checks are recorded separately in docs/ISSUE31_SAMPLING_SIGNATURES.md.

## 2026-10-14 — Issue #31 Phase 1, unpublished

- Final standard CPU validation: 1,777 passed / 1 skipped / 2 existing Inspector expected failures; no failures. All three standard commands recorded zero CUDA initialization attempts. Native PackedLayout, prompt planning and twelve-node registration checks passed.
- Limit production edits to the MODEL attention signature adapter in run_storage.py. Use already-loaded Core registries and implementation bindings; never import Core/Kitchen or execute an attention kernel during observation.
- Include both container functions and provider implementations/state without persistent addresses. Keep unrelated v6 signatures and every existing reuse guard; do not rewrite old unsafe manifests or raw files.
- Add real-Core CPU signature, clone/recreation, separate-process/hash-seed, mutation detection, prefix reuse and history immutability regressions. Kernel registration in CPU fixtures is structural evidence, not INT8 execution acceptance.
- GPU Review continuity, Spectrum/KJ execution, browser behavior and reporter-exact reproduction remain separate. No public node, official workflow, installed runtime, package version, commit or release changes.

## 2026-10-14 — package 3.9.4 Registry packaging repair

- Reconcile the actual Registry ZIP with its declared Manifest: include the Review restoration guide and exclude prompt-authoring source files.
- Add an exact archive file-set, CRC and hash gate before Registry upload using the same pinned publishing CLI. Preserve runtime code, public node IDs, workflows and saved data.
- Publish 3.9.4 as a separate version; keep prior GitHub tags and assets unchanged. Registry scan approval and real Manager installation remain independent of upload success.


## 2026-10-13 - 3.9.3 storage panel failure handling

- Reproduce the initial panel failure with an empty HTTP 404. Startup logs identified a stale process retaining the configured address/port while the updated backend failed to bind; the new frontend could still be served from updated files.
- Keep Core's request address, base path and user/auth handling. Add explicit HTTP/invalid-response guidance, an initialized full-width storage candidate field, safe disabled mutation controls and manual recovery without reloading the page. Do not retry save or cleanup automatically.
- Keep the backend and generation contracts unchanged. Core 0.39.0 CPU regression passed 1,740 cases with 2 skips and 2 existing expected Inspector failures; CUDA attempts were zero. The frontend 1.53.10 browser gate passed empty-response diagnostics, manual recovery, save and cleanup at an alternate host/port. See PACKAGE_VALIDATION.txt for scope.

## 2026-10-13 — package 3.9.3 temporary storage

- Re-review the scratch storage proposal against actual Finalize, Decode Cache and Core settings lifecycles. Implement server-side settings with revision checks, queue coordination, immutable directory identities and no silent disk fallback.
- Add read-only status and explicit cleanup paths. Preserve live aliases and unknown owners; track detached helper disk entries using only metadata and weak leases.
- Add a ComfyUI settings panel without draw-loop scans or periodic polling. Keep existing workflow controls and node registration.
- Add CPU, real HTTP and filesystem regressions plus a Windows-focused CI storage gate. The real-Core CPU candidate passed 1,740 cases with 2 skips and the 2 existing Inspector expected failures, without CUDA initialization. Standard compile/runtime and actual Core/frontend settings save/reload/cleanup checks passed. All 25 JSON/ZIP assets retain their bytes; see PACKAGE_VALIDATION.txt for scope and platform limits.

## 2026-10-13 — Issue #30 frontend hotfix, package 3.9.2

- Limit production changes to baseline-free Review snapshot skipping, one Reference selection notification per connected Sampler, and dimension checks before resizing the Reference helper. Align package metadata and current public guidance with 3.9.2; retain 3.9.1 records as history.
- Keep Review drawing-time upstream monitoring when a baseline exists and fresh synchronous Take/Queue checks. Preserve native callbacks, immediate saved assignment values, public widget/socket order and official workflow bytes.
- Add frontend regression coverage for upstream widget/link edits, rapid Reference selections, All/Off with future assignments, helper reconfiguration and independent helpers/Samplers. Track the independent Inspector reconfigure bug at 2 and 100 passes with explicit expected failures; one-pass refresh must succeed.
- Browser checks use isolated Chromium DOM and graph fixtures without generation. Full ComfyUI canvas, mobile performance and live workflow acceptance remain separate checks.
- Validation: 1,703 CPU/JavaScript regression cases passed, 2 skipped and 2 expected failures for the independent Inspector bug; zero CUDA initialization attempts. Offline runtime planning and twelve-node registration passed. In isolated Chromium, 600 baseline-free draw callbacks made zero snapshots (previously 600); 30 connected Reference checks notified the Sampler 30 times (previously 60), with zero same-dimension resize calls (previously 30). DOM rebuilds remain, and mobile freeze resolution is unconfirmed.

- Final 3.9.2 candidate CPU gate passed 1,703 cases with 2 skips and 2 explicit Inspector expected failures. The actual Core/frontend/LiteGraph browser smoke passed checkbox interactions, Prompt/link/Bypass edit/restore and native assignment graph reload without submitting a prompt. This desktop headless/model-free check is separate from UI file-save, mobile hardware and stored-Take acceptance.

## 2026-10-04 — V3.9 stability patch, package 3.9.1

- Preserve Second Pass audio/mixed-keyframe conditions and inherit the conditioning and References belonging to the selected Review output.
- Strengthen Take compatibility with Sampling Contract v6 / Graph Contract v4. Retain old v5 history without adopting its prefixes into new generation.
- Align Review Driving Audio with the original physical-group time range. Prefer Core audio resampling and document the same-object VAE mutation/cache limitation.
- Keep public V3.9 node IDs, official workflows and stored State/Session formats unchanged. LoRA Plan is not part of this patch.
- Full CPU validation: 1,696 passed / 1 skipped / no failures, with zero CUDA initialization attempts. Offline layout/planning and twelve-node registration passed.
- Targeted Review Second Pass and integrated generation/reuse GPU checks passed. Browser acceptance remains pending; optional latent-upscale artifacts remain a separate issue.
- Put the patch summary and v5-to-v6 restart instructions at the beginning of both language READMEs.
- Replace workstation paths and private operational history in public documentation with portable instructions and public validation summaries. Original development records are preserved outside the publication checkout.
- Mark the eighteen real-Core integration cases as dependency skips in standalone CI when ComfyUI Core is absent. They still execute with Core installed; broken Core dependencies remain test failures. Production code is unchanged.
- Release-preparation checks for the affected tests and package metadata: 66 passed with real Core; 48 passed / 18 dependency skips without Core. Both CPU gates had zero CUDA initialization attempts.
- GitHub Actions confirmed 1,676 passed / 21 skipped / no failures in standalone CI. Eighteen skips require real Core; the remaining three reflect existing platform/fixture limits. Prepare the versioned GitHub Release with English/Japanese repair and migration notes; Registry publication remains separate.
- Reconcile PACKAGE_VALIDATION.txt, PACKAGE_INFO_JA.txt and docs/VALIDATION_JA.md with package 3.9.1, the actual CPU/CI scopes, v5 migration and Release status. Retain the original V3.9.0/V2 text under explicit historical sections. Documentation corrections follow the fixed v3.9.1 release tag on main; runtime and official workflow bytes are unchanged.

Earlier product behavior is described in CHANGELOG.md and the historical Release/tag versions. This log contains public engineering summaries rather than private operational records.


## 2026-10-13 — Prepare 3.9.3 versioned downloads

- Add 3.9.3 and retained 3.9.2 Release, custom-node ZIP and checksum links to the current English/Japanese guides. Update the installation heading to 3.9.3 and retain the implemented settings screenshot and historical validation records.
- Refresh Registry then development manifests from saved bytes. The existing release-metadata/public-surface CPU gate passes 8 tests with zero CUDA initialization attempts; all 25 tracked JSON/ZIP assets retain their bytes.
- Product code, package metadata, public schemas and saved-data contracts are unchanged. GitHub Release/asset and Registry publication are verified separately; no new GPU, long-form performance or physical SSD-write validation is claimed.


## 2026-10-15 — Issue #31 Spectrum binding identity candidate

Added a dedicated, fail-closed Spectrum binding adapter without changing the generic observer, Sampling v6, runtime signature v1, Graph v4, public nodes, workflows or package version. The immutable config fields and audited source/loaded-callable contract identify generation; reviewed runtime history, counters and profile caches do not change persistent identity. Unsupported structures, additional attributes and altered implementations remain non-reusable. Existing unsafe Takes are preserved without migration. CPU and GPU evidence are recorded separately; no commit or publication is authorized.


Issue #31 Phase 3 validation: the final standard CPU entry point passed 1,834 tests, 1 skip and 2 existing expected Inspector failures, with zero CUDA initialization attempts. The 57 new Spectrum tests cover all 27 config fields, transient-state/process stability, implementation/extra-state refusal, unaffected v6 contract identity and old unsafe Take protection; the 36 Phase 1 attention tests also pass. Under one audited local provider implementation, both PyTorch+Spectrum and Kitchen+Spectrum persisted new Chunk 1 Takes and reused them from a separate Queue to generate Chunk 2, with unchanged prefix hashes, identical safe contracts and fully decodable 10-second AV output. This is a targeted local GPU gate, not acceptance of other providers, KJ, browser behavior, subjective quality or benchmarks. No commit, push or publication occurred.


## 2026-10-20 — External Chunks Reference assignment table candidate

Only the V3.9 Reference Images helper presentation changes: external Chunks links make the destination count unresolved, expose assignment range 1–16, and label All/Off with that range. Direct counts retain the existing table. The frontend does not resolve arbitrary upstream values or alter native Chunks, saved selectors, Sampling identity or stored Takes. Added 21 JavaScript cases and four public-input CPU cases cover stale widget counts, zero/unrestored links, multiple Samplers, range actions, future assignments and callback stability. Existing CPU coverage passed 310 tests with two known Inspector expected failures; the four added CPU cases and metadata checks also pass. Targeted browser acceptance passed for external INT with stale widget values, live disconnection/restoration, actual KJ Set/Get routing, all-page All/Off actions, saving/reloading and workflow tab switching. The candidate display code was deployed to the chosen runtime and reloaded without restarting its backend. Existing saved Takes and workflows were preserved. No GPU generation, commit, push or public release occurred.

## 2026-10-20 — Spectrum source/runtime audit portability candidate

Normalize CRLF to LF in Spectrum provider-file and module-closure source checks. Add fixed Python 3.12 profiles generated from the same hash-verified 44-file and upstream 0.2.29 55-file sources. Retain the original Python 3.13 profile bytes and valid identity descriptors. Unknown code, file sets, closures and runtime extensions remain non-reusable; unsupported Python runtimes are not promoted. Old unsafe/v5 Takes remain readable without conversion, and public nodes, Sampling v6, Graph v4 and official workflows are unchanged.

The full standard CPU/JS gate passed 2,096 tests with two skips and two existing Inspector expected failures; compile and offline runtime verification passed with twelve public nodes. Targeted Spectrum/Attention coverage passed 169 tests with one legacy-profile skip. Python 3.12 component coverage passed 112 tests with one legacy-profile skip, checking all 27 configuration fields, code/state refusal and newline parity; 21 independent older-Core/Attention cases were outside that component gate. Separate-process storage checks passed 16 PyTorch/Kitchen cases on Python 3.13 and eight Spectrum/default-model cases on Python 3.12. Actual Take read-only JavaScript agreed with all 24 storage results, and all six previously valid complete Sampling Contracts remained identical. No CUDA initialization, new GPU generation, browser acceptance, commit, push or publication is claimed. The older Core/Kitchen observation limitation remains separate from Spectrum recognition.

## 2026-10-20 — 3.9.10 publication preparation

Prepare the tested Spectrum audit portability and Reference assignment display
repairs as the next 3.9 patch. Use SemVer 3.9.10 for GitHub and Registry while
reserving 4.0 for the major update. Preserve existing 3.9.9 and historical tags,
assets and official workflow bytes. Publish CPU/browser scope explicitly without
claiming new GPU acceptance. Version metadata, release workflows and package
manifests identify the same candidate; public asset and CI checks follow upload.
