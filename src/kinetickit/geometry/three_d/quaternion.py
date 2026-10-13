"""Unit quaternions ``(w, x, y, z)`` with shortest-arc interpolation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from kinetickit.errors import ConfigurationError
from kinetickit.geometry.three_d.vector import Vec3


@dataclass(frozen=True, slots=True)
class Quaternion:
    """A rotation. Components are normalized on construction."""

    w: float = 1.0
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def __post_init__(self) -> None:
        comps = [float(self.w), float(self.x), float(self.y), float(self.z)]
        if not all(math.isfinite(c) for c in comps):
            raise ConfigurationError("quaternion components must be finite")
        n = math.sqrt(sum(c * c for c in comps))
        if n == 0.0:
            raise ConfigurationError("a quaternion cannot be all zeros")
        for name, c in zip(("w", "x", "y", "z"), comps, strict=True):
            object.__setattr__(self, name, c / n)

    @classmethod
    def coerce(cls, value: Any) -> Quaternion:
        if isinstance(value, Quaternion):
            return value
        try:
            w, x, y, z = value
        except (TypeError, ValueError):
            raise ConfigurationError(f"cannot interpret {value!r} as a quaternion") from None
        return cls(w, x, y, z)

    @classmethod
    def from_axis_angle(cls, axis: Any, radians: float) -> Quaternion:
        a = Vec3.coerce(axis).normalized()
        s = math.sin(radians / 2.0)
        return cls(math.cos(radians / 2.0), a.x * s, a.y * s, a.z * s)

    def conjugate(self) -> Quaternion:
        return Quaternion(self.w, -self.x, -self.y, -self.z)

    def __mul__(self, o: Quaternion) -> Quaternion:
        return Quaternion(
            self.w * o.w - self.x * o.x - self.y * o.y - self.z * o.z,
            self.w * o.x + self.x * o.w + self.y * o.z - self.z * o.y,
            self.w * o.y - self.x * o.z + self.y * o.w + self.z * o.x,
            self.w * o.z + self.x * o.y - self.y * o.x + self.z * o.w,
        )

    def rotate(self, v: Vec3) -> Vec3:
        # computed on raw components: normalizing a pure vector quaternion would distort it
        q = (self.w, self.x, self.y, self.z)
        r = _raw_mul(_raw_mul(q, (0.0, v.x, v.y, v.z)), (self.w, -self.x, -self.y, -self.z))
        return Vec3(r[1], r[2], r[3])

    def as_tuple(self) -> tuple[float, float, float, float]:
        return (self.w, self.x, self.y, self.z)

    def dot(self, o: Quaternion) -> float:
        return self.w * o.w + self.x * o.x + self.y * o.y + self.z * o.z


def _raw_mul(
    a: tuple[float, float, float, float], b: tuple[float, float, float, float]
) -> tuple[float, float, float, float]:
    return (
        a[0] * b[0] - a[1] * b[1] - a[2] * b[2] - a[3] * b[3],
        a[0] * b[1] + a[1] * b[0] + a[2] * b[3] - a[3] * b[2],
        a[0] * b[2] - a[1] * b[3] + a[2] * b[0] + a[3] * b[1],
        a[0] * b[3] + a[1] * b[2] - a[2] * b[1] + a[3] * b[0],
    )


class QuaternionInterpolator:
    """Shortest-arc spherical interpolation."""

    def interpolate(self, start: Quaternion, end: Quaternion, progress: float) -> Quaternion:
        if progress == 0.0:
            return start
        if progress == 1.0:
            return end
        d = start.dot(end)
        e = end
        if d < 0.0:  # take the short way around the 4-sphere
            e, d = Quaternion(-end.w, -end.x, -end.y, -end.z), -d
        if d > 0.9995:  # nearly parallel: lerp is numerically safer
            return Quaternion(
                *(
                    a + (b - a) * progress
                    for a, b in zip(start.as_tuple(), e.as_tuple(), strict=True)
                )
            )
        theta = math.acos(min(1.0, d))
        sin_theta = math.sin(theta)
        k0 = math.sin((1.0 - progress) * theta) / sin_theta
        k1 = math.sin(progress * theta) / sin_theta
        return Quaternion(
            *(k0 * a + k1 * b for a, b in zip(start.as_tuple(), e.as_tuple(), strict=True))
        )
