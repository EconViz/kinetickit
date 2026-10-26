"""SMIL planning and encoding of animated channels."""

from __future__ import annotations

import itertools
from dataclasses import replace
from typing import Any

from kinetickit.easing import CubicBezier, linear, step
from kinetickit.interpolation import StepInterpolator
from kinetickit.renderers.vector.compiler.base import CompilerBase
from kinetickit.renderers.vector.compiler.model import (
    Channel,
    Track,
)
from kinetickit.renderers.vector.svg import Element, num
from kinetickit.scene import (
    Camera2D,
)
from kinetickit.timeline import PropertyRef


class ChannelEncoder(CompilerBase):
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
