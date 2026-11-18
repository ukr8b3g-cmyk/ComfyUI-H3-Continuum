"""Fixed nine-slot Reference Images input for the V3.9 sampler."""

from __future__ import annotations

from dataclasses import dataclass

import torch

from ..reference import ReferenceImageBundle
from .reference_routing import REFERENCE_SLOT_IDS, parse_chunk_selector


REFERENCE_IMAGES_V39_TYPE = "H3_CONTINUUM_REFERENCE_IMAGES_V39"
REFERENCE_USE_ALL = "All chunks"
REFERENCE_USE_PER_CHUNK = "Per chunk"
REFERENCE_USE_OPTIONS = (REFERENCE_USE_ALL, REFERENCE_USE_PER_CHUNK)
MAX_CHUNKS = 16  # Current Sampler schema limit; checked in integration tests.


@dataclass(frozen=True, slots=True)
class ReferenceImagesV39Bundle:
    images: tuple[torch.Tensor | None, ...]
    reference_use: str
    selectors: tuple[str, ...]


def _canonical_selector(value: str) -> str:
    parsed = parse_chunk_selector(value, total_chunks=MAX_CHUNKS)
    if not parsed.valid:
        details = "; ".join(issue.message for issue in parsed.issues)
        raise ValueError(f"invalid V3.9 Reference chunk selection: {details}")
    return ",".join(map(str, parsed.logical_chunks)) or "off"


def effective_reference_inputs(bundle: ReferenceImagesV39Bundle | None, *, chunks: int):
    """Return legacy-shaped images and private selectors without changing saved data."""
    if not isinstance(chunks, int) or isinstance(chunks, bool) or not 1 <= chunks <= MAX_CHUNKS:
        raise ValueError(f"V3.9 Reference Chunks must be within 1..{MAX_CHUNKS}")
    if bundle is None:
        images = (None,) * 9
        mode = REFERENCE_USE_ALL
        selections = ("off",) * 9
    elif (not isinstance(bundle, ReferenceImagesV39Bundle)
          or len(bundle.images) != 9 or len(bundle.selectors) != 9
          or bundle.reference_use not in REFERENCE_USE_OPTIONS):
        raise ValueError("V3.9 Reference Images requires its nine-slot V3.9 bundle")
    else:
        images = bundle.images
        mode = bundle.reference_use
        selections = bundle.selectors
    selectors = {}
    for index, (image, selection) in enumerate(zip(images, selections, strict=True), start=1):
        if image is None:
            selectors[f"R{index}"] = "off"
        elif mode == REFERENCE_USE_ALL:
            selectors[f"R{index}"] = "all"
        else:
            parsed = parse_chunk_selector(selection, total_chunks=MAX_CHUNKS)
            if not parsed.valid:
                details = "; ".join(issue.message for issue in parsed.issues)
                raise ValueError(f"R{index} chunk selection: {details}")
            active = (n for n in parsed.logical_chunks if n <= chunks)
            selectors[f"R{index}"] = ",".join(map(str, active)) or "off"
    if tuple(selectors) != REFERENCE_SLOT_IDS:
        raise ValueError("V3.9 Reference slot ordering changed")
    return images[:3], ReferenceImageBundle(images[3:]), selectors


class H3ContinuumReferenceImagesV39:
    CATEGORY = "MiniMax H3/Continuum/Input"
    DESCRIPTION = "Connect up to nine fixed Reference Images; choose chunks in this node."
    RETURN_TYPES = (REFERENCE_IMAGES_V39_TYPE,)
    RETURN_NAMES = ("reference_images",)
    FUNCTION = "pack"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "reference_use": (REFERENCE_USE_OPTIONS, {
                    "default": REFERENCE_USE_ALL,
                    "display_name": "Reference Use",
                    "tooltip": "All chunks uses connected images throughout. Per chunk uses the assignments below.",
                }),
                **{
                    f"reference_r{index}_chunks": ("STRING", {
                        "default": "off", "advanced": True,
                        "display_name": f"Image {index} chunks",
                        "tooltip": f"Saved assignments for Reference Image {index}; use the in-node table.",
                    }) for index in range(1, 10)
                },
            },
            "optional": {
                f"reference_image_{index}": ("IMAGE", {
                    "display_name": f"Reference Image {index} (Optional)",
                    "tooltip": f"Fixed Image {index} / @R{index}. Its number never changes with other connections.",
                }) for index in range(1, 10)
            },
        }

    def pack(self, reference_use=REFERENCE_USE_ALL, **kwargs):
        if reference_use not in REFERENCE_USE_OPTIONS:
            raise ValueError("Reference Use must be All chunks or Per chunk")
        images = tuple(kwargs.get(f"reference_image_{index}") for index in range(1, 10))
        selectors = tuple(
            (_canonical_selector(kwargs.get(f"reference_r{index}_chunks", "off"))
             if reference_use == REFERENCE_USE_PER_CHUNK and images[index - 1] is not None else
             str(kwargs.get(f"reference_r{index}_chunks", "off")))
            for index in range(1, 10)
        )
        return (ReferenceImagesV39Bundle(images, reference_use, selectors),)
