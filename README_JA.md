# ComfyUI-H3-Continuum 3.9.1 — V3.9

## 3.9.1で変わった点（2026-10-04）

Second Pass、Takeの再利用、Review音声に関するバグを修正しました。

- **Second Pass**：音声のみ／複合キーフレームを保持し、途中Reviewや中間Chunk単独でも、その出力区間のconditioningとReference割当を照合して引き継ぎます。
- **Takeの再利用**：Samplerのclosure、MODELのCFG／wrapperも互換性判定に含め、異なる生成設定のTakeを誤って再利用しないようにしました。
- **ReviewのDriving Audio**：物理groupの自然時間に合わせて元PCMを1回だけ切り出します。Exact ON/OFFで開始位置を揃えます。
- **音声resample**：ComfyUI Core標準APIを優先し、古いCoreでは従来方式へ戻します。同じVAE内部の重みを直接変更する場合のReference Encode Cacheの制約も下記に明記しました。

**3.9.0から更新する場合**：更新後にComfyUIを再起動し、ブラウザーも更新してください。旧v5 Takeと履歴は読めて、削除されませんが、新しいv6生成の前半として再利用できません。新規Full Video、または **Start again from Chunk 1** で開始してください。公開Node ID・widget順・公式Workflowは維持し、引き続き **V3.9ノード** を使います。

修正済みコードは **CPU 1,696成功・1スキップ**、対象を絞ったReview Second PassのGPU検証、生成／Take再利用の統合GPU検証に合格しています。ブラウザー受入は未完了です。任意のLATENT拡大で出る二重輪郭は別課題の [Issue #27](https://github.com/ukr8b3g-cmyk/ComfyUI-H3-Continuum/issues/27) として管理し、今回の修正の必須Gateには含めません。今回もmainソースの更新で、GitHub Release／Registry公開ではありません。

![H3 Continuum V3.9：固定の参照画像番号、チャンク別割り当て、Samplerへの1本の接続](docs/images/v39/v39-feature-summary.png)

*現在の`main`はV3.9です。Image 1～9の固定番号、チャンク別のReference選択、V3.9 Samplerへの1本の接続が新しい操作です。*

## 3.9.1の修正詳細

Second Passで音声のみのキーフレームを保持し、複合キーフレームでは映像だけを空間適応します。ReviewのDriving Audioは、区間選択前の物理decode groupの自然時間から元PCMを切り出します。Exact ON/OFFの開始位置は共通です。完全に空のReview音声だけは選択映像の尺に合う無音を補い、部分的に短い音声はExact OFFで引き延ばしません。

新しい生成はSampling Contract v6／Graph Contract v4を使用します。Samplerのコード・closureとMODELのCFG／wrapper等の設定も再利用判定へ含めます。旧v5のTake・raw・生成履歴は読めますが、v6生成へ継ぎ足せません。新規Full Video、またはReviewの「Start again from Chunk 1」で新しいrevisionを作成してください。旧Takeは残ります。署名を観測できない外部設定でも新規生成は可能ですが、自動再利用は無効になります。明示した不適合TakeやRetryを別Takeへ置き換えません。

Reference／DrivingのresampleはCore標準APIを優先し、そのAPIがない旧Coreだけ従来のTorchAudioを使います。最終出力へ渡す元PCMの波形とsample rateは保持します。

**Reference Encode Cacheの制約**：同じVAEオブジェクトの内部重みを直接書き換えた場合、その変更を自動検知しません。変更後は`v3.ref_encode_cache.clear_ref_encode_cache()`を呼ぶか、新しいVAEオブジェクトへ再ロードしてください。通常の同一VAE・同一入力ではcache HITを維持します。Decode Cache Helperのresetは別のcacheを対象とし、Reference Encode Cacheを消しません。

この修正はV3.9内の変更です。公開Node ID・socket・widget順、公式Workflow、Run Storage v3、State／Session形式を維持し、LoRA Planは追加しません。CPU検証と実ブラウザー・GPU受入は別です。

V3.9では、Second Passへ渡す条件を実際のReview出力区間へ対応させます。途中までの出力や中間Chunk単独でも、条件の照合に成功すれば、その区間自身のconditioningとReference割当を継承します。全体の完了状態や保存済みTakeは変更しません。条件が不足・不一致の場合は、従来の診断付きprompt-only fallbackを維持します。

修正済みランタイムは**CPU 1696成功・1スキップ**、**512×512・24fpsのGPU 3ケース**（途中2区間、Chunk 2単独、完了済み3区間の再利用）で合格しました。全区間の条件継承を確認し、保存FLACと元PCMの対応区間は完全一致、既存Takeとrawファイルも保持しています。合格対象は修正対象の動作です。ブラウザー受入は未完了で、任意のLATENT拡大時の二重輪郭はIssue #27で別途調査します。過去のV3.8 Release／tagはそのまま利用できます。

## V3.9の基本操作を動画で見る

[H3 Continuum V3.9 — Getting Started: Chunks, Prompts & Reference Images](https://youtu.be/AKJxBXaiG6Q)（12分26秒）

First Imageの基本設定、チャンクの設定、Review／Takeでの再試行、Timeline形式のプロンプト、Reference Imagesの使い方を紹介します。英語のナレーションと字幕、7つのチャプターがあり、バージョンを明記したUIの静止画と実際の生成例で説明します。

![公開当時のH3 Continuum V3.8X2機能紹介画像](docs/images/v39/v38x2-feature-summary-historical.png)

*V3.8X2の画像も比較用に残しています。画像内の「CURRENT MAIN」は作成当時の表記で、現在の`main`はV3.9です。V3.8 SamplerとV3.8X2 Workflowは利用できますが、Reference配線はV3.9へ自動変換されません。*

## main更新：外部INTによるWidth／Height入力の修正（2026-10-01）

V3.8／V3.9のWidth／Height入力と表示コントロールの対応を修正しました。外部INTの接続位置をWorkflow保存・再読込やタブ切替後も維持します。接続中の欄は編集不可になり、表示する数値は保存済みのManual予備値です。上流ノードが実行時に出す値を推測して表示するものではありません。接続を外すと手動編集に戻ります。

Coreの **Int** ノードから正確な幅・高さを指定する場合は、**Size Source = Manual**にしてWidth／HeightのINT入力へ接続してください。**First Image**は引き続き画像とResolution設定からサイズを決めます。INTを接続しても優先順位やSize Sourceは自動で変わりません。有効なFirst Imageがない場合は従来のManualフォールバックを使います。寸法検証、Backend入力順序・初期値は変更していません。

確認済み：**全CPU試験1569 PASS／1 skipped**（新Frontend試験22/22・既存Review試験60/60を含む）、両バージョンのChrome保存・再読込とタブ5往復。外部INTを使ったV3.9のGPUテスト1回では、**480×640・24fps・96フレーム・映像／音声とも4秒**を正確に出力しました。20ステップ、全体**107.3秒**で、保存動画の全フレームを正常にデコードできました。短い単一条件の確認であり、長時間継続や全モデルでの受入確認ではありません。Sampling、Run Storage、先行するReview／キャッシュ修正、公式Workflow JSON／ZIP、過去Releaseは変更していません。

Continuumを`main`から更新し、**ブラウザーをCtrl+F5で強制更新**してください。このJavaScript修正だけならComfyUI本体の再起動は不要です。同時にPython修正や新ノード定義も更新された場合は通常どおり再起動してください。今回もmainのソース修正で、新Release／Registry公開ではありません。

## main更新：V3.9の条件付け準備の速度修正（2026-10-01）

**Prompt Format = Fixedかつ有効なReference Imagesがない場合**に、V3.9で余分なプロンプト条件付けの準備が繰り返される経路を修正しました。入力が同じ場合に既存の上限付きconditioningキャッシュを再利用します。First Imageは利用できます。List／Timeline、有効なReference Images、Reference Audio、Timeline Video、終端ペアのgroupは従来の経路を維持します。Decode Cache Helperとは別の修正で、Samplingは省略しません。

検証した`2 × 5秒`・480×640・First Imageの条件では、group準備が約**10.76秒から0.013秒**へ短縮しました。修正後の同セッション比較（warm-up後、各版3回）では、全体時間の中央値は**V3.8が273.58秒、V3.9が273.78秒**で測定範囲も重なり、以前の約6％差は見られなくなりました。全Workflow／モデル／GPUでの解決や、GPU演算そのものの高速化を確認したという意味ではありません。

Continuumを`main`から更新し、Python修正を読み込むため**ComfyUIを完全に再起動**してください。確認済み：**CPU 1558 PASS／1 skipped、GPU生成8回すべて成功**（ComfyUI 0.38.0／RTX 5060 Ti 16 GB）。Seed、チャンク／フレーム契約、Run Storage、V3.8X2／V3.9公式Workflow・ZIP、過去Releaseは変更していません。今回もmainのソース修正で、新Release／Registry公開ではありません。

## main更新：Review表示の復元修正（2026-10-01）

別のWorkflowタブへ切り替えて戻ると、保存済みTakeが残っていてもReview操作が消える問題を修正しました。Workflowの復元完了後に履歴を取得し、古い画面の非同期結果は反映しません。実際に生成設定を変えた場合のReview／Take適用ガードは維持し、元の設定に戻すと操作が復帰します。

カスタムノードを`main`から更新後、ブラウザーを更新して新しいJavaScriptを読み込んでください。確認済み：Frontend回帰60/60、関連CPU試験108件、Chromeのタブ5往復とBase Seed変更／復元。Take管理データは不変です。Sampling、Run Storage契約、V3.8X2／V3.9のWorkflowファイルと過去Releaseは変更していません。この修正のGPU継続生成は未検証です。[詳細と検証範囲](docs/REVIEW_RESTORATION_REPAIR.md)。

## 最初に：V3.9とV3.8X2

ComfyUIの **Templates → ComfyUI-H3-Continuum** には、今回選んだ[V3.9公式Workflow](examples/workflows/MiniMax_H3_Continuum_V39.json)と、別の[V3.8X2 Workflow](examples/workflows/MiniMax_H3_Continuum_V38X2.json)を2件表示します。[V3.8X2 Workflow ZIP](examples/workflows/MiniMax_H3_Continuum_V38X2.zip)には、**V3.8X2とV3.9の両JSON**を同梱しました。[V3.9単独ZIP](examples/workflows/MiniMax_H3_Continuum_V39.zip)も残します。いずれもWorkflow用ZIPで、カスタムノード本体のインストーラーではありません。V3.8 Samplerは残るので既存のV3.8X2 Workflowは使えます。ただしV3.9へReference配線や保存済みRun／Takeは自動移行しません。旧Workflowを保存しておき、新しい作業ではV3.9専用Workflowを開いてください。

選択したV3.9テンプレートは32ノードです。画像Loader 1～6は新ヘルパーへ配線済み・初期Bypassです。7～9番の入力欄は残し、必要な人が画像Loaderを追加して接続します。使用する画像を選んで必要なLoaderだけ有効にしてください。保存済みサイズ設定は**First Image＋Draft — 0.30 MP**で、別のFirst Image Loaderは有効です。Queue前に自分のFirst Imageファイルを選び直してください。保存済みのWidth/Height 480×640はManual時だけ有効です。`Reference Image Size`は`Match Output`で、読み込み後のconditioningを縮小しますが元画像ファイル自体は縮小しません。チャンク別Referenceの効果を明瞭に試すなら、First ImageとLast ImageをOFFにし、Manualへ切り替えてReference Imagesだけを使うのが勧められます。First／Lastを入れるとそれ自体が動画を拘束し、Last Imageは最後の2つの論理チャンクを1つの生成groupに結合する場合があります。その場合、両チャンクの有効Reference集合は同じにしてください。Referenceを外しても、前チャンクの映像から人物が引き継がれることはあります。

ヘルパーの `All chunks` は接続画像を全チャンクに、`Per chunk` は画像×チャンクの表で指定します。このテンプレートは`Per chunk`で全チェックOFFから始まるため、Loaderを有効にした後、使用したいチャンクにもチェックしてください。空欄があっても番号はずれず、Image 1は常に`@R1`、Image 9は`@R9`です。Sequence Promptにはチャンクごとの動作を短く書き、そのチャンクで使う画像の`@R`タグを付けます。内部の`<Picture N>`番号はgroupごとに自動変換されます。使わないタグは警告しますが生成を止めません。まず短いチャンクと縮小済み画像で試してください。入力元画像はSamplerのReference Image Size設定より前にRAMを使うことがあります。

V3.9.1は`main`の現行ソースです。バージョンを固定したソースは[GitHub Releases](https://github.com/ukr8b3g-cmyk/ComfyUI-H3-Continuum/releases)から取得してください。ComfyUI Registryへの公開は別の作業です。過去のReleaseとtagも残します。設定済み1024×1024のReference-only GPU/APIテストは通っていますが、無改変の公式テンプレート初期設定とブラウザー保存・再読込は別の受入項目です。古い環境を厳密に再現するには対応する過去のRelease／tagとWorkflowを使用してください。現行mainにもV3.8 Samplerを残し、V3.8X2 Workflowを使えるようにしています。

`pyproject.toml`の宣言上はComfyUI `>=0.32.0`ですが、以前の実生成・GPU検証はComfyUI `0.34.2`、上記の限定したFixedキャッシュ比較は`0.38.0`で行いました。最低宣言版でV3.9の実機動作を確認済みという意味ではありません。最新の記録済みWindows CPU試験は`1696 passed / 1 skipped / 0 failed`、以前の別環境Linux再実行報告は`1534 passed / 3 skipped / 0 failed`で、新しいキャッシュ／外部INT試験は含みません。これらは無改変の公式テンプレートの実ブラウザー保存・再読込やGPU受入を代替しません。

## V3.9 Reference Images

### Reference Imagesノード：画像とチャンクを選ぶ

![H3 Continuum Reference Images V3.9ノードの固定スロットとチャンク別割り当て表](docs/images/v39/v39-reference-images-node.png)

*この画像は操作例で、配布Workflowの初期割り当てではありません。* Image 1～9は固定スロットで、途中が空でもImage 1は常に`@R1`です。`Reference Use = Per chunk`にすると、使いたい画像とチャンクの交点をチェックできます。各行の`All`／`Off`は、その画像を全チャンクで選択／解除します。画像ではImage 1をChunk 1・2に割り当て、ほかの画像は別のチャンクに割り当てています。公式V3.9 Workflowは画像Loaderが初期Bypass、割り当てが全OFFです。実ファイルを選び、Loaderを有効化してから、使うチャンクにチェックしてください。

### Sampler V3.9：ヘルパーから1本で接続

![Reference Images Optional入力を1本持つH3 Continuum Sampler V3.9](docs/images/v39/v39-sampler-node.png)

ヘルパーの緑色の`reference_images`出力を、Samplerの`Reference Images (Optional)`入力へ1本つなぎます。V3.8X2 Workflowは旧V3.8 Samplerと従来のReference接続を使用し、開くだけでV3.9配線へ変換されるわけではありません。この画像のサイズ設定は**Manual 480×640の操作例**で、公式V3.9 Workflowの保存値は**First Image＋Draft 0.30 MP**です。`Reference Image Size = Match Output`は画像読込後のReference conditioningサイズを決め、元ファイルを事前縮小したり、動画の出力解像度を直接決めたりはしません。

V3.9では、固定番号の参照画像1～9を新しい **H3 Continuum Reference Images V3.9** ノードにまとめます。ノード内の表で「All chunks」またはチャンク別のチェックを選び、Samplerへは1本だけ接続します。`Sequence Prompt`で`@R1`と書けば固定の画像1を指します。有効なタグは各生成groupの実際の`<Picture N>`へ変換されます。両モードとも同じチャンク別処理を通ります。

Promptは実行を止めません。明示的なTimelineでも解析できなければ元の入力をFixedとして扱い、診断`H3C-P100`を出します。Timelineで指定のないチャンクは前のPromptを再利用し、`H3C-P101`で知らせます。どの画像を各チャンクに使うかはReference Imagesノードで選び、Prompt中の`@R1`～`@R9`は接続画像の固定番号に対応させてください。

同梱の`2 × 10秒`Workflowでは、時間見出しを必ず単独行にし、各チャンクの動作だけを短く書きます。対応する画像LoaderをONにしてチャンク欄へチェックを入れた場合の書式例です。

```text
[0-10s]
@R1 walks forward through a quiet hallway. The camera follows smoothly.

[10-20s]
@R2 enters from the right. The camera turns to follow @R2.
```

人物や動作は実際の画像に合わせて書き換えてください。これは書式例で、配布WorkflowのPromptは空欄です。`[0-10s]`と本文を同じ行には書かないでください。チェックされた画像は、Prompt中に`@R`を書かなくてもそのチャンクのconditioningに入ります。

[公式V3.9 Workflow](examples/workflows/MiniMax_H3_Continuum_V39.json)は、今回指定された添付JSONを無改変で採用しました。[単独ZIP](examples/workflows/MiniMax_H3_Continuum_V39.zip)も用意しています。V38X2のモデル・LoRA、Decode Cache、Finalize、Saveのフル構成を維持し、画像Loaderは1～6だけを配線済み・初期Bypassにしています。7～9番を使う場合は`H3 Continuum Load Image`を追加し、ヘルパーの同じ番号の入力へ接続してください。Sequence Promptの入力ノードと配線は残し、文章は空欄です。Queue前に自分のプロンプトを入力してください。保存設定は`Timeline`、2×10秒、`Full Run`（画面表示はGenerate Full Video）、First Image＋Draft 0.30 MP、別Project IDです。従来の[V3.9 Reference Inline移行用Workflow](examples/workflows/MiniMax_H3_Continuum_V39_Reference_Inline.json)は変更せず残します。チャンク別割り当て、First/Lastとの終端結合、保存・再読込、画像メモリの注意点は[操作ガイド](docs/V39_REFERENCE_INLINE.md)を参照してください。Queue前にモデル・素材のファイル名を確認し、画像を有効化する場合は実ファイルを選択してください。7～9枚の参照は特に高負荷なので、最初は枚数と元画像サイズを抑えてください。新ノードを表示するにはComfyUI本体の完全再起動とブラウザーの強制再読込が必要です。無改変の公式テンプレートの実ブラウザー保存・再読込／GPU受入はまだ未実施です。GitHub Releaseの公開は、これらの受入やRegistry公開の完了を意味しません。

**互換性：** V3.8X2の既存Workflowは旧V3.8 Samplerと旧4～9ヘルパーで引き続き利用します。V3.9では新ヘルパーへの接続が必要です。旧Workflow上でSamplerの型だけ変えず、上記のV3.9専用Workflowを開いてください。以前のV3.9試作WorkflowにあったSampler直結1～3やSampler側の割り当て欄は配線と保存widgetの位置が異なります。V3.8の途中Run／Takeは自動移行しません。元Workflowを保存し、V3.9では別Run Nameを使ってください。

以前のV3.9操作系のブラウザー確認は、新しいヘルパーの保存・再読込確認とは別です。新ヘルパーは設定済みGPU/API実行の証拠がありますが、公式テンプレート初期設定の受入は別です。CPU／JS・Manifestも別に判定し、V3.9 GitHub Release／Registry公開はまだ行っていません。

**バージョン境界：** V3.8X2（package 3.8.3）とV3.9.0は別Workflowです。今回、新しいtag・GitHub Release・保守ブランチ・Registry版は作成せず、既存Releaseも削除しません。旧V3.8.0は既存の`v3.8.0` tagから取得できます。

## mainのLoader保存・復元修正（2026-09-21、3.8.3以降）

現行V3.8X2ワークフローは、音声を **Core Load Audio**、動画を **Core Load Video → H3 Continuum Video Adapter** に変更しました。Video Adapterは24fpsへの変換（Force Rate初期値24）とIMAGE/AUDIO出力だけを担当し、**Enableやファイル選択UIはありません**。動画を使わない場合はAdapter、または動画入力グループ全体をBypassしてください。Load VideoだけをBypassして必須入力のAdapterをONに残す構成は避けてください。

画像は **H3 Continuum Load ImageとEnable Imageを維持**します。Issue #23の継承されたmode setterへの委譲と、描画・保存中のwidget配列差し替え廃止を適用します。EnableはCoreの欄の後ろに配置し、画像ファイルとBypassの保存はCoreに委ねます。旧Audio/VideoノードIDは既存workflow用の非推奨互換ノードとして残します。V3.8X2の登録IDは互換用2個を含め10個で、V3.9では別IDのV3.9 SamplerとReference Imagesヘルパーを追加して計12個です。V3.8 Sampler設定・Sampling・Decode Cache・Finalize・既存Run Storage契約は変更しません。

更新後はComfyUI再起動と画面の再読み込みが必要です。既に保存JSONから消えたファイル名やOFF状態は推測で復元できないため、一度選び直して保存してください。既存ユーザーworkflowや保存済みTakeは自動変更しません。上流ノードの種類変更でRun Storageが新revisionになることはあるため、過去Runの再開には元workflowを保管してください。

検証範囲は[Loader修正記録](docs/LOADER_PERSISTENCE_REPAIR.md)を参照してください。CPU回帰テストと実ブラウザ確認は別です。Windows Core 0.36.0 / frontend 1.53.6のタブ切替確認は未実施で、Release/tag・Registry公開も別作業です。以下の旧Loader画像は互換ノードの説明です。


## Timeline Video — main上のExperimental機能

従来の動画IMAGE入力を**`Timeline Video Frames`**と表示し、末尾に省略可能な設定**`Video Reference Mode`**を1項目追加しました。新しい設定を持たない既存Workflow／APIは、初期値の**`Repeat Reference`**で従来動作を維持します。

- **`Repeat Reference`**：従来のVideo Guide契約です。各physical生成groupで、同じ先頭側の上限付き参照を使います。短い素材を自動ループ／Stretchしません。
- **`Follow Timeline`**：各physical出力groupの時間位置に対応する24fps参照区間を使います。Continuationの過去prefixを二重消費しません。素材終了後は動画参照なしで続行し、利用可能な終端区間にはH3 frame-grid整列分だけ短いpaddingを行う場合があります。

これは`Prompt Format = Timeline`とは別の設定です。新しいsocketやLoaderは増やさず、元動画のAudioも自動使用しません。参照動画はsoft conditioningであり、motionをframe単位で完全コピーする機能ではありません。また、decode済みIMAGE batch全体をsystem RAMへ保持するため、長尺入力のRAM削減機能ではありません。

接続は既存のままです。

```text
Core Load Video → H3 Continuum Video Adapter → Timeline Video Frames
```

公式V3.8X2 Workflow本体は変更せず、比較用Experimental Workflowを別名で追加しています。

- [Follow Timeline JSON](examples/workflows/MiniMax_H3_Continuum_V38X2_Timeline_Experimental_Follow.json)／[ZIP](examples/workflows/MiniMax_H3_Continuum_V38X2_Timeline_Experimental_Follow.zip)
- [Repeat Reference JSON](examples/workflows/MiniMax_H3_Continuum_V38X2_Timeline_Experimental_Repeat.json)／[ZIP](examples/workflows/MiniMax_H3_Continuum_V38X2_Timeline_Experimental_Repeat.zip)

ローカル受入ではFull CPU `1424 passed / 1 skipped / 0 failed`、ブラウザ保存・再読込、Follow／Repeatの`2 × 5秒` GPUテストがPASSしました。両方とも704×416、24fps、240フレーム、映像10秒、32kHz stereo音声10秒で、OOM／NaN／allocation failure／crashはありません。FollowはChunk 2で後半区間へ切り替わり、Repeatは同じ先頭側参照を維持しました。RTX 5060 Ti 16 GBで観測した最大VRAMは約15.6～15.7 GiBで、16 GBの余裕は小さい条件です。これは機能・mode分離の受入結果であり、一般的な速度や主観画質の保証ではありません。詳細は[Timeline Video Experimental](docs/TIMELINE_VIDEO_EXPERIMENTAL.md)を参照してください。

> **V3.8X2**はpackage `3.8.3`の製品名・Workflow名です。V3.8 Production Samplerを維持し、任意のReference Image 4～9と内蔵Decode Cache Helperを追加しています。旧V3.8.0は[`v3.8.0`タグ](https://github.com/ukr8b3g-cmyk/ComfyUI-H3-Continuum/tree/v3.8.0)から導入できます。

## V3.8X2 公式Workflow

- **標準名：** [JSON](examples/workflows/MiniMax_H3_Continuum_V38X2.json)／[ZIP](examples/workflows/MiniMax_H3_Continuum_V38X2.zip)
- **Helper明示名：** [JSON](examples/workflows/MiniMax_H3_Continuum_V38X2+Decode_Cache_Helper.json)／[ZIP](examples/workflows/MiniMax_H3_Continuum_V38X2+Decode_Cache_Helper.zip)

V3.8X2の2つのJSON名は**同じ公式graph**を収録した配布上の別名で、異なる設定のWorkflowではありません。どちらも内蔵Decode Cache Helperと9枚Reference Image用の接続を含み、Helperの保存値は`Auto / RAM 256MB / Disk 8GB / reset_token 0`です。標準名のV3.8X2 ZIPには別のV3.9 JSONも同梱し、Helper明示名ZIPは対応するV3.8X2 JSONだけを収録します。既存projectでは従来のV3.8X Workflowも引き続き使用できます。

## Reference Image 9枚使用時のメモリ注意

Reference Image 1～3はSamplerへ直接接続し、任意の4～9は`H3 Continuum Reference Images`を経由して`Reference Images (Optional)`へ接続します。9枚すべてを使う構成は高負荷であり、通常の最低要件ではありません。

受入テストでは、**RTX 5060 Ti 16 GB／RAM 64 GB**環境で、9枚の元画像を各**約0.30 MP**に抑えた条件で完走しました。`512 × 608`出力、`3 × 5秒`、Spectrum Off、LoRA Off、Sage Attention、Balanced 22-frame continuityで、Sampling中のVRAMは`16,311 MiB`中の約**15.0～15.5 GiB**でした。16 GB環境では余裕がほとんどありません。

多数、特に9枚を使う場合は、読み込み・接続前に元画像のコピーを約0.30 MPへ縮小してください。Sampler内の通常のconditioning用Resizeは引き続き行われますが、小さい入力ファイルにすることで読み込み・前処理時の負荷を抑えられます。高解像度参照、大きな出力、追加wrapper、同時GPU処理では、より高性能なGPUと多いシステムRAMが必要になる可能性があります。9枚は任意であり、3枚より常に高画質になる保証はありません。

## 内蔵 Decode Cache Helper

### 重要：新規生成が一律に速くなる機能ではありません

**キャッシュの手動クリア**：普段は操作不要です。Helperの「キャッシュをクリア」ボタンを押すと、次回QueueでこのHelperのキャッシュを破棄し、通常Decodeからやり直します。ボタンは即時削除や自動Queueを行いません。内部の`reset_token`は保存・API互換用に残り、押すたびに1増えます（INT上限では0へ戻ります）。作成・読込・複製だけでは変更しません。JavaScriptが使えない環境やAPI版では、従来どおり`reset_token`の値を変更してください。

**短縮するのは、変更していないlatentを再びデコードする時間です。Sampling（生成計算）自体は高速化しません。** 初回は通常Decodeとキャッシュ保存を行うためMISSとなり、保存・照合の負荷で遅くなる場合があります。毎回ランダムシードで異なるlatentを新規生成する使い方では、基本的にMISSとなり、この機能による短縮は期待できません。

具体的に再利用できる場面：

- **Continueでチャンクを追加**：既存チャンクのlatentを保持し、出力時にもう一度Decodeする場合、保存済みの既存部分だけを再利用します。追加チャンクは初回MISSです。
- **Fix／部分再生成**：変更していないチャンクのlatentがそのまま再入力される場合、その部分だけを再利用します。再生成してlatentが変わった部分はMISSです。
- **Complete／Resumeで再出力**：Samplingをやり直さず、保存済みlatentから全体を再Decodeする場合に有効です。単なる既存動画ファイルの再生ではありません。
- **Decode以降のリトライ、Finalizeや出力設定の変更**：Helperへ同じlatent・Decode関連情報が再入力され、Decodeが再実行される場合に有効です。
- **固定シードで同条件を再生成**：生成後のlatentが完全に一致した場合だけ再利用できます。同じシードだけではHITを保証しません。

これらの操作名そのものが有効条件ではありません。**各Video／Audioの入力latentの内容・shape・dtype、Decode関連メタデータ、VAE識別情報が一致し、そのHelperにキャッシュが残っていること**がHITの条件です。ComfyUIが上流／出力をそのまま再利用してDecode自体を実行しない場合、Helperによる追加のDecode短縮はありません。Helperを接続し、`Auto`または`RAM`で使ってください。レポートの`hit`は再利用、`miss`は通常Decode、`off`／`bypass`はキャッシュ再利用なしを表します。

キャッシュはPythonプロセス内の利用に限られ、再起動後は再利用しません。上限による退避・破棄やVAE識別情報の変化でもMISSになります。モード、RAM／Disk予算、`reset_token`を変更すると、この実装ではHelperキャッシュをクリアします。`reset_token = 0`を維持することは、毎回リセットする意味ではありません。

`H3DecodeCacheHelper`をContinuumパッケージ内に収録し、UI上は`MiniMax H3/Continuum/Helpers`の独立公開ノードとして残します。インストール対象はContinuumだけです。V3.8X2の公開IDは、旧互換Loader 2件を含め計10件です。V3.9は別IDのSamplerとReference Imagesヘルパーを追加して計12件です。V3.8 Sampler、Finalize、Assembly Plan、Core Decode、保存済みwidget/socket契約は変更しません。

Samplerの`video_latents`／`audio_latents`と同じVideo／Audio VAEをHelperへ接続し、Helperの`images`／`audio`をFinalizeへ接続します。Samplerの`assembly_plan`はFinalizeへ直接接続したままです。[公式V3.8X2 Workflow](examples/workflows/MiniMax_H3_Continuum_V38X2.json)は保存済みgraphと設定を維持します。このgraphにはCore VAE Decodeノードがないため、Core直結へ戻すにはCore Video／Audio Decodeを追加してFinalizeへ再配線するか、旧V3.8XのCore直結graphを開いてください。Helperを単に削除しても自動では戻りません。

`Auto`は全physical groupのVideo Decodeをプロセス専用Diskへ、小さなAudio Decodeを上限付きRAMへ保存します。`Off`はnative Decodeを使い、Helper Cacheを破棄します。Cache障害時はnative Decodeへ戻りますが、native DecodeのOOMやQueue中断は再試行しません。Python再起動後にCacheファイルを再利用しません。移行時は同じ`H3DecodeCacheHelper` IDを提供する旧単独addonと内蔵版を同時登録しないでください。内蔵版の導入確認後に旧addonを無効化または撤去します。

736×416（0.306MP）、3×5秒、Euler/simple 6 steps、Turbo FL2V v1.2、ウォーム、Video 3/3 HITの1条件では、Full Run Totalの**機構推定中心値は約47秒／約24.5%短縮**でした。直接A/Bの1ペアは50.887秒／26.46%、Samplingを伴わないComplete/Resumeの2ペアは平均46.309秒／79.826%短縮でした。これは限定条件の観測値で、反復された一般平均や無条件の20%以上高速化保証ではありません。初回MISSは遅くなる場合があり、新規Samplingは高速化せず、latentまたはVAE識別情報が変わればMISSになります。

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

旧V3.8.0を別フォルダへ導入する場合：

```bash
cd ComfyUI/custom_nodes
git clone --branch v3.8.0 --single-branch https://github.com/ukr8b3g-cmyk/ComfyUI-H3-Continuum.git ComfyUI-H3-Continuum-v3.8.0
```

Continuumのcheckoutは同時に1つだけ有効にしてください。ComfyUI Managerの**Update**は`main`を更新するため、過去tagの選択には使いません。

V3.8X2 Workflow：[JSON](examples/workflows/MiniMax_H3_Continuum_V38X2.json)／[V3.8X2・V3.9両JSONを含むZIP](examples/workflows/MiniMax_H3_Continuum_V38X2.zip)。V3.8X2 JSONはSpectrum対応の1本で、保存状態ではSpectrumとTurbo LoRAはどちらもOFFです。[LightX2V Turbo](https://github.com/ModelTC/Minimax-H3-Turbo)にも切り替えられます。完全なgraphを開くにはSpectrum・rgthree・KJNodesが必要です。ComfyUI-Easy-Useは不要です。

## プロンプト・スキルのダウンロード

- [V3.9 Reference Images用プロンプトスキル本文](write-h3-v39-reference-prompts/SKILL.md)／[ZIP](write-h3-v39-reference-prompts.zip)：固定の`@R1`～`@R9`とチャンク別の画像割り当てに対応します。V3.9のReference Imagesノード用で、下記の汎用Continuumスキルとは別です。
- [LLM用システムプロンプトZIP](H3-Continuum-LLM-System-Prompt-v1.zip)：Continuum向けプロンプト作成のシステム指示と詳細資料。
- [Continuum専用プロンプトスキルZIP](H3-Continuum-Skill-v1.zip)：Codexなどで使う、チャンク構成に対応した汎用プロンプト作成スキル。
- [Continuum Dance DirectorスキルZIP](minimax-h3-continuum-dance-director.zip)：主役のダンサー1人を対象に、チャンク間の身体動作とカメラの連続性を考慮した長尺ダンス用プロンプトを作成するスキル。

いずれも任意のプロンプト作成支援資料で、ComfyUIのカスタムノードではありません。ZIPを展開し、同梱の案内に従って利用してください。Samplerを変更するものではなく、生成動作や画質を保証するものでもありません。

## V3.8の公開範囲

H3 Continuumは、長尺映像を最初からやり直さずに生成・確認・部分再生成・再開するProduction Samplerです。V3.8は`Main / Production`と`Advanced`の2層に整理しました。

以下の9ノードに`H3 Continuum Video Adapter`を加えた計10 IDがV3.8X2の登録面です。旧Audio／Video Loaderは互換IDとして残ります。V3.9はさらにSampler V3.9とReference Images V3.9を追加した計12 IDです。

- `H3 Continuum Sampler V3.8`
- `H3 Continuum Finalize`
- `H3 Continuum Load Image`
- `H3 Continuum Load Audio`
- `H3 Continuum Load Video`
- `H3 Continuum Second Pass`
- `H3 Continuum Reference Audios`
- `H3 Continuum Reference Images`
- `Decode Cache Helper`

Main Sampler内の`Show Advanced Settings`／`Hide Advanced Settings`で詳細設定を開閉します。旧node property `H3 Continuum View`を含む保存Workflowは対応する開閉状態へ移行し、旧propertyを削除します。これは表示状態だけの変更です。Python input、widget順、保存済みwidget値、backend引数、Sampling identity、Run Storage identityは変更しません。Frontend extensionが読み込まれない場合も、Python定義の全widgetが表示された状態で実行できます。

V3.8X2公式Workflowの標準経路は`Sampler V3.8 -> Decode Cache Helper -> Finalize -> Create Video -> Save Video`です。HelperはMISSしたentryをCore Video／Audio Decodeへ委譲します。Core Decodeへ直接つなぐ手動構成も使用できますが、Decode結果のcacheはありません。Finalizeの`IMAGE`／`AUDIO`出力をCoreの`Create Video`で`VIDEO`へまとめてから保存します。Save、Upscalerは外付けとし、外部latent processorやupscalerはSecond Passをbridgeとして接続します。外部processorが変更できるのはVideo LATENTの空間解像度だけで、physical group、B/C/T、finite値、First Pass Audio、元のAssembly Planを維持する必要があります。Finalizeは公開`IMAGE`／`AUDIO`型を受け取り、特定decoder classへ依存しません。SageAttention、Sol-Attn、Spectrumは外部MODEL wrapperのままです。詳細は[V3.8 Open Integration Contract](docs/V38_OPEN_INTEGRATION_CONTRACT.md)を参照してください。旧Hi-Res FixはV3.8X2標準Workflowに含めません。

### Reference Audio 1/2/3

`H3 Continuum Reference Audios`は、最大3本の単独Reference Audioを1本の`Audio References (Optional)` socketへまとめます。入力は間を空けずに接続し、Promptでは接続順どおりに`<Audio 1>`、`<Audio 2>`、`<Audio 3>`を使用します。共通のCore Audio VAEで各Audioを個別encodeします。生成後の最終Audioを置換せず、Driving Audio契約も変更しません。既存Workflowは従来の単数`Reference Audio (Optional)`をそのまま使用できますが、単数経路とbundle経路は同時接続しないでください。

> **対応範囲:** 元のV3.8公開面は7 ID、V3.8X2は互換Loaderを含め10 ID、V3.9は12 IDです。Finalizeの`H3ContinuumAssembleSeamV35`、Second Passの`H3ContinuumSecondPassV35`などは旧IDを維持しますが、すべての旧Workflowに互換性があるという意味ではありません。未対応のnode IDには対応するhistorical Release/tagを使用してください。詳細は[V3.8 Release／Migration Policy](docs/V38_RELEASE_AND_MIGRATION.md)を参照してください。

複雑な16GB GPU受入Gateでは約`15.5～15.6 GiB`を使用しました。GPU、driver、backend、model精度、解像度、接続ノードで変動するため、すべての16GB GPUでの動作保証ではありません。

Reference Imageは最大9枚です。Samplerの直入力1～3を維持し、追加4～9は`H3 Continuum Reference Images`のoptional IMAGE入力へ接続して、出力をSamplerの`Reference Images (Optional)`へ渡します。補助ノードは画像を束ねるだけで、Resize・hash・VAE Encodeは既存Sampler経路で実行します。未接続を除き1→9の順に使い、Picture番号はFirst／Last Imageの後に連番で割り当てます。空のbundleは参照なしとなり、旧0～3枚の生成・再利用契約は変わりません。

以前の4・5直入力を含む保存Workflowは、グラフ読み込み後に元の画像接続をbundleへ移します。新接続を検証した後だけ旧接続口を削除し、接続元が不明・移行先が使用中の場合は警告して元の線を残します。旧API入力も維持しますが、同じ番号の画像を旧直入力とbundleの両方から指定すると入力競合として明示します。既存の3枚loaderテンプレートは上書きせず、そのまま利用できます。

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

ComfyUI上端の実行ボタンは、frontendにより`Queue`、`Run`、または`実行する`と表示されます。この手順内の`Queue`は、その実行ボタンを指します。

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

> **V3.8 Reviewの制限:** Review途中のpartial sequenceでは、Second Pass／`refine_context`を正式対応範囲に含めません。Reviewを完了してsequenceを確定してからSecond Passを実行してください。V3.9では、上記のとおり検証済みの出力区間条件を継承できます。

### Take・Branch・安全な継続

Run Storageを有効にすると、Production表示に**Render History / Takes**が表示されます。
Takeを選択してもcanonical結果は変わりません。**Use This Take**でそのrevisionを
canonicalにし、**Continue From Here**で選択したTakeまでを保持して後続groupだけを
再生成します。どちらの操作も自動Queueは行いません。

## アーカイブされた実装・受入記録（V3.8現行ガイドではありません）

以下は一時的にsource historyとして残る旧リリース記録です。V3.8の標準経路・公開範囲・推奨配線を示すものではありません。旧WorkflowにはMigration Policyと対応するhistorical Release/tagを使用してください。

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

**V3.8.0はhistorical release baselineです。V3.8X2はpackage 3.8.3の別Workflowとして維持し、V3.9はmainの現行ソースです。** V3.8X2が内部利用する旧module/classはsourceへ維持します。現在の登録面はV3.8X2の10 IDとV3.9追加の2 IDです。一部は旧IDを維持しますが、それ以外のIDを必要とする旧保存Workflowは対応するhistorical Release/tagを使用してください。Still Image Guideは引き続きExperimentalです。

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

退役したV3.5.1 LBH＋Conditioning Bridgeの接続例は、対応するhistorical Release/tagでのみ参照できます。これはV3.8 Workflowではありません。

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

- [V3.9 Workflow JSON](examples/workflows/MiniMax_H3_Continuum_V39.json)／[単独ZIP](examples/workflows/MiniMax_H3_Continuum_V39.zip) — 現行V3.9 graph。ZIPにはこのJSONだけを収録
- [V3.8X2 Workflow JSON](examples/workflows/MiniMax_H3_Continuum_V38X2.json) — 併存する旧系公式graph。Spectrumは初期状態でOFF
- [V3.8X2 Workflow ZIP](examples/workflows/MiniMax_H3_Continuum_V38X2.zip) — V3.8X2とV3.9の両JSONを格納。カスタムノードのインストーラーではありません
- [V3.8X2 Helper明示名JSON](examples/workflows/MiniMax_H3_Continuum_V38X2+Decode_Cache_Helper.json)／[ZIP](examples/workflows/MiniMax_H3_Continuum_V38X2+Decode_Cache_Helper.zip) — 同じgraphを説明的な配布名で収録

Registry配布予定の対象はV3.9とV3.8X2のJSON／ZIPです。依存なしのテンプレートではなく、Spectrum・rgthree・KJNodesが必要です。ComfyUI-Easy-Useは不要です。Turboへ切り替えてもgraph内の外部ノードは残ります。SpectrumをOFFにし、用途に合うLightX2V Turbo LoRAを1本だけONにしてsampler／Stepsを合わせます。保存状態はSpectrum OFF、Turbo LoRA OFF、res_multistep／simple／20 Stepsです。

配布元のprompt、画像・音声名、ノード表示名、設定は変更していません。手元にあるファイルを選び、不要な入力をOFFにし、promptを入力してください。モデルやメディアは同梱しません。`Save 3x5s Video`などの保存済み表示名は生成時間を決めません。実際の長さはSamplerのChunksとSeconds per Chunkで決まります。

旧Workflowは開発履歴としてsource repositoryへ保持しますが、V3.8 Registry packageからは除外します。旧保存Workflowは[Migration Policy](docs/V38_RELEASE_AND_MIGRATION.md)に従い、対応するhistorical Release/tagで開いてください。Registryの正式pack検証・公開はGitHub sourceの更新とは別工程です。

## V3.4互換

V3.4の実装moduleは内部継承とhistorical testのためsourceへ保持しています。現行の登録面は上記12 IDに限定します。それ以外のIDを必要とするV3.4保存Workflowは、対応するhistorical packageを使用してください。

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

再起動後はV3.8X2 Workflowで`H3 Continuum Sampler V3.8`、V3.9 Workflowで`H3 Continuum Sampler V3.9`と`H3 Continuum Reference Images V3.9`を確認してください。現行の登録面は計12 IDです。

旧`ComfyUI-H3-Continuum-Join`が残っている場合は同時ロードを避けるため削除または退避してください。同梱`install_windows.bat`は旧名・新名の既存フォルダーを日時付きでバックアップします。

## 検査

Public Surface suiteはV3.8X2の10 IDとV3.9を含む計12 ID、公式Workflowと各ZIP内JSONの同一性、外部依存、Registry除外、既存V3.8 widget/socket順、`Show Advanced Settings`／`Hide Advanced Settings`による表示切替を確認します。Registry配布対象のハッシュは`REGISTRY_MANIFEST.sha256`、source側の整合性は`MANIFEST.sha256`で管理します。

**過去のV3.8X2準備証拠：** Full CPU suiteは**1,367 passed / 1 skipped / 0 failed**です。従来の最終GPU Functional Gateでは`3 × 5秒`のReview Each Chunkを実行し、Q1～Q3はphysical groupを1つずつ生成、Q4は`3 reused / 0 generated`で3 groupすべてを再利用しました。Q3とQ4の復号後RGBおよびPCM SHA-256は一致しています。9枚Reference Imageの別Gateは下記に記録しています。これは実行、prefix再利用、AV再構築、テストした9枚経路の確認であり、画像・音声の総合的な主観品質評価ではありません。

### 9枚Reference Image入力Gate（0.3 MP参照画像）

テストしたNVIDIA GeForce RTX 5060 Ti 16 GB／RAM 64 GB環境では、Reference Image 1～9、`512 × 608`出力、`3 × 5秒` Full Run、Spectrum Off、LoRA Off、Sage Attention、Balanced 22-frame continuity、各約`0.30 MP`のテスト参照画像で完走しました。Sampling中のVRAM使用量は、利用可能な`16,311 MiB`のうち約`15.0～15.5 GiB`であり、16 GB GPUでは余裕の小さい高負荷構成です。

9枚bundleは、追加の外観・ポーズ情報が必要で、十分なVRAM余裕を確保できる環境で使用してください。このsingle-seed Gateは実行と基本的な視覚的連続性を確認したものです。9枚が3枚より常に高画質であること、高解像度参照・大きな出力・別model・同時GPU負荷でも動作することを保証するものではありません。

16 GB GPUで9枚を使う場合は、読み込む前に元画像のコピーを約0.30 MPへ縮小してください。内部のconditioning用Resizeは継続しますが、9枚の大きな元画像によるメモリ負荷を管理する代わりにはなりません。

検証結果はテストしたローカルsourceと環境に限られます。導入済み環境が最新版であること、すべてのmodel／wrapperが任意のGPUに収まること、別のpromptでも同じ画質になることを保証するものではありません。

```text
python -m compileall -q .
pytest -q
```

MIT License。
