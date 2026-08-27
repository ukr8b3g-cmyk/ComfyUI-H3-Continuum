# ComfyUI-H3-Continuum 3.6.0

MiniMax H3を複数チャンクで連続生成し、直前チャンク末尾の**映像latent / 音声latentを直接**次チャンクへ継承するComfyUIカスタムノードです。チャンク間でVideo/Audio VAEのDecode→Encodeは行いません。

## V3.6 Masked AV Continuation

V3.6では`H3 Continuum Sampler V3.6`を追加しました。標準backendは、前Chunkで確定したVideo／Audio latent prefixを次のH3 Target内へ直接配置し、CoreのNoise Maskで保持します。V3.5のReference Context方式のように、同じ過去フレームを別Reference blockとして追加しないため、H3が処理するpacked sequenceを短縮できます。

| Continuation Backend | 用途 |
|---|---|
| `Standard` | 推奨V3.6経路。次Target内でVideo／Audioを保持します。Audio Continuity OFF時はVideoだけを保持します。 |
| `Compatibility` | 受入済みV3.5 Reference Context動作へ戻すAdvanced fallbackです。 |

内部transport識別子はUIへ表示しません。Run Storage revisionはStandard／Compatibilityで分離し、`Regenerate From`でもLong Terminal Mergeのlogical `[2,3]`を1つのphysical sampleとして再利用・再生成します。

### 受入結果

- T2VA、I2VA、Reference Image＋Reference Audio、Balanced 22-frame Joint AV、3×5秒FL2VA Long Terminal MergeのGPU GateをPASS。
- 保護Video／Audio prefixは最終的にbit-exact。生成領域はSamplerの出力を維持します。
- Reference Image＋Reference Audio代表出力は実聴PASSで、click、dropout、定位異常の報告なし。
- 実測したFL2VA Terminal Group 2では、StandardがCompatibilityよりpacked rowsを2,874行（`8.01%`）削減し、Sampling中央値を`4.06%`短縮。速度はmodel、hardware、workflowで変わります。
- `chunk_seconds`は4.0～30.0秒、初期値5.0秒、step 0.1です。5～15秒を推奨・検証済み範囲として維持し、長時間・高解像度ChunkはVRAMと処理時間が大きく増える場合があります。

V3.5.3、V3.5、V3.4のNode IDと保存済みWorkflowは維持します。V3.5.3は従来Reference Contextのままで、V3.6標準backendへ暗黙に切り替えません。

## V3.5.3 Maintenance Hotfix

V3.5.3は配布整合性だけを修正するメンテナンス版です。公開Conditioning Bridge WorkflowのWidth／Height接続、V3.4／V3.5テンプレート内の孤立link ID、Hybridの`<Picture N>`警告番号、厳密な画像decoderで読めなかった旧PNG 1件を修正しました。

生成動作、Node、socket、Sampling、Conditioning payload、Terminal Merge、Assembly、Seam、Run Storage、Prompt/CLIP cache、Video Guide最適化、V3.4互換性は変更していません。既存V3.5.x Workflowはそのまま読み込めます。

## V3.5.2 Stabilization & Optimization Update

V3.5.2は新しい生成モードを追加する版ではありません。V3.5.xを安定化し、安全な条件で繰り返しPrompt/CLIP処理を省略し、長いVideo Guide入力の一時メモリを削減します。既存Workflowと生成契約は維持します。

![H3 Continuum V3.5.2の安定化・最適化結果](docs/images/v352-stabilization-optimization.png)

画像は受入済み最適化の実測値です。最終パッケージゲートでは、さらにComfyUI 0.33.3と、この画像を含む172項目のManifestでPASSを確認しています。

### 主な変更

1. **繰り返し実行Prompt/CLIP cache**: 条件が変わらないT2VA、I2VA、FL2VAではCPU上のPrompt/CLIP結果を再利用できます。Reference、schedule、tokenizer option、hook変更CLIPは安全側でbypassします。Sampling自体は通常どおり再実行します。
2. **Video Guideメモリ最適化**: source全体をfinite検査とSHA-256 identityへ含めたまま、VAE/conditioningに必要なprefixだけを保持します。
3. **安定化監査**: Sampling、Decode、Assembly、保存、任意機能の負荷、保持memoryを実測しました。根拠のないSampling、Driving Audio、Audio hash、Assembly、Seam、Session、V3.4最適化は採用していません。

### 実測結果

| 項目 | 変更前 | V3.5.2 | 結果 |
|---|---:|---:|---:|
| T2VA繰り返しPrompt/CLIP | 5.898398秒 | 0.000028秒 | Cache HIT、`encode_calls=0` |
| FL2VA繰り返しPrompt/CLIP | 21.642687秒 | 0.007128秒 | Cache HIT、`encode_calls=0` |
| Video Guide Peak追加RSS | 396.8 MiB | 114.7 MiB | 約71%削減 |
| Video Guide保持Storage | 225 MiB | 93 MiB | 約59%削減 |

Prompt/CLIPの数値はconditioning区間だけで、総生成時間ではありません。Video Guideメモリ比較は300×256×256 RGB入力／必要prefix 124 framesの固定CPU条件です。別のGPU A/Bでは実際の15秒／360-frame Video Guideを使い、decoded videoとaudio PCMの完全一致を確認しています。

RTX 5060 Ti 16 GB／RAM 64 GBの検証環境で測定したSage-only Production baselineは、576×576 T2VA 1×5秒が168.069秒、640×640 FL2VA Long Terminal Merge 3×5秒が379.765秒です。環境・設定固有の測定値であり、すべての環境に対する速度保証ではありません。Samplingが最大コストで、Continuum Assemble + Seamは1%未満でした。

**V3.6.0が現在の公開版です。** V3.5.3はmaintenance／compatibility baseline、V3.5.2は受入済みStabilization & Optimization baselineとして維持します。旧Node ID、backend socket key、保存済みWorkflow読込は維持します。撤回済みの実験的Last Queued Seed overrideは含まれていません。

## V3.5.1 Reference Audio／互換性更新

V3.5.1ではV3.4のSampling、Conditioning、Terminal Merge、Assembly、Seam、Run Storage契約を変更せず、次の2点を追加しました。

1. **Reference Audio（任意）**: 生成音声を置換しない、H3 nativeの音声conditioningです。Workflowの保存・再読込互換を守るため、2つのsocketは常時表示します。
2. **Conditioning Bridge V3.5**: Continuumのphysical groupごとに、完全なCore互換`MODEL`と`CONDITIONING`を外部Samplerへ公開します。

Reference Audio socketはPython `INPUT_TYPES`で常設し、保存・再読込時の値ずれを防ぐため動的socket変更とUI-onlyの`Hidden`／`Show` controlを削除しました。V3.4のNode IDとbackend socket keyは保存済みWorkflow互換のため維持しており、既存V3.4/V3.5 Workflowの接続は変わりません。

### Reference系入力の違い

表示名は役割の違いを示しています。名前が似ていても同じ組み合わせではありません。

| 表示入力 | 接続元 | 用途 | 最終音声 |
|---|---|---|---|
| `reference_image_1`～`reference_image_3` | 静止画`IMAGE` | 人物、被写体、外観などの継続参照 | 音声なし |
| `Video Guide Frames` | Video loaderの`IMAGE`フレームbatch | 全chunkでmotion、framing、timing、appearanceをガイド | 元動画の音声は含まない |
| `Driving Audio` + `Driving Audio VAE` | Audio loader、またはVideo loaderの`AUDIO`と対応Audio VAE | 音声で生成をガイドし、入力音声を最終出力へ維持 | 生成音声を選択した元音声へ置換 |
| `Reference Audio (Optional)` + `Reference Audio VAE (Optional)` | 単独Audioと対応Audio VAE | H3 native conditioning専用 | 生成音声をcopy・置換しない |

音声付き動画を使う通常の接続は、loaderの`IMAGE`を`Video Guide Frames`へ、`AUDIO`を`Driving Audio`へ接続します。conditioning専用動作が目的でない限り、動画の音声を`Reference Audio (Optional)`へ接続しないでください。

![Sampler V3.5の常設Reference Audio、Video Guide Frames、Driving Audio、Reference Image入力](docs/images/v351-video-guide-frames.png)

`Reference Audio (Optional)`と`Reference Audio VAE (Optional)`は、Pythonのinput schemaどおり常時表示します。V3.5.1ではこの2 socketをFrontendで動的に追加・削除せず、UI-onlyの`Hidden`／`Show` widgetも使用しません。これによりWorkflowを保存・再読込した際のwidget値の位置ずれを防ぎます。backend input keyと既存接続は変更しません。

![常設Reference Audio socketと正常なwidget配置](docs/images/v351-reference-audio-permanent.png)

### Conditioning Bridge V3.5

`H3 Continuum Conditioning Bridge V3.5`は外部sampling用のAdvanced接続点です。`model`、`clip`、外部処理後の`video_latents`、`assembly_plan`、`refine_context`を接続し、選択したconditioning経路で必要な場合だけ`video_vae`を接続します。出力`group_models`と`conditioning`はphysical group数と同数で、各要素は完全なComfyUI objectのままです。CONDITIONING内部entryをphysical-group listへflattenしません。

```text
H3 Continuum Sampler V3.5.video_latents
  → LBH等の外部H3 latent処理
  → H3 Continuum Conditioning Bridge V3.5
  → Core BasicGuider + 外部Sampler
  → Core Video / Audio VAE Decode
  → H3 Continuum Assemble + Seam V3.5
```

AV LATENTの組、Noise、SIGMAS、Audio Lock、sampling、audio passthroughは外部workflow側の責任です。Bridgeは準備済み`MODEL`と`CONDITIONING`、更新済みAssembly Planだけを公開します。

![V3.5.1 LBH＋Conditioning Bridge外部sampling接続図](docs/images/v351-lbh-conditioning-bridge-flow.svg)

完全な接続例: [V3.5.1 LBH＋Conditioning Bridgeワークフロー](examples/workflows/MiniMax_H3_Continuum_V351_LBH_Conditioning_Bridge.json)

接続例ではCore標準名の`BasicGuider`、`BasicScheduler`、`SamplerCustomAdvanced`を変更していません。公開サンプルではCoreノードを独自タイトルへ変更せず、Continuumノードや外部カスタムノードと直感的に区別できる状態を維持します。LBH latent upscaler、AV LATENTの結合／分離、load／save、任意accelerationは外部ノードなので、各ComfyUI環境に合わせて導入または置換してください。

LBHはlatent geometryだけを変更し、Continuumのdenoise強度は持ちません。拡大後latentをどれだけ再生成するかは外部`BasicScheduler`のSIGMASで調整します。1.5x等へ上げても高速な場合がありますが、target canvasに応じてmemory、decode、sampling負荷は増加します。

## V3.5の主な追加機能

V3.5の大きな追加は2点です。

1. **Continuum対応Second Pass / Hi-Res Fix**: physical group構造を維持した再Samplingと、標準Pixel/VAE 2x経路。
2. **低メモリAssemble + Seam**: Exact Duration、Seam、Terminal Merge、Audioを維持したRAM / Disk-backed / Auto出力。

### 1. Second Pass / Hi-Res Fix

`H3 Continuum Hi-Res Fix V3.5`はVideo VAE Decode → pixel resize → Encode → low-denoise Second Passを1ノード化したMain経路です。長尺2xではVRAM上限に達する場合があるためExperimentalです。

![H3 Continuum Hi-Res Fix V3.5 node](docs/images/v35-hires-fix-node.png)

通常のHi-Res Fix接続:

```text
H3 Continuum Sampler V3.5
  → H3 Continuum Hi-Res Fix V3.5
  → Core Video / Audio VAE Decode
  → H3 Continuum Assemble + Seam V3.5
```

`H3 Continuum Second Pass V3.5`は外部加工したH3 video latentをphysical group構造のまま再Samplingする安定版Advanced入口です。Issue #8への本体回答です。

![H3 Continuum Second Pass V3.5 node](docs/images/v35-second-pass-node.png)

外部latent upscaler接続:

```text
H3 Continuum Sampler V3.5.video_latents
  → LBH等の外部H3 latent処理
  → H3 Continuum Second Pass V3.5
  → Core Video / Audio VAE Decode
  → H3 Continuum Assemble + Seam V3.5
```

画像では`BasicScheduler`を省略していますが、Second Pass用`SIGMAS`の接続は必要です。GPU受入済み基準は`res_multistep`、`simple / 10 steps / denoise 0.35`、Lanczos pixel resize、FL2VA 1×5秒・576→1152です。Hybrid FL2VA + Referenceも1×5秒で、統合2x Hi-Res FixとAdvanced Second Pass直結の両方を受入しました。

Hi-Res Fixを接続しなければV3.4 Sampling経路は変わりません。強制CPU offloadや低VRAM samplerは追加していません。`enabled=false`ではResize、VAE、Second Passを評価せず、元のVideo／Audio LATENTとAssembly Planをそのまま返します。

### 2. 低メモリAssemble + Seam

`H3 Continuum Assemble + Seam V3.5`はRAM / Disk-backed / Autoを選択できます。Disk-backedでは完成Video IMAGEをWindows対応mapped fileへ直接writeし、AudioはRAMに維持します。

1536×1536・360 frames・完成IMAGE 9.49 GiBの実測では、RAM版とDisk-backed版の映像／音声hashが完全一致しました。

| Windows process指標 | RAM | Disk-backed | 削減 |
|---|---:|---:|---:|
| Private memory | 12.41 GiB | 2.91 GiB | **9.50 GiB** |
| USS | 10.29 GiB | 0.80 GiB | **9.49 GiB** |

これはContinuum Assembly時の**システムRAM／private commitment削減**であり、SamplerのGPU VRAM削減値ではありません。Disk I/Oにより最終Assemblyが遅くなる可能性はありますが、前段のモデルSampling速度は変えません。

### GPU受入範囲

| 経路 | 条件 | 結果 |
|---|---|---|
| Main Hi-Res Fix | FL2VA 1×5秒、576→1152 | PASS |
| Main Hi-Res Fix | Hybrid FL2VA + Reference 1×5秒、576→1152 | PASS |
| Advanced Second Pass | Hybrid／Reference 1×5秒、576×576 | PASS |
| Main Hi-Res Fix | FL2VA 3×5秒、576→1152、RTX 5060 Ti 16 GiB | **Terminal 77TでCUDA OOM** |

3×5秒2xではFirst Passと37T groupのSecond Passは完了し、最後のlogical `[2,3]`を維持した77T physical groupが1152×1152の最初の推論でVRAM上限に達しました。group構造の破損ではなく、16 GiB実機でのリソース上限です。

詳しいsocket接続・OFF時のpassthrough・既知の制限は[英語版V3.5接続ガイド](docs/V35_HIRES_FIX.md)を参照してください。

## 推奨テンプレートワークフロー

- [V3.6推奨テンプレート](examples/workflows/MiniMax_H3_Continuum_V36.json)
- [V3.5互換テンプレート](examples/workflows/MiniMax_H3_Continuum_V35.json)
- [V3.5.1 LBH＋Conditioning Bridge接続例](examples/workflows/MiniMax_H3_Continuum_V351_LBH_Conditioning_Bridge.json)

V3.6テンプレートはContinuation BackendがStandard、Hi-Res Fixが初期OFF、AssembleのBuffer BackendがAutoです。First Frame、Last Frame、Reference Image 1～3は1つのmegapixel設定を共有します。`Video Guide Size`は`Video Guide Frames`に使うframe batchを調整し、decodeとframe-rate変換はVideo loader側で行います。V3.5テンプレートは互換用として変更せず維持します。

## V3.4互換

V3.4ノードは保存済みワークフローを壊さないため残しています。Node ID、公開socket、Sampling、Conditioning、Terminal Merge、Assembly、Seam、Run StorageをV3.5へ置換していません。Second PassやDisk-backed Assembleを必要としない場合は、従来どおりV3.4を使用できます。

## V3.4.0 Stable

V3.4.0は、最大3枚のReference Image、Run Storage、Spectrum Interop、Decode後のAudio / Video Seam補正を維持し、`Driving Audio`と`Video Guide Frames`を正式な入力として追加します。

`Driving Audio`は入力音声を絶対時間で各Chunkのガイドに使い、最終出力には元音声を維持します。`Video Guide Frames`はVideo loaderが出力したIMAGE frame batchを全Chunkで継続使用し、`Efficient - 0.4 MP`、`Balanced - 0.6 MP`、`Match Output`から処理解像度を選択できます。青いIMAGE socketですが、通常の1枚の静止画参照ではなく動画フレーム列を接続します。

### Size項目の条件付き表示と内部Resize

V3.5のCompact UIでは、対応する入力を接続した時だけSize項目を表示します。

- `reference_image_1`～`reference_image_3`のいずれかを接続すると、`Reference Size`を表示します。
- `Video Guide Frames`を接続すると、`Video Guide Size`を表示します。以前のWorkflowやIssueで`Video Reference Size`と記載されている項目と同じもので、V3.5.1では表示名だけを`Video Guide Size`へ明確化し、既存のbackend keyと保存済みWorkflowの互換性を維持しています。

したがって、新規ノードで見えないSize項目は欠落ではなく、未接続のため非表示になっています。Reference ImageとVideo Guide FramesはVAE Encode前に内部Resizeされます。Video Guide Framesはアスペクト比を維持してH3 canvasへ整列し、縮小が必要な場合はLanczosを使用します。小さい入力を自動的に拡大はしません。通常は外部Resizeノードを必要としませんが、意図的なcrop、小さい素材の強制upscale、独自のresize／upscale方式を使う場合には外部処理を利用できます。動画のdecodeとframe-rate変換は引き続きloader側の責任です。

Reference入力のバイパスされたソケットは無視され、有効な画像だけがPicture 1から連続採番されます。空欄や不完全なプロンプトも停止せず、警告とFixed fallbackで生成を続行します。未知のモデル、ノード、プロンプト形式を独自判断で拒否する制限も撤廃しました。

Run Storageの保存契約にはDriving AudioとVideo Guide Framesのidentityを含め、入力変更後に古いChunkを誤再利用しないようにしています。

## Driving Audio / Video Guide Frames / Seam

Driving Audioだけを使う、Video Guide Framesだけを使う、Video Guide Framesと別音声を組み合わせる、という3通りの接続に対応します。Video Guide Framesは24 fps入力を基準とし、異なるfpsの素材はLoad Video側で24 fpsへ設定してください。

H3 Continuum Assemble + SeamはAudio Seam AutoとVideo Seam Autoを既定とし、フレーム削除を行わずに境界の一時的な露出・色変化を補正します。Auto 2は露出ランプ向けの実験的な追加モードです。

## Legacy V2.1.7 Stable Facade UI

V2.1.7では、V2.1.6の動的表示制御を廃止し、標準ComfyUI描画だけを使用する静的Facadeへ移行しました。生成処理は互換用`H3ContinuumSamplerV2`を再利用し、State、Session、Prompt Plan、Spectrum Interop、保存Schemaは変更していません。

通常表示は次を中心にします。

```text
model / clip / video_vae / audio_vae / sampler / sigmas
Sequence Prompt
first_frame
prompt_overrides（任意pack）
advanced（任意pack）

Prompt Format
chunks
chunk_seconds
width / height
continuity
base_seed
control after generate
Seam Correction
Seam Correction

outputs: images / audio / result
```

### 補助ノード

- `H3 Continuum Clip Overrides`: Clip別Promptを1本のpackへまとめます。
- `H3 Continuum Advanced`: resume/session入力と低頻度設定をまとめます。
- `H3 Continuum Result`: resultから`last_state / session / report`を展開します。
- 補助ノードを使わない通常生成では、Sampler本体だけで動作します。

### Legacy互換

旧`H3ContinuumSamplerV2`は削除せずLegacy/Coreノードとして登録を維持します。既存WorkflowのノードID、入力順、出力順は変更していません。

## Continuity

- `Auto — conservative`
- `Balanced — 22 frames`（標準）
- `Fast — 5 frames`
- `Strong — 39 frames (Experimental)`

5/22/39フレームはH3の時間latent周期`1,4,4,4,4`に対して、それぞれ2/7/12 temporal latent stepsです。

## Spectrum

Continuumは有効な前チャンクContextがある場合だけ`h3_continuum` Interop API v1をMODEL optionsへ付与し、対応Spectrumへ`min_actual_prefix_steps=2`を要求します。初回チャンクにはInterop keyを付与しません。未知・未対応Spectrumでは通常Spectrumとしてfail-openします。

## 推奨配線

```text
UNET -> SageAttention -> Sol-Attn -> LoRA -> Spectrum -> H3 Continuum Sampler
```

まず`chunks=2 / chunk_seconds=5 / Balanced 22f / Seam Correction=Off`でNative Continuityを確認し、その後`Seam Correction=Auto`を比較してください。

## インストール

ZIPを展開して、`ComfyUI-H3-Continuum`フォルダーを`ComfyUI/custom_nodes/`へ置き、ComfyUIを再起動します。

旧`ComfyUI-H3-Continuum-Join`が残っている場合は同時ロードを避けるため削除または退避してください。同梱`install_windows.bat`は旧名・新名の既存フォルダーを日時付きでバックアップします。

## 検査

V3.6 release gateはPIG-0～PIG-5を完了し、backend別Run Storage、実cache Save／Resume／Regenerate From、Terminal Mergeのatomic再利用、Reference Image／Audio保持、保護prefix bit-exact、GPU Workflow、Audio Seam数値検証、実聴Audio PASSを含みます。最終自動検証は`527 passed`で、完全なpackage checklistは`PACKAGE_VALIDATION.txt`へ記録しています。source/runtime登録、PackedLayout、Fixed 3×5 Prompt Plan、JavaScript UI harness、Prompt/CLIP cache一致、Video Guide bit-exact A/B、V3.5 Second Pass／Hi-Res、V3.5.3配布整合性の回帰も維持します。

Main Hi-Res Fixの3×5秒2xは、RTX 5060 Ti 16 GiBで37T groupの1152×1152 Second Pass完了後、Terminal Mergeの77T group最初の推論時にCUDA OOMとなり未受入です。Reference/Hybrid固有の1×5秒Second Passは受入済みですが、長尺Reference/Hybridは未確認です。Disk-backedが保証する低メモリ範囲はContinuum Assemblyであり、Core Decodeや下流ノードが別の全量copyを作る可能性は残ります。

```text
python -m compileall -q .
pytest -q
```

MIT License。
