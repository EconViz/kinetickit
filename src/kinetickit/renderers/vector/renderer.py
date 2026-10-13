"""The ``vector`` renderer capability."""

from __future__ import annotations

from typing import Any

from kinetickit.animation import Animation
from kinetickit.errors import ConfigurationError
from kinetickit.renderers.capabilities import (
    DIM_2D,
    DIM_PROJECTED_3D,
    OUT_ANIMATED_DOCUMENT,
    OUT_VECTOR_DOCUMENT,
    RendererCapabilities,
)
from kinetickit.renderers.vector.compiler import SvgCompiler, SvgDocument, SvgSettings

VECTOR_CAPABILITIES = RendererCapabilities(
    name="vector",
    dimensions=frozenset({DIM_2D, DIM_PROJECTED_3D}),
    geometry=frozenset(
        {"point", "line", "path", "shape", "group", "text"}
        | {"point3d", "pointcloud", "line3d", "polyline3d", "mesh", "surface", "group3d", "light"}
    ),
    features=frozenset({"clip", "overlay", "camera-animation", "draw-progress"}),
    outputs=frozenset({OUT_VECTOR_DOCUMENT, OUT_ANIMATED_DOCUMENT}),
    interactions=frozenset(),
    notes=(
        "Native SVG elements and SMIL animation; no raster frames.",
        "3D is exported as a time-varying 2D projection, not a rotatable scene.",
    ),
)


class VectorRenderer:
    """Compiles animations into native Animated SVG documents."""

    @property
    def capabilities(self) -> RendererCapabilities:
        return VECTOR_CAPABILITIES

    def render_document(self, animation: Animation, settings: Any = None) -> SvgDocument:
        if settings is None:
            settings = SvgSettings()
        if not isinstance(settings, SvgSettings):
            raise ConfigurationError("vector renderer settings must be an SvgSettings")
        return SvgCompiler(animation, settings).build()


__all__ = ["DIM_PROJECTED_3D", "VECTOR_CAPABILITIES", "VectorRenderer"]
