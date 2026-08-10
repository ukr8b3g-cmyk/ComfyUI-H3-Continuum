# H3 Continuum Join 2.1

MiniMax H3を4〜15秒のチャンク単位で連続生成し、前チャンク末尾の**映像latentと音声latent**を次チャンクへ直接継承するComfyUIカスタムノードです。

V2の主要ノード **H3 Continuum Sampler V2** は、V1で実機確認されたContinuation処理を変更せず、Nチャンクの準備・Sampling・State管理・Decode・結合を1ノードへ統合します。V1の5ノードもそのまま残るため、既存ワークフローは継続利用できます。

## V2の主な特徴

- `chunks`を指定するだけでNチャンクを順番に生成
- V1と同じnative H3 video/audio latent continuation coreを使用
- 同一MODEL、Sampler、Sigmasを全チャンクで共有
- CLIP conditioningと入力画像latentをSampling前にまとめて準備
- H3チャンク間でVideo/Audio VAE Decodeを行わず、全Sampling終了後にDecode
- 全チャンクのraw latentをCPU RAMへ退避し、VRAMに蓄積しない
- Spectrumは1ノードのみ。各チャンクでSpectrum自身のrunを開始・終了
- SageAttention、Sol-Attn、Spectrumのprivate APIを内蔵・複製しない
- 固定`Sequence Prompt`端子とAuto / Fixed / List / Timeline解析
- `chunks`に連動する1〜16個の`Clip N Prompt`は折りたたみ式の任意Override
- `Settings > H3 Continuum > Preview`で生成中latentサムネイルをON/OFF
- `Seam Correction: Off / Basic`。Offは2.0.2経路、BasicはDecode後だけの境界補正
- Basicでは最大3fのAdaptive Cut、制限付き色・輝度補正、最大2f Blend、境界限定Audio補正
- 同じPromptのQwen conditioningを1回だけ作成して再利用
- 5 / 22 / 39フレーム、および保守的なAuto Context
- 64bitの決定的なチャンク別Seed
- Session保存、再開、指定チャンク以降の安全なリロール
- Decode時に最終IMAGEを1回だけ確保し、反復`torch.cat`を回避
- 音声境界を累積フレーム数から計算し、チャンクごとの丸め誤差を蓄積しない
- `chunks × chunk_seconds × 24fps`への最終尺補正
- 大きすぎる出力はSampling前のRAM見積りで安全停止
- 追加pip依存なし

## 対応環境

- ComfyUI v0.31.0以降のnative MiniMax H3
- MiniMax H3 FL2VA / Image-to-Videoモデル
- Python 3.10以降
- batch size 1
- Windows / Linux

本パッケージはComfyUI本体、Spectrum、Sol-Attn、SageAttentionのソースコードを同梱しません。各アクセラレータは別途導入してください。

## インストール

1. ComfyUIを終了します。
2. ZIPを展開します。
3. フォルダー全体を次へ配置します。

```text
D:\StabilityMatrix\Data\Packages\ComfyUI_W\custom_nodes\ComfyUI-H3-Continuum-Join\
```

または展開後に`install_windows.bat`を実行します。インストーラーは既存フォルダーを日時付きバックアップへ移し、native H3のAPI、PackedLayout、ノード登録を検査します。

```powershell
powershell -ExecutionPolicy Bypass -File .\install_windows.ps1
```

導入後、ComfyUIを再起動してください。

## V2の最小ワークフロー

```text
H3 UNET Loader
  → SageAttention
  → Sol-Attn
  → 通常LoRA（必要時）
  → Spectrum Apply MiniMax H3
  → H3 Continuum Sampler V2

CLIP Loader ───────────────→ H3 Continuum Sampler V2
Video VAE Loader ──────────→ H3 Continuum Sampler V2
Audio VAE Loader ──────────→ H3 Continuum Sampler V2
KSampler Select ───────────→ H3 Continuum Sampler V2
Basic Scheduler ───────────→ H3 Continuum Sampler V2
Load Image / scaled IMAGE ─→ first_frame

H3 Continuum Sampler V2
  ├─ images ─→ CreateVideo
  ├─ audio  ─→ CreateVideo
  ├─ session ─→ Save Session（任意）
  └─ report
```

MODELへの推奨順は次です。

```text
UNET → Sage → Sol → LoRA → Spectrum → H3 Continuum Sampler V2
```

ContinuumはSampler内部でMODELを1回だけ追加cloneし、MODEL単位の`APPLY_MODEL` wrapperを付加します。グローバルなH3クラス変更は行いません。

## H3 Continuum Sampler V2

### 必須入力

- `model`：Sage / Sol / LoRA / Spectrumを適用済みのH3 MODEL
- `clip`：MiniMax用Qwen3-VL CLIP
- `video_vae`：H3 Video VAE
- `audio_vae`：H3 Audio VAE
- `sampler`：標準は`res_multistep`
- `sigmas`：標準は`simple / 20 steps / denoise 1.0`
- `Sequence Prompt`：標準`Text (Multiline)`を1個接続する固定STRING入力
- `Prompt Format`：Auto / Fixed / List / Timeline。形式変更時も接続を維持
- `Clip N Prompt`：折りたたみ内の任意Override。接続済み旧端子は折りたたんでも維持
- `prompt_script`：画面上では非表示。旧Workflow用の内部フォールバックとして保持
- `chunks`：1〜16
- `chunk_seconds`：4.0〜15.0。標準5.0
- `width` / `height`：32の倍数
- `continuity`
- `base_seed`
- `audio_continuity`
- `exact_total_duration`
- `diagnostics`
- `reroll_from_chunk` / `reroll_nonce`
- `strict_compatibility`
- `seam_correction`：`Off`は2.0.2互換、`Basic`はV2.1の非破壊境界補正

### 任意入力

- `first_frame`：全チャンクの長期Identity cue。画像ロードは1回だけでよい
- `last_frame`：最終チャンク末尾のFL2VA anchor
- `session`：保存済みV2 Sessionの再開・リロール
- `initial_state`：V1の`H3_CONTINUUM_STATE`からV2を開始
- `prompt_plan`：`H3 Continuum Prompt Plan`出力を接続可能

`session`と`initial_state`は同時接続できません。

Promptの優先順位は次のとおりです。

```text
外部 Clip N Prompt Override
→ Sequence Prompt
→ prompt_plan
→ 保存済み prompt_mode / prompt_script
```

Clip別Overrideがないチャンクは、`Sequence Prompt`、接続済み`prompt_plan`、内部フォールバックの順に対応Promptを維持します。生成中サムネイルは`Settings > H3 Continuum > Preview > Show latent preview`で切り替えます。初期値はONで、OFFにしても最終IMAGE / AUDIOには影響しません。

## Promptモード

### Fixed — one prompt

同一Promptを全チャンクで使用します。Qwen conditioningは1回だけ作成されます。

```text
The same woman continues singing in one uninterrupted shot...
```

### List — split with ---

```text
Chunk 1 prompt...
---
Chunk 2 prompt...
---
Chunk 3 prompt...
```

Prompt数が不足すると最後のPromptを繰り返し、余分なPromptは無視してReportへ記録します。JSON文字列配列も使用できます。

### Timeline — [0-5s] sections

```text
[0-5s]
First section prompt...

[5-10s]
Second section prompt...

[10-15s]
Third section prompt...
```

`[Chunk 1]` / `[Clip 2]`形式も使えます。時間範囲がチャンクをまたぐ場合は、重なり時間が最大のセクションを採用します。

## Continuity

- `Auto — conservative`：latent motion量を測定。境界付近は22fへ戻す
- `Balanced — 22 frames`：V1標準。最初の実機検証に推奨
- `Fast — 5 frames`：静かな動き、速度優先
- `Strong — 39 frames (Experimental)`：激しい動き・カメラ、計算量増加

Autoは前Stateのvideo latent時間差を正規化して判定します。判定不能、State容量不足、しきい値付近では安全側の22fを選びます。39fは実験的です。

## IdentityとMotionの分離

V2は次を別に扱います。

```text
Long-term Identity
  = first_frameをQwen visual tokenとして全チャンクで共有

Short-term Motion / Audio
  = 直前チャンク末尾の5 / 22 / 39f video latent
    + 対応するaudio latent
```

継続チャンクでは旧first-frameの空間keyframeを外しますが、Qwen visual tokenは人物・衣装・背景のIdentity cueとして残します。前チャンクの姿勢、移動方向、口の動き、カメラ運動、音声はnative latent Contextから継続します。

## Sessionとリロール

V2出力の`session`には、各チャンクのraw AV latent、Prompt hash、Seed、Plan、Context情報をCPUで保持します。

```text
H3 Continuum Sampler V2.session
  → H3 Continuum Save Session
```

保存形式：

```text
h3_continuum_session_slot0001.safetensors
h3_continuum_session_slot0001.json
```

### 再開

保存済みSessionをLoadし、Samplerの`session`へ接続します。Prompt、解像度、first_frame fingerprintが一致する採用済みチャンクは再生成しません。追加したチャンクだけ生成します。

### リロール

```text
reroll_from_chunk = 3
reroll_nonce = 1
```

この場合、Chunk 1〜2を保持し、Chunk 3以降を新しい決定的Seedで生成します。途中チャンクを変更すると、それ以降は旧Continuationと一致しないため自動的に新しいSession branchになります。元Sessionは上書きされません。

`reroll_from_chunk=0`は、接続Sessionの一致する採用済みチャンクをすべて再利用します。

## SamplingとDecodeの実行順

```text
Phase 1
  first/last image resize・VAE encode
  unique PromptのQwen encode

Phase 2
  H3 Chunk 1 Sampling → CPU latent / State
  H3 Chunk 2 Sampling → CPU latent / State
  H3 Chunk 3 Sampling → CPU latent / State
  ※この間Video/Audio Decodeなし

Phase 3
  Video/Audio VAE Decode
  overlap Trim
  累積sample境界で音声を配置
  final IMAGE/AUDIOを組立
```

ComfyUIの動的VRAM管理は引き続き有効です。RTX 5060 Ti 16GBでH3全重みを完全VRAM常駐させるという意味ではありません。V2は**同じMODEL objectを使い、H3チャンク間にCLIP/VAE処理を挟まない**ことで、不要なモデル切替を抑えます。

## Spectrum互換

SpectrumはV2の外部MODELノードとして1回だけ適用します。V2はSpectrumのprivate APIを呼びません。

各チャンクの`guider.sample()`がSpectrumの通常wrapperを通るため、Spectrumはチャンクごとに独立したrunを開始・終了します。前チャンクのSpectrum forecast historyは次チャンクへ流用されません。継承するのはnative video/audio Contextだけです。

推奨初期値：

```text
blend_weight: 0.50
degree: 1
warmup_steps: 1
offline_smoothing_replay: true
audio_blend_weight: 0.00
```

`offline_smoothing_replay=true`ではSpectrumが1チャンクにつきcapture/replayの2 passを行います。V2はこの動作を変更しません。

## SageAttention / Sol-Attn互換

- SageAttention：Attention kernelを変更せず、そのまま使用
- Sol-Attn：Continuumは`PackedLayout.position_ids` Tensorを置換せずin-place補正
- SolからSageへのfallback chainを維持
- Contextはnative H3 `video` / `video_audio` reference blockとして渡す

本ノードからSolのtau、sink、Morton設定は変更しません。GPU、解像度、内容ごとにA/B比較してください。

## Audio / exact duration

V2は各セグメントを個別に丸めて連結しません。累積フレーム境界から、次を直接計算します。

```text
sample_start = round(cumulative_frames / 24 × sample_rate)
sample_stop  = round(next_cumulative_frames / 24 × sample_rate)
```

そのため119フレーム区間を多数つないでも、1sample単位の丸め誤差が累積しません。

`exact_total_duration=true`では、最終結果を次へ合わせます。

```text
target_frames = round(chunks × chunk_seconds × 24)
```

余分なフレームは通常末尾からTrimします。`last_frame`が接続されている場合は最終アンカーを失わないよう、余剰を最終フレーム直前から除去し、音声側も短い補間でクリックを抑えながら同じ長さへ合わせます。不足が小さい場合のみ最終フレームと最終音声sampleを最小限反復します。

## RAM安全設計

長尺の最終`IMAGE`はCPU float tensorになるため、解像度と長さに比例してRAMを消費します。V2はSampling開始前に、

- 最終IMAGE
- 1チャンク分のraw Decode
- 基本headroom

を見積もります。現在利用可能RAMの安全範囲を超える場合は、すべてのH3 Samplingを終えた後で失敗しないよう事前停止します。

Decode時は最終IMAGE tensorを1回だけ確保し、各チャンクを所定範囲へcopyします。反復`torch.cat`による全長コピーは行いません。

## Diagnostics

- `Off`：診断を最小化
- `Basic`：標準。Seed、Context、motion score、アクセラレータ検出、尺、RAM見積り
- `Full`：Basicに加え、接続部のvideo MAE/PSNR、audio correlation、boundary jump

FullはDecode後の測定であり、外部の顔認識モデルやoptical-flowモデルには依存しません。

## V1互換ノード

次のV1ノードは2.0でも同じIDで残ります。

- H3 Continuum Join
- H3 Continuum Finish
- H3 Continuum Assemble
- H3 Continuum Save State
- H3 Continuum Load State

V1の`H3_CONTINUUM_STATE`はV2の`initial_state`へ直接接続できます。V2 Sessionからは`H3 Continuum Session Info`で最終V1 Stateを取得できます。

## 制限

- SVI専用学習済みモデルではなく、native H3 conditioningを利用した独自Continuationです
- H3モデル自体の再生成による長期Identity・音色のドリフトを完全には排除できません
- 39fとAutoは内容ごとの実機比較が必要です
- 解像度をまたぐState/Session継続は安全停止します
- Spectrumは近似高速化です。同一SeedでON/OFF比較してください
- 本配布環境ではH3 checkpointを使ったRTX実生成は実施できません。実機検証手順は`docs/VALIDATION_JA.md`を参照してください

## 同梱ノード

### V2

- H3 Continuum Sampler V2
- H3 Continuum Prompt Plan
- H3 Continuum Save Session
- H3 Continuum Load Session
- H3 Continuum Session Info

### V1互換

- H3 Continuum Join
- H3 Continuum Finish
- H3 Continuum Assemble
- H3 Continuum Save State
- H3 Continuum Load State

## 開発・検査

```bash
python -m compileall -q .
pytest -q
python tools/verify_runtime.py --comfy-root D:\StabilityMatrix\Data\Packages\ComfyUI_W
```

## ライセンス

GPL-3.0-or-later。
