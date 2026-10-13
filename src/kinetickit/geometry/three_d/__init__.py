"""3D geometry values. Importing this package registers their interpolators."""

from __future__ import annotations

from kinetickit.geometry.three_d.arrays import (
    MeshData,
    MeshDataInterpolator,
    SurfaceGrid,
    SurfaceGridInterpolator,
    Vec3Array,
    Vec3ArrayInterpolator,
)
from kinetickit.geometry.three_d.bounds import Bounds3D
from kinetickit.geometry.three_d.matrix import Matrix4, Transform3D, Transform3DInterpolator
from kinetickit.geometry.three_d.quaternion import Quaternion, QuaternionInterpolator
from kinetickit.geometry.three_d.vector import Vec3, Vec3Interpolator
from kinetickit.interpolation import DEFAULT_REGISTRY

DEFAULT_REGISTRY.register(Vec3, Vec3Interpolator())
DEFAULT_REGISTRY.register(Quaternion, QuaternionInterpolator())
DEFAULT_REGISTRY.register(Transform3D, Transform3DInterpolator())
DEFAULT_REGISTRY.register(Vec3Array, Vec3ArrayInterpolator())
DEFAULT_REGISTRY.register(MeshData, MeshDataInterpolator())
DEFAULT_REGISTRY.register(SurfaceGrid, SurfaceGridInterpolator())

__all__ = [
    "Bounds3D",
    "Matrix4",
    "MeshData",
    "Quaternion",
    "SurfaceGrid",
    "Transform3D",
    "Vec3",
    "Vec3Array",
]
