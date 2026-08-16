# H3 Continuum Seam Test Source

`H3 Continuum Seam Test Source (Experimental)`は、Video Seamの比較専用ノードです。
H3 Samplingは実行せず、同じ入力画像から決定的な3つの5秒Chunkを作ります。

## 接続

```text
Load Image
  image
    -> H3 Continuum Seam Test Source (Experimental)

Seam Test Source: images
    -> H3 Continuum Assemble + Seam: images

Seam Test Source: audio
    -> H3 Continuum Assemble + Seam: audio

Seam Test Source: assembly_plan
    -> H3 Continuum Assemble + Seam: assembly_plan
```

Assembler側は次の設定にします。

```text
exact_total_duration = true
Audio Seam = Off
Report Detail = Detailed Report
```

## 比較手順

同じ入力画像と`Exposure Change = 0.08`を維持し、`Video Seam`だけ変更します。

1. `Analyze Only`
2. `Auto`
3. `Auto 2`（露出ランプ補正はExperimental）

期待結果は次のとおりです。

```text
Analyze Only
  -> 1->2、2->3とも class=exposure_ramp
  -> フレームは未変更

Auto
  -> exposure rampは補正対象外
  -> action=kept native boundary

Auto 2
  -> 各境界の先頭4フレームだけ露出を補間
  -> action=normalized exposure/color on 4 exposure ramp boundary frame(s)
```

`Test Resolution = 256 px (Fast)`を推奨します。アルゴリズムの判定確認に高解像度は不要です。
`Input Size`は800x800入力で数GiBのRAMを消費する可能性があります。
