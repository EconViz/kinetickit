"""The ``raster`` renderer capability."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import numpy.typing as npt

from kinetickit.animation import Animation
from kinetickit.errors import ConfigurationError
from kinetickit.layout import LayoutResult, Viewport, resolve_layout
from kinetickit.renderers.capabilities import (
    DIM_2D,
    DIM_PROJECTED_3D,
    OUT_RASTER_FRAME,
    RendererCapabilities,
)
from kinetickit.renderers.raster.settings import RasterSettings, ResolvedSize
from kinetickit.scene import Scene2D, Scene3D

RASTER_CAPABILITIES = RendererCapabilities(
    name="raster",
    dimensions=frozenset({DIM_2D, DIM_PROJECTED_3D}),
    geometry=frozenset(
        {"point", "line", "path", "shape", "group", "text"}
        | {"point3d", "pointcloud", "line3d", "polyline3d", "mesh", "surface", "group3d", "light"}
    ),
    features=frozenset({"clip", "overlay", "camera-animation", "draw-progress", "z-animation"}),
    outputs=frozenset({OUT_RASTER_FRAME}),
    interactions=frozenset(),
    notes=(
        "Antialiased RGBA frames; group opacity multiplies child alpha.",
        "3D is projected with flat, baked shading and painter's-algorithm ordering.",
    ),
)


@dataclass(frozen=True)
class RenderedFrame:
    """A rendered frame: ``pixels`` is an ``(height, width, 4)`` ``uint8`` RGBA array."""

    pixels: npt.NDArray[np.uint8]
    width: int
    height: int
    dpi: int


class RasterRenderer:
    """Renders scene snapshots to RGBA frames through a private backend adapter."""

    @property
    def capabilities(self) -> RendererCapabilities:
        return RASTER_CAPABILITIES

    def resolve_size(self, settings: RasterSettings) -> ResolvedSize:
        return settings.resolve()

    def layout_for(self, animation: Animation, settings: RasterSettings) -> LayoutResult | None:
        if isinstance(animation.scene, Scene3D):
            return None  # 3D cameras define their own view; there is nothing to fit
        size = settings.resolve()
        vp = Viewport(size.logical_width, size.logical_height, settings.margins)
        return resolve_layout(animation, vp, padding=settings.padding)

    def render_frame(
        self, snapshot: Any, layout: LayoutResult | None, settings: RasterSettings
    ) -> RenderedFrame:
        from kinetickit.renderers.raster import _matplotlib

        if not isinstance(snapshot, (Scene2D, Scene3D)):
            raise ConfigurationError("the raster renderer draws Scene2D and Scene3D snapshots")
        if isinstance(snapshot, Scene2D) and layout is None:
            raise ConfigurationError("a 2D snapshot needs the layout from layout_for()")
        size = settings.resolve()
        pixels = _matplotlib.render_snapshot(snapshot, layout, size, settings)
        return RenderedFrame(pixels, size.pixel_width, size.pixel_height, size.dpi)


def make_raster_renderer() -> RasterRenderer:
    """Factory used by the registry; fails with ImportError when the extra is missing."""
    from kinetickit.renderers.raster import _matplotlib  # noqa: F401

    return RasterRenderer()
