"""Projected 3D scenes as native SVG.

A 3D scene exported to vector is a time-varying 2D projection (it cannot be rotated afterwards).
Every projected primitive becomes an ordinary SVG element; its geometry and colors are animated by
sampling the projection at breakpoints and interpolating linearly in between. Painter's-algorithm
order is fixed at ``t = 0`` and recorded as a warning when anything moves.
"""

from __future__ import annotations

import itertools
from collections.abc import Iterator
from typing import TYPE_CHECKING

import numpy as np

from kinetickit.errors import CapabilityError
from kinetickit.interpolation import Color
from kinetickit.renderers.projection import Projected, project_scene
from kinetickit.renderers.vector.svg import Element, num, svg_id
from kinetickit.scene import Node, Scene3D
from kinetickit.scene.two_d.symbols import SYMBOL_PATHS

if TYPE_CHECKING:
    from kinetickit.renderers.vector.compiler import SvgCompiler

MAX_SAMPLES = 600


def _hex(rgba: tuple[float, float, float, float]) -> str:
    c = Color(*rgba)
    return "#" + c.to_hex()[1:7]


class ProjectedWorld:
    def __init__(self, compiler: SvgCompiler) -> None:
        self.c = compiler
        scene = compiler.snapshot
        assert isinstance(scene, Scene3D)
        overlay_ids = {n.id for root in scene.overlay for n in _walk(root)}
        self.refs = [r for r in compiler.animated if r.node_id not in overlay_ids]

    def times(self) -> list[float]:
        c = self.c
        if not self.refs:
            return [0.0]
        stamps = {0.0, c.D}
        for r in self.refs:
            for seg in c.tl.segments(r):
                for t in (seg.start, seg.end):
                    if 0.0 <= t <= c.D:
                        stamps.add(t)
        pts = sorted(stamps)
        k = max(1, c.settings.samples)
        out: list[float] = []
        for a, b in itertools.pairwise(pts):
            out.extend(a + (b - a) * i / k for i in range(k))
        out.append(pts[-1])
        if len(out) > MAX_SAMPLES:
            raise CapabilityError(
                f"projected 3D export needs {len(out)} samples (limit {MAX_SAMPLES}); "
                "lower SvgSettings.samples or shorten the animation",
                missing=("feature:dense-sampling",),
            )
        return out

    def build(self, parent: Element) -> None:
        c = self.c
        st = c.settings
        times = self.times()
        frames: list[dict[tuple[str, int], Projected]] = []
        order: list[tuple[str, int]] = []
        for i, t in enumerate(times):
            scene = c.animation.sample(t)
            prims = project_scene(scene, st.width, st.height)
            keyed = {p.key: p for p in prims}
            if i == 0:
                order = [p.key for p in prims]
            elif set(keyed) != set(frames[0]):
                gone = sorted(set(frames[0]) ^ set(keyed))[:3]
                raise CapabilityError(
                    "the projected primitives change over time (clipping against the camera's "
                    f"near/far planes, e.g. {gone}); widen near/far so nothing enters or leaves "
                    "the view, or export with the 'raster' or 'interactive' renderer",
                    missing=("feature:topology-change",),
                )
            frames.append(keyed)
        self.c.consumed.update(self.refs)
        if len(times) > 1:
            c.warnings.append(
                f"projected 3D animation sampled at {len(times)} times; painter's order is fixed at t=0"
            )
        sample_keys = [t / c.D if c.D else 0.0 for t in times]
        for key in order:
            series = [f[key] for f in frames]
            parent.add(self.element(key, series, sample_keys))
        # element ids are the first primitive of each node (stable, valid XML ids)
        for key in order:
            c.idmap.setdefault(key[0], c.idmap.get(f"{key[0]}#0", ""))

    # ------------------------------------------------------------------ elements
    def element(
        self, key: tuple[str, int], series: list[Projected], key_times: list[float]
    ) -> Element:
        c = self.c
        first = series[0]
        sid = svg_id(f"{key[0]}.{key[1]}", c.ids)
        c.idmap.setdefault(key[0], sid)
        c.idmap[f"{key[0]}#{key[1]}"] = sid
        attrs = {"id": sid, "data-kk-id": key[0], "data-kk-kind": first.kind}

        def d_of(p: Projected) -> str:
            pts = " ".join(f"{c.fmt(x)} {c.fmt(y)}" for x, y in p.points)
            if first.kind == "polygon":
                head, *rest = (f"{c.fmt(x)} {c.fmt(y)}" for x, y in p.points)
                return f"M{head}" + "".join(f"L{r}" for r in rest) + "Z"
            head, *rest = pts.split(" ")
            coords = [f"{c.fmt(x)} {c.fmt(y)}" for x, y in p.points]
            return "M" + coords[0] + "".join(f"L{r}" for r in coords[1:])

        el: Element
        if first.kind == "point":
            el = Element("g", attrs)
            sym = el.add(Element("path", {"d": " ".join(_symbol_d(first.symbol))}))
            assert first.fill is not None
            sym.set("fill", _hex(first.fill))
            if first.fill[3] != 1.0:
                sym.set("fill-opacity", num(first.fill[3], 4))
            sym.set("transform", f"scale({c.fmt(first.size)} {c.fmt(-first.size)})")
            el.set(
                "transform", f"translate({c.fmt(first.points[0][0])} {c.fmt(first.points[0][1])})"
            )
            self.animate(
                el,
                "transform",
                "translate",
                [f"{c.fmt(p.points[0][0])} {c.fmt(p.points[0][1])}" for p in series],
                key_times,
            )
            self.animate(sym, "fill", None, [_hex(p.fill) for p in series if p.fill], key_times)
            self.animate(
                sym, "fill-opacity", None, [num(p.fill[3], 4) for p in series if p.fill], key_times
            )
            self.animate(
                sym,
                "transform",
                "scale",
                [f"{c.fmt(p.size)} {c.fmt(-p.size)}" for p in series],
                key_times,
            )
            return el
        el = Element("path", attrs)
        el.set("d", d_of(first))
        if first.fill is not None:
            el.set("fill", _hex(first.fill))
            if first.fill[3] != 1.0:
                el.set("fill-opacity", num(first.fill[3], 4))
        else:
            el.set("fill", "none")
        if first.stroke is not None:
            el.set("stroke", _hex(first.stroke))
            if first.stroke[3] != 1.0:
                el.set("stroke-opacity", num(first.stroke[3], 4))
            el.set("stroke-width", c.fmt(first.stroke_width))
            el.set("stroke-linejoin", "round")
            if first.kind == "polyline":
                el.set("stroke-linecap", "round")
            if first.dash:
                el.set("stroke-dasharray", " ".join(c.fmt(v) for v in first.dash))
        self.animate(el, "d", None, [d_of(p) for p in series], key_times)
        if first.fill is not None:
            self.animate(el, "fill", None, [_hex(p.fill) for p in series if p.fill], key_times)
            self.animate(
                el, "fill-opacity", None, [num(p.fill[3], 4) for p in series if p.fill], key_times
            )
        if first.stroke is not None:
            self.animate(
                el, "stroke", None, [_hex(p.stroke) for p in series if p.stroke], key_times
            )
        return el

    def animate(
        self, el: Element, attr: str, kind: str | None, values: list[str], key_times: list[float]
    ) -> None:
        if len(values) != len(key_times) or all(v == values[0] for v in values):
            return
        # collapse runs of equal consecutive values (keep the first and last of each run)
        keep = [
            i
            for i in range(len(values))
            if i in (0, len(values) - 1) or values[i] != values[i - 1] or values[i] != values[i + 1]
        ]
        c = self.c
        a = Element("animateTransform" if kind else "animate")
        a.set("attributeName", attr)
        if kind:
            a.set("type", kind)
        a.set("begin", "0s")
        a.set("dur", f"{c.fmt(c.D)}s")
        a.set("values", ";".join(values[i] for i in keep))
        a.set("keyTimes", ";".join(num(key_times[i], 6) for i in keep))
        a.set("calcMode", "linear")
        a.set("fill", "freeze")
        if c.settings.loop:
            a.set("repeatCount", "indefinite")
        el.add(a)
        c.count += 1


def _symbol_d(symbol: str) -> list[str]:
    return [SYMBOL_PATHS[symbol].to_svg(4)]


def _walk(node: Node) -> Iterator[Node]:
    yield node
    for child in node.children_nodes():
        yield from _walk(child)


__all__ = ["ProjectedWorld", "np"]
