"""Transforms, groups, text, ordering, semantics and node dispatch."""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

from kinetickit.errors import CapabilityError
from kinetickit.geometry.two_d import Transform2D, Vec2
from kinetickit.renderers.vector.compiler.model import (
    Channel,
    Track,
    _hex,
    _paint,
)
from kinetickit.renderers.vector.compiler.shapes import ShapeEmitters
from kinetickit.renderers.vector.svg import Element, svg_id
from kinetickit.scene import (
    Group2D,
    Line2D,
    Node,
    PathNode2D,
    Point2D,
    Shape2D,
    Text2D,
)


class StructureEmitters(ShapeEmitters):
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
