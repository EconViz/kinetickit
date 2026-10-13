"""Renderer protocols. Implementations live behind private adapters."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from kinetickit.renderers.capabilities import RendererCapabilities


@runtime_checkable
class Renderer(Protocol):
    """Anything that declares capabilities. Capability detection never uses ``hasattr``."""

    @property
    def capabilities(self) -> RendererCapabilities: ...


@runtime_checkable
class FrameRenderer(Renderer, Protocol):
    """Turns one scene snapshot into a raster frame."""

    def render_frame(self, snapshot: Any, layout: Any, settings: Any) -> Any: ...


@runtime_checkable
class DocumentRenderer(Renderer, Protocol):
    """Turns a whole animation into one document (animated or interactive)."""

    def render_document(self, animation: Any, settings: Any) -> Any: ...
