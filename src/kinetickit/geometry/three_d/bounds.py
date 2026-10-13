"""Axis-aligned 3D bounds."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from kinetickit.errors import ConfigurationError
from kinetickit.geometry.three_d.vector import Vec3


@dataclass(frozen=True, slots=True)
class Bounds3D:
    min: Vec3
    max: Vec3

    def __post_init__(self) -> None:
        lo, hi = Vec3.coerce(self.min), Vec3.coerce(self.max)
        if hi.x < lo.x or hi.y < lo.y or hi.z < lo.z:
            raise ConfigurationError(f"bounds max {hi} is below min {lo}")
        object.__setattr__(self, "min", lo)
        object.__setattr__(self, "max", hi)

    @classmethod
    def of(cls, points: Iterable[Vec3]) -> Bounds3D | None:
        pts = list(points)
        if not pts:
            return None
        return cls(
            Vec3(min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)),
            Vec3(max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)),
        )

    @property
    def size(self) -> Vec3:
        return self.max - self.min

    @property
    def center(self) -> Vec3:
        return (self.min + self.max) * 0.5

    def union(self, o: Bounds3D) -> Bounds3D:
        return Bounds3D(
            Vec3(min(self.min.x, o.min.x), min(self.min.y, o.min.y), min(self.min.z, o.min.z)),
            Vec3(max(self.max.x, o.max.x), max(self.max.y, o.max.y), max(self.max.z, o.max.z)),
        )

    def corners(self) -> tuple[Vec3, ...]:
        lo, hi = self.min, self.max
        return tuple(
            Vec3(x, y, z) for x in (lo.x, hi.x) for y in (lo.y, hi.y) for z in (lo.z, hi.z)
        )

    def radius(self) -> float:
        return self.size.length() / 2.0
