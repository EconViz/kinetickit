"""Exact 2D vectors."""

from __future__ import annotations

import math
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from kinetickit.errors import ConfigurationError


def _finite(v: float, what: str) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        raise ConfigurationError(f"{what} must be a number, got {v!r}") from None
    if not math.isfinite(f):
        raise ConfigurationError(f"{what} must be finite, got {v!r}")
    return f


@dataclass(frozen=True, slots=True)
class Vec2:
    """A 2D vector or point. World space is Cartesian: +x right, +y up."""

    x: float
    y: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "x", _finite(self.x, "x"))
        object.__setattr__(self, "y", _finite(self.y, "y"))

    @classmethod
    def coerce(cls, value: Any) -> Vec2:
        if isinstance(value, Vec2):
            return value
        try:
            x, y = value
        except (TypeError, ValueError):
            raise ConfigurationError(f"cannot interpret {value!r} as a 2D vector") from None
        return cls(x, y)

    def __iter__(self) -> Iterator[float]:
        yield self.x
        yield self.y

    def __add__(self, other: Any) -> Vec2:
        o = Vec2.coerce(other)
        return Vec2(self.x + o.x, self.y + o.y)

    def __sub__(self, other: Any) -> Vec2:
        o = Vec2.coerce(other)
        return Vec2(self.x - o.x, self.y - o.y)

    def __mul__(self, k: float) -> Vec2:
        return Vec2(self.x * k, self.y * k)

    __rmul__ = __mul__

    def __truediv__(self, k: float) -> Vec2:
        return Vec2(self.x / k, self.y / k)

    def __neg__(self) -> Vec2:
        return Vec2(-self.x, -self.y)

    def dot(self, other: Vec2) -> float:
        return self.x * other.x + self.y * other.y

    def cross(self, other: Vec2) -> float:
        return self.x * other.y - self.y * other.x

    def length(self) -> float:
        return math.hypot(self.x, self.y)

    def as_tuple(self) -> tuple[float, float]:
        return (self.x, self.y)


class Vec2Interpolator:
    def interpolate(self, start: Vec2, end: Vec2, progress: float) -> Vec2:
        if progress == 0.0:
            return start
        if progress == 1.0:
            return end
        return Vec2(start.x + (end.x - start.x) * progress, start.y + (end.y - start.y) * progress)
