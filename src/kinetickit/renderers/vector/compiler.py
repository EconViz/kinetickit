"""Compile an animation into a native Animated SVG document.

World content lives in a y-up group (geometry stays in world coordinates, strokes use
``vector-effect: non-scaling-stroke`` so widths are pixels); overlay content is plain pixel
space. Motion becomes SMIL ``<animate>``/``<animateTransform>`` elements with exact
``keySplines`` for linear and cubic-Bézier segments and dense sampling for every other shape of
curve. No raster frames are ever embedded.
"""

from __future__ import annotations

import base64
import itertools
import math
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from typing import Any

from kinetickit.accessibility import ReducedMotion
from kinetickit.animation import Animation
from kinetickit.easing import CubicBezier, linear, step
from kinetickit.errors import CapabilityError
from kinetickit.geometry.two_d import Path2D, Transform2D, Vec2
from kinetickit.interpolation import Color, StepInterpolator
from kinetickit.layout import LayoutResult, Margins, Viewport, resolve_layout
from kinetickit.renderers.vector.projected import ProjectedWorld
from kinetickit.renderers.vector.svg import Element, num, svg_id
from kinetickit.scene import (
    Camera2D,
    Group2D,
    Line2D,
    Node,
    PathNode2D,
    Point2D,
    Scene3D,
    Shape2D,
    Text2D,
)
from kinetickit.styles import MinimalTheme, Theme
from kinetickit.timeline import PropertyRef
from kinetickit.typography import FontResource

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


class SvgCompiler:
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

    # ---------------------------------------------------------------- nodes
    def stroke_attrs(
        self, color: Color | None, width: float, cap: str | None, join: str, dash: tuple[float, ...]
    ) -> dict[str, str]:
        attrs: dict[str, str] = {}
        _paint(attrs, "stroke", color)
        if color is not None:
            attrs["stroke-width"] = self.fmt(width)
            if cap and cap != "butt":
                attrs["stroke-linecap"] = cap
            if join != "miter":
                attrs["stroke-linejoin"] = join
            if dash:
                attrs["stroke-dasharray"] = " ".join(self.fmt(d) for d in dash)
            attrs["vector-effect"] = "non-scaling-stroke"
        return attrs

    def stroke_channels(
        self,
        node: Node,
        target: Element,
        color_attr: str,
        color_path: str,
        width_path: str,
        dash_path: str | None = None,
    ) -> None:
        if self.is_animated(node, color_path):

            def color_track(n: Any, c: Camera2D) -> str:
                v = getattr(n, color_path)
                return "none" if v is None else _hex(v)

            def alpha_track(n: Any, c: Camera2D) -> str:
                v = getattr(n, color_path)
                return self.fmt(0.0 if v is None else v.a)

            self.channels.append(
                Channel(
                    node,
                    (color_path,),
                    [
                        Track(target, color_attr, color_track),
                        Track(target, f"{color_attr}-opacity", alpha_track),
                    ],
                    optional=(color_path,),
                )
            )
        if self.is_animated(node, width_path):
            self.channels.append(
                Channel(
                    node,
                    (width_path,),
                    [Track(target, "stroke-width", lambda n, c: self.fmt(getattr(n, width_path)))],
                )
            )
        if dash_path and self.is_animated(node, dash_path):
            self.channels.append(
                Channel(
                    node,
                    (dash_path,),
                    [
                        Track(
                            target,
                            "stroke-dasharray",
                            lambda n, c: (
                                " ".join(self.fmt(d) for d in getattr(n, dash_path)) or "none"
                            ),
                        )
                    ],
                )
            )

    def emit_point(self, node: Point2D, overlay: bool) -> Element:
        sid = self.element_id(node)
        attrs = self.base_attrs(node, sid)
        attrs["transform"] = f"translate({self.fmt(node.position.x)} {self.fmt(node.position.y)})"
        g = Element("g", attrs)
        sym_attrs: dict[str, str] = {"d": _SYMBOLS[node.symbol]}
        _paint(sym_attrs, "fill", node.color)
        sym_attrs.update(self.stroke_attrs(node.stroke, node.stroke_width, None, "miter", ()))
        cam = self.snapshot.camera
        sym_attrs["transform"] = f"scale({self.point_scale(node, cam, overlay)})"
        sym = g.add(Element("path", sym_attrs))
        self.common_channels(node, g)
        if self.is_animated(node, "position"):
            self.channels.append(
                Channel(
                    node,
                    ("position",),
                    [
                        Track(
                            g,
                            "transform",
                            lambda n, c: f"{self.fmt(n.position.x)} {self.fmt(n.position.y)}",
                            transform="translate",
                        )
                    ],
                )
            )
        zoom_animated = (not overlay) and any(
            r.node_id == self.snapshot.camera.id for r in self.animated
        )
        if self.is_animated(node, "size") or zoom_animated:
            self.channels.append(
                Channel(
                    node,
                    ("size",),
                    [
                        Track(
                            sym,
                            "transform",
                            lambda n, c: self.point_scale(n, c, overlay),
                            transform="scale",
                        )
                    ],
                    uses_camera=not overlay,
                )
            )
        if self.is_animated(node, "symbol"):
            self.channels.append(
                Channel(
                    node,
                    ("symbol",),
                    [Track(sym, "d", lambda n, c: _SYMBOLS[n.symbol])],
                    discrete=True,
                )
            )
        if self.is_animated(node, "color"):
            self.channels.append(
                Channel(
                    node,
                    ("color",),
                    [
                        Track(sym, "fill", lambda n, c: _hex(n.color)),
                        Track(sym, "fill-opacity", lambda n, c: self.fmt(n.color.a)),
                    ],
                )
            )
        self.stroke_channels(node, sym, "stroke", "stroke", "stroke_width")
        return g

    def line_d(self, node: Line2D) -> str:
        end = node.start + (node.end - node.start) * node.draw_progress
        return f"M{self.fmt(node.start.x)} {self.fmt(node.start.y)}L{self.fmt(end.x)} {self.fmt(end.y)}"

    def path_d(self, path: Path2D) -> str:
        return path.to_svg(self.settings.precision)

    def emit_line(self, node: Line2D) -> Element:
        sid = self.element_id(node)
        attrs = self.base_attrs(node, sid)
        attrs["d"] = self.line_d(node)
        attrs["fill"] = "none"
        attrs.update(self.stroke_attrs(node.color, node.width, node.cap, node.join, node.dash))
        el = Element("path", attrs)
        self.common_channels(node, el)
        if any(self.is_animated(node, p) for p in ("start", "end", "draw_progress")):
            self.channels.append(
                Channel(
                    node,
                    ("start", "end", "draw_progress"),
                    [Track(el, "d", lambda n, c: self.line_d(n))],
                )
            )
        self._style_channels(node, el)
        return el

    def _style_channels(self, node: Any, el: Element) -> None:
        if self.is_animated(node, "color"):
            self.channels.append(
                Channel(
                    node,
                    ("color",),
                    [
                        Track(el, "stroke", lambda n, c: _hex(n.color)),
                        Track(el, "stroke-opacity", lambda n, c: self.fmt(n.color.a)),
                    ],
                )
            )
        if self.is_animated(node, "width"):
            self.channels.append(
                Channel(
                    node, ("width",), [Track(el, "stroke-width", lambda n, c: self.fmt(n.width))]
                )
            )
        for p, attr in (("cap", "stroke-linecap"), ("join", "stroke-linejoin")):
            if self.is_animated(node, p):
                self.channels.append(
                    Channel(node, (p,), [Track(el, attr, self._getter(p))], discrete=True)
                )
        if self.is_animated(node, "dash"):
            self.channels.append(
                Channel(
                    node,
                    ("dash",),
                    [
                        Track(
                            el,
                            "stroke-dasharray",
                            lambda n, c: " ".join(self.fmt(d) for d in n.dash) or "none",
                        )
                    ],
                )
            )

    def emit_path(self, node: PathNode2D) -> Element:
        sid = self.element_id(node)
        attrs = self.base_attrs(node, sid)
        trimmed = self.is_animated(node, "draw_progress") or node.draw_progress < 1.0
        if trimmed:
            self.warnings.append(
                f"{node.id}: draw_progress exported as an explicit-close path (closing joins lost)"
            )

        def d_of(n: PathNode2D) -> str:
            return self.path_d(n.path.trimmed(n.draw_progress) if trimmed else n.path)

        attrs["d"] = d_of(node)
        attrs["fill"] = "none"
        attrs.update(self.stroke_attrs(node.color, node.width, node.cap, node.join, node.dash))
        el = Element("path", attrs)
        self.common_channels(node, el)
        if self.is_animated(node, "path") or self.is_animated(node, "draw_progress"):
            self.channels.append(
                Channel(
                    node,
                    ("path", "draw_progress"),
                    [Track(el, "d", lambda n, c: d_of(n))],
                    linear=not trimmed,
                )
            )
        self._style_channels(node, el)
        return el

    def emit_shape(self, node: Shape2D) -> Element:
        sid = self.element_id(node)
        attrs = self.base_attrs(node, sid)
        attrs["d"] = self.path_d(node.path)
        _paint(attrs, "fill", node.fill)
        if node.fill_rule != "nonzero":
            attrs["fill-rule"] = node.fill_rule
        attrs.update(self.stroke_attrs(node.stroke, node.stroke_width, None, node.join, node.dash))
        el = Element("path", attrs)
        self.common_channels(node, el)
        if self.is_animated(node, "path"):
            self.channels.append(
                Channel(node, ("path",), [Track(el, "d", lambda n, c: self.path_d(n.path))])
            )
        if self.is_animated(node, "fill"):

            def fill_color(n: Any, c: Camera2D) -> str:
                return "none" if n.fill is None else _hex(n.fill)

            def fill_alpha(n: Any, c: Camera2D) -> str:
                return self.fmt(0.0 if n.fill is None else n.fill.a)

            self.channels.append(
                Channel(
                    node,
                    ("fill",),
                    [Track(el, "fill", fill_color), Track(el, "fill-opacity", fill_alpha)],
                    optional=("fill",),
                )
            )
        if self.is_animated(node, "fill_rule"):
            self.channels.append(
                Channel(
                    node,
                    ("fill_rule",),
                    [Track(el, "fill-rule", lambda n, c: n.fill_rule)],
                    discrete=True,
                )
            )
        self.stroke_channels(node, el, "stroke", "stroke", "stroke_width", "dash")
        if self.is_animated(node, "join"):
            self.channels.append(
                Channel(
                    node,
                    ("join",),
                    [Track(el, "stroke-linejoin", lambda n, c: n.join)],
                    discrete=True,
                )
            )
        return el

    def _transform_layers(
        self, node: Any, outer: Element, tf_of: Callable[[Any], Transform2D], path: str
    ) -> Element:
        """Nest translate/rotate/scale/pivot layers for a Transform2D property; returns innermost."""
        t = tf_of(node)
        animated = self.is_animated(node, path)
        if not animated:
            if not t.is_identity:
                outer.attrs["transform"] = self.transform_string(t)
            return outer
        layer_t = outer.add(Element("g", {"data-kk-layer": "translate"}))
        layer_r = layer_t.add(Element("g", {"data-kk-layer": "rotate"}))
        layer_s = layer_r.add(Element("g", {"data-kk-layer": "scale"}))
        layer_p = layer_s.add(Element("g", {"data-kk-layer": "pivot"}))
        layer_t.set(
            "transform",
            f"translate({self.fmt(t.translate.x + t.pivot.x)} {self.fmt(t.translate.y + t.pivot.y)})",
        )
        layer_r.set("transform", f"rotate({self.fmt(math.degrees(t.rotation))})")
        layer_s.set("transform", f"scale({self.fmt(t.scale.x)} {self.fmt(t.scale.y)})")
        layer_p.set("transform", f"translate({self.fmt(-t.pivot.x)} {self.fmt(-t.pivot.y)})")
        paths = (path,)

        def tr(n: Any) -> Transform2D:
            return tf_of(n)

        self.channels.append(
            Channel(
                node,
                paths,
                [
                    Track(
                        layer_t,
                        "transform",
                        lambda n, c: (
                            f"{self.fmt(tr(n).translate.x + tr(n).pivot.x)} "
                            f"{self.fmt(tr(n).translate.y + tr(n).pivot.y)}"
                        ),
                        transform="translate",
                    ),
                    Track(
                        layer_r,
                        "transform",
                        lambda n, c: self.fmt(math.degrees(tr(n).rotation)),
                        transform="rotate",
                    ),
                    Track(
                        layer_s,
                        "transform",
                        lambda n, c: f"{self.fmt(tr(n).scale.x)} {self.fmt(tr(n).scale.y)}",
                        transform="scale",
                    ),
                    Track(
                        layer_p,
                        "transform",
                        lambda n, c: f"{self.fmt(-tr(n).pivot.x)} {self.fmt(-tr(n).pivot.y)}",
                        transform="translate",
                    ),
                ],
            )
        )
        return layer_p

    def transform_string(self, t: Transform2D) -> str:
        parts = []
        tx, ty = t.translate.x + t.pivot.x, t.translate.y + t.pivot.y
        if tx or ty:
            parts.append(f"translate({self.fmt(tx)} {self.fmt(ty)})")
        if t.rotation:
            parts.append(f"rotate({self.fmt(math.degrees(t.rotation))})")
        if t.scale != Vec2(1.0, 1.0):
            parts.append(f"scale({self.fmt(t.scale.x)} {self.fmt(t.scale.y)})")
        if t.pivot != Vec2(0.0, 0.0):
            parts.append(f"translate({self.fmt(-t.pivot.x)} {self.fmt(-t.pivot.y)})")
        return " ".join(parts)

    def emit_group(self, node: Group2D, overlay: bool) -> Element:
        sid = self.element_id(node)
        outer = Element("g", self.base_attrs(node, sid))
        inner = self._transform_layers(node, outer, lambda n: n.transform, "transform")
        if node.clip is not None:
            if self.is_animated(node, "clip"):
                raise CapabilityError(
                    f"{node.id}: animating clip bounds is not supported by the vector renderer",
                    missing=("feature:clip-animation",),
                )
            cid = svg_id(f"clip-{node.id}", self.ids)
            c = self.defs.add(Element("clipPath", {"id": cid}))
            lo, hi = node.clip.min, node.clip.max
            c.add(
                Element(
                    "rect",
                    {
                        "x": self.fmt(lo.x),
                        "y": self.fmt(lo.y),
                        "width": self.fmt(hi.x - lo.x),
                        "height": self.fmt(hi.y - lo.y),
                    },
                )
            )
            inner.set("clip-path", f"url(#{cid})")
        self.common_channels(node, outer)
        for child in self.ordered(node.children):
            el = self.emit(child, overlay)
            if el is not None:
                inner.add(el)
        return outer

    def emit_text(self, node: Text2D, overlay: bool) -> Element:
        sid = self.element_id(node)
        attrs = self.base_attrs(node, sid)
        attrs["role"] = "img"
        attrs["aria-label"] = node.asset.text
        _paint(attrs, "fill", node.color)
        outer = Element("g", attrs)
        sign = -1 if overlay else 1
        pos = f"translate({self.fmt(node.position.x)} {self.fmt(node.position.y)})"
        lt = outer.add(Element("g", {"transform": pos}))
        rot = f"rotate({self.fmt(math.degrees(node.rotation))})"
        lr = lt.add(Element("g", {"transform": rot}))
        scl = f"scale({self.fmt(node.scale)} {self.fmt(node.scale * sign)})"
        ls = lr.add(Element("g", {"transform": scl}))
        for glyph in node.asset.glyphs:
            ls.add(Element("path", {"d": self.path_d(glyph.outline)}))
        for font in node.asset.fonts:
            self.fonts[(font.family, font.weight, font.style)] = font
        self.common_channels(node, outer)
        if self.is_animated(node, "position"):
            self.channels.append(
                Channel(
                    node,
                    ("position",),
                    [
                        Track(
                            lt,
                            "transform",
                            lambda n, c: f"{self.fmt(n.position.x)} {self.fmt(n.position.y)}",
                            transform="translate",
                        )
                    ],
                )
            )
        if self.is_animated(node, "rotation"):
            self.channels.append(
                Channel(
                    node,
                    ("rotation",),
                    [
                        Track(
                            lr,
                            "transform",
                            lambda n, c: self.fmt(math.degrees(n.rotation)),
                            transform="rotate",
                        )
                    ],
                )
            )
        if self.is_animated(node, "scale"):
            self.channels.append(
                Channel(
                    node,
                    ("scale",),
                    [
                        Track(
                            ls,
                            "transform",
                            lambda n, c: f"{self.fmt(n.scale)} {self.fmt(n.scale * sign)}",
                            transform="scale",
                        )
                    ],
                )
            )
        if self.is_animated(node, "color"):
            self.channels.append(
                Channel(
                    node,
                    ("color",),
                    [
                        Track(outer, "fill", lambda n, c: _hex(n.color)),
                        Track(outer, "fill-opacity", lambda n, c: self.fmt(n.color.a)),
                    ],
                )
            )
        return outer

    def ordered(self, nodes: tuple[Node, ...]) -> list[Node]:
        for n in nodes:
            if self.is_animated(n, "z"):
                raise CapabilityError(
                    f"{n.id}: animating z-order is not supported by the vector renderer; "
                    "animate opacity instead",
                    missing=("feature:z-animation",),
                )
        return [n for _, n in sorted(enumerate(nodes), key=lambda p: (p[1].z, p[0]))]

    def apply_semantics(self, node: Node, el: Element) -> None:
        sem = node.semantics
        if sem is None or sem.is_empty:
            return
        if sem.hidden:
            el.set("aria-hidden", "true")
            el.set("role", "presentation")
            return
        if sem.role:
            el.set("role", sem.role)
        if sem.label:
            el.set("aria-label", sem.label)
        if sem.reading_order is not None:
            el.set("data-kk-order", str(sem.reading_order))
        extra: list[Element] = []
        if sem.label:
            extra.append(Element("title", text=sem.label))
        if sem.description:
            extra.append(Element("desc", text=sem.description))
        el.children[0:0] = extra

    def emit(self, node: Node, overlay: bool) -> Element | None:
        el = self._emit(node, overlay)
        if el is not None:
            self.apply_semantics(node, el)
        return el

    def _emit(self, node: Node, overlay: bool) -> Element | None:
        if isinstance(node, Point2D):
            return self.emit_point(node, overlay)
        if isinstance(node, Line2D):
            return self.emit_line(node)
        if isinstance(node, PathNode2D):
            return self.emit_path(node)
        if isinstance(node, Shape2D):
            return self.emit_shape(node)
        if isinstance(node, Group2D):
            return self.emit_group(node, overlay)
        if isinstance(node, Text2D):
            return self.emit_text(node, overlay)
        raise CapabilityError(
            f"the vector renderer has no mapping for {type(node).__name__}",
            missing=(f"geometry:{node.kind}",),
        )

    # ---------------------------------------------------------------- camera
    def world_group(self) -> tuple[Element, Element]:
        """The (outermost, innermost) elements of the world transform stack."""
        cam = self.snapshot.camera
        assert isinstance(cam, Camera2D)
        assert self.layout is not None
        lay = self.layout
        if not any(r.node_id == cam.id for r in self.animated):
            m = lay.world_to_pixel(cam).m
            matrix = " ".join(self.fmt(v) for v in (m[0], m[3], m[1], m[4], m[2], m[5]))
            world = Element("g", {"id": "world", "transform": f"matrix({matrix})"})
            return world, world
        vp = lay.viewport
        cx = vp.margins.left + vp.plot_width / 2.0
        cy = vp.margins.top + vp.plot_height / 2.0
        top = Element(
            "g", {"id": "world", "transform": f"translate({self.fmt(cx)} {self.fmt(cy)})"}
        )
        zoom = top.add(Element("g", {"data-kk-layer": "zoom"}))
        pan = zoom.add(Element("g", {"data-kk-layer": "pan"}))

        def window(c: Camera2D) -> tuple[float, Vec2]:
            view = LayoutResultView(lay, c)
            return view.scale, view.center

        s, ctr = window(cam)
        zoom.set("transform", f"scale({self.fmt(s)} {self.fmt(-s)})")
        pan.set("transform", f"translate({self.fmt(-ctr.x)} {self.fmt(-ctr.y)})")
        self.channels.append(
            Channel(
                cam,
                ("view", "pan", "zoom"),
                [
                    Track(
                        zoom,
                        "transform",
                        lambda n, c: f"{self.fmt(window(n)[0])} {self.fmt(-window(n)[0])}",
                        transform="scale",
                    ),
                    Track(
                        pan,
                        "transform",
                        lambda n, c: f"{self.fmt(-window(n)[1].x)} {self.fmt(-window(n)[1].y)}",
                        transform="translate",
                    ),
                ],
                linear=False,
            )
        )
        return top, pan

    def build(self) -> SvgDocument:
        st = self.settings
        w, h = st.width, st.height
        root = Element(
            "svg",
            {
                "xmlns": SVG_NS,
                "width": self.fmt(w),
                "height": self.fmt(h),
                "viewBox": f"0 0 {self.fmt(w)} {self.fmt(h)}",
                "role": "img",
            },
        )
        info = self.animation.accessibility
        title = st.title or (info.title if info else None)
        description = st.description or (info.description if info else None)
        if info is not None:
            root.set("lang", info.lang)
        if title:
            title_id = svg_id("kk-title", self.ids)
            root.add(Element("title", {"id": title_id}, text=title))
            root.set("aria-labelledby", title_id)
        if description:
            desc_id = svg_id("kk-desc", self.ids)
            root.add(Element("desc", {"id": desc_id}, text=description))
            root.set("aria-describedby", desc_id)
        defs_index = len(root.children)
        if st.background is not None:
            attrs = {"id": "background", "width": "100%", "height": "100%"}
            _paint(attrs, "fill", Color.parse(st.background))
            root.add(Element("rect", attrs))
        if self.is3d:
            top = inner = Element("g", {"id": "world"})
            ProjectedWorld(self).build(inner)
            root.add(top)
        else:
            top, inner = self.world_group()
            root.add(top)
            for node in self.ordered(self.snapshot.nodes):
                el = self.emit(node, False)
                if el is not None:
                    inner.add(el)
        overlay = Element("g", {"id": "overlay"})
        for node in self.ordered(self.snapshot.overlay):
            el = self.emit(node, True)
            if el is not None:
                overlay.add(el)
        if overlay.children:
            root.add(overlay)
        self.encode_all()
        unconsumed = [r for r in self.animated if r not in self.consumed]
        if unconsumed:
            names = ", ".join(sorted(str(r) for r in unconsumed))
            raise CapabilityError(
                f"the vector renderer cannot animate: {names}",
                missing=("feature:property-animation",),
            )
        if self.fonts and st.embed_fonts:
            self.defs.children.insert(
                0, Element("style", {"type": "text/css"}, text=self.font_css())
            )
        if self.defs.children:
            root.children.insert(defs_index, self.defs)
        rm = st.reduced_motion
        if rm == "auto":
            rm = info.reduced_motion if info else ReducedMotion()
        if rm is not None and self.D > 0 and self.count > 0:
            rep = rm.representative_time(self.D)
            js = (
                "(function(){var s=document.currentScript.ownerSVGElement;"
                'if(window.matchMedia&&matchMedia("(prefers-reduced-motion: reduce)").matches'
                f"&&s.pauseAnimations){{s.pauseAnimations();s.setCurrentTime({rep:.6g});}}}})();"
            )
            root.add(Element("script", {"type": "application/ecmascript"}, text=js))
        text = '<?xml version="1.0" encoding="UTF-8"?>\n' + root.serialize(2 if st.pretty else None)
        return SvgDocument(
            root=root,
            text=text,
            width=w,
            height=h,
            duration=self.D,
            element_ids=dict(self.idmap),
            warnings=tuple(self.warnings),
            animation_count=self.count,
            fonts=tuple(sorted({f.family for f in self.fonts.values()})),
        )

    def font_css(self) -> str:
        rules = []
        for f in self.fonts.values():
            kind = {"opentype": "otf", "truetype": "ttf"}.get(f.format, f.format)
            data = base64.b64encode(f.data).decode("ascii")
            rules.append(
                f'@font-face{{font-family:"{f.family}";font-weight:{f.weight};'
                f"font-style:{f.style};src:url(data:font/{kind};base64,{data})}}"
            )
        return "".join(rules)

    def encode_all(self) -> None:
        for ch in self.channels:
            self.encode(ch)

    def plan(self, refs: list[PropertyRef[Any]], single_exact: bool) -> list[dict[str, Any]]:
        D = self.D
        bounds = {0.0, D}
        for r in refs:
            for seg in self.tl.segments(r):
                for t in (seg.start, seg.end):
                    if 0.0 <= t <= D:
                        bounds.add(t)
        pts = sorted(bounds)
        K = max(1, self.settings.samples)
        out: list[dict[str, Any]] = []
        for a, b in itertools.pairwise(pts):
            if b - a <= 1e-12:
                continue
            m = (a + b) / 2.0
            govs = [self.tl.governing(r, m) for r in refs]
            if all(g is None for g in govs):
                out.append(
                    {"a": a, "b": b, "times": [a, b], "spline": None, "constant": True, "m": m}
                )
                continue
            constant = any(
                g is not None
                and (
                    g.easing is step
                    or isinstance(self.registry.resolve(g.ref.value_type), StepInterpolator)
                )
                for g in govs
            )
            spline: tuple[float, float, float, float] | None = None
            times = [a, b]
            if constant:
                pass
            else:
                exact = False
                if single_exact and len(refs) == 1:
                    g = govs[0]
                    assert g is not None
                    if (
                        g.start == a
                        and g.end == b
                        and g.lo == 0.0
                        and g.hi == 1.0
                        and not g.flipped
                    ):
                        if g.easing is linear:
                            spline, exact = (0.0, 0.0, 1.0, 1.0), True
                        elif isinstance(g.easing, CubicBezier):
                            spline, exact = g.easing.control_points, True
                if not exact:
                    times = [a + (b - a) * k / K for k in range(K)] + [b]
            out.append(
                {"a": a, "b": b, "times": times, "spline": spline, "constant": constant, "m": m}
            )
        return out

    def state_at(
        self, ch: Channel, refs: list[PropertyRef[Any]], t: float, m: float
    ) -> tuple[Any, Camera2D]:
        values: dict[str, Any] = {}
        cam_values: dict[str, Any] = {}
        for r in refs:
            g = self.tl.governing(r, m)
            v = self.tl.initial(r) if g is None else g.value_at(t, self.registry)
            (cam_values if r.node_id == self.snapshot.camera.id else values)[r.path] = v
        node = ch.node
        if node.id == self.snapshot.camera.id:
            node_t = replace(node, **cam_values) if cam_values else node
            return node_t, node_t  # type: ignore[return-value]
        base = self.snapshot.get(node.id)
        node_t = base.replace(**values) if values else base
        cam = self.snapshot.camera
        assert isinstance(cam, Camera2D)
        return node_t, (cam.replace(**cam_values) if cam_values else cam)  # type: ignore[return-value]

    def encode(self, ch: Channel) -> None:
        cam_id = self.snapshot.camera.id
        node_refs = [r for r in self.animated if r.node_id == ch.node.id and r.path in ch.paths]
        cam_refs = (
            [r for r in self.animated if r.node_id == cam_id]
            if ch.uses_camera and ch.node.id != cam_id
            else []
        )
        refs = sorted(node_refs + cam_refs, key=str)
        if not refs:
            return
        self.consumed.update(refs)
        plan = self.plan(refs, single_exact=len(refs) == 1 and ch.linear and not cam_refs)
        for track in ch.tracks:
            knots: list[tuple[float, str]] = []
            splines: list[str] = []
            saw_none = False
            for iv in plan:
                if iv["constant"]:
                    node_t, cam_t = self.state_at(ch, refs, iv["a"], iv["m"])
                    v = track.value(node_t, cam_t)
                    vals = [(iv["a"], v), (iv["b"], v)]
                    saw_none = saw_none or any(getattr(node_t, p, 1) is None for p in ch.optional)
                else:
                    vals = []
                    for t in iv["times"]:
                        node_t, cam_t = self.state_at(ch, refs, t, iv["m"])
                        saw_none = saw_none or any(
                            getattr(node_t, p, 1) is None for p in ch.optional
                        )
                        vals.append((t, track.value(node_t, cam_t)))
                if len(vals) == 2:
                    inner = [" ".join(num(s, 5) for s in (iv["spline"] or (0.0, 0.0, 1.0, 1.0)))]
                else:
                    inner = ["0 0 1 1"] * (len(vals) - 1)
                if not knots:
                    knots.extend(vals)
                    splines.extend(inner)
                elif knots[-1][1] == vals[0][1]:
                    knots.extend(vals[1:])
                    splines.extend(inner)
                else:  # a jump: two knots at the same time
                    knots.extend(vals)
                    splines.append("0 0 1 1")
                    splines.extend(inner)
            if knots and self.D - knots[-1][0] < 1e-9:
                node_t, cam_t = self.state_at(ch, refs, self.D, self.D)
                saw_none = saw_none or any(getattr(node_t, p, 1) is None for p in ch.optional)
                final = track.value(node_t, cam_t)
                if final != knots[-1][1]:  # a step that completes exactly at the end
                    knots.append((self.D, final))
                    splines.append("0 0 1 1")
            if len(knots) < 2 or all(v == knots[0][1] for _, v in knots):
                continue  # nothing changes over time; the static attribute already says it
            self.count += 1
            if ch.discrete or saw_none:
                stepped: list[tuple[float, str]] = []
                for t, v in knots:
                    if stepped and abs(stepped[-1][0] - t) < 1e-12:
                        stepped[-1] = (t, v)
                    elif not stepped or stepped[-1][1] != v:
                        stepped.append((t, v))
                stepped[0] = (0.0, stepped[0][1])
                if len(stepped) < 2:
                    continue
                track.target.add(
                    self.animate_element(
                        track, [t for t, _ in stepped], [v for _, v in stepped], None, True
                    )
                )
            else:
                track.target.add(
                    self.animate_element(
                        track, [t for t, _ in knots], [v for _, v in knots], splines, False
                    )
                )

    def animate_element(
        self,
        track: Track,
        times: list[float],
        values: list[str],
        splines: list[str] | None,
        discrete: bool,
    ) -> Element:
        D = self.D
        tag = "animateTransform" if track.transform else "animate"
        el = Element(tag)
        el.set("attributeName", track.attribute)
        if track.transform:
            el.set("type", track.transform)
        el.set("begin", "0s")
        el.set("dur", f"{self.fmt(D)}s")
        el.set("values", ";".join(values))
        el.set("keyTimes", ";".join(num(t / D, 6) for t in times))
        if discrete:
            el.set("calcMode", "discrete")
        else:
            el.set("calcMode", "spline")
            el.set("keySplines", ";".join(splines or []))
        el.set("fill", "freeze")
        if self.settings.loop:
            el.set("repeatCount", "indefinite")
        return el


class LayoutResultView:
    """Scale and centre of the world window for one camera state."""

    def __init__(self, layout: LayoutResult, cam: Camera2D) -> None:
        base = cam.view if cam.view is not None else layout.base_view
        view = LayoutResult(layout.viewport, base)
        self.scale = view.scale(cam)
        self.center = view.window(cam).center
