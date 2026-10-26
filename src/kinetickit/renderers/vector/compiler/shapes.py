"""Strokes and point, line, path and shape emitters."""

from __future__ import annotations

from typing import Any

from kinetickit.geometry.two_d import Path2D
from kinetickit.interpolation import Color
from kinetickit.renderers.vector.compiler.base import CompilerBase
from kinetickit.renderers.vector.compiler.model import (
    _SYMBOLS,
    Channel,
    Track,
    _hex,
    _paint,
)
from kinetickit.renderers.vector.svg import Element
from kinetickit.scene import (
    Camera2D,
    Line2D,
    Node,
    PathNode2D,
    Point2D,
    Shape2D,
)


class ShapeEmitters(CompilerBase):
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
