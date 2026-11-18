# H3 Continuum 3.10.3 — Review and reference input fixes

## What changed

- **Review Each Chunk** accepts an external fixed INT connected to the Sampler's seed input. The local seed control still applies when the seed is entered on the Sampler. The backend verifies the seed actually submitted before it reuses a Take.
- **Per chunk** Reference Images keeps the selector text of a disconnected image. A stale duplicate in that slot no longer blocks other images. Connecting the image validates its assignment. For a duplicate on a connected slot, use **Reset to Off** on that slot and select the intended chunks again.
- The **Reference Plan Inspector** matches execution results to the submitted prompt, Sampler and settings. Changing an assignment invalidates the old plan, including when an older queue finishes later.
- **Project / Take Manager** keeps the selected Project, trial and savepoint when an operation is refused. A real revision conflict still prompts a refresh.
- **State and V2 Session** can read valid embedded metadata when the accompanying JSON mirror contains a non-object value. Corrupt embedded metadata still fails validation.

This release also packages changes previously published on main since 3.10.2, including the audited KJ Preview Override profile, stale Run lock recovery, empty-target reconnect handling, metadata recovery and the [Second Pass wiring guide](https://github.com/ukr8b3g-cmyk/ComfyUI-H3-Continuum/blob/v3.10.3/docs/SECOND_PASS_GUIDE.md).

## Verification

- The full CPU and JavaScript suite passed **2,378 tests**, with two skips and zero CUDA initialization attempts. The skipped cases cover a profile outside its original fixture and a legacy workflow fixture absent from this checkout. Offline registration and the native layout check passed for all 12 public nodes.
- On an RTX 5060 Ti 16 GB, two real Review queues used the same external fixed INT, a reference assigned to Chunk 2 and a disconnected reference slot containing `1,1`. The second queue kept Chunk 1 and generated only Chunk 2. Both Takes were reusable under Sampling v6. The first raw file retained its SHA-256, and the new Take points back to it.
- The two live Inspector results matched their submitted queue IDs. The first clip decoded to 120 frames and 5 seconds of audio. The continued clip decoded to 240 frames and 10 seconds of audio (512 × 512, 24 fps). Both video and audio tensors contained finite values. Browser interactions were exercised in JavaScript fixtures. The GPU test used the ComfyUI API and its live event stream.

## Updating

Install the GitHub release, fully restart ComfyUI and refresh the browser with Ctrl+F5. Existing workflows use the same public nodes and input order. Keep existing saved Takes. Sampling v6 continues to validate their reuse eligibility. Registry submission remains on hold pending the earlier manual review.

## 日本語

外部INTから固定シードを渡したReviewと、未接続の参照画像欄に古い指定を残した生成を修正しました。画像をつなぎ直した時は指定を検査します。Inspectorの古いPlan表示、Managerの選択解除、State／Sessionの付属JSON読み込みも修正しました。

GitHub版へ更新したらComfyUIを完全に再起動し、ブラウザーをCtrl+F5で更新してください。既存WorkflowとTakeをそのまま使えます。Takeの再利用には従来と同じ互換性検証が適用されます。

CPU・JavaScript回帰は2,378件成功、2件スキップでした。RTX 5060 Tiの実機でChunk 1を保持してChunk 2だけを生成し、元の保存ファイルのSHA-256一致と、5秒・10秒の両方の映像と音声を確認しました。
