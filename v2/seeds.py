"""Deterministic per-chunk seed derivation."""

from __future__ import annotations

_MASK64 = (1 << 64) - 1
_GOLDEN = 0x9E3779B97F4A7C15
_MIX_A = 0xBF58476D1CE4E5B9
_MIX_B = 0x94D049BB133111EB


def _splitmix64(value: int) -> int:
    value = (value + _GOLDEN) & _MASK64
    value = ((value ^ (value >> 30)) * _MIX_A) & _MASK64
    value = ((value ^ (value >> 27)) * _MIX_B) & _MASK64
    return (value ^ (value >> 31)) & _MASK64


def derive_chunk_seed(base_seed: int, chunk_index: int, reroll_nonce: int = 0) -> int:
    """Return a stable 64-bit seed for a zero-based chunk index.

    The index and reroll nonce are mixed independently so rerolling chunk N does
    not alter accepted chunks before N.
    """

    if isinstance(base_seed, bool) or isinstance(chunk_index, bool) or isinstance(reroll_nonce, bool):
        raise TypeError("seed inputs must be integers, not booleans")
    chunk_index = int(chunk_index)
    reroll_nonce = int(reroll_nonce)
    if chunk_index < 0:
        raise ValueError("chunk_index must be non-negative")
    if reroll_nonce < 0:
        raise ValueError("reroll_nonce must be non-negative")
    value = int(base_seed) & _MASK64
    value ^= _splitmix64(chunk_index + 1)
    value ^= _splitmix64((reroll_nonce + 1) * 0xD6E8FEB86659FD93)
    return _splitmix64(value)
