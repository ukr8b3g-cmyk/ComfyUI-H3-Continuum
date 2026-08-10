# V2.1.5 UI Serialization Stability

V2.1.5 preserves the backend-defined Sampler V2 widget and slot structure.
The frontend may change labels, computed height, and DOM/slot visibility only.

## Stability contract

- Backend widget type, serialization behavior, and relative order are unchanged.
- Backend inputs and outputs are never removed or re-added for UI folding.
- Individual Clip Overrides and Advanced buttons are appended non-serialized frontend widgets.
- Prompt and advanced sockets remain registered in stable order while collapsed slots are hidden visually.
- onNodeCreated and onConfigure are wrapped by one Sampler V2 extension only.

This release does not change Sampling, State, Session, Prompt Plan, Spectrum Interop, or project schemas.

## Browser regression

Set chunks=2, chunk_seconds=5.0, width=1344, height=768, Balanced 22 frames, Seam Correction Auto, and a fixed seed.
Open and close Individual Clip Overrides and Advanced settings, change tabs, save, reload ComfyUI, and reload the workflow.
All values and connections must remain in their original slots.
