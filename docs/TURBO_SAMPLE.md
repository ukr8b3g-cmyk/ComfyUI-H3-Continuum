# V3.9 Turbo Sample

A separate, user-supplied example of Continuum prompt formatting, not a new model
or a verified quality preset. Available in Templates as
`MiniMax_H3_Continuum_V39_Turbo_Sample` (no parenthesized suffix).

- Prompt Format: Auto; 2 chunks x 8 seconds; Full Run; Progress OFF.
- The multiline prompt demonstrates `[Chunk 1]`, `[Chunk 2]`, first-image alignment,
  continuous dancing with a fixed background/camera, and an off-screen male Thai rap.
  `<d>[Thai] ... </d>` is H3 lyric syntax, not part of the template name.
- Saved model: `minimax/DasiwaMinimaxH3_dasiwaHybridV4_int8.safetensors`.
  Obtain it from the [author's model page](https://civitai.com/models/2877206?modelVersionId=3391862)
  or select a compatible installed H3 model. No model weights are bundled.
- One LoRA is enabled: `minimax/minimax_h3_fl2v_turbo_4step_v1.2_768p_comfyui_bf16.safetensors`,
  strength 1, from [LightX2V](https://huggingface.co/lightx2v/Minimax-h3-Turbo).
  The supplied graph uses Euler / simple / 6 steps / Draft 0.30 MP. These are
  preserved sample values, not a validated 4-step/768p configuration; check the
  selected model and LoRA instructions before generation.
- Video VAE: `minimax_h3_video_vae_int8_convrot.safetensors`; audio VAE:
  `minimax_h3_audio_vae_fp32.safetensors`; text encoder:
  `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors`, type `minimax`.
  See [model download links and folders](../README.md#required-models-and-extensions).
- Select your own First Image (`example.png` is only a placeholder). The disabled
  optional audio/video inputs retain sample filenames; select real files before
  enabling them. Reselect model/LoRA paths if you do not use a `minimax` subfolder.
- Requires KJNodes (SageAttention and Model Preview Override), rgthree, and Spectrum
  node definitions. Spectrum is OFF. Preview Override uses Tiny VAE `none` and leaves its two optional VAE inputs disconnected.
  For Review, enable Progress and Review Each Chunk in a new Run. Connecting a preview VAE makes new Takes read-only.
- Thai lyric accuracy, unchanged background, identity preservation and subjective
  video/audio quality are not established by adding this sample. Thai is outside
  H3's explicitly listed stable dialogue languages. No new GPU test is claimed.
- Existing standard workflows and saved Runs/Takes are unchanged. Outputs use the
  separate `video/MiniMax_H3_Continuum_V39_Turbo_Sample` prefix. GitHub main includes
  this sample; the already-published v3.9.8 release/Registry package is not replaced.

## 日本語

標準Workflowとは別のTurboサンプルです。Auto・2チャンク×8秒で、改行した
映像・環境音・音楽の記述、入力画像の指定、固定背景、画面外の男性タイ語ラップを
示します。画像・モデル・LoRAは各自で導入して選択してください。
4-step/768p LoRAに対して6 steps・Draft解像度という添付の設定を保持しています。
推奨設定や画質の合格を意味しません。タイ語の発音、人物・背景保持も未保証です。
KJのプレビュー用VAE入力は両方未接続、Tiny VAEはnoneです。Reviewは新規RunでProgressとReview Each Chunkを有効にします。プレビュー用VAEを接続すると、新しいTakeは読み取り専用になります。
今回はサンプル追加とCPU検証のみで、実環境反映・新規GPU試験・Release更新は行いません。
