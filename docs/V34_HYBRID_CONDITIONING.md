# V3.4 hybrid First / Last / Reference conditioning

V3.4 treats Reference Images and temporal keyframes as orthogonal MiniMax H3 conditioning.

## Contract

- `Reference Image 1..8` build persistent `minimax_refs` blocks and the Qwen reference presentation (`<Picture N>`).
- `First Frame` is a frame-0 keyframe guide.
- `Last Frame` is a keyframe guide at the final frame of the generated target.
- Connecting one or more Reference Images does **not** disable or discard First Frame or Last Frame.

This mirrors the Core H3 composition model: reference conditioning can be created first and keyframe guides can then be layered onto the same conditioning payload.

## Supported input combinations

| First Frame | Last Frame | Reference Image(s) | Temporal mode | Reference blocks |
|---|---|---|---|---|
| no | no | no | T2VA | none |
| yes | no | no | I2VA | none |
| no | yes | no | Last-only | none |
| yes | yes | no | FL2VA | none |
| no | no | yes | Reference | present |
| yes | no | yes | I2VA | present |
| no | yes | yes | Last-only | present |
| yes | yes | yes | FL2VA | present |

The temporal mode is used for keyframe and persistence semantics. Reference assets are fingerprinted separately and remain active whenever connected.

## Continuation methods

### Native Masked

For chunk 2 and later, the protected continuation prefix is copied into the new target latent and masked against denoising. A First Frame keyframe at frame 0 is removed from continuation-chunk conditioning because it would compete with that protected prefix. Persistent Reference blocks remain. A Last Frame keyframe remains on the final target because it is outside the protected prefix.

### Guide / Motion Context

For chunk 2 and later, Continuum context replaces the old frame-0 keyframe according to the normal recommended continuation policy. Persistent Reference blocks remain, the continuation context reference is appended, and a final Last Frame keyframe is moved to the final frame of the expanded continuation target.

## Run Storage

Hybrid inputs are fingerprinted independently:

- First Frame participates in the global I2VA/FL2VA sampling contract, so changing it invalidates all stored chunks for that revision.
- Reference Images participate in the separate reference contract, so changing the active references invalidates the corresponding sampling revision.
- Last Frame participates in the final chunk contract, so changing only Last Frame preserves reusable earlier chunks and invalidates the final chunk.

This prevents a saved Reference run from reusing stale chunks after a hybrid First/Last keyframe changes.

## Dynamic references

The V3.4 public facade exposes Reference Image inputs through 8. Inputs 4..8 are compacted internally before entering the stable inherited sampler signature, without changing First/Last behavior. Active references retain connection order and are presented as contiguous `<Picture 1>..<Picture N>` references.
