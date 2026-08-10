# H3 Continuum Sampler V2 — 配線

## MODEL

```text
UNET Loader
  → Patch Sage Attention KJ
  → Sol-Attn Patch
  → Power LoRA Loader（任意）
  → Spectrum Apply MiniMax H3
  → H3 Continuum Sampler V2.model
```

## 共有入力

```text
CLIP Loader     → clip
Video VAE       → video_vae
Audio VAE       → audio_vae
KSampler Select → sampler
Basic Scheduler → sigmas
Load Image → ImageScaleToTotalPixels → first_frame
GetImageSize.width/height → width/height（widgetをinputへ変換して接続する場合）
```

## 出力

```text
Sampler V2.images ─→ CreateVideo.images
Sampler V2.audio  ─→ CreateVideo.audio
CreateVideo       ─→ SaveVideo

Sampler V2.session ─→ Save Session（任意）
```

## 3×5秒の初期値

```text
Prompt Format: Auto
Sequence Prompt: Text (Multiline)を1個接続
chunks: 3
chunk_seconds: 5.0
continuity: Balanced — 22 frames
base_seed: 固定値
audio_continuity: true
exact_total_duration: true
diagnostics: Basic
reroll_from_chunk: 0
reroll_nonce: 0
strict_compatibility: true
```

## 再開

```text
Load Session.session → Sampler V2.session
chunks: 保存時より大きい値
reroll_from_chunk: 0
```

## 最終チャンクだけリロール

```text
Load Session.session → Sampler V2.session
reroll_from_chunk: 最終チャンク番号
reroll_nonce: 1以上へ変更
```

同梱の`H3_Continuum_V2_3x5s.json`は、上記配線を1本のV2ノードにまとめた編集可能なComfyUI workflow例です。モデル名、入力画像、Prompt、LoRAを自分の環境に合わせて変更してください。
