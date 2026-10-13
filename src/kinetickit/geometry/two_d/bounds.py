"""Axis-aligned 2D bounds."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from kinetickit.errors import ConfigurationError
from kinetickit.geometry.two_d.vector import Vec2, Vec2Interpolator


@dataclass(frozen=True, slots=True)
class Bounds2D:
    min: Vec2
    max: Vec2

    def __post_init__(self) -> None:
        lo, hi = Vec2.coerce(self.min), Vec2.coerce(self.max)
        if hi.x < lo.x or hi.y < lo.y:
            raise ConfigurationError(f"bounds max {hi} is below min {lo}")
        object.__setattr__(self, "min", lo)
        object.__setattr__(self, "max", hi)

    @classmethod
    def coerce(cls, value: Any) -> Bounds2D:
        if isinstance(value, Bounds2D):
            return value
        try:
            lo, hi = value
        except (TypeError, ValueError):
            raise ConfigurationError(f"cannot interpret {value!r} as 2D bounds") from None
        return cls(Vec2.coerce(lo), Vec2.coerce(hi))

    @classmethod
    def of(cls, points: Iterable[Vec2]) -> Bounds2D | None:
        pts = list(points)
        if not pts:
            return None
        return cls(
            Vec2(min(p.x for p in pts), min(p.y for p in pts)),
            Vec2(max(p.x for p in pts), max(p.y for p in pts)),
        )

    @property
    def size(self) -> Vec2:
        return self.max - self.min

    @property
    def center(self) -> Vec2:
        return (self.min + self.max) * 0.5

    def union(self, other: Bounds2D) -> Bounds2D:
        return Bounds2D(
            Vec2(min(self.min.x, other.min.x), min(self.min.y, other.min.y)),
            Vec2(max(self.max.x, other.max.x), max(self.max.y, other.max.y)),
        )

    def padded(self, amount: float) -> Bounds2D:
        d = Vec2(amount, amount)
        return Bounds2D(self.min - d, self.max + d)

    def contains(self, p: Vec2) -> bool:
        return self.min.x <= p.x <= self.max.x and self.min.y <= p.y <= self.max.y

    def corners(self) -> tuple[Vec2, Vec2, Vec2, Vec2]:
        return (
            self.min,
            Vec2(self.max.x, self.min.y),
            self.max,
            Vec2(self.min.x, self.max.y),
        )


class Bounds2DInterpolator:
    _vec = Vec2Interpolator()

    def interpolate(self, start: Bounds2D, end: Bounds2D, progress: float) -> Bounds2D:
        if progress == 0.0:
            return start
        if progress == 1.0:
            return end
        return Bounds2D(
            self._vec.interpolate(start.min, end.min, progress),
            self._vec.interpolate(start.max, end.max, progress),
        )
