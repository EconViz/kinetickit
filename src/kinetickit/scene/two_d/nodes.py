"""Precise 2D scene primitives.

Units: positions are world coordinates (+x right, +y up) unless the node lives in the overlay
(origin top-left, +y down, logical pixels). ``size`` and ``*width`` are logical pixels so
markers and strokes keep their thickness under camera zoom. Angles are radians.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar

from kinetickit.easing import Easing, linear
from kinetickit.errors import ConfigurationError
from kinetickit.geometry.two_d import Bounds2D, Matrix3, Path2D, Transform2D, Vec2
from kinetickit.interpolation import Color
from kinetickit.morph import PathMorph, normalize_paths
from kinetickit.scene.node import Node, prop
from kinetickit.scene.scene import SceneBase
from kinetickit.timeline import Motion
from kinetickit.tween import Tween
from kinetickit.typography import TextAssetLike

SYMBOLS = ("circle", "square", "diamond", "triangle", "cross", "plus")
CAPS = ("butt", "round", "square")
JOINS = ("miter", "round", "bevel")
FILL_RULES = ("nonzero", "evenodd")
INK = Color.parse("#1f2933")


def _choice(node: Node, name: str, allowed: tuple[str, ...]) -> None:
    value = getattr(node, name)
    if value not in allowed:
        raise ConfigurationError(f"{node.id}.{name} must be one of {allowed}, got {value!r}")


def _nonneg(node: Node, name: str) -> None:
    if getattr(node, name) < 0:
        raise ConfigurationError(f"{node.id}.{name} must be non-negative")


def _check_dash(node: Node, dash: tuple[float, ...]) -> None:
    if any(d < 0 for d in dash) or (dash and sum(dash) == 0):
        raise ConfigurationError(f"{node.id}.dash must be non-negative with a positive total")


def _morph_to(
    node: Node,
    target: Any,
    duration: float,
    easing: Easing,
    morph: PathMorph | None,
) -> Motion:
    """Morph ``node.path`` to ``target`` or fail loudly; never fall back silently."""
    end = Path2D.coerce(target)
    pair = normalize_paths(getattr(node, "path"), end, morph)
    if not pair.compatible:
        reasons = "; ".join(d.message for d in pair.diagnostics)
        raise ConfigurationError(
            f"cannot morph {node.id}.path automatically ({reasons}). Pass a PathMorph with an "
            "explicit normalizer, or cross-fade with a SceneTransition."
        )
    return Tween(node.ref("path"), pair.end, duration, easing, pair.start)


def _union(boxes: list[Bounds2D | None]) -> Bounds2D | None:
    out: Bounds2D | None = None
    for b in boxes:
        if b is not None:
            out = b if out is None else out.union(b)
    return out


@dataclass(frozen=True, slots=True, kw_only=True)
class Node2D(Node):
    dimension: ClassVar[int] = 2

    def bounds(self) -> Bounds2D | None:
        """World-space extent of the geometry, ignoring stroke width."""
        return None


@dataclass(frozen=True, slots=True, kw_only=True)
class Point2D(Node2D):
    kind: ClassVar[str] = "point"
    position: Vec2 = prop(Vec2(0.0, 0.0), Vec2)
    size: float = prop(4.0, float)
    symbol: str = prop("circle", str)
    color: Color = prop(INK, Color)
    stroke: Color | None = prop(None, Color, optional=True)
    stroke_width: float = prop(1.0, float)

    def _validate(self) -> None:
        _choice(self, "symbol", SYMBOLS)
        _nonneg(self, "size")
        _nonneg(self, "stroke_width")

    def bounds(self) -> Bounds2D | None:
        return Bounds2D(self.position, self.position)


@dataclass(frozen=True, slots=True, kw_only=True)
class _Stroked(Node2D):
    color: Color = prop(INK, Color)
    width: float = prop(2.0, float)
    cap: str = prop("round", str)
    join: str = prop("round", str)
    dash: tuple[float, ...] = prop((), tuple)
    draw_progress: float = prop(1.0, float)

    def _validate(self) -> None:
        _choice(self, "cap", CAPS)
        _choice(self, "join", JOINS)
        _nonneg(self, "width")
        _check_dash(self, self.dash)


@dataclass(frozen=True, slots=True, kw_only=True)
class Line2D(_Stroked):
    kind: ClassVar[str] = "line"
    start: Vec2 = prop(Vec2(0.0, 0.0), Vec2)
    end: Vec2 = prop(Vec2(1.0, 0.0), Vec2)

    def bounds(self) -> Bounds2D | None:
        return Bounds2D.of([self.start, self.end])

    def path(self) -> Path2D:
        return Path2D.polyline([self.start, self.end])


@dataclass(frozen=True, slots=True, kw_only=True)
class PathNode2D(_Stroked):
    """An open or closed stroked path."""

    kind: ClassVar[str] = "path"
    path: Path2D = prop(Path2D.polyline([(0, 0), (1, 0)]), Path2D)

    def bounds(self) -> Bounds2D | None:
        return self.path.bounds()

    def morph_to(
        self,
        target: Any,
        *,
        duration: float,
        easing: Easing = linear,
        morph: PathMorph | None = None,
    ) -> Motion:
        """Morph this node's path to ``target``; ``morph`` overrides every automatic choice."""
        return _morph_to(self, target, duration, easing, morph)

    @classmethod
    def polyline(cls, id: str, points: Any, *, closed: bool = False, **style: Any) -> PathNode2D:
        return cls(id=id, path=Path2D.polyline(points, closed=closed), **style)


@dataclass(frozen=True, slots=True, kw_only=True)
class Shape2D(Node2D):
    """A filled area made of one or more closed rings (holes via the fill rule)."""

    kind: ClassVar[str] = "shape"
    path: Path2D = prop(Path2D.rect(0, 0, 1, 1), Path2D)
    fill: Color | None = prop(INK, Color, optional=True)
    fill_rule: str = prop("nonzero", str)
    stroke: Color | None = prop(None, Color, optional=True)
    stroke_width: float = prop(1.0, float)
    join: str = prop("round", str)
    dash: tuple[float, ...] = prop((), tuple)

    def _validate(self) -> None:
        _choice(self, "fill_rule", FILL_RULES)
        _choice(self, "join", JOINS)
        _nonneg(self, "stroke_width")
        _check_dash(self, self.dash)

    def bounds(self) -> Bounds2D | None:
        return self.path.bounds()

    def morph_to(
        self,
        target: Any,
        *,
        duration: float,
        easing: Easing = linear,
        morph: PathMorph | None = None,
    ) -> Motion:
        """Morph this node's path to ``target``; ``morph`` overrides every automatic choice."""
        return _morph_to(self, target, duration, easing, morph)


@dataclass(frozen=True, slots=True, kw_only=True)
class Group2D(Node2D):
    """Composites children under a transform, opacity and optional rectangular clip."""

    kind: ClassVar[str] = "group"
    children: tuple[Node, ...] = field(default=())
    transform: Transform2D = prop(Transform2D(), Transform2D)
    clip: Bounds2D | None = prop(None, Bounds2D, optional=True)

    def __post_init__(self) -> None:
        object.__setattr__(self, "children", tuple(self.children))
        Node.__post_init__(self)

    def children_nodes(self) -> tuple[Node, ...]:
        return self.children

    def with_children(self, children: tuple[Node, ...]) -> Node:
        return self.replace(children=children)

    def bounds(self) -> Bounds2D | None:
        inner = _union([c.bounds() for c in self.children if isinstance(c, Node2D)])
        if inner is None:
            return None
        m: Matrix3 = self.transform.matrix()
        moved = Bounds2D.of(m.apply(c) for c in inner.corners())
        if self.clip is not None and moved is not None:
            clip = Bounds2D.of(m.apply(c) for c in self.clip.corners())
            assert clip is not None
            lo = Vec2(max(moved.min.x, clip.min.x), max(moved.min.y, clip.min.y))
            hi = Vec2(min(moved.max.x, clip.max.x), min(moved.max.y, clip.max.y))
            return Bounds2D(lo, Vec2(max(lo.x, hi.x), max(lo.y, hi.y)))
        return moved


@dataclass(frozen=True, slots=True, kw_only=True)
class Text2D(Node2D):
    """A pre-laid-out text asset placed, styled and animated as one object."""

    kind: ClassVar[str] = "text"
    asset: Any = None
    position: Vec2 = prop(Vec2(0.0, 0.0), Vec2)
    rotation: float = prop(0.0, float)
    scale: float = prop(1.0, float)
    color: Color = prop(INK, Color)

    def _validate(self) -> None:
        if not isinstance(self.asset, TextAssetLike):
            raise ConfigurationError(
                f"{self.id}.asset must be a text asset (text, glyphs, width, height, fonts)"
            )

    def bounds(self) -> Bounds2D | None:
        box = _union([g.outline.bounds() for g in self.asset.glyphs])
        if box is None:
            return None
        m = (
            Matrix3.translation(self.position)
            @ Matrix3.rotation(self.rotation)
            @ Matrix3.scaling(Vec2(self.scale, self.scale))
        )
        return Bounds2D.of(m.apply(c) for c in box.corners())


@dataclass(frozen=True, slots=True, kw_only=True)
class Camera2D(Node2D):
    """Pans and zooms the world view.

    ``view`` is an explicit world window; when ``None`` the layout fits the whole animation.
    ``pan`` shifts the view centre and ``zoom`` (>0) magnifies around it.
    """

    kind: ClassVar[str] = "camera"
    id: str = "camera"
    view: Bounds2D | None = prop(None, Bounds2D, optional=True)
    pan: Vec2 = prop(Vec2(0.0, 0.0), Vec2)
    zoom: float = prop(1.0, float)

    def _validate(self) -> None:
        if self.zoom <= 0:
            raise ConfigurationError("camera zoom must be positive")


class Scene2D(SceneBase):
    """A 2D scene: world nodes (y up), a screen-space overlay (y down) and a camera."""

    dimension = 2
    camera_type = Camera2D
    __slots__ = ()

    def bounds(self) -> Bounds2D | None:
        """Union of the world nodes' geometric bounds at this snapshot."""
        return _union([n.bounds() for n in self.nodes if isinstance(n, Node2D)])
