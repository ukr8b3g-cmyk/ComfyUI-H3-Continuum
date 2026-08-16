# ComfyUI-H3-Continuum 3.3.0

**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。


**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。
MiniMax H3を複数チャンクで連続生成し、直前チャンク末尾の**映像latent / 音声latentを直接**次チャンクへ継承するComfyUIカスタムノードです。チャンク間でVideo/Audio VAEのDecode→Encodeは行いません。

**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。


**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。
## V3.2.4 Stable

**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。


**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。
V3.2.4は、T2VA / I2VA / FL2VA / Reference + Continuationに対応し、最大3枚のReference ImageとReference Audio 1をCore互換の順序で扱います。First/Last FrameとReference Audioを併用する場合も、Tokenizer側のPicture/Audio表示とDiT側のKeyframe/Audio conditioningを分離して処理します。Run Storage、Spectrum Interop、外部Core VAE Decodeは従来どおりです。

**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。


**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。
Reference入力のバイパスされたソケットは無視され、有効な画像だけがPicture 1から連続採番されます。プロンプト内の利用できないPicture/Audioタグは警告として扱い、生成は継続します。

**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。


**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。
## Legacy V2.1.7 Stable Facade UI

**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。


**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。
V2.1.7では、V2.1.6の動的表示制御を廃止し、標準ComfyUI描画だけを使用する静的Facadeへ移行しました。生成処理は互換用`H3ContinuumSamplerV2`を再利用し、State、Session、Prompt Plan、Spectrum Interop、保存Schemaは変更していません。

**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。


**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。
通常表示は次を中心にします。

**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。


**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。
```text

**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。
model / clip / video_vae / audio_vae / sampler / sigmas

**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。
Sequence Prompt

**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。
first_frame

**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。
prompt_overrides（任意pack）

**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。
advanced（任意pack）

**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。


**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。
Prompt Format

**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。
chunks

**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。
chunk_seconds

**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。
width / height

**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。
continuity

**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。
base_seed

**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。
control after generate

**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。
Seam Correction

**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。
Seam Correction

**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。


**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。
outputs: images / audio / result

**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。
```

**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。


**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。
### 補助ノード

**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。


**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。
- `H3 Continuum Clip Overrides`: Clip別Promptを1本のpackへまとめます。

**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。
- `H3 Continuum Advanced`: resume/session入力と低頻度設定をまとめます。

**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。
- `H3 Continuum Result`: resultから`last_state / session / report`を展開します。

**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。
- 補助ノードを使わない通常生成では、Sampler本体だけで動作します。

**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。


**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。
### Legacy互換

**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。


**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。
旧`H3ContinuumSamplerV2`は削除せずLegacy/Coreノードとして登録を維持します。既存WorkflowのノードID、入力順、出力順は変更していません。

**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。


**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。
## Continuity

**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。


**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。
- `Auto — conservative`

**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。
- `Balanced — 22 frames`（標準）

**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。
- `Fast — 5 frames`

**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。
- `Strong — 39 frames (Experimental)`

**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。


**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。
5/22/39フレームはH3の時間latent周期`1,4,4,4,4`に対して、それぞれ2/7/12 temporal latent stepsです。

**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。


**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。
## Spectrum

**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。


**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。
Continuumは有効な前チャンクContextがある場合だけ`h3_continuum` Interop API v1をMODEL optionsへ付与し、対応Spectrumへ`min_actual_prefix_steps=2`を要求します。初回チャンクにはInterop keyを付与しません。未知・未対応Spectrumでは通常Spectrumとしてfail-openします。

**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。


**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。
## 推奨配線

**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。


**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。
```text

**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。
UNET -> SageAttention -> Sol-Attn -> LoRA -> Spectrum -> H3 Continuum Sampler

**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。
```

**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。


**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。
まず`chunks=2 / chunk_seconds=5 / Balanced 22f / Seam Correction=Off`でNative Continuityを確認し、その後`Seam Correction=Auto`を比較してください。

**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。


**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。
## インストール

**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。


**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。
ZIPを展開して、`ComfyUI-H3-Continuum`フォルダーを`ComfyUI/custom_nodes/`へ置き、ComfyUIを再起動します。

**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。


**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。
旧`ComfyUI-H3-Continuum-Join`が残っている場合は同時ロードを避けるため削除または退避してください。同梱`install_windows.bat`は旧名・新名の既存フォルダーを日時付きでバックアップします。

**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。


**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。
## 検査

**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。


**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。
```text

**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。
python -m compileall -q .

**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。
pytest -q

**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。
```

**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。


**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。
GPL-3.0-or-later。

**V3.3.0 Stable:** Timeline Video、Audio Seam Auto、Video Seam Auto、Reference Audio、Run Storageを含む安定版です。
