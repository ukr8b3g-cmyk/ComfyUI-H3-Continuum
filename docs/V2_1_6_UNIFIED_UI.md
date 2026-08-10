# V2.1.6 Unified UI

V2.1.6 replaces the layered V2.1.4/2.1.5 display patches with one frontend
controller in `web/h3_continuum_v2.js`.

## Contract

- Sampling, Native Continuity, State, Session, Prompt Plan and Spectrum Interop
  semantics are unchanged.
- Backend inputs, outputs and serialized widget order remain registered in the
  same order for saved-workflow compatibility.
- The frontend never calls `removeInput`, `addInput`, `removeOutput`,
  `addOutput`, `node.widgets.splice`, or fixed-height `node.setSize`.
- Clip Prompt sockets are selected by socket name. For `chunks=N`, unconnected
  Clip 1..N sockets are visible; unconnected sockets above N are hidden.
- A connected Clip Prompt remains visible after reducing `chunks` so hidden
  links are not created.
- `Individual Clip Overrides` is removed; the visible sockets themselves are
  the override UI.
- Advanced inputs/outputs remain registered. They are shown while Advanced is
  open, and connected Advanced sockets remain visible while it is closed.
- Advanced scalar widgets are display-only folded; their values and serialized
  positions are not rewritten.
- Node height is recalculated from current content; no fixed height is imposed.
- Core visibility works without DOM selectors in both classic LiteGraph canvas and Vue nodes.
- Vue DOM handling is only a fallback for advanced output rows.

## Browser regression

Test at minimum:

1. Set `chunks=3`, then 5, then 2.
2. Connect a prompt to Clip 5 before reducing to 2; Clip 5 must remain visible.
3. Open/close Advanced with both unconnected and connected Advanced sockets.
4. Switch workflow tabs.
5. Save, reload ComfyUI, and reload the workflow.
6. Confirm widget values, socket indices, and links remain unchanged.
