# ComfyUI-H3-Continuum 3.8.0

MiniMax H3を複数チャンクで連続生成し、直前チャンク末尾の**映像latent / 音声latentを直接**次チャンクへ継承するComfyUIカスタムノードです。チャンク間でVideo/Audio VAEのDecode→Encodeは行いません。

## インストール・更新

新規導入：

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/ukr8b3g-cmyk/ComfyUI-H3-Continuum.git
```

既存のGit導入を更新：

```bash
cd ComfyUI/custom_nodes/ComfyUI-H3-Continuum
git pull --ff-only origin main
```

ComfyUIを再起動してください。Managerから導入した場合はManagerのUpdateを使い、同じノードを重複配置しないでください。

V3.8 Workflow：[JSON](examples/workflows/MiniMax_H3_Continuum_V38.json)／[同じJSONを含むZIP](examples/workflows/MiniMax_H3_Continuum_V38.zip)。Spectrumを初期設定とする1本です。[LightX2V Turbo](https://github.com/ModelTC/Minimax-H3-Turbo)にも切り替えられますが、完全なgraphを開くにはSpectrum・rgthree・KJNodes・ComfyUI-Easy-Useが必要です。外部ノードは別途導入してください。

## プロンプト・スキルのダウンロード

- [LLM用システムプロンプトZIP](H3-Continuum-LLM-System-Prompt-v1.zip)：Continuum向けプロンプト作成のシステム指示と詳細資料。
- [Continuum専用プロンプトスキルZIP](H3-Continuum-Skill-v1.zip)：Codexなどで使う、チャンク構成に対応した汎用プロンプト作成スキル。
- [Continuum Dance DirectorスキルZIP](minimax-h3-continuum-dance-director.zip)：主役のダンサー1人を対象に、チャンク間の身体動作とカメラの連続性を考慮した長尺ダンス用プロンプトを作成するスキル。

いずれも任意のプロンプト作成支援資料で、ComfyUIのカスタムノードではありません。ZIPを展開し、同梱の案内に従って利用してください。Samplerを変更するものではなく、生成動作や画質を保証するものでもありません。

## V3.8の公開範囲

H3 Continuumは、長尺映像を最初からやり直さずに生成・確認・部分再生成・再開するProduction Samplerです。V3.8は`Main / Production`と`Advanced`の2層に整理しました。

V3.8で検索可能な公開ノードは次の7つです。

- `H3 Continuum Sampler V3.8`
- `H3 Continuum Finalize`
- `H3 Continuum Load Image`
- `H3 Continuum Load Audio`
- `H3 Continuum Load Video`
- `H3 Continuum Second Pass`
- `H3 Continuum Reference Audios`

Main Sampler内の`Show Advanced Settings`／`Hide Advanced Settings`で詳細設定を開閉します。旧node property `H3 Continuum View`を含む保存Workflowは対応する開閉状態へ移行し、旧propertyを削除します。これは表示状態だけの変更です。Python input、widget順、保存済みwidget値、backend引数、Sampling identity、Run Storage identityは変更しません。Frontend extensionが読み込まれない場合も、Python定義の全widgetが表示された状態で実行できます。

標準経路は`Sampler V3.8 -> Core Video/Audio Decode -> Finalize -> Create Video -> Save Video`です。Finalizeの`IMAGE`／`AUDIO`出力をCoreの`Create Video`で`VIDEO`へまとめてから保存します。Core Decode、Save、Upscalerは外付けとし、外部latent processorやupscalerはSecond Passをbridgeとして接続します。外部processorが変更できるのはVideo LATENTの空間解像度だけで、physical group、B/C/T、finite値、First Pass Audio、元のAssembly Planを維持する必要があります。Finalizeは公開`IMAGE`／`AUDIO`型を受け取り、特定decoder classへ依存しません。SageAttention、Sol-Attn、Spectrumは外部MODEL wrapperのままです。詳細は[V3.8 Open Integration Contract](docs/V38_OPEN_INTEGRATION_CONTRACT.md)を参照してください。旧Hi-Res FixはV3.8標準Workflowに含めません。

### Reference Audio 1/2/3

`H3 Continuum Reference Audios`は、最大3本の単独Reference Audioを1本の`Audio References (Optional)` socketへまとめます。入力は間を空けずに接続し、Promptでは接続順どおりに`<Audio 1>`、`<Audio 2>`、`<Audio 3>`を使用します。共通のCore Audio VAEで各Audioを個別encodeします。生成後の最終Audioを置換せず、Driving Audio契約も変更しません。既存Workflowは従来の単数`Reference Audio (Optional)`をそのまま使用できますが、単数経路とbundle経路は同時接続しないでください。

> **V3.8 support boundary:** V3.8からexportするのは上記7ノードだけです。Finalizeの`H3ContinuumAssembleSeamV35`、Second Passの`H3ContinuumSecondPassV35`など、公開ノードの一部は旧IDを維持していますが、すべての旧Workflowに互換性があるという意味ではありません。現在の7ノード以外のIDを含む保存Workflowはunknown nodeになる場合があります。その場合は対応するhistorical Release/tagを使用してください。詳細は[V3.8 Release／Migration Policy](docs/V38_RELEASE_AND_MIGRATION.md)を参照してください。

複雑な16GB GPU受入Gateでは約`15.5～15.6 GiB`を使用しました。GPU、driver、backend、model精度、解像度、接続ノードで変動するため、すべての16GB GPUでの動作保証ではありません。

### サイズの決め方を直接選択

| Preset | 目安 |
|---|---|
| `Draft` | 約0.30 MP |
| `Balanced` | 約0.60 MP |
| `Native 768` | 短辺768を目標。極端なAspectでは長辺1344 capを優先 |
| `Custom MP` | Megapixelを直接指定。Native 768のcapとは別 |

Mainの`Size Source`は次の2択です。

- `First Image`：接続したFirst Imageの縦横比を維持し、Presetの目標面積から最終Width／Heightを算出します。
- `Manual`：Width／Heightを32 pixel単位で直接指定します。この場合、Presetは適用しません。

MainのWidth／Heightは`Manual`のときだけ表示・編集できます。`First Image`ではResolutionを表示し、画像の縦横比からサイズを決めます。有効なFirst ImageがSamplerへ届かない場合は、保持しているManual Width／Heightへフォールバックし、その寸法をStatusへ表示します。手動寸法を確認・変更する場合は`Size Source = Manual`を選びます。Reference ImageやVideo Guideからサイズを暗黙取得することはありません。

旧V3.8の`Auto / Landscape / Portrait / Square`はWorkflow／API互換用として内部で受け付けます。FrontendはAutoをFirst Imageへ、3つの固定Aspectを同じ解決結果のManual Width／Heightへ移行します。

### 10秒を5秒ずつ確認しながら作る

ここでは、画面に表示される名前だけを使って手順を説明します。

#### 最初に知っておくこと

`Chunks = 2`、`Seconds per Chunk = 5`は、完成目標が合計10秒という意味です。ただし、`Run = Review Each Chunk`では10秒を一度に生成しません。最初のQueueでは、確認用に**Chunk 1の5秒だけ**を生成します。これは正常動作です。

Chunk 1を確認した後に操作を選び、もう一度QueueするとChunk 2へ進みます。`Chunks = 1`では最初の5秒が最後なので、次へ進む操作はありません。

#### 手順1：生成前の設定

`H3 Continuum Sampler V3.8`で、上から次の順に設定します。

1. `Control After Generate`を`fixed`にします。`randomize`、`increment`、`decrement`では続きを再利用できません。
2. `Chunks`を`2`にします。
3. `Seconds per Chunk`を`5`にします。
4. `Total Length`が`10 seconds`になったことを確認します。`Total Length`は確認表示で、直接変更する項目ではありません。
5. `Run`を`Review Each Chunk`にします。
6. `Progress`を`On — Resume and Takes available`にします。
7. 緑色の`Ready to Queue`欄に、`2 × 5s = 10 seconds`と`Review each chunk`が表示されていることを確認します。`Set Control After Generate to fixed`と表示された場合は、Queueする前に手順1を直します。

#### 手順2：最初の5秒を作る

1. ComfyUIの`Queue`を押します。
2. Chunk 1だけが生成されます。出力動画が5秒でも正常です。
3. Queueの処理が完了すると、Samplerの表示が自動的に`Chunk 1 is ready for review`へ切り替わります。

#### 手順3：Chunk 1の動画を確認する

保存された5秒の動画を再生し、そのまま採用するか、作り直すかを決めます。この時点ではまだ合計10秒の動画は完成していません。

#### 手順4：次の操作を1つ選ぶ

| 画面上のボタン | 次のQueueで行うこと |
|---|---|
| `Use it and continue` | 現在の5秒を採用し、次のChunkを1つ生成します。 |
| `Try this chunk again` | 現在のChunkだけを別のTakeとして作り直します。 |
| `Use it and finish the rest` | 現在までを採用し、残りのChunkをまとめて生成します。 |

ボタンを選んだだけでは生成は始まりません。選択したボタンに`✓`が付いたことを確認してから、ComfyUIの`Queue`を押します。

`Try this chunk again`はContinuum側で別Takeを作るため、作り直しでも`Control After Generate`は`fixed`のままにしてください。

#### 手順5：2本目の5秒を作り、10秒を完成させる

1. `Use it and continue`を選びます。
2. ComfyUIの`Queue`をもう一度押します。
3. 採用済みのChunk 1を再利用し、Chunk 2を生成します。
4. Samplerから後ろのDecode、`H3 Continuum Finalize`、Save Videoまで通常どおり実行されると、合計10秒の完成動画が出力されます。

設定を確認し直したい場合は`Back to Settings`を押します。未処理のReviewへ戻る場合は`Return to Review`を押します。どちらも生成を自動開始せず、選択済みのTakeや保存済みChunkも削除しません。

#### 迷ったときの確認

- 最初のQueueで5秒だけ出た：`Review Each Chunk`の正常動作です。
- 次へ進むボタンが出ない：Queueが完了しており、`Progress = On — Resume and Takes available`、`Chunks = 2`以上であることを確認してください。正常なら完了後に自動表示されます。
- ボタンを押しても生成されない：操作を選んだ後、ComfyUIの`Queue`をもう一度押してください。
- `Set Control After Generate to fixed`と表示された：`Control After Generate`を`fixed`にしてください。別SeedのChunk 1が増えることを防ぐ安全チェックです。
- 1回で10秒すべて作りたい：`Run`を`Generate Full Video`にします。

Long Terminal Mergeのpairは分割せず、1つのReview単位として扱います。

Driving AudioはReview／Smart Regenerateと併用できます。Continuum Image／Audio／Video Loaderは任意入力向けのnative bypassに対応します。

> **Reviewの制限:** Review途中のpartial sequenceでは、Second Pass／`refine_context`を正式対応範囲に含めません。Reviewを完了してsequenceを確定してからSecond Passを実行してください。

### Take・Branch・安全な継続

Run Storageを有効にすると、Production表示に**Render History / Takes**が表示されます。
Takeを選択してもcanonical結果は変わりません。**Use This Take**でそのrevisionを
canonicalにし、**Continue From Here**で選択したTakeまでを保持して後続groupだけを
再生成します。どちらの操作も自動Queueは行いません。

## 歴史的な実装・受入記録（V3.8標準Workflowではありません）

以下の節は旧リリースと互換性作業の記録です。上記のV3.8標準経路を変更するものではありません。

### V3.7 高解像度Refinement基盤

V3.7では`H3 Continuum Sampler V3.7`を追加し、解像度を変更するSecond Passに必要な2つの基盤を完成させました。V3.6のProduction初期値と既存SIGMAS socketは変更していません。

### 解像度変更後もConditioningを再構築

Conditioning Adapterは、First／Last Image、Continuation context、Still Image Guideの元画像をtarget latent geometryに合わせて再構築します。Physical group ownership、Long Terminal Merge、Core側のPackedLayout／RoPE再構築、First Pass Audioのpassthroughは維持します。704×704と1152×1152のCorrectness GateはPASSしていますが、大きなcanvasほどmemory使用量と処理時間は増えます。

### RefineScheduleでRefinement範囲を明示

内部のversioned contractである`RefineSchedule`は、`External`、`Full`、`Tail`、`Partial`に対応します。`External`は入力SIGMAS tensorをそのまま維持し、`Tail`と`Partial`は同じsource scheduleから範囲を正確に切り出します。内部Tail 6 Gateでは、6 evaluationのsuffix再現とdecoded Audio PCMのbit-exact passthroughを確認しました。現時点では実装基盤として内部で扱い、公開widgetは追加していません。Production初期値も変更していません。

### Still Image GuideはExperimental

V3.7では、Still Image Guide 1枚をabsolute frameからowner physical groupへ割り当て、高解像度Second Passでも元画像から再encodeできます。位置変換、Terminal Merge ownership、Run Storage identity、non-owner groupの非干渉はCorrectness PASSです。一方、Core Add Guideはhard anchorとして働くため、anchor位置で急なtrajectory変化が起き、その後のmotionも別の軌道へ分岐する場合があります。**Still Image GuideはExperimentalで、Production昇格はHOLDです。** 滑らかなtransition制御としては扱わないでください。

### V3.6.1 Maintenance Hotfix

V3.6.1は、受入済みBalanced 22 Masked AV経路を変更せず、限定的なfail-open／互換性問題を修正します。Timeline/List記法が混在したPromptは`H3C-P105`を表示し、Timeline解析ではstandalone `---`行だけを除去します。未指定Chunkの既存fallbackとFixed Promptのfail-open動作は維持し、Prompt構文だけを理由に生成を停止しません。

`Continuation Backend = Standard`かつAudio Continuity ONでは、`Balanced — 22 frames`が引き続きMasked AVを使用します。`Fast — 5 frames`、`Strong — 39 frames`、`Auto — conservative`はRun Storage identity作成前に、受入済みReference Contextへ解決します。UIの選択値は書き換えず、status reportへ解決結果と理由を表示します。Audio Continuity OFFのStandardはMasked Video、Compatibilityは常にReference Contextのままです。

Run Storageは、Last Frame未接続を表す値をすべて同じ空identityとして扱います。通常のLast Frameなし2チャンク生成を3チャンクへ延長すると、旧最終Chunkが`none`だったV3.6.1 cacheを含めて`2 reused, 1 generated`になります。実Last Frame接続時とLong Terminal Mergeのatomic pairは従来どおり厳密です。Run StorageをOffへ変更した場合は、Queue前にhiddenのRegenerate FromとVariation Nonceも`Auto`と`0`へ戻します。

### V3.6 Masked AV Continuation

V3.6では`H3 Continuum Sampler V3.6`を追加しました。標準backendは、前Chunkで確定したVideo／Audio latent prefixを次のH3 Target内へ直接配置し、CoreのNoise Maskで保持します。V3.5のReference Context方式のように、同じ過去フレームを別Reference blockとして追加しないため、H3が処理するpacked sequenceを短縮できます。

| Continuation Backend | 用途 |
|---|---|
| `Standard` | 推奨V3.6経路。Balanced 22＋Audio ContinuityはMasked AV、Fast 5／Strong 39／Autoは安全にReference Contextへfallbackします。Audio Continuity OFF時はMasked Videoです。 |
| `Compatibility` | 受入済みV3.5 Reference Context動作へ戻すAdvanced fallbackです。 |

内部transport識別子はUIへ表示しません。Run Storage identityは実行前に解決したtransportへ従います。Balanced 22 Masked AVはReference Contextと分離し、非Balanced Standard fallbackは同一動作のReference contractを安全に共有します。`Regenerate From`でもLong Terminal Mergeのlogical `[2,3]`を1つのphysical sampleとして再利用・再生成します。

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

**V3.8.0が現在のRelease Candidateです。** V3.8が内部利用する旧module/classはsourceへ維持します。exportするのは現在の公開7ノードだけで、その一部は旧IDを維持しています。それ以外のIDを必要とする旧保存Workflowは、対応するhistorical Release/tagを使用してください。Still Image Guideは引き続きExperimentalです。

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

## 公開テンプレートワークフロー

- [V3.8 Workflow JSON](examples/workflows/MiniMax_H3_Continuum_V38.json) — Spectrum初期設定の現行graph 1本
- [V3.8 Workflow ZIP](examples/workflows/MiniMax_H3_Continuum_V38.zip) — 同じJSONのみを格納。カスタムノードのインストーラーではありません

Registry配布予定の対象もこのJSONとZIPです。依存なしのテンプレートではなく、Spectrum・rgthree・KJNodes・ComfyUI-Easy-Useが必要です。Turboへ切り替えてもgraph内の外部ノードは残ります。SpectrumをOFFにし、用途に合うLightX2V Turbo LoRAを1本だけONにしてsampler／Stepsを合わせます。初期状態はSpectrum ON、Turbo LoRA OFF、res_multistep／simple／20 Stepsです。

配布元のprompt、画像・音声名、ノード表示名、設定は変更していません。手元にあるファイルを選び、不要な入力をOFFにし、promptを入力してください。モデルやメディアは同梱しません。`Save 3x5s Video`などの保存済み表示名は生成時間を決めません。実際の長さはSamplerのChunksとSeconds per Chunkで決まります。

旧Workflowは開発履歴としてsource repositoryへ保持しますが、V3.8 Registry packageからは除外します。旧保存Workflowは[Migration Policy](docs/V38_RELEASE_AND_MIGRATION.md)に従い、対応するhistorical Release/tagで開いてください。Registryの正式pack検証・公開はGitHub sourceの更新とは別工程です。

## V3.4互換

V3.4の実装moduleは内部継承とhistorical testのためsourceへ保持しています。V3.8からexportするのは現在の公開7ノードに含まれるIDだけです。それ以外のIDを必要とするV3.4保存Workflowは、対応するhistorical packageを使用してください。

## V3.4.0 Stable

V3.4.0は、最大3枚のReference Image、Run Storage、Spectrum Interop、Decode後のAudio / Video Seam補正を維持し、`Driving Audio`と`Video Guide Frames`を正式な入力として追加します。

`Driving Audio`は入力音声を絶対時間で各Chunkのガイドに使い、最終出力には元音声を維持します。`Video Guide Frames`はVideo loaderが出力したIMAGE frame batchを全Chunkで継続使用し、`Efficient - 0.4 MP`、`Balanced - 0.6 MP`、`Match Output`から処理解像度を選択できます。青いIMAGE socketですが、通常の1枚の静止画参照ではなく動画フレーム列を接続します。

### Size項目の条件付き表示と内部Resize

V3.5のCompact UIでは、対応する入力を接続した時だけSize項目を表示します。

- `reference_image_1`～`reference_image_3`のいずれかを接続すると、`Reference Size`を表示します。
- `Video Guide Frames`を接続すると、`Video Guide Size`を表示します。以前のWorkflowやIssueで`Video Reference Size`と記載されている項目と同じもので、V3.5.1では表示名だけを`Video Guide Size`へ明確化し、既存のbackend keyと保存済みWorkflowの互換性を維持しています。

したがって、新規ノードで見えないSize項目は欠落ではなく、未接続のため非表示になっています。Reference ImageとVideo Guide FramesはVAE Encode前に内部Resizeされます。Video Guide Framesはアスペクト比を維持してH3 canvasへ整列し、縮小が必要な場合はLanczosを使用します。小さい入力を自動的に拡大はしません。通常は外部Resizeノードを必要としませんが、意図的なcrop、小さい素材の強制upscale、独自のresize／upscale方式を使う場合には外部処理を利用できます。動画のdecodeとframe-rate変換は引き続きloader側の責任です。

Reference入力のバイパスされたソケットは無視され、有効な画像だけがPicture 1から連続採番されます。空欄や不完全なプロンプトも停止せず、警告とFixed fallbackで生成を続行します。未知のモデル、ノード、プロンプト形式を独自判断で拒否する制限も撤廃しました。

## Run Storage：第2部分だけを再生成

通常のT2VA／I2VAを`2 chunks x 5 seconds`にした場合、Chunk 1が最初の5秒、Chunk 2が次の5秒です。

初回生成前に次を設定します。

1. `Run Storage`を`Save + Auto Resume`にします。
2. 固定の`Run Name`を選び、Base Seedも固定します。
3. まず10秒全体を一度生成します。Continuumは完了した各Chunkのraw Video／Audio latentを保存します。

最初の5秒を保持して、第2部分だけを作り直す手順は次のとおりです。

1. Run Name、Base Seed、model、LoRA、解像度、sampler、SIGMAS／steps、Reference、Continuity設定を初回と同じに保ちます。
2. `Regenerate From`を`Chunk 2`にします。
3. `Variation Nonce = 0`なら、完了済みの再生成に対して新しいバリエーションを自動選択します。互換性のある未完了runを再開する場合は、既存のバリエーションを引き継ぎます。`1以上`は指定値を固定するため、同じ入力で別の結果を求める場合は別の正の値へ変更します。Base Seedは固定のままにします。
4. Workflowをもう一度Queueします。

Review画面の`Try this chunk again`は、この手動指定とは別に、内部のバリエーションを自動で進めます。

Continuumは保存済みChunk 1を再Samplingせずに読み込み、その確定済み末尾をContinuation contextとして新しいChunk 2をSamplingします。Reportの目安は`1 reused, 1 generated`です。その後、10秒全体を再Decode／Assemblyします。第1ChunkのSampling結果は再利用され、境界のSeam処理は新しいAssembly時に再評価されます。

第1部分と第2部分で異なる指示を使う場合は、初回生成前にListまたはTimeline Promptとして分けておきます。保存後にPrompt Planや生成Contractの入力を変更すると新しいRevisionになり、以前のChunk 1を再利用できない場合があります。初回を`Run Storage = Off`で生成した場合も、後から遡って再利用することはできません。`Regenerate From`はChunk境界単位であり、1つのChunk内部の任意領域を編集する機能ではありません。

FL2VA Long Terminal Mergeは重要な例外です。最後の2つのlogical Chunkを1つのatomicなphysical Samplingとして扱うため、その2つは一緒に再生成されます。

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

当時のV2.1.7では、旧`H3ContinuumSamplerV2`をLegacy/Coreノードとして登録し、既存WorkflowのノードID、入力順、出力順を維持していました。これはV3.8の公開範囲を示す説明ではありません。このIDを使う旧Workflowは対応するhistorical Release/tagで開いてください。

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

V3.8はComfyUI 0.34.2で検証しています。以下の歴史的な受入記録には旧ComfyUI版も登場しますが、現在のインストール目標ではありません。V3.8の依存を満たす限り、ComfyUIの最新版は必須ではありません。

ZIPを展開して、`ComfyUI-H3-Continuum`フォルダーを`ComfyUI/custom_nodes/`へ置き、ComfyUIを再起動します。

再起動後は`H3 Continuum Sampler V3.8`を検索してください。V3.8の検索面は上記7ノードだけです。

旧`ComfyUI-H3-Continuum-Join`が残っている場合は同時ロードを避けるため削除または退避してください。同梱`install_windows.bat`は旧名・新名の既存フォルダーを日時付きでバックアップします。

## 検査

現在のV3.8 Public Surface suiteは、正確な7 ID export、Spectrum graph 1本とZIP内JSONの同一性、外部依存、Registry除外、既存V3.8 widget/socket順を維持したAUDIO-R1 socket末尾追加、`Show Advanced Settings`／`Hide Advanced Settings`による表示切替と旧`H3 Continuum View` propertyからの移行を確認します。Registry配布対象のハッシュは`REGISTRY_MANIFEST.sha256`、source側の対象ファイルは`MANIFEST.sha256`で管理します。Gitの改行変換は無効にして配布バイト列を維持します。旧実装はmodule-local testで維持しますが、それによってV3.8の公開ノードが増えることはありません。

**配布名の最終整理前のCPU総検証（2026-09-07）：1,154/1,154 PASS。** failure、error、skip、記録されたCUDA初期化要求はいずれも0件でした。ComfyUI Core 0.34.5の隔離CPU検査で7ノード登録とnative PackedLayoutを確認し、旧Core-onlyテンプレートと提供されたSpectrum graphのgraph／schemaも確認しました。CUDAは未初期化のままです。最終配布ではSpectrum graphを変更せず汎用のV38ファイル名に統一します。これはCPU上のソフトウェア契約の検証であり、新たなGPU画質PASSや、起動中の実行環境へ最新版が反映されたことを示すものではありません。

**過去のV3.6受入記録：** PIG-0～PIG-5を完了し、backend別Run Storage、実cache Save／Resume／Regenerate From、Terminal Mergeのatomic再利用、Reference Image／Audio保持、保護prefix bit-exact、GPU Workflow、Audio Seam数値検証、実聴Audio PASSを含みます。当時の自動検証は`527 passed`であり、現在のV3.8 CPUテスト件数ではありません。package checklistと過去の受入記録は`PACKAGE_VALIDATION.txt`にあります。source/runtime登録、PackedLayout、Fixed 3×5 Prompt Plan、JavaScript UI harness、Prompt/CLIP cache一致、Video Guide bit-exact A/B、V3.5 Second Pass／Hi-Res、V3.5.3配布整合性の回帰も維持します。

Main Hi-Res Fixの3×5秒2xは、RTX 5060 Ti 16 GiBで37T groupの1152×1152 Second Pass完了後、Terminal Mergeの77T group最初の推論時にCUDA OOMとなり未受入です。Reference/Hybrid固有の1×5秒Second Passは受入済みですが、長尺Reference/Hybridは未確認です。Disk-backedが保証する低メモリ範囲はContinuum Assemblyであり、Core Decodeや下流ノードが別の全量copyを作る可能性は残ります。

```text
python -m compileall -q .
pytest -q
```

MIT License。
