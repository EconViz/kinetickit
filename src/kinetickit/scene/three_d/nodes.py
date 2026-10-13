"""Precise 3D scene primitives. World space is right-handed: +x right, +y forward, +z up."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, ClassVar

import numpy as np

from kinetickit.easing import Easing, linear
from kinetickit.errors import ConfigurationError
from kinetickit.geometry.three_d import (
    Bounds3D,
    Matrix4,
    MeshData,
    SurfaceGrid,
    Transform3D,
    Vec3,
    Vec3Array,
)
from kinetickit.interpolation import Color
from kinetickit.morph import MeshMorph, SurfaceMorph
from kinetickit.scene.node import Node, prop
from kinetickit.scene.scene import SceneBase
from kinetickit.scene.two_d.nodes import CAPS, INK, JOINS, SYMBOLS, _check_dash, _choice, _nonneg
from kinetickit.styles import ColorScale, Material
from kinetickit.timeline import Motion

PROJECTIONS = ("perspective", "orthographic")


@dataclass(frozen=True, slots=True, kw_only=True)
class Node3D(Node):
    dimension: ClassVar[int] = 3

    def bounds(self) -> Bounds3D | None:
        """World-space extent of the geometry, ignoring stroke width and marker size."""
        return None


@dataclass(frozen=True, slots=True, kw_only=True)
class Point3D(Node3D):
    kind: ClassVar[str] = "point3d"
    position: Vec3 = prop(Vec3(0.0, 0.0, 0.0), Vec3)
    size: float = prop(4.0, float)
    symbol: str = prop("circle", str)
    color: Color = prop(INK, Color)

    def _validate(self) -> None:
        _choice(self, "symbol", SYMBOLS)
        _nonneg(self, "size")

    def bounds(self) -> Bounds3D | None:
        return Bounds3D(self.position, self.position)


@dataclass(frozen=True, slots=True, kw_only=True)
class PointCloud3D(Node3D):
    kind: ClassVar[str] = "pointcloud"
    points: Vec3Array = prop(Vec3Array(np.zeros((0, 3))), Vec3Array)
    size: float = prop(4.0, float)
    symbol: str = prop("circle", str)
    color: Color = prop(INK, Color)

    def _validate(self) -> None:
        _choice(self, "symbol", SYMBOLS)
        _nonneg(self, "size")

    def bounds(self) -> Bounds3D | None:
        return self.points.bounds()


@dataclass(frozen=True, slots=True, kw_only=True)
class _Stroked3D(Node3D):
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
class Line3D(_Stroked3D):
    kind: ClassVar[str] = "line3d"
    start: Vec3 = prop(Vec3(0.0, 0.0, 0.0), Vec3)
    end: Vec3 = prop(Vec3(1.0, 0.0, 0.0), Vec3)

    def bounds(self) -> Bounds3D | None:
        return Bounds3D.of([self.start, self.end])

    def vertices(self) -> Vec3Array:
        return Vec3Array(np.array([self.start.as_tuple(), self.end.as_tuple()]))


@dataclass(frozen=True, slots=True, kw_only=True)
class Polyline3D(_Stroked3D):
    kind: ClassVar[str] = "polyline3d"
    points: Vec3Array = prop(Vec3Array(np.zeros((2, 3))), Vec3Array)
    closed: bool = field(default=False)

    def _validate(self) -> None:
        _Stroked3D._validate(self)
        if len(self.points) < 2:
            raise ConfigurationError(f"{self.id}: a polyline needs at least two vertices")

    def bounds(self) -> Bounds3D | None:
        return self.points.bounds()

    def vertices(self) -> Vec3Array:
        return self.points


@dataclass(frozen=True, slots=True, kw_only=True)
class _Surfaced(Node3D):
    color: Color = prop(Color.parse("#3e7cb1"), Color)
    material: Material = prop(Material(), Material)
    edge_color: Color | None = prop(None, Color, optional=True)
    edge_width: float = prop(0.5, float)
    two_sided: bool = field(default=True)

    def _validate(self) -> None:
        _nonneg(self, "edge_width")


@dataclass(frozen=True, slots=True, kw_only=True)
class Mesh3D(_Surfaced):
    kind: ClassVar[str] = "mesh"
    mesh: MeshData = prop(MeshData(np.zeros((0, 3)), np.zeros((0, 3), dtype=np.int64)), MeshData)

    def bounds(self) -> Bounds3D | None:
        return self.mesh.bounds()

    def mesh_data(self) -> MeshData:
        return self.mesh

    def morph_to(
        self,
        target: MeshData,
        *,
        duration: float,
        easing: Easing = linear,
        morph: MeshMorph | None = None,
    ) -> Motion:
        """Morph to ``target``; incompatible topology needs an explicit ``MeshMorph``."""
        return self.morph_property("mesh", target, duration=duration, easing=easing, spec=morph)


@dataclass(frozen=True, slots=True, kw_only=True)
class Surface3D(_Surfaced):
    """A sampled surface (height field or parametric) drawn as a triangulated grid.

    ``colorscale`` colors faces by height over ``value_range`` (default: the grid's own z range).
    """

    kind: ClassVar[str] = "surface"
    grid: SurfaceGrid = prop(SurfaceGrid(np.zeros((2, 2, 3))), SurfaceGrid)
    colorscale: ColorScale | None = field(default=None)
    value_range: tuple[float, float] | None = field(default=None)

    @classmethod
    def height_field(cls, id: str, xs: Any, ys: Any, zs: Any, **kw: Any) -> Surface3D:
        return cls(id=id, grid=SurfaceGrid.from_height(xs, ys, zs), **kw)

    @classmethod
    def parametric(
        cls,
        id: str,
        fn: Any,
        u: tuple[float, float],
        v: tuple[float, float],
        nu: int,
        nv: int,
        **kw: Any,
    ) -> Surface3D:
        """Sample ``fn(u, v) -> (x, y, z)`` once; the node stores the immutable samples."""
        return cls(id=id, grid=SurfaceGrid.parametric(fn, u, v, nu, nv), **kw)

    def bounds(self) -> Bounds3D | None:
        return self.grid.bounds()

    def mesh_data(self) -> MeshData:
        return self.grid.to_mesh()

    def morph_to(
        self,
        target: SurfaceGrid,
        *,
        duration: float,
        easing: Easing = linear,
        morph: SurfaceMorph | None = None,
    ) -> Motion:
        """Morph to ``target``; a different sampling needs an explicit ``SurfaceMorph``."""
        return self.morph_property("grid", target, duration=duration, easing=easing, spec=morph)


@dataclass(frozen=True, slots=True, kw_only=True)
class DirectionalLight3D(Node3D):
    """Light travelling along ``direction`` (from the light toward the scene)."""

    kind: ClassVar[str] = "light"
    direction: Vec3 = prop(Vec3(-0.4, 0.6, -0.7), Vec3)
    color: Color = prop(Color.parse("#ffffff"), Color)
    intensity: float = prop(1.0, float)

    def _validate(self) -> None:
        if self.direction.length() == 0.0:
            raise ConfigurationError(f"{self.id}: a light direction cannot be zero")
        _nonneg(self, "intensity")


@dataclass(frozen=True, slots=True, kw_only=True)
class Group3D(Node3D):
    kind: ClassVar[str] = "group3d"
    children: tuple[Node, ...] = field(default=())
    transform: Transform3D = prop(Transform3D(), Transform3D)

    def __post_init__(self) -> None:
        object.__setattr__(self, "children", tuple(self.children))
        Node.__post_init__(self)

    def children_nodes(self) -> tuple[Node, ...]:
        return self.children

    def with_children(self, children: tuple[Node, ...]) -> Node:
        return self.replace(children=children)

    def bounds(self) -> Bounds3D | None:
        boxes = [c.bounds() for c in self.children if isinstance(c, Node3D)]
        inner = None
        for b in boxes:
            if b is not None:
                inner = b if inner is None else inner.union(b)
        if inner is None:
            return None
        m = self.transform.matrix()
        return Bounds3D.of(m.apply_point(c) for c in inner.corners())


@dataclass(frozen=True, slots=True, kw_only=True)
class Camera3D(Node3D):
    """Pose and projection. ``fov`` (radians, vertical) applies to perspective; ``ortho_height`` is
    the visible world height for orthographic projection."""

    kind: ClassVar[str] = "camera"
    id: str = "camera"
    position: Vec3 = prop(Vec3(5.0, -7.0, 4.0), Vec3)
    target: Vec3 = prop(Vec3(0.0, 0.0, 0.0), Vec3)
    up: Vec3 = prop(Vec3(0.0, 0.0, 1.0), Vec3)
    projection: str = prop("perspective", str)
    fov: float = prop(math.radians(40.0), float)
    ortho_height: float = prop(6.0, float)
    near: float = prop(0.1, float)
    far: float = prop(1000.0, float)

    def _validate(self) -> None:
        _choice(self, "projection", PROJECTIONS)
        if not 0.0 < self.fov < math.pi:
            raise ConfigurationError("camera fov must lie in (0, pi) radians")
        if self.ortho_height <= 0:
            raise ConfigurationError("camera ortho_height must be positive")
        if not 0.0 < self.near < self.far:
            raise ConfigurationError("camera needs 0 < near < far")
        Matrix4.look_at(self.position, self.target, self.up)  # validates the pose

    def view_matrix(self) -> Matrix4:
        return Matrix4.look_at(self.position, self.target, self.up)

    def projection_matrix(self, aspect: float) -> Matrix4:
        if self.projection == "perspective":
            return Matrix4.perspective(self.fov, aspect, self.near, self.far)
        return Matrix4.orthographic(self.ortho_height, aspect, self.near, self.far)

    @classmethod
    def fitting(
        cls,
        bounds: Bounds3D,
        *,
        direction: Any = (1.0, -1.2, 0.8),
        fov: float = math.radians(40.0),
        margin: float = 1.15,
        **kw: Any,
    ) -> Camera3D:
        """A perspective camera that sees the bounding sphere of ``bounds`` from ``direction``."""
        d = Vec3.coerce(direction).normalized()
        radius = max(bounds.radius(), 1e-9) * margin
        distance = radius / math.sin(fov / 2.0)
        center = bounds.center
        return cls(position=center + d * distance, target=center, fov=fov, **kw)


class Scene3D(SceneBase):
    """A 3D scene: world nodes, a 2D screen-space overlay (y down) and a 3D camera."""

    dimension = 3
    camera_type = Camera3D
    __slots__ = ()

    def bounds(self) -> Bounds3D | None:
        out: Bounds3D | None = None
        for n in self.nodes:
            if isinstance(n, Node3D):
                b = n.bounds()
                if b is not None:
                    out = b if out is None else out.union(b)
        return out

    def lights(self) -> tuple[DirectionalLight3D, ...]:
        return tuple(n for n in self.walk() if isinstance(n, DirectionalLight3D))
