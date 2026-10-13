"""Immutable array-backed values: point lists, meshes and surface grids."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import numpy.typing as npt

from kinetickit.errors import ConfigurationError
from kinetickit.geometry.three_d.bounds import Bounds3D
from kinetickit.geometry.three_d.matrix import Matrix4
from kinetickit.geometry.three_d.vector import Vec3


def _frozen(a: npt.ArrayLike, shape_tail: tuple[int, ...], name: str, dtype: Any = float) -> Any:
    try:
        arr = np.array(a, dtype=dtype)  # a private copy
    except (TypeError, ValueError):
        raise ConfigurationError(f"{name} must be numeric") from None
    if arr.ndim != len(shape_tail) + 1 or arr.shape[1:] != shape_tail:
        raise ConfigurationError(f"{name} must have shape (N, {', '.join(map(str, shape_tail))})")
    if dtype is float and not np.isfinite(arr).all():
        raise ConfigurationError(f"{name} must be finite")
    arr.setflags(write=False)
    return arr


def _same(a: Any, b: Any) -> bool:
    return (a is None and b is None) or (
        a is not None and b is not None and a.shape == b.shape and bool(np.array_equal(a, b))
    )


def _key(a: Any) -> bytes:
    return b"" if a is None else a.tobytes()


@dataclass(frozen=True, eq=False)
class Vec3Array:
    """An immutable ``(N, 3)`` list of 3D points."""

    data: npt.NDArray[np.float64]

    def __post_init__(self) -> None:
        object.__setattr__(self, "data", _frozen(self.data, (3,), "points"))

    @classmethod
    def coerce(cls, value: Any) -> Vec3Array:
        return value if isinstance(value, Vec3Array) else cls(np.asarray(value, dtype=float))

    def __len__(self) -> int:
        return int(self.data.shape[0])

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Vec3Array) and _same(self.data, other.data)

    def __hash__(self) -> int:
        return hash(self.data.tobytes())

    def bounds(self) -> Bounds3D | None:
        if len(self) == 0:
            return None
        lo, hi = self.data.min(axis=0), self.data.max(axis=0)
        return Bounds3D(Vec3(*lo), Vec3(*hi))

    def transformed(self, matrix: Matrix4) -> Vec3Array:
        return Vec3Array(matrix.transform_points(self.data))


class Vec3ArrayInterpolator:
    def interpolate(self, start: Vec3Array, end: Vec3Array, progress: float) -> Vec3Array:
        if progress == 0.0:
            return start
        if progress == 1.0:
            return end
        if start.data.shape != end.data.shape:
            raise ConfigurationError(
                f"point lists differ in length ({len(start)} vs {len(end)}); resample them first"
            )
        return Vec3Array(start.data + (end.data - start.data) * progress)


@dataclass(frozen=True, eq=False)
class MeshData:
    """An indexed triangle mesh: ``(N, 3)`` vertices, ``(M, 3)`` faces, optional normals/colors.

    ``colors`` is ``(N, 4)`` RGBA in ``[0, 1]``. Normals are computed from the faces when absent
    (see :meth:`vertex_normals`).
    """

    vertices: npt.NDArray[np.float64]
    faces: npt.NDArray[np.int64]
    normals: npt.NDArray[np.float64] | None = None
    colors: npt.NDArray[np.float64] | None = None

    def __post_init__(self) -> None:
        v = _frozen(self.vertices, (3,), "vertices")
        f = _frozen(self.faces, (3,), "faces", dtype=np.int64)
        if len(f) and (f.min() < 0 or f.max() >= len(v)):
            raise ConfigurationError(
                f"face indices must lie in [0, {len(v) - 1}], got [{f.min()}, {f.max()}]"
            )
        n = None if self.normals is None else _frozen(self.normals, (3,), "normals")
        if n is not None and len(n) != len(v):
            raise ConfigurationError("normals need one row per vertex")
        c = None if self.colors is None else _frozen(self.colors, (4,), "colors")
        if c is not None:
            if len(c) != len(v):
                raise ConfigurationError("colors need one row per vertex")
            if c.size and (c.min() < 0.0 or c.max() > 1.0):
                raise ConfigurationError("mesh colors must lie in [0, 1]")
        object.__setattr__(self, "vertices", v)
        object.__setattr__(self, "faces", f)
        object.__setattr__(self, "normals", n)
        object.__setattr__(self, "colors", c)

    @classmethod
    def coerce(cls, value: Any) -> MeshData:
        if isinstance(value, MeshData):
            return value
        raise ConfigurationError(f"cannot interpret {type(value).__name__} as a mesh")

    @classmethod
    def from_quads(cls, vertices: npt.ArrayLike, quads: npt.ArrayLike, **kw: Any) -> MeshData:
        q = np.asarray(quads, dtype=np.int64)
        if q.ndim != 2 or q.shape[1] != 4:
            raise ConfigurationError("quads must have shape (M, 4)")
        tris = np.concatenate([q[:, [0, 1, 2]], q[:, [0, 2, 3]]], axis=0)
        return cls(np.asarray(vertices, dtype=float), tris, **kw)

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, MeshData)
            and _same(self.vertices, other.vertices)
            and _same(self.faces, other.faces)
            and _same(self.normals, other.normals)
            and _same(self.colors, other.colors)
        )

    def __hash__(self) -> int:
        return hash((_key(self.vertices), _key(self.faces), _key(self.normals), _key(self.colors)))

    # -- topology -----------------------------------------------------------------------
    @property
    def topology(self) -> tuple[int, int, bytes]:
        """Identity of the connectivity: two meshes morph directly only if this matches."""
        return (len(self.vertices), len(self.faces), self.faces.tobytes())

    def same_topology(self, other: MeshData) -> bool:
        return self.topology == other.topology

    def face_normals(self) -> npt.NDArray[np.float64]:
        v = self.vertices
        f = self.faces
        n: npt.NDArray[np.float64] = np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]])
        return n

    def face_areas(self) -> npt.NDArray[np.float64]:
        a: npt.NDArray[np.float64] = np.linalg.norm(self.face_normals(), axis=1) / 2.0
        return a

    def degenerate_faces(self, tolerance: float = 1e-12) -> tuple[int, ...]:
        """Indices of faces with (near-)zero area or repeated vertices."""
        repeated = (
            (self.faces[:, 0] == self.faces[:, 1])
            | (self.faces[:, 1] == self.faces[:, 2])
            | (self.faces[:, 0] == self.faces[:, 2])
        )
        flat = self.face_areas() <= tolerance
        return tuple(int(i) for i in np.nonzero(repeated | flat)[0])

    def vertex_normals(self) -> npt.NDArray[np.float64]:
        """Supplied normals, or area-weighted vertex normals computed from the faces."""
        if self.normals is not None:
            return self.normals
        acc = np.zeros_like(self.vertices)
        fn = self.face_normals()  # length = 2 * area, so this is area weighting
        for k in range(3):
            np.add.at(acc, self.faces[:, k], fn)
        lengths = np.linalg.norm(acc, axis=1, keepdims=True)
        out: npt.NDArray[np.float64] = acc / np.where(lengths == 0.0, 1.0, lengths)
        return out

    def bounds(self) -> Bounds3D | None:
        if len(self.vertices) == 0:
            return None
        return Bounds3D(Vec3(*self.vertices.min(axis=0)), Vec3(*self.vertices.max(axis=0)))

    def transformed(self, matrix: Matrix4) -> MeshData:
        normals = None
        if self.normals is not None:
            inv_t = np.linalg.inv(matrix.array()[:3, :3]).T
            raw = self.normals @ inv_t.T
            lengths = np.linalg.norm(raw, axis=1, keepdims=True)
            normals = raw / np.where(lengths == 0.0, 1.0, lengths)
        return MeshData(matrix.transform_points(self.vertices), self.faces, normals, self.colors)


class MeshDataInterpolator:
    """Interpolate meshes that share connectivity; anything else needs explicit resampling."""

    def interpolate(self, start: MeshData, end: MeshData, progress: float) -> MeshData:
        if progress == 0.0:
            return start
        if progress == 1.0:
            return end
        if not start.same_topology(end):
            raise ConfigurationError(
                "meshes have different topology; morph them with an explicit correspondence "
                "(kinetickit.morph) or cross-fade"
            )

        def lerp(a: Any, b: Any) -> Any:
            return a + (b - a) * progress

        normals = None
        if start.normals is not None and end.normals is not None:
            raw = lerp(start.normals, end.normals)
            lengths = np.linalg.norm(raw, axis=1, keepdims=True)
            normals = raw / np.where(lengths == 0.0, 1.0, lengths)
        colors = None
        if start.colors is not None and end.colors is not None:
            colors = np.clip(lerp(start.colors, end.colors), 0.0, 1.0)
        return MeshData(lerp(start.vertices, end.vertices), start.faces, normals, colors)


@dataclass(frozen=True, eq=False)
class SurfaceGrid:
    """A sampled surface: ``(ny, nx, 3)`` positions on a regular parameter grid."""

    points: npt.NDArray[np.float64]

    def __post_init__(self) -> None:
        try:
            arr = np.array(self.points, dtype=float)
        except (TypeError, ValueError):
            raise ConfigurationError("surface points must be numeric") from None
        if arr.ndim != 3 or arr.shape[2] != 3 or arr.shape[0] < 2 or arr.shape[1] < 2:
            raise ConfigurationError("a surface grid needs shape (ny >= 2, nx >= 2, 3)")
        if not np.isfinite(arr).all():
            raise ConfigurationError("surface points must be finite")
        arr.setflags(write=False)
        object.__setattr__(self, "points", arr)

    @classmethod
    def coerce(cls, value: Any) -> SurfaceGrid:
        return value if isinstance(value, SurfaceGrid) else cls(np.asarray(value, dtype=float))

    @classmethod
    def from_height(cls, xs: npt.ArrayLike, ys: npt.ArrayLike, zs: npt.ArrayLike) -> SurfaceGrid:
        """A height field ``z[j, i]`` over ``x[i]`` and ``y[j]``."""
        x, y, z = np.asarray(xs, float), np.asarray(ys, float), np.asarray(zs, float)
        if z.shape != (len(y), len(x)):
            raise ConfigurationError(f"z must have shape ({len(y)}, {len(x)}), got {z.shape}")
        gx, gy = np.meshgrid(x, y)
        return cls(np.stack([gx, gy, z], axis=-1))

    @classmethod
    def parametric(
        cls,
        fn: Any,
        u: tuple[float, float],
        v: tuple[float, float],
        nu: int,
        nv: int,
    ) -> SurfaceGrid:
        """Sample ``fn(u, v) -> (x, y, z)`` on an ``nv x nu`` grid (sampled once, then immutable)."""
        if nu < 2 or nv < 2:
            raise ConfigurationError("parametric surfaces need at least a 2x2 sampling")
        us, vs = np.linspace(u[0], u[1], nu), np.linspace(v[0], v[1], nv)
        pts = np.empty((nv, nu, 3))
        for j, vv in enumerate(vs):
            for i, uu in enumerate(us):
                pts[j, i] = fn(float(uu), float(vv))
        return cls(pts)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, SurfaceGrid) and _same(self.points, other.points)

    def __hash__(self) -> int:
        return hash(self.points.tobytes())

    @property
    def shape(self) -> tuple[int, int]:
        return (int(self.points.shape[0]), int(self.points.shape[1]))

    def to_mesh(self) -> MeshData:
        ny, nx = self.shape
        idx = np.arange(ny * nx).reshape(ny, nx)
        a, b, c, d = idx[:-1, :-1], idx[:-1, 1:], idx[1:, 1:], idx[1:, :-1]
        quads = np.stack([a.ravel(), b.ravel(), c.ravel(), d.ravel()], axis=1)
        return MeshData.from_quads(self.points.reshape(-1, 3), quads)

    def bounds(self) -> Bounds3D:
        flat = self.points.reshape(-1, 3)
        return Bounds3D(Vec3(*flat.min(axis=0)), Vec3(*flat.max(axis=0)))

    def transformed(self, matrix: Matrix4) -> SurfaceGrid:
        ny, nx = self.shape
        return SurfaceGrid(matrix.transform_points(self.points.reshape(-1, 3)).reshape(ny, nx, 3))


class SurfaceGridInterpolator:
    def interpolate(self, start: SurfaceGrid, end: SurfaceGrid, progress: float) -> SurfaceGrid:
        if progress == 0.0:
            return start
        if progress == 1.0:
            return end
        if start.shape != end.shape:
            raise ConfigurationError(
                f"surface grids differ in sampling {start.shape} vs {end.shape}; resample first"
            )
        return SurfaceGrid(start.points + (end.points - start.points) * progress)
