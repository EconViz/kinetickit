"""Native vector (Animated SVG) rendering."""

from __future__ import annotations

from kinetickit.renderers.vector.compiler import SvgDocument, SvgSettings
from kinetickit.renderers.vector.renderer import VECTOR_CAPABILITIES, VectorRenderer

__all__ = ["VECTOR_CAPABILITIES", "SvgDocument", "SvgSettings", "VectorRenderer"]
