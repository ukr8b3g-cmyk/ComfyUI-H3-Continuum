"""H3 Continuum Join — native MiniMax H3 chunk continuation."""

from __future__ import annotations

import logging

WEB_DIRECTORY = "./web"

# ComfyUI loads custom-node folders as packages. Standalone test collection may
# import this file as a top-level module; keep that path inert because ComfyUI is
# intentionally not a unit-test dependency.
if __package__:
    from .nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS
    from .temporal import run_temporal_self_test
    from .version import PACKAGE_VERSION

    try:
        run_temporal_self_test()
    except Exception as exc:
        raise RuntimeError(f"H3 Continuum Join self-test failed: {exc}") from exc
    logging.getLogger("h3_continuum_join").info(
        "H3 Continuum Join %s loaded (V2 integrated sampler + hidden legacy workflow compatibility)",
        PACKAGE_VERSION,
    )
else:  # pragma: no cover
    NODE_CLASS_MAPPINGS = {}
    NODE_DISPLAY_NAME_MAPPINGS = {}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
