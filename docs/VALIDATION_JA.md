# H3 Continuum 3.9.1 — 検証手順と受入範囲

現行版はパッケージ3.9.1、公開12ノードです。引き続きV3.9ノードを使用します。
旧版の検証手順は末尾に履歴として残しています。

## CPU・登録確認

リポジトリのルートで、ComfyUIに使用しているPythonを指定して実行します。

```powershell
powershell -ExecutionPolicy Bypass -File tools/validate.ps1 `
  -Python "path/to/ComfyUI/venv/Scripts/python.exe" `
  -ComfyRoot "path/to/ComfyUI"
```

pytestが実Coreを必要とするケースまで実行したかは、結果のスキップ理由と
使用したCore環境を確認してください。`-ComfyRoot`はruntime verifierへの指定で、
この指定だけでpytestのCore import環境を設定するわけではありません。
Coreがないstandalone環境では、実Core依存18件を明示的にスキップします。
Core内部の依存エラーや計算エラーをスキップで隠す設計ではありません。

記録済みの結果は環境別です。実Coreの全CPUは1,696成功・1スキップ、公開CIは
1,676成功・21スキップです。CIの21件は実Core依存18件と既存環境制約3件です。
詳細・対象コミットは[PACKAGE_VALIDATION.txt](../PACKAGE_VALIDATION.txt)を参照し、
異なる環境の件数を単純合算しないでください。

## 実ブラウザー受入

生成中のワークフローを再起動・置換せず、実行中と待機中のキューが空の状態で
検証用Workflowを使用します。元Workflowと採用済みTakeを先に保存してください。

1. 実backendの`object_info`で公開12ノードの登録を確認します。
2. V3.9公式Workflowを開き、モデル・素材・Promptを検証用に設定します。
3. 別名保存→再読込→別Workflowタブへ移動→戻る、を実際の画面で確認します。
4. 外部INTのWidth／Height接続、Reference割り当て、Decode Cache Helper設定が
   保存・復元されていることを確認します。
5. 保存済み履歴のReviewとTake選択が表示されることを確認します。
6. Second Passの接続・設定が保存・復元されることを確認します。実際の生成完走、
   条件継承、音声一致は次のGPU Gateで別途確認します。

Canvasの表示だけ、API登録だけ、DOM代替のJSテストだけで、保存・再読込の
実ブラウザーPASSとはしません。検証用Workflowの合格も、無改変公式Workflowの
初期設定でのGPU受入とは区別します。

## 修正対象のGPU Gate

- R1／Review Second Pass: audio-only／mixed keyframes、partial prefix、
  中央Chunk単独、complete sequenceを確認します。出力group自身のconditioning、
  Referenceのlogical chunk対応、First Pass Audio passthroughを記録します。
- R2: 同一v6条件は前半を再利用し、Sampler／CFG／wrapper等が異なる条件では
  誤再利用しないことを確認します。旧v5履歴は読めてもv6へ継ぎ足しません。
- R3: 識別できるDriving Audioで、元physical groupの自然時間に対応するPCMを
  Exact ON／OFFとも一度だけ切り出すことを確認します。
- 保存済みTakeのJSON／raw、動画と音声の尺、CUDA／OOM／NaN、残留キューも記録します。

対象修正のGPU確認は記録済みですが、ブラウザー受入、無改変公式Workflow全体、
全アクセラレータ構成や総合画質の受入まで済んだとは扱いません。
任意LATENT拡大の二重輪郭は[Issue #27](https://github.com/ukr8b3g-cmyk/ComfyUI-H3-Continuum/issues/27)
として分けて扱います。

## 更新と旧Take

更新後はComfyUIを再起動し、ブラウザーも更新してください。旧v5 Takeは保持・閲覧
できますが、新しいv6生成の前半としては再利用できません。新規Full Video、または
**Start again from Chunk 1**で開始します。旧manifestを新契約へ書き換えません。
同一VAEオブジェクトの重みを直接変更した場合は、Reference Encode Cacheを
明示的にクリアするか、VAEを再読込してください。

GitHub ReleaseとRegistry公開は別作業です。公開済みv3.9.1 tagは保持し、後続の
文書訂正はmainで参照してください。

---

## 履歴：V2専用の旧検証手順

以下は当時の記録です。V1／V2ノード数、`strict_compatibility`、旧Session再開手順を
3.9.1の現行仕様や受入結果として使用しないでください。

# H3 Continuum Join 2.0 — 実機検証

## 1. インストール検査

ComfyUIを終了後、展開フォルダーで実行します。

```powershell
.\install_windows.bat
```

または：

```powershell
$ComfyRoot = "path/to/ComfyUI" # 使用中のComfyUIの場所へ置き換える
& "$ComfyRoot/venv/Scripts/python.exe" `
  .\tools\verify_runtime.py `
  --comfy-root $ComfyRoot
```

確認項目：

- native H3 API
- Sol-Attn形式の`*args/**kwargs` PackedLayout wrapper互換
- real PackedLayout行構造とin-place座標補正
- V1/V2計10ノード登録
- Fixed 3×5秒Prompt Plan

## 2. 最初のV2基準生成

```text
chunks: 3
chunk_seconds: 5.0
continuity: Balanced — 22 frames
audio_continuity: true
exact_total_duration: true
diagnostics: Basic
reroll_from_chunk: 0
reroll_nonce: 0
strict_compatibility: true
```

Model：

```text
H3 INT8 ConvRot
20 steps / CFG 1
Turbo LoRA OFF
```

同じ入力画像とPromptで、既存V1の3×5秒ワークフローとV2を比較します。

## 3. アクセラレータ比較

同じBase Seed、Prompt、解像度で次を順番に確認します。

1. SageAttentionのみ
2. Sage + Sol-Attn
3. Sage + Spectrum
4. Sage + Sol-Attn + Spectrum

RTX 5060 Ti環境で既に動作したSage backendを基準にします。クラッシュしたbackendへ切り替えません。

確認：

- 全チャンクが順番に完了
- Spectrumのrunが各チャンクで開始・終了
- `Sol-Attn takes first refusal...`ログ
- 黒出力、NaN、CUDA errorなし
- VAE Decodeが全H3 Sampling後に始まる
- 最終出力が指定尺になる

## 4. 接続品質

Basic確認：

- 人物ID、髪、服、背景
- 前チャンクからの姿勢・移動方向・カメラ速度
- 口形、歌唱・発話の継続
- 音声tick、無音、語尾重複
- 最終フレーム数と音声samples

Full DiagnosticsではReportに次を出します。

```text
video overlap MAE
video overlap PSNR
audio overlap correlation
audio boundary jump
```

絶対的な合格値ではなく、V1と各アクセラレータ構成の相対比較に使います。

## 5. Session再開

1. 3チャンク生成
2. `Save Session slot 1`
3. ComfyUI再起動
4. `Load Session slot 1`
5. chunksを4へ変更し、sessionへ接続
6. Chunk 1〜3がreused、Chunk 4だけSamplingされることをReportで確認

## 6. リロール

```text
reroll_from_chunk: 3
reroll_nonce: 1
```

確認：

- Chunk 1〜2はSamplingされない
- Chunk 3以降だけ新Seed
- 入力Sessionファイルは変更されない
- 出力Sessionの`parent_session_id`が入力Sessionを示す

## 7. Promptモード

- Fixed：Qwen encodeが1回
- List：`---`で3 Prompt
- Timeline：`[0-5s] / [5-10s] / [10-15s]`
- Prompt変更時、変更前チャンクだけSession再利用される

## 8. Auto Context

Balanced 22fを品質基準にします。その後Autoと比較します。

- 静かな動き：5fを選ぶ可能性
- 通常：22f
- 強いlatent motionかつ39f State：39f

Autoの結果が悪い内容ではBalancedへ固定します。

## 9. RAM guard

高解像度・多数チャンクで、Sampling前にRAM見積りエラーが出ることを確認します。これは意図した安全停止です。chunks、秒数、解像度を下げます。

## 10. 報告時に必要な情報

```text
ComfyUI version / revision
Python / Torch / CUDA
GPU / VRAM / RAM
H3 checkpoint
Sage backend
Sol settings
Spectrum settings
chunks / seconds / context
steps / scheduler / sampler
Console log
V2 report
```
