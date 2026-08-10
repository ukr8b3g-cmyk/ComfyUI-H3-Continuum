# Future roadmap after V2

V2 is the integrated production path. Future changes must preserve V1/V2 schemas and remain optional.

Possible additions:

- streaming decode/save that does not retain the complete final IMAGE tensor;
- interactive per-chunk approval UI with a frontend timeline;
- persisted multiple child branches and branch comparison;
- richer identity diagnostics using optional external encoders;
- adaptive Spectrum seam policy only if Spectrum exposes a stable public hook;
- reference-video / Ref2VA identity-memory mode;
- multi-resolution continuation through explicit regeneration, never silent resize;
- batch-independent server/API orchestration.

These are not promises for a specific release. The current V2 avoids private accelerator APIs so updates remain maintainable.
