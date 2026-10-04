# Contributor rules

## Scope

MiniMax H3 Continuum for ComfyUI. Package 3.9.1 provides the V3.9 Sampler and Reference Images helper, while retaining the separate V3.8X2 workflow. Source publication does not imply a GitHub Release or Registry package publication.

Sampling Contract v6 and Graph Contract v4 apply to new generation. Keep original v5 history readable, without reusing its Takes in v6 generation or rewriting stored manifests. Public node IDs, socket/widget order, official workflows, Run Storage v3 and State/Session formats remain unchanged.

## Product and data contracts

- Keep normal generation, Review, retry, continuation and finalization discoverable. Advanced controls must not rewrite hidden values or generation identity.
- Follow ComfyUI Core validation. Do not reject prompts, unknown models, wrappers or merged models solely because they are unknown. Unrecognized prompt syntax falls back to Fixed and passes through as entered.
- Keep legacy strict_compatibility inputs loadable but ignore their values. Warnings remain diagnostic unless an unusable internal payload or corrupted data makes execution impossible.
- Preserve accepted chunks and prior Takes. State and Session remain safetensors plus JSON, written atomically.
- Keep full accepted chunk latents on CPU. Do not accumulate generated chunks in VRAM or decode Video/Audio VAE between chunks.
- Preserve native PackedLayout behavior and position_ids identity. Never silently resize continuation State or Session.
- Keep Reference conditioning, First/Last Image, Driving Audio and generated Audio contracts separate. Second Pass must preserve First Pass audio when the selected path requires passthrough.
- Keep SageAttention, Sol-Attn and Spectrum external and use their public wrappers. Do not replace Core classes globally or import private Spectrum runtime functions.
- UI nodes delegate to reusable modules. Preserve legacy implementation modules while current registered nodes import or inherit them.
- Main UI disclosure is presentation-only. It must not change backend kwargs, Sampling Contract or Run Storage identity.
- Keep standard Core display titles in public examples so users can identify node providers.
- Experimental changes default OFF and must not change Production behavior. Still Image Guide and deferred continuation interventions remain outside accepted Production scope.
- Keep V3.8X2 and V3.9 as distinct workflows. Do not automatically migrate historical node IDs, workflows, Runs or Takes.
- Keep the shipped workflow JSON/ZIP files byte-for-byte unless a workflow change is explicitly requested.

## Validation and contribution

- Preserve unrelated work and take a verified snapshot before changes. The snapshot destination is configurable through tools/snapshot.ps1.
- Reuse the existing pytest configuration, tests and runtime verifier. Distinguish CPU checks, offline registration, live loading, browser acceptance and GPU results.
- Runtime checks record prompts, media, model/LoRA/sampler settings, dimensions, chunk timings and observed results. Check saved workflow metadata when available.
- Verify all hashes declared by MANIFEST.sha256 and REGISTRY_MANIFEST.sha256 after modifying their payloads.
- Current public registration contains twelve nodes. Do not register experimental implementations implicitly.
- Do not claim whole-release acceptance from a targeted repair test. Browser save/reload and the unchanged default workflow remain separate acceptance checks.
- Keep machine-specific paths, credentials, service addresses, process identifiers and private operational records out of public documentation.
- Record public behavior and version history in CHANGELOG.md and WORKLOG.md. PROJECT_STATE.md describes the public source status.
- Commit and publish only when explicitly requested. Release/tag/Registry publication is a separate action.

Run the standard validation entry point from the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File tools/validate.ps1
```
