"""Compile an animation into a native Animated SVG document.

World content lives in a y-up group (geometry stays in world coordinates, strokes use
``vector-effect: non-scaling-stroke`` so widths are pixels); overlay content is plain pixel
space. Motion becomes SMIL ``<animate>``/``<animateTransform>`` elements with exact
``keySplines`` for linear and cubic-Bézier segments and dense sampling for every other shape of
curve. No raster frames are ever embedded.
"""

from __future__ import annotations

from kinetickit.renderers.vector.compiler.document import SvgCompiler
from kinetickit.renderers.vector.compiler.model import (
    _SYMBOLS,
    SVG_NS,
    Channel,
    LayoutResultView,
    SvgDocument,
    SvgSettings,
    Track,
    _hex,
    _paint,
)

__all__ = [
    "SVG_NS",
    "_SYMBOLS",
    "Channel",
    "LayoutResultView",
    "SvgCompiler",
    "SvgDocument",
    "SvgSettings",
    "Track",
    "_hex",
    "_paint",
]
