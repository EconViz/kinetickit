"""Private raster adapter. Nothing here appears in a public signature."""

from __future__ import annotations

import gc
from typing import Any

import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.patches import PathPatch, Polygon
from matplotlib.path import Path as MplPath

from kinetickit.geometry.two_d import Matrix3, Path2D, Transform2D, Vec2
from kinetickit.interpolation import Color
from kinetickit.renderers.projection import Projected, project_scene
from kinetickit.scene import (
    Camera2D,
    Group2D,
    Line2D,
    Node,
    PathNode2D,
    Point2D,
    Scene2D,
    Scene3D,
    Shape2D,
    Text2D,
)
from kinetickit.scene.two_d.symbols import SYMBOL_PATHS

_MOVE, _LINE, _CURVE3, _CURVE4, _CLOSE = (
    int(MplPath.MOVETO),
    int(MplPath.LINETO),
    int(MplPath.CURVE3),
    int(MplPath.CURVE4),
    int(MplPath.CLOSEPOLY),
)
_CODES = {"M": _MOVE, "L": _LINE, "Q": _CURVE3, "C": _CURVE4}
_PT = 72.0 / 96.0  # points per logical pixel
_CAP = {"butt": "butt", "round": "round", "square": "projecting"}


def _rgba(color: Color, opacity: float) -> tuple[float, float, float, float]:
    return (color.r, color.g, color.b, max(0.0, min(1.0, color.a * opacity)))


def _flatten(path: Path2D, matrix: Matrix3) -> tuple[list[tuple[float, float]], list[int]]:
    verts: list[tuple[float, float]] = []
    codes: list[int] = []
    start = (0.0, 0.0)
    for c in path.commands:
        if c.kind == "Z":
            verts.append(start)
            codes.append(_CLOSE)
            continue
        for p in c.points:
            q = matrix.apply(p)
            verts.append((q.x, q.y))
            codes.append(_CODES[c.kind])
        if c.kind == "M":
            start = verts[-1]
    return verts, codes


def _polygon_points(path: Path2D, matrix: Matrix3, n: int = 12) -> list[list[tuple[float, float]]]:
    """Each subpath flattened to a polyline (used for even-odd nesting tests)."""
    rings: list[list[tuple[float, float]]] = []
    for sub in path.subpaths():
        pts: list[tuple[float, float]] = []
        cur = Vec2(0.0, 0.0)
        for c in sub:
            if c.kind == "M":
                cur = c.points[0]
                pts.append((matrix.apply(cur).x, matrix.apply(cur).y))
            elif c.kind == "L":
                cur = c.points[0]
                q = matrix.apply(cur)
                pts.append((q.x, q.y))
            elif c.kind in ("Q", "C"):
                ctrl = [cur, *c.points]
                for k in range(1, n + 1):
                    t = k / n
                    pts.append(_bezier(ctrl, t, matrix))
                cur = c.points[-1]
        rings.append(pts)
    return rings


def _bezier(ctrl: list[Vec2], t: float, matrix: Matrix3) -> tuple[float, float]:
    pts = list(ctrl)
    while len(pts) > 1:
        pts = [pts[i] + (pts[i + 1] - pts[i]) * t for i in range(len(pts) - 1)]
    q = matrix.apply(pts[0])
    return (q.x, q.y)


def _inside(point: tuple[float, float], ring: list[tuple[float, float]]) -> bool:
    x, y = point
    hit = False
    for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1], strict=True):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            hit = not hit
    return hit


def _signed_area(ring: list[tuple[float, float]]) -> float:
    return 0.5 * sum(
        x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1], strict=True)
    )


def _evenodd_path(path: Path2D, matrix: Matrix3) -> MplPath:
    """Emulate the even-odd rule with non-zero winding by alternating ring orientation."""
    rings = _polygon_points(path, matrix)
    verts: list[tuple[float, float]] = []
    codes: list[int] = []
    for i, ring in enumerate(rings):
        if len(ring) < 3:
            continue
        depth = sum(
            1
            for j, other in enumerate(rings)
            if j != i and len(other) >= 3 and _inside(ring[0], other)
        )
        want_positive = depth % 2 == 0
        pts = ring if (_signed_area(ring) > 0) == want_positive else ring[::-1]
        verts.extend(pts + [pts[0]])
        codes.extend([_MOVE] + [_LINE] * (len(pts) - 1) + [_CLOSE])
    if not verts:
        return MplPath([(0.0, 0.0)], [MplPath.MOVETO])
    return MplPath(np.array(verts), np.array(codes, dtype=np.uint8))


def _mpl_path(path: Path2D, matrix: Matrix3) -> MplPath:
    verts, codes = _flatten(path, matrix)
    if not verts:
        return MplPath([(0.0, 0.0)], [MplPath.MOVETO])
    return MplPath(np.array(verts), np.array(codes, dtype=np.uint8))


class _Painter:
    def __init__(self, ax: Any, antialias: bool, scale: float) -> None:
        self.ax = ax
        self.aa = antialias
        self.scale = scale  # logical pixels per layout unit are already in the matrices
        self.order = 0

    def patch(self, mpl_path: MplPath, z: float, clip: Any, **kw: Any) -> None:
        self.order += 1
        p = PathPatch(mpl_path, antialiased=self.aa, zorder=z + self.order * 1e-6, **kw)
        if clip is not None:
            p.set_clip_path(clip)
        self.ax.add_patch(p)

    def stroke_kw(
        self,
        color: Color,
        opacity: float,
        width: float,
        cap: str,
        join: str,
        dash: tuple[float, ...],
    ) -> dict[str, Any]:
        kw: dict[str, Any] = {
            "fill": False,
            "edgecolor": _rgba(color, opacity),
            "linewidth": width * _PT,
            "capstyle": _CAP[cap],
            "joinstyle": join,
        }
        if dash:
            kw["linestyle"] = (0, [d * _PT / max(width * _PT, 1e-9) for d in dash])
        return kw

    def node(self, node: Node, m: Matrix3, opacity: float, clip: Any, overlay: bool) -> None:
        if not node.visible:
            return
        op = opacity * node.opacity
        if isinstance(node, Group2D):
            gm = m @ node.transform.matrix()
            child_clip = clip
            if node.clip is not None:
                corners = [gm.apply(c) for c in node.clip.corners()]
                poly = Polygon(
                    [(c.x, c.y) for c in corners], closed=True, transform=self.ax.transData
                )
                child_clip = poly
            for child in sorted(enumerate(node.children), key=lambda p: (p[1].z, p[0])):
                self.node(child[1], gm, op, child_clip, overlay)
            return
        z = node.z
        if isinstance(node, Point2D):
            self.point(node, m, op, clip, overlay)
        elif isinstance(node, Line2D):
            path = (
                node.path().trimmed(node.draw_progress) if node.draw_progress < 1 else node.path()
            )
            self.patch(
                _mpl_path(path, m),
                z,
                clip,
                **self.stroke_kw(node.color, op, node.width, node.cap, node.join, node.dash),
            )
        elif isinstance(node, PathNode2D):
            path = node.path.trimmed(node.draw_progress) if node.draw_progress < 1 else node.path
            self.patch(
                _mpl_path(path, m),
                z,
                clip,
                **self.stroke_kw(node.color, op, node.width, node.cap, node.join, node.dash),
            )
        elif isinstance(node, Shape2D):
            kw: dict[str, Any] = {"fill": node.fill is not None}
            if node.fill is not None:
                kw["facecolor"] = _rgba(node.fill, op)
            if node.stroke is not None:
                kw["edgecolor"] = _rgba(node.stroke, op)
                kw["linewidth"] = node.stroke_width * _PT
                kw["joinstyle"] = node.join
                if node.dash:
                    kw["linestyle"] = (
                        0,
                        [d * _PT / max(node.stroke_width * _PT, 1e-9) for d in node.dash],
                    )
            else:
                kw["linewidth"] = 0
                kw["edgecolor"] = "none"
            mp = (
                _evenodd_path(node.path, m)
                if node.fill_rule == "evenodd"
                else _mpl_path(node.path, m)
            )
            self.patch(mp, z, clip, **kw)
        elif isinstance(node, Text2D):
            tm = (
                m
                @ Transform2D(
                    translate=node.position,
                    rotation=node.rotation,
                    scale=Vec2(node.scale, node.scale),
                ).matrix()
            )
            if overlay:
                tm = tm @ Matrix3.scaling(Vec2(1.0, -1.0))
            for glyph in node.asset.glyphs:
                self.patch(
                    _mpl_path(glyph.outline, tm),
                    z,
                    clip,
                    facecolor=_rgba(node.color, op),
                    edgecolor="none",
                    linewidth=0,
                )

    def projected(self, prim: Projected, order: int) -> None:
        z = float(order)
        if prim.kind == "polygon":
            assert prim.fill is not None
            kw: dict[str, Any] = {"facecolor": prim.fill}
            if prim.stroke is not None:
                kw.update(
                    edgecolor=prim.stroke, linewidth=prim.stroke_width * _PT, joinstyle="round"
                )
            else:
                # hairline in the face color hides antialiasing seams between neighbours
                kw.update(edgecolor=prim.fill, linewidth=0.4 * _PT)
            pts = [tuple(p) for p in prim.points]
            self.patch(
                MplPath(np.array(pts + [pts[0]]), [_MOVE] + [_LINE] * (len(pts) - 1) + [_CLOSE]),
                z,
                None,
                **kw,
            )
        elif prim.kind == "polyline":
            assert prim.stroke is not None
            pts = [tuple(p) for p in prim.points]
            kw = {
                "fill": False,
                "edgecolor": prim.stroke,
                "linewidth": prim.stroke_width * _PT,
                "capstyle": "round",
                "joinstyle": "round",
            }
            if prim.dash:
                kw["linestyle"] = (
                    0,
                    [d * _PT / max(prim.stroke_width * _PT, 1e-9) for d in prim.dash],
                )
            self.patch(MplPath(np.array(pts), [_MOVE] + [_LINE] * (len(pts) - 1)), z, None, **kw)
        else:
            assert prim.fill is not None
            cx, cy = prim.points[0]
            pm = Matrix3.translation(Vec2(float(cx), float(cy))) @ Matrix3.scaling(
                Vec2(prim.size, -prim.size)
            )
            self.patch(
                _mpl_path(SYMBOL_PATHS[prim.symbol], pm),
                z,
                None,
                facecolor=prim.fill,
                edgecolor="none",
                linewidth=0,
            )

    def point(self, node: Point2D, m: Matrix3, op: float, clip: Any, overlay: bool) -> None:
        center = m.apply(node.position)
        k = node.size
        flip = 1.0 if overlay else -1.0  # pixel space is y-down; symbols are drawn y-up
        pm = Matrix3.translation(center) @ Matrix3.scaling(Vec2(k, k * flip))
        kw: dict[str, Any] = {"facecolor": _rgba(node.color, op)}
        if node.stroke is not None:
            kw["edgecolor"] = _rgba(node.stroke, op)
            kw["linewidth"] = node.stroke_width * _PT
        else:
            kw["edgecolor"] = "none"
            kw["linewidth"] = 0
        self.patch(_mpl_path(SYMBOL_PATHS[node.symbol], pm), node.z, clip, **kw)


def render_snapshot(
    snapshot: Scene2D | Scene3D, layout: Any, size: Any, settings: Any
) -> np.ndarray:
    """Render one snapshot to an RGBA ``uint8`` array of ``(pixel_height, pixel_width, 4)``."""
    fig = Figure(
        figsize=(size.logical_width / 96.0, size.logical_height / 96.0),
        dpi=size.dpi,
        facecolor=_rgba(Color.parse(settings.background), 1.0),
    )
    try:
        canvas = FigureCanvasAgg(fig)
        ax = fig.add_axes((0.0, 0.0, 1.0, 1.0))
        ax.set_xlim(0.0, size.logical_width)
        ax.set_ylim(size.logical_height, 0.0)
        ax.set_axis_off()
        painter = _Painter(ax, settings.antialias, 1.0)
        if isinstance(snapshot, Scene3D):
            prims = project_scene(snapshot, size.logical_width, size.logical_height)
            for i, prim in enumerate(prims):
                painter.projected(prim, i)
        else:
            cam = snapshot.camera
            assert isinstance(cam, Camera2D)
            world = layout.world_to_pixel(cam)
            for _, node in sorted(enumerate(snapshot.nodes), key=lambda p: (p[1].z, p[0])):
                painter.node(node, world, 1.0, None, False)
        for _, node in sorted(enumerate(snapshot.overlay), key=lambda p: (p[1].z, p[0])):
            painter.node(node, Matrix3.identity(), 1.0, None, True)
        canvas.draw()
        pixels: np.ndarray[Any, Any] = np.array(canvas.buffer_rgba(), dtype=np.uint8)
    finally:
        fig.clear()
        gc.collect()  # figures hold reference cycles; release this frame's backend objects now
    return pixels


__all__ = ["render_snapshot"]
