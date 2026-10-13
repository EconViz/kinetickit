"""Affine 3x3 matrices and decomposed 2D transforms."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from kinetickit.errors import ConfigurationError
from kinetickit.geometry.two_d.vector import Vec2


@dataclass(frozen=True, slots=True)
class Matrix3:
    """A row-major 3x3 matrix acting on column vectors ``(x, y, 1)``."""

    m: tuple[float, float, float, float, float, float, float, float, float]

    def __post_init__(self) -> None:
        if len(self.m) != 9 or not all(math.isfinite(v) for v in self.m):
            raise ConfigurationError("Matrix3 needs nine finite values")

    @classmethod
    def identity(cls) -> Matrix3:
        return cls((1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0))

    @classmethod
    def translation(cls, t: Vec2) -> Matrix3:
        return cls((1.0, 0.0, t.x, 0.0, 1.0, t.y, 0.0, 0.0, 1.0))

    @classmethod
    def scaling(cls, s: Vec2) -> Matrix3:
        return cls((s.x, 0.0, 0.0, 0.0, s.y, 0.0, 0.0, 0.0, 1.0))

    @classmethod
    def rotation(cls, radians: float) -> Matrix3:
        c, s = math.cos(radians), math.sin(radians)
        return cls((c, -s, 0.0, s, c, 0.0, 0.0, 0.0, 1.0))

    def __matmul__(self, other: Matrix3) -> Matrix3:
        a, b = self.m, other.m
        return Matrix3(
            tuple(  # type: ignore[arg-type]
                sum(a[3 * r + k] * b[3 * k + c] for k in range(3))
                for r in range(3)
                for c in range(3)
            )
        )

    def apply(self, p: Vec2) -> Vec2:
        m = self.m
        return Vec2(m[0] * p.x + m[1] * p.y + m[2], m[3] * p.x + m[4] * p.y + m[5])

    def determinant(self) -> float:
        m = self.m
        return m[0] * m[4] - m[1] * m[3]

    def inverse(self) -> Matrix3:
        det = self.determinant()
        if det == 0.0:
            raise ConfigurationError("singular matrix cannot be inverted")
        m = self.m
        a, b, c, d = m[4] / det, -m[1] / det, -m[3] / det, m[0] / det
        tx = -(a * m[2] + b * m[5])
        ty = -(c * m[2] + d * m[5])
        return Matrix3((a, b, tx, c, d, ty, 0.0, 0.0, 1.0))


@dataclass(frozen=True, slots=True)
class Transform2D:
    """Scale, then rotate, then translate (about an optional pivot).

    The matrix is ``T(translate) · T(pivot) · R(rotation) · S(scale) · T(-pivot)`` and angles are
    radians.
    """

    translate: Vec2 = Vec2(0.0, 0.0)
    rotation: float = 0.0
    scale: Vec2 = Vec2(1.0, 1.0)
    pivot: Vec2 = Vec2(0.0, 0.0)

    def __post_init__(self) -> None:
        object.__setattr__(self, "translate", Vec2.coerce(self.translate))
        object.__setattr__(self, "scale", _scale(self.scale))
        object.__setattr__(self, "pivot", Vec2.coerce(self.pivot))
        if not math.isfinite(self.rotation):
            raise ConfigurationError("rotation must be finite")
        object.__setattr__(self, "rotation", float(self.rotation))

    @classmethod
    def coerce(cls, value: Any) -> Transform2D:
        if isinstance(value, Transform2D):
            return value
        raise ConfigurationError(f"cannot interpret {value!r} as a Transform2D")

    @property
    def is_identity(self) -> bool:
        return self == Transform2D()

    def matrix(self) -> Matrix3:
        return (
            Matrix3.translation(self.translate)
            @ Matrix3.translation(self.pivot)
            @ Matrix3.rotation(self.rotation)
            @ Matrix3.scaling(self.scale)
            @ Matrix3.translation(-self.pivot)
        )

    def apply(self, p: Vec2) -> Vec2:
        return self.matrix().apply(p)


def _scale(value: Any) -> Vec2:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return Vec2(value, value)
    return Vec2.coerce(value)


class Transform2DInterpolator:
    """Component-wise interpolation of translate, rotation, scale and pivot."""

    def interpolate(self, start: Transform2D, end: Transform2D, progress: float) -> Transform2D:
        if progress == 0.0:
            return start
        if progress == 1.0:
            return end
        k = progress

        def lerp(a: float, b: float) -> float:
            return a + (b - a) * k

        def vec(a: Vec2, b: Vec2) -> Vec2:
            return Vec2(lerp(a.x, b.x), lerp(a.y, b.y))

        return Transform2D(
            vec(start.translate, end.translate),
            lerp(start.rotation, end.rotation),
            vec(start.scale, end.scale),
            vec(start.pivot, end.pivot),
        )
