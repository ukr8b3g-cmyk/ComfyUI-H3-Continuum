# H3 Continuum A/B実機テスト記録

更新日: 2026-08-11  
状態: 継続中。現時点の結果であり、最終推奨ではない。

## 1. 目的

H3 Continuumの3×5秒生成について、次を分離して評価する。

- 解像度とチャンク累積による顔・肌・Identity drift
- Spectrumの速度向上とSeed依存のForecast誤差
- WarmupとContinuum Actual Prefixの組み合わせ
- Seam Correction Off/Autoの映像・音声境界への効果
- 無音に近い条件と明確な歌唱・発話条件の違い

MP4本体は現時点ではGitへ追加しない。各番号はローカル出力ファイル名の末尾番号に対応する。

## 2. 主なテスト環境

```text
GPU                  RTX 5060 Ti 16GB
System RAM           64GB
Output               640×960 / 24fps / 15秒 / 360 frames
Image scale          area / 0.60MP / resolution_steps 32
Chunks               3
Chunk seconds        5.0
Continuity           Balanced — 22 frames
SageAttention        sageattn_qk_int8_pv_fp8_cuda++
Sol-Attn             なし
Audio continuity     true
Exact total duration true
Diagnostics          Basic
```

Spectrum ON時の主要設定:

```text
blend_weight                  0.5
degree                        1
ridge_lambda                  0.1
window_size                   2.0
flex_window                   0.75
tail_actual_steps             1
max_history                   8
history_storage               system_ram
bootstrap_first_forecast      true
anchor_residual_feedback      false
selective_rollback_correction false
offline_smoothing_replay      true
audio_blend_weight            0.0
```

## 3. 暫定実用設定

品質最優先ではなく、約31%の時間短縮を取る実用バランス設定として扱う。

```text
Spectrum       On
Warmup         2
Actual Prefix  2
Continuity     Balanced 22
Seam           Off
```

注意: Seed 1235でSpectrum ON時の明確な画質崩れを確認しているため、全Seedで安定する設定ではない。

## 4. 解像度・チャンク比較

| 動画 | 解像度 | 尺 | 所見 |
|---|---:|---:|---|
| 00032 | 448×672、約0.3MP | 15秒 | 低解像度では肌・顔の微細なdriftが目立ちにくい |
| 00033 | 576×896、約0.5MP | 15秒 | 比較的安定 |
| 00034 | 576×896、約0.5MP | 5秒 | 単チャンクは安定 |
| 00035 | 640×960、約0.6MP | 5秒 | 0.6MP単独では大きな破綻なし |
| 00036 | 640×960、約0.6MP | 15秒 | 後続チャンクほど肌の変化が見えやすい |

暫定解釈: 0.6MPそのものより、Continuationで小さな誤差が次チャンクへ累積し、高解像度で可視化される可能性が高い。

## 5. Warmup比較

| 動画 | Warmup | 所見 |
|---|---:|---|
| 00038 | 1 | プッシュインあり。境界フリックは比較的目立たない |
| 00039 | 3 | 6秒台以降に顔の暗転・粗れが発生し、重大な破綻 |
| 00040 | 3 | 重大破綻は再現せず、軽い肌drift。結果の振れが大きい |
| 00041 | 2 | Seed 1234、Spectrum ON、Seam Off。全体として良好 |

暫定解釈:

- Warmup 3は結果が不安定なため不採用。
- Warmup 2はWarmup 3より安全だが、Spectrumの全Seed安定性は保証しない。
- Continuation chunkではActual Prefix 2が先頭2stepをActualへ要求する。

## 6. 厳密または準厳密なA/B比較

境界比は、境界の隣接フレームMAEを周辺の通常フレーム間MAE中央値で割った参考値。1未満なら境界変化が周辺動作より小さい。

### 6.1 Spectrum ON/OFF、Seed 1234

| 動画 | Spectrum | Warmup | Seam | 所見 |
|---|---|---:|---|---|
| 00041 | ON | 2 | Off | 良好。音声はほぼ無音、RMS約-63.7dBFS |
| 00045 | OFF | 無効 | Off | 良好。00041と視覚的にかなり近い |

Seed 1234ではSpectrum ONでもNativeに近い結果を維持した。

### 6.2 Spectrum ON/OFF、Seed 1235

| 動画 | Spectrum | Warmup | Seam | 5秒比 | 10秒比 | 所見 |
|---|---|---:|---|---:|---:|---|
| 00042 | ON | 2 | Off | 1.392 | 1.810 | Clip 1途中で服色変化。Clip 3で顔に強い斑点と肌崩れ |
| 00047 | OFF | 無効 | Off | 0.909 | 0.904 | 服色、肌、Identityを維持 |

確定事項:

- Seed 1235自体はNative生成で正常。
- 00042の崩れはSpectrumとSeed 1235の組み合わせで発生した可能性が高い。
- Seam CorrectionではClip内部のSpectrum Forecast誤差を修正できない。

### 6.3 Seam Auto/Off、Seed 1237

| 動画 | Spectrum | Warmup | Seam | 5秒比 | 10秒比 | 所見 |
|---|---|---:|---|---:|---:|---|
| 00044 | ON | 2 | Auto | 0.570 | 0.248 | 良好。Autoによる不自然な色変化なし |
| 00046 | ON | 2 | Off | 0.564 | 0.333 | 良好。Auto版と視覚差は非常に小さい |

確定事項:

- 無音に近い映像ではAutoの視覚的効果は小さい。
- Autoは10秒境界をわずかに平滑化したが、Offでも十分安定。
- 現時点ではOffを映像品質の基準とする。

## 7. Seed耐性

| Seed | Spectrum | Warmup | Seam | 動画 | 判定 |
|---:|---|---:|---|---|---|
| 1234 | ON | 2 | Off | 00041 | 良好 |
| 1234 | OFF | 無効 | Off | 00045 | 良好 |
| 1235 | ON | 2 | Off | 00042 | 失敗 |
| 1235 | OFF | 無効 | Off | 00047 | 良好 |
| 1236 | ON | 2 | Auto | 00043 | 許容。カメラ動作が強い |
| 1237 | ON | 2 | Auto | 00044 | 良好 |
| 1237 | ON | 2 | Off | 00046 | 良好 |

Spectrum ONの品質はSeed依存で変化する。結果確認なしの長尺・大量生成には追加の誤差検出またはフォールバックが必要。

## 8. 速度比較

| 条件 | 動画 | 生成時間 |
|---|---|---:|
| Spectrum ON | 00046 | 882.52秒、約14分43秒 |
| Spectrum OFF | 00047 | 1274.40秒、約21分14秒 |

```text
短縮時間   約391.88秒、約6分32秒
短縮率     約30.8%
処理速度   約1.44倍
```

別の比較でも約31.6%短縮しており、Spectrumの速度効果は再現している。ただし00046と00047はSeedが異なるため、この値は実用上の参考値。

## 9. 音声の現状

00041〜00047にはAAC音声ストリームがあるが、測定RMSは概ね-58〜-68dBFSで、聴感上ほぼ無音。したがって、歌唱、会話、伴奏を含むAudio ContinuityとSeam Autoの効果は未確定。

現時点の運用仮説:

```text
映像中心・無音に近い  Seam Off
会話・歌唱・演奏あり  Seam Autoの可能性。A/B未完了
```

## 10. 保留中・次のテスト

1. Seed 1235 / Spectrum ON / Warmup 1 / Seam Off
2. 固定カメラ・明確な持続歌唱で、同一SeedのSeam Off/Auto
3. 歌唱と小振幅・低速プッシュインを含む実用Promptで、同一SeedのSeam Off/Auto
4. 音声境界の前後100〜200msについて、瞬間ピーク、短時間RMS、F0、波形相関、スペクトル差、DC offsetを比較
5. 3チャンクで安定後、5×5秒または6×5秒でIdentity driftを確認

## 11. 検討中の対策

- Clip 1だけNative計算し、Continuation chunkからSpectrumを使用
- Spectrumの予測誤差が大きいstepだけActualへ戻す
- selective rollback correctionとanchor residual feedbackの同一Seed A/B
- 元画像による定期的なIdentity再アンカー
- 異常Contextを検出し、該当チャンクだけSpectrumなしで再生成
- Seam Autoの映像補正と音声補正を個別に選択可能にする

## 12. 将来のGitHub公開方法

- このMarkdownと機械可読なJSON/CSVを通常Gitへ追加する。
- コンタクトシートは`docs/assets/ab-tests/`等へ追加する。
- 大容量MP4は通常Gitへ直接追加せず、GitHub Release assetsまたはGit LFSを検討する。
- 公開前にPrompt、Workflow、モデル、ComfyUI revision、Python/Torch/CUDA、GPU、生成時間を各サンプルへ紐付ける。

## 00048 / 00049: 0.5 MP Seam Off vs Auto

- 共通条件: 576x896 (約0.5 MP), 24 fps, 3 x 5秒, Spectrum On, Warmup 1, Actual Prefix 2, Balanced 22, base seed 1235。
- 00048: Seam Off。5秒境界比 0.3583、10秒境界比 0.8562。
- 00049: Seam Auto。5秒境界比 0.3709、10秒境界比 0.4271。
- 視覚評価: 両方とも人物・衣装・肌は安定し、見た目の差は小さい。Autoは10秒境界を数値上改善した。
- 音声: 両方ともほぼ無音のため、音声シーム効果は未評価。
- 注意: 0.5 MP条件のため、0.6 MPで発生したSeed 1235の崩れをWarmup 1が解消したとは断定しない。

### 目視評価の補足

- ユーザー目視では00049（Seam Auto）の方がフリックが若干目立つ。
- 00048（Seam Off）の方が境界変化を比較的抑えられている。
- 境界指標の改善と主観的なフリック低減は一致しなかったため、本比較では目視評価を優先しSeam Offを採用候補とする。


## 00050: 音声あり一貫性テスト

- 条件: 576x896（約0.5 MP）、24 fps、3 x 5秒、Spectrum On、Warmup 1、Balanced 22、base seed 1235、Seam Off。
- 音声レベル: mean -19.9 dB、peak -6.4 dB。前回のほぼ無音サンプルより音声境界の評価に適する。
- 目視: 3チャンクを通して人物、髪、衣装、背景、露出は安定。肌・顔の累積崩れも目立たない。
- 5秒境界: 境界付近で瞬きが始まるためフレーム差はあるが、露出フリックより自然動作として見える。
- 10秒境界: 口形、顔、背景の連続性が高く、明確な視覚ジャンプは小さい。
- 未確認: 音声境界のクリック、F0、短時間RMS、スペクトル差の数値解析。
- 次の比較: 同一Prompt・Seed・解像度・Warmupのまま、SeamだけAutoへ変更した1本と比較する。

### 00050 音声の目視・聴感補足

- ユーザー聴感で10秒（Chunk 2→3境界）に短いプチノイズを確認。
- 同境界の映像連続性は良好であり、映像シームと音声シームの品質が一致しない例となった。
- 暫定対策候補: Video Seam Off、Audio Seam Autoを独立設定にする。


### 00050 実行レポート補足

- Prompt plan: Fixed、3 chunks、5.000秒。Seam correction Off。
- Chunk seeds: 12362262848839836333 / 1129406137053299874 / 8524677167168820503。
- Continuity motion: Chunk 2 = 0.378492、Chunk 3 = 0.388277。Continuation chunksはActual Prefix 2を要求。
- Retained frames: 124 + 119 + 119 = 362。Exact-durationで360 framesへ末尾調整。
- Audio: 480000 samples（32 kHz、15.000秒）。末尾補正 -2667 samplesは2 frames相当で、10秒境界のプチノイズ原因とは分離して扱う。
- 判定: sample-boundary alignmentは尺を整合させているが、波形位相・振幅の連続性までは保証しない。Audio Seam Off基準として保存する。

### 00050 境界評価の訂正

- 5秒（Chunk 1→2）: 映像フリックが確認できる。
- 10秒（Chunk 2→3）: 映像フリックは目立たないが、音声に短いプチノイズがある。
- 映像と音声の問題位置は一致していないため、Video SeamとAudio Seamは独立評価・独立処理が必要。

### 00050 最終訂正（この評価を優先）

- 5秒（Chunk 1→2）: 映像フリックあり。
- 10秒（Chunk 2→3）: 映像フリックは目立たない。
- 音声: 明確なプチノイズは確認できない。先行する「10秒に音声ノイズあり」という記録は取り消し、未検出として扱う。
- 00050はAudio Seam不具合の根拠にはせず、音声は専用テストで改めて検証する。
