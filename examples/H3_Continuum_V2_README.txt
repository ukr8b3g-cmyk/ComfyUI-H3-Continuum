H3 Continuum V2 standard workflow

Contents:
- H3_Continuum_V2.json
- H3_Continuum_V2_reference.webp

Setup:
1. Copy H3_Continuum_V2_reference.webp to ComfyUI/input/.
2. Drag H3_Continuum_V2.json onto the ComfyUI canvas.
3. Install or replace any custom nodes reported as missing.
4. Confirm the model selections before queueing.

Default profile:
- 3 chunks x 5.0 seconds
- Timeline prompt with three sections
- Scale Image to Total Pixels: area, 0.60 MP, 32-step rounding
- Continuity: Balanced, 22 frames
- Seam correction: Auto

Reference test environment:
- NVIDIA GeForce RTX 5060 Ti 16GB
- 64GB system RAM

The 0.60 MP profile is a starting point. If VRAM is insufficient, reduce the image scale to 0.30 MP.
