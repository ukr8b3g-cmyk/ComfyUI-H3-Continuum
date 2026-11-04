# ComfyUI-H3-Continuum 3.10.2 — V3.9

MiniMax H3の映像・音声をチャンクに分けて生成し、結果を確認しながら
一部分の再生成や、互換性のある保存Takeからの継続ができます。
**現在のWorkflowはV3.9です。V3.8X2も別のWorkflowとして保持しています。**

[v3.10.2本体ZIP](https://github.com/ukr8b3g-cmyk/ComfyUI-H3-Continuum/releases/download/v3.10.2/ComfyUI-H3-Continuum-v3.10.2.zip) ·
[Release](https://github.com/ukr8b3g-cmyk/ComfyUI-H3-Continuum/releases/tag/v3.10.2) ·
[チェックサム](https://github.com/ukr8b3g-cmyk/ComfyUI-H3-Continuum/releases/download/v3.10.2/SHA256SUMS.txt) ·
[English](README.md)

## クイックスタート — チャンクごとに違うプロンプトを使う

最初の実行前に、すべてのチャンクの指示を **Sequence Prompt** に書きます。以下は **Chunks = 2**、**Seconds per Chunk = 5** の例です。3形式のうち1つを選んでください。

REF2VAのテンプレートは **hatt2** さんの提案をもとにしています。必要な項目だけ記入してください。

### 1. チャンク番号 — `Prompt Format = Timeline`

見出しは単独の行に置きます。最初の見出しより前の文章は全チャンクに共通です。

**テンプレート**

```text
subject_definitions:
summary:
retention_analysis: [reference generation]
detailed_description:
overall_soundscape:
non_diegetic_music:

[Chunk 1]
Describe the first action here.

[Chunk 2]
Describe what happens next here.
```

**記入例**

```text
subject_definitions: The woman in the reference image.
retention_analysis: [reference generation] Keep her face and red coat.
overall_soundscape: Soft wind and flowing water.

[Chunk 1]
She walks to the railing and rests her hand on it.

[Chunk 2]
With her hand still on the railing, she turns to look at the river.
```

### 2. 秒数 — `Prompt Format = Timeline`

Samplerで設定した尺に合わせて、動画の先頭からの時間範囲を書きます。

**テンプレート**

```text
subject_definitions:
summary:
retention_analysis: [reference generation]
detailed_description:
overall_soundscape:
non_diegetic_music:

[0-5s]
Describe the first action here.

[5-10s]
Describe what happens next here.
```

**記入例**

```text
subject_definitions: The woman in the reference image.
retention_analysis: [reference generation] Keep her face and red coat.
overall_soundscape: Soft wind and flowing water.

[0-5s]
She walks to the railing and rests her hand on it.

[5-10s]
With her hand still on the railing, she turns to look at the river.
```

### 3. 区切り線で分ける — `Prompt Format = List`

`---` を単独の行に置きます。上から順に各チャンクへ渡るため、共通設定も各ブロックに書きます。

**テンプレート**

```text
subject_definitions:
summary:
retention_analysis: [reference generation]
detailed_description: Describe the first action here.
overall_soundscape:
non_diegetic_music:

---

subject_definitions:
summary:
retention_analysis: [reference generation]
detailed_description: Describe what happens next here.
overall_soundscape:
non_diegetic_music:
```

**記入例**

```text
subject_definitions: The woman in the reference image.
retention_analysis: [reference generation] Keep her face and red coat.
overall_soundscape: Soft wind and flowing water.

She walks to the railing and rests her hand on it.

---

subject_definitions: The woman in the reference image.
retention_analysis: [reference generation] Keep her face and red coat.
overall_soundscape: Soft wind and flowing water.

With her hand still on the railing, she turns to look at the river.
```

`Auto` でも形式を判別できます。まずは表記に対応する形式を明示すると確認しやすくなります。Chunk 1を先に確認したい場合は **Review Each Chunk** を選び、継続時も同じSequence Promptを使います。

## 3.10.2 — ホットフィックス：Review履歴と再生成指定を保護

- Continueの失敗・中断後も、確定済みTakeと名前付き保存点を保持します。
  新しい処理は別の保存Revisionへ書き込みます。
- Reviewの到達不能な再生成指定を計算前に拒否し、外部ノードからRun Storageを
  接続した場合も、再生成チャンク・番号を勝手にリセットしません。
- HTTPのLAN接続でも、暗号学的乱数によるUUID代替処理でManagerを操作できます。
- `--gpu-only`を含め、Second Passの生成済み映像をCPUへ保持し、前区間の結果が
  VRAMへ蓄積する経路を修正します。First Pass音声は維持します。

CPU・JavaScriptは **2,248成功／2スキップ／失敗0**、CUDA初期化試行0。
12ノードのオフライン登録・Layoutを確認しました。**今回の実ブラウザー・GPU受入は
未実施**で、実VRAM使用量・OOM・画質への効果はまだ測定していません。

既存Take・Workflow・Sampling v6／Graph v4・未知コードの拒否を維持します。
過去の中断履歴の自動修復や読取専用Takeの再利用許可は行いません。
更新後はComfyUIを完全に再起動し、Ctrl+F5でブラウザーを更新してください。
履歴削除・配線変更は不要です。**Registry再送信は3.10.0の手動レビュー待ちで保留し、
GitHub ZIPで配布します。** [修正内容・検証・更新手順](docs/RELEASE_NOTES_V3102.md)。

## 3.10.1 — Project / Take Managerの拒否理由を正しく表示

読取専用Take、rawデータの不整合、実行中Run、容量上限などのHTTP 409を、
すべて「別タブでProjectが更新された」と表示する不具合を修正しました。
本当の更新競合だけをその案内にし、その他はサーバーの具体的な拒否理由を表示します。
日本語UIでも、サーバー由来の説明文は英語の原文です。

CPU・JavaScriptは **2,214成功／2スキップ／失敗0**、CUDA初期化試行0。
Chromeの英語・日本語UIで、実際の更新競合とRun重複登録の表示を確認しました。
その他の拒否理由はCPU・API・JavaScriptで検証し、新しいGPU生成は行っていません。

既存Take・Workflow・Sampling v6の安全判定を維持します。更新後はComfyUIを完全に
再起動し、Ctrl+F5でブラウザーを更新してください。新規Runや履歴削除は不要です。
**Registry送信は3.10.0の手動レビュー結果が出るまで保留し、3.10.1はGitHubで配布します。**
[修正内容・検証・更新手順](docs/RELEASE_NOTES_V3101.md)。

## 3.10.0 — Project / Take Manager V1.2

Project・独立した試行・名前付きTake保存点を管理する右側パネルです。初期OFFで、
**設定 → H3Continuum → Project Manager** で有効にし、メニューの
**H3 Continuum → Project / Take** から開きます。保存点からの再開準備は既存Reviewへ
渡し、生成は通常のQueue操作で開始します。ノード追加や配線変更は不要です。

再表示修正を含む最終CPU・JavaScript回帰は **2,210成功／2スキップ／失敗0**、
CUDA初期化試行0。Chromeで保存・再読込を確認し、専用Runで
「Chunk 1 → Chunk 2継続 → 同じ保存点から別Chunk 2 → 独立試行」の4 Queueが成功しました。
元Chunk 1のrawハッシュと以前のTakeを保持し、4本すべての映像・音声を正常にデコードできました。

Managerを使わず従来どおり生成できます。保存点は既存データへの参照で、バックアップや
Workflow全体の復元ではありません。今回の合格は管理機能の動作確認で、画質・速度全般を
保証するものではありません。
[操作方法・安全条件](docs/PROJECT_TAKE_MANAGER_V12.md)・
[変更内容・検証条件と制限](docs/RELEASE_NOTES_V3100.md)。
パッケージ3.10.0で追加した機能です。Workflowは引き続きV3.9です。

### Managerの使い方 — 実画面で順番に操作

以下はChromeで撮影したManager V1.2の実画面です。画面は英語ロケールですが、
日本語ロケールでは対応する日本語名になります。既存のV3.9 Workflowをそのまま使い、
**Samplerを増やしたり、配線を変更したりする必要はありません**。

まず言葉を区別します。

| 名前 | 何を管理するものか | 例 |
| --- | --- | --- |
| Project | 試行や保存点をまとめる管理用の箱 | 「ヘリコプターのシーン」 |
| Trial / Run（試行） | 一つの生成履歴。独立試行には別のRunを使う | 「案A」「案B」 |
| Take | 実際に生成して保存された候補 | Chunk 2の1回目・2回目の結果 |
| Named savepoint（保存点） | 選択Takeまでの履歴に付ける固定の名前 | 「Chunk 1を採用」 |

#### 1. Managerを有効にする

1. ComfyUI左側の歯車 **Settings（設定）** を開きます。
2. 設定カテゴリ **H3Continuum** を選びます。
3. **Project Manager** の **Enable Project / Take Manager (experimental)** をONにします。
   初期状態はOFFです。画像の青いスイッチがONの状態です。
4. 設定を閉じます。他のDetailed Report・Sampling Preview等を変更する必要はありません。

![設定のH3ContinuumでProject ManagerをONにする](docs/images/project-manager-v12/manager-guide-01-settings.png)

#### 2. パネルを開き、対象Samplerを選ぶ

1. 左上のComfyUIメニューを開き、**H3 Continuum → Project / Take** を選びます。
   設定内の **Open Project / Take** からも開けます。設定画面を閉じてパネルが
   見えなくなった場合は、メニューからもう一度開いてください。
2. 右側に管理パネルが開きます。
3. **Target Sampler（対象Sampler）** で、管理したいV3.9 Samplerを選びます。
   複数ある場合は、末尾のノード番号をWorkflow内の番号と照合します。

![左上メニューからH3 ContinuumのProject / Takeを開く](docs/images/project-manager-v12/manager-guide-02-menu.png)

パネルは上から **対象Sampler → Project → Trial / Run → Named savepoints** の順です。
画像には検証用に作成済みのProjectと二つの試行が表示されています。

![Project、試行、保存点の三段構成の管理パネル](docs/images/project-manager-v12/manager-guide-03-panel.png)

#### 3. Projectを作り、現在のRunを登録する

既に生成中の動画を管理する場合の手順です。

1. Sampler側で一意の **Run Name** を設定し、通常どおり生成します。
   Takeを保存する **Run Storage: Save + Auto Resume** を使用します。
   まず試すなら **Review Each Chunk** でChunk 1を生成して止めます。
2. Managerの **Project** 欄の名前入力に、作品名などを入力し、**Create Project（Projectを作成）** を押します。
   作成したProjectを上の一覧で選びます。既存Projectを使う場合は作成不要です。
3. **Trial / Run** 欄の名前入力に「案A」などの表示名を入力します。
4. **Add current Run（現在のRunを追加）** を押し、追加された試行を選びます。
   これは対象SamplerのRunを管理一覧に登録する操作です。動画やrawをコピーせず、
   既存Takeも変更しません。

**Project名を入力するだけでは作成されません。試行名を入力するだけでもRunは切り替わりません。**
それぞれの実行ボタンを押した後、一覧に追加されたことを確認します。

#### 4. 残したいTakeに名前を付ける

1. Samplerの **Render History** を開き、Previous Take／Next Takeで残したいTakeを選びます。
   一覧が既に開いている場合は、その選択内容を確認します。
2. Managerで、そのTakeと同じRunを登録した試行を選びます。
   別Runの試行を選んだまま保存しようとすると拒否されます。
3. **Named savepoints** の名前入力に「Chunk 1を採用」などを入力します。
4. **Name selected Take（選択Takeに名前を付ける）** を押します。
5. 一覧に保存点が追加され、**Through Chunk 1** など、どこまで保存したかを確認します。

下の実例では **Keep Chunk 1 · Through Chunk 1** が保存済みです。
Chunk 2のTakeを選んで保存すれば、そのTakeの祖先を含めたChunk 2までが対象になります。
後から続きを生成しても、既に付けた保存点の終点は勝手に移動しません。

![Chunk 1までの保存点とPrepare from savepointボタン](docs/images/project-manager-v12/manager-guide-04-savepoint.png)

#### 5. 保存点を使って続きを作る

1. 対象Samplerで、再開に使うWorkflow・モデル・プロンプトなどの条件を用意します。
   Managerはそれらを自動復元しません。前半を再利用するには既存の互換性判定を満たす必要があります。
2. **Project → 試行 → 保存点** の順に選びます。
3. **Prepare from savepoint（保存点から再開準備）** を押します。
4. 「Prepared. Check the Sampler and use the normal Queue button.」の成功表示と、
   SamplerのRender Historyで選ばれたTakeを確認します。
5. 通常の **Run／Queue** を押します。準備ボタンだけではGPU生成は始まりません。

Sampler側では、選択Takeや **Continue From Here** に示される前半の再利用範囲を確認します。
Managerから再開準備が済んでいる場合、別のTake操作を押し直す必要はありません。
以下は既存Reviewの画面例で、Managerとは別の生成・履歴操作部分です。

![SamplerのRender Historyで選択TakeとContinue From Hereを確認](docs/images/project-manager-v12/manager-guide-06-review.png)

**具体例：Chunk 1を残して、Chunk 2を二通り作る**

1. Chunk 1のTakeに「Chunk 1を採用」と名前を付けます。
2. その保存点から再開準備し、Runを押してChunk 2を作ります。
3. 別案も欲しければ、再び同じ保存点を選び、再開準備してRunを押します。
4. 検証した同一条件では、Chunk 1のrawは不変で、Chunk 2のVariationが1→2へ進みました。
   前のChunk 2のTakeも残ります。必要ならそれぞれのChunk 2 Takeにも別名を付けます。

#### 6. 前の案を残して、独立した別案を始める

1. 同じProject内の **Trial / Run** 名前入力に「案B」などを入力します。
2. **New trial（新しい試行）** を押します。
3. 作成した試行を一覧で選び、**Prepare new trial（新しい試行へ切替準備）** を押します。
4. 成功表示を確認します。この操作はSamplerのRun Nameを空欄にし、新しいRun識別子を設定します。
5. 必要な生成条件を確認して通常のRunを押すと、別RunのChunk 1から生成します。

![独立試行の名前入力、New trialとPrepare new trial](docs/images/project-manager-v12/manager-guide-05-independent.png)

画像の **Trial C — new idea** は新しい試行名の入力例です。名前を入力しただけでは、
一覧で選択中のTrial Bを改名したり、新規試行を作成したりしません。
**New trialは前半を複製する操作ではありません。Chunk 1を残して続きを変える場合は、
手順5の保存点を使います。** 前の試行へ戻るときも、Project／試行を眺めるだけでは
Samplerは切り替わらないため、使いたい保存点を選んで再開準備してください。

#### 7. 名前の整理・非表示・閉じ方

| 操作 | 手順と結果 |
| --- | --- |
| 表示名を変更 | 対象Project／試行／保存点を選び、その欄の名前を書き換えて **Rename**。元Runのファイル名や生成条件は変わりません。 |
| 一覧から隠す | 対象を選んで **Archive**。動画・Take・rawを削除する操作ではありません。 |
| 元に戻す | **Show archived items（アーカイブも表示）** をONにし、対象を選んで **Restore（戻す）**。 |
| 他のタブで変更された情報を読む | **Refresh**。未確認の内容を上書きせず、再読込して確認します。 |
| パネルを閉じる | 右上の **Close**。保存済み管理情報は残り、生成やQueueの停止にはなりません。 |
| 従来どおり使う | パネルを開かずに生成できます。設定でManagerをOFFにもできます。 |

#### 8. ボタンが押せない・再開できないとき

- **一覧が空**：対象SamplerとProject、試行を選んでいるか確認します。まだRunを登録していなければ手順3へ進みます。
- **Name selected Takeでエラー**：SamplerのRender HistoryでTakeを選び、Manager側の試行と同じRunか確認します。
- **Prepare new trialが灰色**：既存の名前付きRunを登録した試行では使いません。**New trial** で作成した独立試行を選びます。
- **再開準備を拒否**：対象SamplerのQueue実行・待機が終わってから操作します。Run識別・操作入力に外部接続がある場合や、同じRun識別子が競合している場合も拒否されます。外部制御しているWorkflowを無理に書き換えないでください。
- **v6 read-only・互換性不一致**：Managerは再利用制限を解除しません。必要な元条件を用意するか、独立試行でChunk 1から生成します。既存Takeの削除やフラグの書換えは不要です。
- **保存元が見つからない・破損**：保存点はバックアップではありません。元Runのメタデータとrawが必要です。名前を付けた後も元データを削除しないでください。

Workflow保存とProject管理情報の保存は別です。**モデル・プロンプト・参照画像などは
引き続きWorkflowとして保存**してください。詳細な制約は[Managerガイド](docs/PROJECT_TAKE_MANAGER_V12.md)を参照してください。

## 3.9.12 — Reference Plan Inspectorの表示更新

SamplerのUI再構成やWorkflow保存・再読込後に、古い検証済みReference Planが
残る問題を修正しました。参照割り当てを変更すると未検証表示へ戻り、次の生成で
バックエンドが返すPlanへ更新します。コールバックの累積やInspector情報の保存は行いません。

CPU・JavaScriptは **2,148成功／2スキップ／失敗・期待失敗0**。
Chromeで保存・再読込を確認し、実GPU生成後に参照割り当てを解除すると、
Inspectorの「runtime verified」が「Configured only — Queue has not verified...」
へ切り替わることを確認しました。追加Queueは不要で、既存保護対象140ファイルと
新規Runの3ファイルのハッシュは不変でした。画質全般の合格を示す検証ではありません。

Managerまたは既存custom-nodeフォルダーの更新後、**ComfyUIを再起動し、
ブラウザーをCtrl+F5で更新**してください。既存Take・Workflowはそのまま使えます。
このUI修正のための配線変更・履歴削除・新規Runは不要です。
[詳しい検証条件と制約](docs/RELEASE_NOTES_V3912.md)。

## 3.9.11 — Spectrum署名の安定化／Review継続

監査済みSpectrumを再読込すると、同じコードでもmarshalの表現が変わり、
新規Takeが誤って「v6 read-only」になる条件を修正しました。旧監査を優先し、
必要な場合だけ固定プロファイルで読込済みコード全体を検査します。
正常な既存v6 Takeの署名は維持し、未知・改変コードの再利用拒否は緩めません。

CPU／JSは **2,139成功／2スキップ／既知Inspector期待失敗2件**。
**Spectrum＋Comfy Kitchen Attention**のブラウザー／GPU検証ではReviewボタンが有効となり、
**Chunk 1保持・Chunk 2生成（再利用1／新規1）**と両出力の映像・音声の全デコードを確認しました。
対象はPython 3.13.12、Core 0.42.1、Kitchen 0.2.39、監査済みローカルSpectrum、
512×512・24fps・5秒×2・8-step Turbo・First Passのみです。
全構成、画質、速度の受入を意味するものではありません。

Managerまたは既存custom-nodeフォルダーの更新後、**ComfyUIを再起動し、Ctrl+F5でブラウザー更新**。
一意な新しいRun NameでSpectrumとReview Each Chunkを有効にしてChunk 1→2を確認してください。
既存Take・ワークフローは維持します。過去のunsafe／v5 Takeの再利用許可は変更しません。

別拡張Custom ScriptsのメニューがMP4を画像として取得してHTTPエラーになる場合は、
**Settingsで「Show Image On Menu」をOFF**にする回避方法を確認済みです。
Continuumのコード修正ではなく、設定を自動変更する更新でもありません。
[詳細・検証範囲](docs/RELEASE_NOTES_V3911.md)。

## 3.9.10 — Spectrum再利用とReference割り当て表示

SpectrumソースのCRLF改行でSampling v6 read-onlyになる判定を修正し、対応済みの
2種類の実装にPython 3.12用の監査済みプロファイルを追加しました。既存3.13の
プロファイルと正常なTakeの識別値は維持します。未知のコード・追加状態は拒否します。

外部Chunks接続時のReference Imagesは、古いWidget値の代わりに割り当て範囲1–16を
表示します。生成チャンク数や保存済みの選択内容は変更しません。

CPU/JS：**2,096成功・2スキップ・既知の期待失敗2件**。Python 3.12の対象試験、
保存・継続と実JS照合も成功。Reference表示は実ブラウザー確認済みです。
**3.9.10としての新たなGPU受入は未実施です。**

更新後はComfyUIを再起動し、ブラウザーを更新してください。既存WorkflowとTakeは
そのまま保持できます。新しく対応した構成は新規Runで確認してください。
旧unsafe/v5 Takeは閲覧用として保持し、自動変換しません。[詳細と制約](docs/RELEASE_NOTES_V3910.md)。

## 3.9.9の修正と検証

確認済みの公開KJ Preview Overrideで、新規Runまでv6 read-onlyとなる対応漏れを修正。
再利用不可のTakeには保存時の理由を表示します。安全判定・既存Take・Workflowは維持します。

CPU **2,075成功／2スキップ／既知の期待失敗2件**。公開KJのGPU継続と、既設KJを維持した
実ブラウザーのReviewボタン・Continue From Here→Runを確認し、**Chunk 1保持・Chunk 2生成
（1再利用・1新規生成）**に成功。4本の映像・音声を全デコードしました。

更新後は再起動とブラウザー強制再読込を行ってください。Preview Override側の任意VAE／Audio VAEは
未接続、Tiny VAEはnoneにし、通常の生成用VAEは維持してください。旧unsafe／v5 Takeは保持されますが
更新だけで再利用可能にはなりません。設定修正後は新Runで開始します。配線変更・Take削除は不要です。
[検証条件と制約・Release notes](docs/RELEASE_NOTES_V399.md)。

## 基本操作を動画で見る

[H3 Continuum V3.9 — Chunks, Prompts & Reference Images](https://youtu.be/AKJxBXaiG6Q) — **12分26秒**、英語ナレーション・字幕・チャプター付き。

First Image、チャンク設定、Review・Takeの再試行、Timeline Prompt、Reference Imagesを説明しています。
画面写真と詳しい操作は[日本語の詳細ガイド](docs/USER_GUIDE_JA.md)を参照してください。

## インストール・更新

Continuumは`ComfyUI/custom_nodes`内に1つだけ配置してください。
モデル・外部カスタムノードは本体ZIPに含まれません。

### 固定バージョンのZIPを使う

1. 冒頭の**本体ZIP**を取得し、必要に応じてチェックサムを確認します。
2. パッケージフォルダーを`ComfyUI/custom_nodes`へ展開します。
   更新時は既存パッケージを置き換え、重複したコピーを残さないでください。
3. ComfyUIを再起動し、ブラウザーを**Ctrl+F5**で強制再読込します。
4. 下記のV3.9 Workflowを開き、導入したモデルと入力ファイルを選びます。

保存済みWorkflow、Run／Takeフォルダー、設定は保持してください。
**Workflow ZIPはグラフの配布物であり、カスタムノードのインストーラーではありません。**

### Git・ComfyUI-Managerを使う

Gitで新規導入する場合：

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/ukr8b3g-cmyk/ComfyUI-H3-Continuum.git
```

既存のGit導入を更新する場合：

```bash
cd ComfyUI/custom_nodes/ComfyUI-H3-Continuum
git pull --ff-only origin main
```

Managerで導入した場合は、そのコピーをManagerから更新してください。
更新後はComfyUIを再起動し、ブラウザーを再読込します。
Registry審査・Managerが選択する版・GitHub Releaseの状態は別です。
正確なv3.9.12を使う場合は、冒頭の固定版リンクを参照してください。

パッケージの宣言上の最低要件は**Python 3.10以降・ComfyUI 0.32.0以降**です。
この最低要件の宣言だけで、すべてのCore版でのGPU動作確認を意味するものではありません。

## 必要なモデル・拡張機能

重みは[Comfy-Org / MiniMax-H3](https://huggingface.co/Comfy-Org/MiniMax-H3)から別途取得します。
次の表は**保存されているV3.9テンプレートの選択値**です。配置先は`ComfyUI/`からの相対パスです。

| 用途 | ファイル・ダウンロード | 配置先 |
| --- | --- | --- |
| H3生成モデル | [minimax_h3_fl2va_pruned_int8_convrot.safetensors](https://huggingface.co/Comfy-Org/MiniMax-H3/resolve/main/diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors) | `models/diffusion_models/` |
| テキストエンコーダー | [qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors](https://huggingface.co/Comfy-Org/MiniMax-H3/resolve/main/text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors) | `models/text_encoders/` |
| 動画VAE | [minimax_h3_video_vae_int8_convrot.safetensors](https://huggingface.co/Comfy-Org/MiniMax-H3/resolve/main/vae/minimax_h3_video_vae_int8_convrot.safetensors) | `models/vae/` |
| 音声VAE | [minimax_h3_audio_vae_fp32.safetensors](https://huggingface.co/Comfy-Org/MiniMax-H3/resolve/main/vae/minimax_h3_audio_vae_fp32.safetensors) | `models/vae/` |

各Loaderで取得したファイルを選び、テキストエンコーダーのtypeは`minimax`にします。
保存済みの`minimax/`サブフォルダーが環境と異なる場合は、実際の配置先から選び直してください。
動画VAEの選択値はINT8版ですが、旧ダウンロード情報にFP16版が残っています。
実際に導入したVAEを選んでください。[別のモデル形式](https://huggingface.co/Comfy-Org/MiniMax-H3/tree/main/diffusion_models)は生成用途とLoaderの対応に合わせて選択します。
量子化形式には対応するCore・GPUが必要であり、上表は全ハードウェアでの動作保証ではありません。

保持しているV3.8X2グラフでは、DasiwaMinimaxH3_dasiwaHybridV2_int8.safetensorsと
[FP16動画VAE](https://huggingface.co/Comfy-Org/MiniMax-H3/resolve/main/vae/minimax_h3_video_vae_fp16.safetensors)が選択されています。
このカスタムモデルは同梱されず、上表の配布元から取得するものでもありません。導入済みの互換H3モデルを選び直してください。

配布グラフ全体を使う場合は、次の外部ノードも必要です。

- [Spectrum](https://github.com/xmarre/ComfyUI-Spectrum-MiniMax-H3)：任意の高速化機能。保存時は無効です。全バージョンでのTake再利用を保証しません。
- [KJNodes](https://github.com/kijai/ComfyUI-KJNodes)：テンプレートのH3 SageAttentionパッチを提供します。必要なAttention依存関係を導入するか、利用できないパッチを置換・Bypassしてください。
- [rgthree-comfy](https://github.com/rgthree/rgthree-comfy)：`Power Lora Loader (rgthree)`を提供します。

**Turboを使う場合のみ：** 用途に合う[LightX2V Turbo LoRA](https://huggingface.co/lightx2v/Minimax-h3-Turbo)を1つ選び、`models/loras/`へ配置します。
標準WorkflowではLoRAはすべて保存時に無効です。別のTurbo Sampleでは1つ有効です。配布元のSampler・Steps指定に従ってください。
[ファイル一覧と設定の詳細](docs/USER_GUIDE.md#turbo-lora-and-spectrum-in-supplied-workflows)も参照できます。Continuumがこれらを自動導入することはありません。

## Workflowを選ぶ

| Workflow | ダウンロード | 用途 |
| --- | --- | --- |
| **V3.9** | [JSON](examples/workflows/MiniMax_H3_Continuum_V39.json) / [ZIP](examples/workflows/MiniMax_H3_Continuum_V39.zip) | 現行Samplerと固定Reference Imageスロット |
| **V3.9 Turbo Sample** | [JSON](examples/workflows/MiniMax_H3_Continuum_V39_Turbo_Sample.json) / [ZIP](examples/workflows/MiniMax_H3_Continuum_V39_Turbo_Sample.zip) | Auto・2×8秒のダンスとタイ語ラップ。[設定・制約](docs/TURBO_SAMPLE.md) |
| **V3.8X2** | [JSON](examples/workflows/MiniMax_H3_Continuum_V38X2.json) / [統合ZIP](examples/workflows/MiniMax_H3_Continuum_V38X2.zip) | 既存Workflow用。統合ZIPにはV3.9も収録 |

ComfyUIの**Templates → ComfyUI-H3-Continuum**からも開けます。
V3.8X2のReference配線や保存履歴はV3.9へ自動変換されません。
元のグラフを保持し、新しい作業は専用のV3.9グラフで開始してください。
不足する外部ノードは導入・置換・削除してからQueueします。ComfyUI-Easy-Useは不要です。

V3.9テンプレートでは、自分の**First Image**を選んでください。
Reference Loader 1〜6はBypass、チャンク別割り当てはすべてOFFで保存されています。
Image 7〜9を使う場合はLoaderを追加・接続します。
[テンプレートの詳しい説明](docs/USER_GUIDE_JA.md#最初にv39とv38x2)。

## 最初の生成

長い動画を作る前に、短い2チャンクで確認してください。

1. H3モデル、テキストエンコーダー、Sampler、対応VAEを選びます。
2. `Sequence Prompt`を記入します。全チャンク共通なら`Prompt Format = Fixed`を使います。
3. 画像から作る場合は`Size Source = First Image`と解像度を選びます。
   初期値は**Draft — 0.30 MP**です。幅・高さを直接指定する場合は`Manual`にします。
4. `Chunks`を**2**、`Seconds per Chunk`を**5**にし、`Total Length`が**10秒**になることを確認します。
5. `Base Seed`を維持し、`Control After Generate`を`fixed`にします。
6. `Run`を`Review Each Chunk`、`Progress`を`On — Resume and Takes available`にします。
7. `Regenerate From = Auto`のまま`Ready to Queue`を読み、ComfyUI上端の**Run／実行ボタン**を押します。

`Chunks`は最終目標数であり、次のQueueで追加する数ではありません。
Reviewでは通常1単位ずつ生成するため、この例の最初の出力は**5秒**です。
Last ImageのTerminal Mergeでは、最後の2チャンクを1単位として扱う場合があります。

一括生成する場合は`Generate Full Video`を選びます。
保存Take・互換Resume・後からの再生成を使う場合はProgressをONにしてください。

## 確認・継続・再試行

Review操作を選ぶだけでは生成は始まりません。選択後にComfyUIの
**Run／実行ボタン**（`Queue`）を押してください。

| 操作 | 次のQueueで行うこと |
| --- | --- |
| `Use it and continue` | 採用済みチャンクを保持して、次のReview単位を生成 |
| `Try this chunk again` | 前のチャンクを保持して、確認中の単位を別Takeで再生成 |
| `Use it and finish the rest` | 採用済みの部分を保持して、残りをまとめて生成 |
| `Back to Settings` / `Return to Review` | 設定と確認画面の移動。生成開始・Take削除は行わない |
| `Use This Take` | 保存結果を採用。新しいSamplingは行わないがDecode・保存は実行され得る |
| `Continue From Here` | 選んだTakeまでを保持した分岐を作り、次の単位を生成 |

**2×5秒**の例では、Chunk 1を採用して継続すると、それを再利用してChunk 2を生成し、**10秒**の完成動画になります。
完了後に現在の単位をRetryすると、別のChunk 2 Takeを作ります。

継続時はモデル・LoRA・Seed・Prompt・入力素材・寸法・Sampling設定・継続設定・Run識別を維持します。
Seedを固定しただけで再利用が保証されるわけではありません。Statusと再利用数を確認してください。
完成動画を延ばす場合は条件を維持し、`Regenerate From = Auto`のまま最終目標の`Chunks`を増やしてQueueします。
[Review・Takeの詳細](docs/USER_GUIDE_JA.md#10秒を5秒ずつ確認しながら作る)。

## 指定チャンクから再生成する

1. 設定を開き、**Regenerate From = Chunk N**を選びます。
2. ProgressをONにし、前のチャンクの生成条件を維持します。
3. N以降をまとめて作るなら`Generate Full Video`、次の単位で確認するなら`Review Each Chunk`を選びます。
4. **Variation Nonce**を指定し、ComfyUIの実行ボタンを押します。
5. 通常の継続・Take操作へ戻る前に、`Regenerate From = Auto`へ戻します。

Nonce **0**は、再生成完了後の再実行で別Variationを自動選択します。
互換性のある中断処理では、同じVariationをResumeします。
正のNonceはVariationを固定します。同じ条件・同じ正数を繰り返しても別結果の要求にはなりません。
ReviewのRetryは、これとは別にVariationを管理します。

前の互換チャンク・以前のTakeは保持します。
後続は変更後の継続に従うため、Full RunのChunk 2指定は、目標数によってChunk 2以降をまとめて再生成します。
Terminal Mergeのpairは分割せず、チャンク内の任意フレームだけを変更することもできません。
[再生成・互換性の詳細](docs/REGENERATE_INTENT_V396.md)。

## Prompt・Reference Images

- **Fixed**は共通Prompt、**List**はチャンク別、**Timeline**は時間指定です。
- V3.9のReference Imagesは**Image 1〜9の固定スロット**を持ち、Samplerへ1本で接続します。
  `All chunks`は共通使用、`Per chunk`は画像とチャンクの交点を選択します。
- `@R1`は空きスロットに関係なくImage 1です。有効なReferenceだけをタグで参照してください。
  実際のPicture番号は物理groupごとに解決されます。
- First／Last Image、Reference Images、Reference Audio、Driving Audioは用途が異なります。
  Driving Audioは元の音声を保持し、Reference Audioは生成条件として使います。
- Reference単独を試す場合はFirst／Last ImageをOFF、サイズをManualにします。
  終端を結合するpairでは、両チャンクの有効なReferenceセットを揃えてください。
- 大きな入力画像は事前に縮小してください。条件付けのresizeだけでは元画像の読込RAMは減りません。
  割り当てを外した後も、映像の連続性により被写体が残る場合があります。

[Referenceガイド](docs/V39_REFERENCE_INLINE.md) ·
[Prompt例（英語）](docs/README_HISTORY.md#prompt-formats) ·
[V3.9用Promptスキル](https://github.com/ukr8b3g-cmyk/ComfyUI-H3-Continuum/tree/main/write-h3-v39-reference-prompts) ·
[Prompt・スキル配布](docs/USER_GUIDE_JA.md#プロンプトスキルのダウンロード)

## 保存・Decode・Second Pass

ProgressはRun／Takeを保存します。任意の**Decode Cache Helper**はデコード結果のキャッシュであり、保存履歴とは別です。
Finalizeで結合し、後段のCoreノードで動画を作成・保存します。

一時保存先は**設定 → H3Continuum → Storage → 一時ストレージを管理**で指定します。
ComfyUIサーバー側のフォルダーで、FinalizeとDecode Cacheに適用します。
Run／Takeや完成動画は移動しません。変更・削除は実行中／待機中Queueが空のときに行ってください。
同じ物理ドライブ内のフォルダー移動だけでは、書き込みを別機器へ逃がせません。
[保存方式・削除・制約](docs/TEMPORARY_STORAGE_JA.md)。

**Second Pass**は、同解像度のRefinementや、対応する外部Upscalerで加工した映像latentの再生成に使う任意機能です。拡大処理そのものは内蔵していません。
元音声・Plan・refine_contextの接続と、Finalizeへ渡す更新後Planを含め、現行V3.9の手順をまとめました。
V3.8の途中Review制約と、V3.9の検証済み出力区間への条件継承は区別してください。
**[接続図・ソケット表・SIGMAS・拡大時の注意点](docs/SECOND_PASS_GUIDE_JA.md)**。
従来の標準Workflowや保存Takeを変更する必要はありません。

## 互換性・検証範囲

| 対象 | 対応条件 |
| --- | --- |
| 保存履歴 | 既存Takeは読取可能です。旧v5・unsafe履歴をSampling v6の再利用可能履歴へ自動修復・昇格しません。必要に応じて新Runを使います。 |
| 未知のMODEL wrapper | 新規生成は可能です。再利用には生成契約の完全な観測と一致が必要で、名前・版だけで許可しません。 |
| Attention／Spectrum | Core PyTorch／Kitchenと、公式v0.2.29を含む指定Spectrum実装の監査済みプロファイルに対応します。[厳密な範囲](docs/ISSUE31_SAMPLING_SIGNATURES.md)。 |
| KJ Model Preview Override | 個別に監査したローカル版と公開upstream版のKJ／Coreプロファイルのみ。**VAE／Audio VAE未接続・Tiny VAE `none`**、Core NoPreviews／Auto／Latent2RGB。KJNodesの版番号だけでは対応を判定できません。[3.9.9での対応追加](docs/RELEASE_NOTES_V399.md) / [対応ハッシュ](docs/KJ_PREVIEW_OVERRIDE_V398.md)。 |

過去の公開版**v3.9.8**の検証では、新Run・別QueueでのChunk 1→2継続を
**PyTorch＋KJ**と**Comfy Kitchen INT8＋監査済みローカルSpectrum＋KJ**で確認しています。
プレビュー画像を保持し、元Chunk 1と契約を維持、映像・音声4本は全デコード成功でした。
条件はRTX 5060 Ti 16 GB、512×512、24fps、2×5秒、8-step Turbo、Core API経由です。
別のKJ／Spectrum実装やPreview VAE接続を合格とするものではありません。
[詳しい条件・未確認範囲](docs/RELEASE_NOTES_V398.md)。

## 既知の問題・制約

- **モバイル：** UI処理の削減は確認していますが、フリーズ解消は未確認です。
- **メモリ：** 大きなReference画像9枚や長尺の最終DecodeでVRAM／RAM不足になる場合があります。
  Disk-backed Finalizeでも、他ノードの大きなメモリ確保は防げません。
- **Refinement：** 高倍率のLatent Resizeでアーティファクトが残る場合があります。
  長いHi-Res／Hybrid条件と二重輪郭には制約・調査中の事項があります（[Issue #27](https://github.com/ukr8b3g-cmyk/ComfyUI-H3-Continuum/issues/27)）。
- **連続性：** 完全な同一性・動作・口の同期・元動画の全フレーム再現は保証しません。長尺には既知の品質制約もあります。
- **検証範囲：** ブラウザー実行／保存再読込、報告者の完全一致グラフ、他実装、主観画質・音質、速度・VRAM比較は、上記の過去のv3.9.8 GPU再検証では確立していません。その後の限定検証は各版のリリースノートに分けて記録しています。

## 詳細資料

| 内容 | 資料 |
| --- | --- |
| 導入・画像・詳細操作 | [日本語の詳細ガイド](docs/USER_GUIDE_JA.md) / [英語の図解ガイド](docs/USER_GUIDE.md) |
| 現行Reference Images | [V3.9 Referenceガイド](docs/V39_REFERENCE_INLINE.md) |
| V3.8X2からの更新 | [移行・保持する仕様](docs/V38_RELEASE_AND_MIGRATION.md) |
| 更新履歴・旧版画像・実装説明 | [日本語の履歴資料](docs/README_HISTORY_JA.md) / [CHANGELOG](CHANGELOG.md) |
| 最新版の検証記録 | [v3.10.2詳細](docs/RELEASE_NOTES_V3102.md) / [配布検証](PACKAGE_VALIDATION.txt) |
| 不具合報告 | [GitHub Issues](https://github.com/ukr8b3g-cmyk/ComfyUI-H3-Continuum/issues) — Workflow、Status、`auto-resume disabled:`の理由を添えてください |

過去のRelease・タグは保持しています。mainの文書更新で、公開済みのタグや配布物を置き換えることはありません。
この整理は文書のみであり、公開ノード・公式Workflow JSON／ZIP・Sampling v6・既存Run／Takeは変更しません。

## ライセンス

[MIT](LICENSE)。外部コンポーネントの[ライセンス・表記](THIRD_PARTY_NOTICES.md)も参照してください。
