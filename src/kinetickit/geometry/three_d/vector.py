"""Exact 3D vectors. World space is right-handed: +x right, +y forward, +z up."""

from __future__ import annotations

import math
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from kinetickit.errors import ConfigurationError


def _finite(v: Any, what: str) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        raise ConfigurationError(f"{what} must be a number, got {v!r}") from None
    if not math.isfinite(f):
        raise ConfigurationError(f"{what} must be finite, got {v!r}")
    return f


@dataclass(frozen=True, slots=True)
class Vec3:
    x: float
    y: float
    z: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "x", _finite(self.x, "x"))
        object.__setattr__(self, "y", _finite(self.y, "y"))
        object.__setattr__(self, "z", _finite(self.z, "z"))

    @classmethod
    def coerce(cls, value: Any) -> Vec3:
        if isinstance(value, Vec3):
            return value
        try:
            x, y, z = value
        except (TypeError, ValueError):
            raise ConfigurationError(f"cannot interpret {value!r} as a 3D vector") from None
        return cls(x, y, z)

    def __iter__(self) -> Iterator[float]:
        yield self.x
        yield self.y
        yield self.z

    def __add__(self, other: Any) -> Vec3:
        o = Vec3.coerce(other)
        return Vec3(self.x + o.x, self.y + o.y, self.z + o.z)

    def __sub__(self, other: Any) -> Vec3:
        o = Vec3.coerce(other)
        return Vec3(self.x - o.x, self.y - o.y, self.z - o.z)

    def __mul__(self, k: float) -> Vec3:
        return Vec3(self.x * k, self.y * k, self.z * k)

    __rmul__ = __mul__

    def __truediv__(self, k: float) -> Vec3:
        return Vec3(self.x / k, self.y / k, self.z / k)

    def __neg__(self) -> Vec3:
        return Vec3(-self.x, -self.y, -self.z)

    def dot(self, o: Vec3) -> float:
        return self.x * o.x + self.y * o.y + self.z * o.z

    def cross(self, o: Vec3) -> Vec3:
        return Vec3(
            self.y * o.z - self.z * o.y, self.z * o.x - self.x * o.z, self.x * o.y - self.y * o.x
        )

    def length(self) -> float:
        return math.sqrt(self.dot(self))

    def normalized(self) -> Vec3:
        n = self.length()
        if n == 0.0:
            raise ConfigurationError("cannot normalize the zero vector")
        return self / n

    def as_tuple(self) -> tuple[float, float, float]:
        return (self.x, self.y, self.z)


class Vec3Interpolator:
    def interpolate(self, start: Vec3, end: Vec3, progress: float) -> Vec3:
        if progress == 0.0:
            return start
        if progress == 1.0:
            return end
        return Vec3(
            start.x + (end.x - start.x) * progress,
            start.y + (end.y - start.y) * progress,
            start.z + (end.z - start.z) * progress,
        )
