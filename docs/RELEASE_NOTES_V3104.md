# H3 Continuum 3.10.4 — KJ Preview Override and Review continuation

## What changed

- Sampling v6 can reuse new Takes with the audited KJ Preview Override on ComfyUI Core 0.46.0 and 0.46.2. Both Core releases have identical audited preview and wrapper-dispatch files. Continuum selects the profile by exact source hashes and still checks the loaded code and wrapper settings.
- The V3.9 Turbo Sample keeps KJ Preview Override in the MODEL path. Its two optional preview VAE inputs are disconnected and Tiny VAE stays at `none`. The Sampler and final output still use their connected video and audio VAEs. [Issue #42](https://github.com/ukr8b3g-cmyk/ComfyUI-H3-Continuum/issues/42) · [Turbo Sample guide](https://github.com/ukr8b3g-cmyk/ComfyUI-H3-Continuum/blob/v3.10.4/docs/TURBO_SAMPLE.md)
- On the audited older Core, an existing reusable Take keeps the same sampling signature. Previously saved read-only Takes remain available in history. Unknown implementations and unsupported preview settings still fail the reuse check.

## Validation

| Check | Result |
|---|---|
| CPU and JavaScript regression on Core 0.42.1 | 2,379 passed, 2 skipped, zero failures. A focused run on the final fixtures also passed all 209 tests. |
| Focused CPU regression on Core 0.46.2 | 89 passed, 120 skipped, zero failures. The older KJ profiles remain outside the newer Core audit. |
| Review Queue JavaScript | 95 cases passed in a separate rerun. |
| CPU Review and Run Storage | On 0.46.0 and 0.46.2, synthetic latents passed Chunk 1 reuse and Chunk 2 save. Unknown loaded code and preview VAE configurations remained ineligible. |
| GPU Review on Core 0.46.2 | Two queues on an RTX 5060 Ti 16 GB using the updated Turbo Sample with KJ enabled. The second queue used `Continue From Here`, reused Chunk 1 and generated only Chunk 2. The saved Chunk 1 latent matched its original SHA-256. The final MP4 contains 16 seconds of video and audio at 544 × 544 and 24 fps. The test used the ComfyUI API. |

## Updating

Install the GitHub package, restart ComfyUI and refresh the browser. Open the updated Turbo Sample, enable Progress and **Review Each Chunk**, and use a new, unique Run Name to check the fix. After Chunk 1, choose **Continue From Here**. On a copy of an existing Turbo Sample, disconnect only the two VAE inputs on KJ Preview Override and set Tiny VAE to `none`. The [KJ compatibility guide](https://github.com/ukr8b3g-cmyk/ComfyUI-H3-Continuum/blob/v3.10.4/docs/KJ_PREVIEW_OVERRIDE_V398.md) lists the audited settings. Registry submission remains on hold.

## 日本語

Core 0.46.0／0.46.2で監査済みのKJ Preview Overrideを使うと、新規TakeからReviewを継続できます。付属のTurbo SampleはKJ自体を有効にしたまま、プレビュー用の映像VAE・音声VAEの入力だけを外しました。Tiny VAEは `none` です。更新後の確認は新しいRunで行ってください。

全CPU・JavaScript回帰は2,379件成功、2件スキップ。Core 0.46.2の対象試験は89件成功、120件スキップ。Review QueueのJavaScriptは95件成功しました。Core 0.46.2とRTX 5060 Tiで2回生成し、2回目にChunk 1を保持してChunk 2だけを生成できました。Chunk 1の保存済みlatentはSHA-256が一致しました。
