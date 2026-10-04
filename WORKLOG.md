# Public development log

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
