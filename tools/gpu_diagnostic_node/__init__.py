"""Standalone GPU diagnostics for H3 Continuum.

This package is intentionally separate from the production node package. Copy the
directory into ComfyUI/custom_nodes only while diagnostics are needed.
"""

from .nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
