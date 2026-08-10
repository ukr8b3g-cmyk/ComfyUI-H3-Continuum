# V2.1.4 UI Simplification

The integrated `H3 Continuum Sampler V2` is the primary workflow node.

## Default workflow

```text
Text (Multiline) -> Sequence Prompt
Image             -> first_frame
Sampler images/audio -> Create Video
```

The default node surface shows Sequence Prompt, first frame, chunk timing,
continuity, seed, and seam correction. Individual clip overrides and Advanced
settings are collapsed.

## Advanced settings

Advanced settings expose `last_frame`, `initial_state`, `session`,
`prompt_plan`, reroll controls, diagnostics, `last_state`, session output, and
report output. A saved workflow with an existing Advanced connection expands
the section automatically.

The Advanced Settings button remains the section header when expanded. The
button is placed before the expanded controls instead of moving below them.

## Legacy nodes

V1 Join, Finish, Assemble, state utilities, and auxiliary V2 plan/session nodes
remain registered for saved-workflow compatibility. They are marked deprecated
and moved to `MiniMax H3/Continuum/Legacy`, so ComfyUI can omit them from the
normal node picker.

No sampling, State/Session schema, output order, or accelerator behavior changes
in V2.1.4.
