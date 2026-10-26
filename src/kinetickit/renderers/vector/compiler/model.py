"""Settings, result and channel types shared by the SVG compiler."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from kinetickit.interpolation import Color
from kinetickit.layout import LayoutResult, Margins
from kinetickit.renderers.vector.svg import Element, num
from kinetickit.scene import (
    Camera2D,
    Node,
)
from kinetickit.styles import MinimalTheme, Theme

SVG_NS = "http://www.w3.org/2000/svg"

_SYMBOLS = {
    "circle": "M1 0A1 1 0 1 0-1 0A1 1 0 1 0 1 0Z",
    "square": "M-1-1L1-1L1 1L-1 1Z",
    "diamond": "M0-1.2L1.2 0L0 1.2L-1.2 0Z",
    "triangle": "M0 1.1L1 -0.7L-1 -0.7Z",
    "plus": "M-.3-1L.3-1L.3-.3L1-.3L1 .3L.3 .3L.3 1L-.3 1L-.3 .3L-1 .3L-1-.3L-.3-.3Z",
    "cross": "M-.75-1L0-.25L.75-1L1-.75L.25 0L1 .75L.75 1L0 .25L-.75 1L-1 .75L-.25 0L-1-.75Z",
}


@dataclass(frozen=True)
class SvgSettings:
    """Options for native Animated SVG output (sizes are logical pixels)."""

    width: float = 640.0
    height: float = 400.0
    margins: Margins = Margins()
    padding: float = 0.05
    background: Color | str | None = None
    theme: Theme = MinimalTheme
    loop: bool = False
    precision: int = 4
    samples: int = 24
    title: str | None = None
    description: str | None = None
    pretty: bool = True
    embed_fonts: bool = True
    layout: LayoutResult | None = None
    degradation: str = "drop"
    reduced_motion: Any = (
        "auto"  # "auto": the animation's policy; None disables; or a ReducedMotion
    )


@dataclass(frozen=True)
class SvgDocument:
    """A finished Animated SVG plus facts about how it was produced."""

    root: Element
    text: str
    width: float
    height: float
    duration: float
    element_ids: dict[str, str]
    warnings: tuple[str, ...] = ()
    animation_count: int = 0
    fonts: tuple[str, ...] = ()
    network_dependencies: tuple[str, ...] = field(default=())

    def to_bytes(self) -> bytes:
        return self.text.encode("utf-8")


@dataclass
class Track:
    """One animated SVG attribute: how to compute its string from the node's state at time t."""

    target: Element
    attribute: str
    value: Callable[[Any, Camera2D], str]
    transform: str | None = None  # animateTransform type, else plain <animate>
    additive: bool = False


@dataclass
class Channel:
    node: Node
    paths: tuple[str, ...]
    tracks: list[Track]
    uses_camera: bool = False
    discrete: bool = False
    optional: tuple[str, ...] = ()
    linear: bool = True  # the attribute value is a linear function of the property value


def _hex(c: Color) -> str:
    return "#" + c.to_hex()[1:7]


def _paint(attrs: dict[str, str], name: str, color: Color | None) -> None:
    if color is None:
        attrs[name] = "none"
        return
    attrs[name] = _hex(color)
    if color.a != 1.0:
        attrs[f"{name}-opacity"] = num(color.a, 4)


class LayoutResultView:
    """Scale and centre of the world window for one camera state."""

    def __init__(self, layout: LayoutResult, cam: Camera2D) -> None:
        base = cam.view if cam.view is not None else layout.base_view
        view = LayoutResult(layout.viewport, base)
        self.scale = view.scale(cam)
        self.center = view.window(cam).center
