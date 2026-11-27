# KJ Model Preview Override continuation — 3.9.8 / Phase A

The audited Preview Override wrapper can keep its transient image list without changing the MODEL sampling identity. The adapter retains fixed settings, source and loaded implementation checks, the complete audit-profile digest, and Core's cross-key/list wrapper execution order. It does not add a generic exception for any field named `frames`.

## Core 0.46.0 and 0.46.2

The audio-scale KJ provider also supports the exact Core preview source shared by these two tags, with the audited dispatcher. The distinct profile preserves the original sampling identity on older Core. Phase A preview settings still apply.

## Audio-scale lookup provider

The adapter additionally recognizes the exact Preview Override source
with LF-normalized SHA-256
`23f497938135ce5428190bdfcaebbeb9fc67294e0e9b3c37f283bad640d81929`.
Its profile is `kj-preview-audio-scale-23f4979-phase-a`, stored in
`preview_override_provider_audio_scale_v1.json`. This identifies file contents,
not a blanket KJNodes version range or a newly verified upstream release.

Compared with the audited public provider below, only the wrapper's audio-scale
lookup changes: it reads `model_sampling.audio_scale` through
`ModelPatcher.get_model_object`, including object patches. A missing scale disables
audio preview. The four sibling/Core file hashes remain exactly as listed below.
The scale affects optional preview audio; this profile still requires preview
VAE/Audio VAE to be absent and Tiny VAE to be `none`.

The two older JSON profiles and their successful descriptors remain unchanged.
The extra profile is optional: missing, malformed or colliding data does not
replace either older profile. Full source, loaded code, defaults, class/state,
dependency and setting checks still apply; unknown implementations remain
non-reusable. No generation, storage-format or workflow change is included.

Use a new Run for this newly recognized implementation. Previously saved unsafe
or v5 Takes remain readable and are not promoted, rewritten or deleted. A profile
change is retained in the sampling identity; adding support does not merge
different implementations into one identity.

The development log records CPU and JavaScript checks and two targeted GPU
queues for this profile. They confirm Review saves a reusable first Take and
Continue From Here preserves Chunk 1 while generating Chunk 2.

日本語：音声プレビュー倍率をobject patch経由で取得する上記SHA-256の実装だけを追加対象にします。
既存2種の署名・保存Take・Workflowは保持し、未知コードや未対応のプレビューVAE設定の拒否は維持します。
確認には新規Runを使用してください。旧read-only Takeの扱いは維持されます。対象のGPU検証ではChunk 1を保持し、Chunk 2だけを生成できました。

## 3.9.9 public-provider repair

The source checkout additionally accepts the pinned upstream implementation from
[KJNodes commit 17195fc](https://github.com/kijai/ComfyUI-KJNodes/blob/17195fcfa8a05f601b766a0f09c9733284f47416/nodes/preview_override_node.py).
Its LF-normalized Preview Override SHA-256 is
`1916295463eb790d3e8ea2b0dae2b25344549479b92e90a1d238acddb2dde3ab`,
profile `kj-preview-upstream-17195fc-phase-a` in
`preview_override_provider_public_v1.json` (canonical profile SHA-256
`da128a4324d8e0a63d893501f8d65652d25da60690afaf1447d80f2a2b67617f`). Its sibling and Core hashes are the
same as the original table below. The wrapper implementation is unchanged; the
node factory additionally resolves display IDs through Core's DynamicPrompt.
Both source and loaded-code audits remain required. This does not cover arbitrary
KJNodes versions, future Core changes or preview-VAE configurations.

The original profile JSON and successful descriptors are preserved. Profile
registration alone cannot invalidate another profile's Takes. KJ-free contracts
are unchanged. Missing or malformed optional public-profile data disables only
that profile. Ordinary generation keeps its existing fallback.

Review and Render History distinguish v5 history from v6 Takes whose generation
conditions could not be verified. Bounded saved reasons identify unsupported
preview settings or implementations; missing metadata points to Detailed Report.
Reasons come from the selected Take's storage revision and do not affect its
sampling identity or enable disabled actions.

For an unsupported KJ/Core implementation, bypass **Model Preview Override** in a
workflow copy and test a new Run. For unsupported preview VAE settings, disconnect
only that preview node's optional VAE/Audio VAE and use Tiny VAE `none`; keep the
generation VAEs connected. For Core approximate-VAE preview, use Auto or
Latent2RGB. Correct the configuration before starting a new Run: repeatedly
restarting Chunk 1 with the same unsupported setup will not repair it.
Old unsafe/v5 Takes remain readable and are never promoted or rewritten.

Full real-Core CPU regression: **2,075 passed, 2 skipped, 2 known Inspector
expected failures, zero unexpected failures**. The 90-case production-JS fixture
also passed with eight real Run Storage project vectors. These checks overlap
the pytest total and must not be added together. Unmodified 3.9.8 fixtures confirm
exact legacy/KJ-free identities and byte-identical saved Takes; all 21 existing
workflow JSON/ZIP files are unchanged. Offline registration retains twelve nodes
and passes native PackedLayout / Fixed 3x5s checks. Recorded CPU drivers attempted
zero CUDA initializations. The skips cover a local-only Spectrum descriptor
fixture on upstream Spectrum and an unavailable historical V3.5 workflow.

The additional public profile passed two targeted H3 GPU Queues with cached
preview images and unchanged Chunk 1. Normal-ComfyUI browser Continue passed
separately with the retained original local profile. See
[3.9.9 validation and limits](RELEASE_NOTES_V399.md). The historical v3.9.8 tag
and assets retain their original local-only profile.

## Exact supported profile

The published v3.9.8 package accepts only the following explicitly audited source combination. KJNodes reports 1.5.2, but that version alone does not identify the supported implementation: this Preview Override file differs from upstream. The 3.9.9 extension is described above. Files are LF-normalized before source hashing. An unsupported provider remains non-reusable rather than blocking ordinary generation.

| Source | SHA-256 |
| --- | --- |
| KJ `nodes/preview_override_node.py` | `d07c8e5ff7d7abd3e31acefe2cf29f618b5da5341b3b434e72ec2ac0953230b0` |
| KJ `nodes/tiny_vae.py` | `61bf4daa634ef6bb901ff8630071caed12e733d17e7c4ba50082dc0aa5506591` |
| KJ `nodes/ltxv_nodes.py` | `11286583c56e653dbd57f5e8eda6902c84b759f16b359b3bf0c895b43e6b5364` |
| Core `latent_preview.py` | `b323be881ade3388254a72f5463e329f6d0a263b0078b69ae4256eb4e22dbba2` |
| Core `comfy/patcher_extension.py` | `1c7b3b855278d0b95d1c1a705fa0b3c91a265f320e2f97bdeb9d15469d6d4ac7` |

Profile: `kj-preview-1.5.2-local-d07c8e5-phase-a`. Canonical full-profile SHA-256: `d146bd89895fef5a8d576134d519e63bbf4ac1c35188f70b4de4e4ebfb498fc7`. The provider JSON is shipped with the runtime adapter.

Preview Override's optional VAE and Audio VAE must be disconnected, Tiny VAE must be exactly `none`, and Core preview must be NoPreviews, Auto or Latent2RGB. A generation Video/Audio VAE is still used normally; the restriction concerns the preview node's optional connections. Core approximate-VAE/TAESD, altered helpers, unknown wrappers, extra state and other providers are outside this profile. Source alone is insufficient: loaded functions, nested code, defaults, classes and selected bindings must match the audited implementation.

## Update and history protection

Restart ComfyUI, refresh the browser and create a new Run. Do not delete or rewrite old Runs/Takes. Earlier safe KJ identities may differ; old unsafe/v5 history is not repaired or promoted. Ordinary non-KJ Sampling v6 signatures remain exact. Sampling v6, Graph v4, Run Storage v3, State/Session formats, public node inputs and official workflow files are unchanged.

## Validation

Full real-Core CPU validation: 1,995 passed, 3 skipped, 2 existing Inspector expected failures, zero unexpected failures or CUDA initialization attempts. The dedicated real-provider tests passed all 48 cases, including 0/1/multiple held frames, reconstruction, fixed-setting changes, wrapper ordering, source/code/default/helper changes, VAE exclusion, Attention/Spectrum combinations, prefix preservation and old unsafe history. Offline registration retains twelve nodes.

The initial acceptance used the same repair product bytes. A subsequent recheck installed all 464 files from the published v3.9.8 tag (`58fbd855`), restarted normal ComfyUI, verified the live 3.9.8 startup banner and saved adapter/profile identity, and passed four new-Run GPU Queues:

| New Run | First Queue | Separate second Queue |
| --- | --- | --- |
| Model Attention Backend PyTorch + KJ Preview Override | Generate Chunk 1; 8 held images | Reuse Chunk 1, generate Chunk 2; 16 held images |
| Model Attention Backend Comfy Kitchen INT8 + audited local Spectrum + KJ Preview Override | Generate Chunk 1; 8 held images | Reuse Chunk 1, generate Chunk 2; 16 held images |

In both second Queues the KJ MODEL node was cached, the Sampler executed, the stored contract/revision stayed equal, and original Chunk 1 latent bytes were unchanged. All four video/audio outputs fully decoded (first Queue 5 seconds / 120 frames; second Queue 10 seconds / 240 frames, 512x512, 24fps). Saved contracts recorded Sampling v6, resume_safe=true and the pinned adapter/profile identity. Runtime source hashes and stored descriptors verified the repair was actually loaded.

Conditions: RTX 5060 Ti 16 GB, Python 3.13.12, PyTorch 2.14.1+cu130, Core 0.41.0, frontend 1.55.17, comfy-kitchen 0.2.37; 8-step Turbo LoRA, Euler/simple, 2x5-second chunks, Review Each Chunk / Continue, saving and Auto Resume on. Preview Override: resolution 512, quality 80, one frame, 12fps, suppress default on, VAE/Audio VAE absent and Tiny VAE none; Core Auto. Spectrum used the previously audited local implementation with offline smoothing/replay, system-RAM history/archive and model-aware off. This does not newly validate upstream Spectrum 0.2.29 combined with KJ, other wrapper orders, Sage patch nodes, or all preview configurations.

These were controlled submissions through the normal Core API. Browser Run-button/save-reload behavior, reporter-exact reproduction, per-kernel CUDA return tracing, subjective audiovisual/preview quality and performance benchmarks are not newly accepted. Held PNGs were 32x32, so the image counts do not establish high-resolution preview quality. The two known Inspector reconfigure expected failures remain. Existing workflow files and prior Takes were hash-protected; no history migration occurred. GitHub Release/package verification, Registry upload/moderation and real Manager installation remain distinct publication checks.

## 日本語

監査済みKJ Preview Overrideの一時画像だけを永続署名から分離し、固定設定・実装識別・ラッパー順序を保持します。KJNodes 1.5.2全体ではなく、上表のソースと読み込み済み関数を照合できる実装だけが対象です。VAE／Audio VAE未接続・Tiny VAE none・Core NoPreviews／Auto／Latent2RGBが条件です。

更新後は再起動し、新Runを使用してください。旧Take・Workflowの削除や移行は不要で、旧unsafe履歴は再利用不可のまま保持します。CPU 1,995成功（専用48件を含む）、PyTorchおよびKitchen＋ローカルSpectrumの各2 Queueで画像保持後のChunk 1→2継続、元Chunk 1保持、4本の映像・音声全デコードを確認しました。初期の同一製品コードによる受入後、公開タグv3.9.8（58fbd855）を実環境へ反映・再起動して、新Runで同じ2構成の4 Queueも再確認済みです。画質・速度・実ブラウザー操作・全KJ構成への合格は主張しません。
