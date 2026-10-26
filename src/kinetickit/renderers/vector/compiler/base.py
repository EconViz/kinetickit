"""Shared state and helpers of the SVG compiler."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from kinetickit.animation import Animation
from kinetickit.layout import LayoutResult, Viewport, resolve_layout
from kinetickit.renderers.vector.compiler.model import (
    Channel,
    LayoutResultView,
    SvgSettings,
    Track,
)
from kinetickit.renderers.vector.svg import Element, num, svg_id
from kinetickit.scene import (
    Camera2D,
    Node,
    Point2D,
    Scene3D,
)
from kinetickit.timeline import PropertyRef
from kinetickit.typography import FontResource


class CompilerBase:
    def __init__(self, animation: Animation, settings: SvgSettings) -> None:
        self.is3d = isinstance(animation.scene, Scene3D)
        self.animation = animation
        self.settings = settings
        self.tl = animation.timeline
        self.D = animation.duration
        self.registry = animation.registry
        vp = Viewport(settings.width, settings.height, settings.margins)
        self.layout: LayoutResult | None = None
        if not self.is3d:
            self.layout = settings.layout or resolve_layout(animation, vp, padding=settings.padding)
        self.snapshot: Any = animation.sample(0.0)
        self.animated: set[PropertyRef[Any]] = set(self.tl.properties) if self.D > 0 else set()
        self.channels: list[Channel] = []
        self.ids: set[str] = set()
        self.idmap: dict[str, str] = {}
        self.defs = Element("defs")
        self.fonts: dict[tuple[str, str, str], FontResource] = {}
        self.warnings: list[str] = []
        self.consumed: set[PropertyRef[Any]] = set()
        self.count = 0
        cam = self.snapshot.camera
        self.s0 = self.layout.scale(cam) if self.layout is not None else 1.0

    # ---------------------------------------------------------------- helpers
    def fmt(self, v: float) -> str:
        return num(v, self.settings.precision)

    def is_animated(self, node: Node, path: str) -> bool:
        return any(r.node_id == node.id and r.path == path for r in self.animated)

    def element_id(self, node: Node) -> str:
        sid = svg_id(node.id, self.ids)
        self.idmap[node.id] = sid
        return sid

    def base_attrs(self, node: Node, sid: str) -> dict[str, str]:
        attrs: dict[str, str] = {"id": sid, "data-kk-id": node.id, "data-kk-kind": node.kind}
        if node.opacity != 1.0:
            attrs["opacity"] = self.fmt(node.opacity)
        if not node.visible:
            attrs["visibility"] = "hidden"
        return attrs

    def common_channels(self, node: Node, target: Element) -> None:
        if self.is_animated(node, "opacity"):
            self.channels.append(
                Channel(
                    node, ("opacity",), [Track(target, "opacity", lambda n, c: self.fmt(n.opacity))]
                )
            )
        if self.is_animated(node, "visible"):
            self.channels.append(
                Channel(
                    node,
                    ("visible",),
                    [
                        Track(
                            target, "visibility", lambda n, c: "visible" if n.visible else "hidden"
                        )
                    ],
                    discrete=True,
                )
            )

    @staticmethod
    def _getter(name: str) -> Callable[[Any, Camera2D], str]:
        def get(node: Any, cam: Camera2D) -> str:
            return str(getattr(node, name))

        return get

    def camera_scale(self, cam: Camera2D) -> float:
        assert self.layout is not None
        return LayoutResultView(self.layout, cam).scale

    def point_scale(self, node: Point2D, cam: Any, overlay: bool) -> str:
        k = node.size if overlay else node.size / self.camera_scale(cam)
        return f"{self.fmt(k)} {self.fmt(-k if overlay else k)}"
