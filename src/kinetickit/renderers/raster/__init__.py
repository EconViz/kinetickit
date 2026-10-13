"""Raster (pixel frame) rendering. Requires the ``raster`` extra at use time."""

from __future__ import annotations

from kinetickit.renderers.raster.renderer import (
    RASTER_CAPABILITIES,
    RasterRenderer,
    RenderedFrame,
    make_raster_renderer,
)
from kinetickit.renderers.raster.settings import MAX_DPI, RasterSettings, ResolvedSize

__all__ = [
    "MAX_DPI",
    "RASTER_CAPABILITIES",
    "RasterRenderer",
    "RasterSettings",
    "RenderedFrame",
    "ResolvedSize",
    "make_raster_renderer",
]
