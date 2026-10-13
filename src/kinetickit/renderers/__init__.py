"""Capability-driven renderer contracts and the built-in ``vector`` renderer."""

from __future__ import annotations

from kinetickit.renderers.analysis import requirements_for
from kinetickit.renderers.capabilities import RendererCapabilities, Requirements, require
from kinetickit.renderers.protocol import DocumentRenderer, FrameRenderer, Renderer
from kinetickit.renderers.registry import (
    available_renderers,
    get_renderer,
    register_renderer,
)
from kinetickit.renderers.vector import VectorRenderer

register_renderer("vector", VectorRenderer, replace=True)

__all__ = [
    "DocumentRenderer",
    "FrameRenderer",
    "Renderer",
    "RendererCapabilities",
    "Requirements",
    "available_renderers",
    "get_renderer",
    "register_renderer",
    "require",
    "requirements_for",
]
