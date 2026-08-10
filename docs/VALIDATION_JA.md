# H3 Continuum Join 2.0 — 実機検証

## 1. インストール検査

ComfyUIを終了後、展開フォルダーで実行します。

```powershell
.\install_windows.bat
```

または：

```powershell
D:\StabilityMatrix\Data\Packages\ComfyUI_W\venv\Scripts\python.exe `
  .\tools\verify_runtime.py `
  --comfy-root D:\StabilityMatrix\Data\Packages\ComfyUI_W
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
