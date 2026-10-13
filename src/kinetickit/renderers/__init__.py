"""Capability-driven renderer contracts and the built-in ``vector`` renderer."""

from __future__ import annotations

from kinetickit.renderers.analysis import requirements_for
from kinetickit.renderers.capabilities import RendererCapabilities, Requirements, require
from kinetickit.renderers.interactive import make_interactive_renderer
from kinetickit.renderers.projection import Projected, project_point, project_scene
from kinetickit.renderers.protocol import DocumentRenderer, FrameRenderer, Renderer
from kinetickit.renderers.raster import make_raster_renderer
from kinetickit.renderers.registry import (
    available_renderers,
    get_renderer,
    register_renderer,
)
from kinetickit.renderers.vector import VectorRenderer

register_renderer("vector", VectorRenderer, replace=True)
register_renderer("raster", make_raster_renderer, replace=True)
register_renderer("interactive", make_interactive_renderer, replace=True)

__all__ = [
    "DocumentRenderer",
    "FrameRenderer",
    "Projected",
    "Renderer",
    "RendererCapabilities",
    "Requirements",
    "available_renderers",
    "get_renderer",
    "project_point",
    "project_scene",
    "register_renderer",
    "require",
    "requirements_for",
]
