"""2D geometry values. Importing this package registers their interpolators."""

from __future__ import annotations

from kinetickit.geometry.two_d.bounds import Bounds2D, Bounds2DInterpolator
from kinetickit.geometry.two_d.matrix import Matrix3, Transform2D, Transform2DInterpolator
from kinetickit.geometry.two_d.path import Path2D, Path2DInterpolator, PathCommand
from kinetickit.geometry.two_d.vector import Vec2, Vec2Interpolator
from kinetickit.interpolation import DEFAULT_REGISTRY

DEFAULT_REGISTRY.register(Vec2, Vec2Interpolator())
DEFAULT_REGISTRY.register(Bounds2D, Bounds2DInterpolator())
DEFAULT_REGISTRY.register(Transform2D, Transform2DInterpolator())
DEFAULT_REGISTRY.register(Path2D, Path2DInterpolator())

__all__ = [
    "Bounds2D",
    "Matrix3",
    "Path2D",
    "PathCommand",
    "Transform2D",
    "Vec2",
]
