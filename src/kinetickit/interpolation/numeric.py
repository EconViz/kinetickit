"""Scalar, angle, and discrete interpolation."""

from __future__ import annotations

import math
from typing import Any

from kinetickit.errors import ConfigurationError


class Angle(float):
    """A public angle in radians; interpolates along the shortest arc."""

    __slots__ = ()

    @classmethod
    def degrees(cls, value: float) -> Angle:
        return cls(math.radians(value))


class NumberInterpolator:
    """Linear interpolation of real numbers with exact endpoints."""

    def interpolate(self, start: float, end: float, progress: float) -> float:
        if progress == 0.0:
            return float(start)
        if progress == 1.0:
            return float(end)
        return float(start) + (float(end) - float(start)) * progress


class AngleInterpolator:
    """Shortest-arc interpolation of radian angles."""

    def interpolate(self, start: float, end: float, progress: float) -> Angle:
        if progress == 0.0:
            return Angle(start)
        if progress == 1.0:
            return Angle(end)
        delta = (float(end) - float(start) + math.pi) % math.tau - math.pi
        return Angle(float(start) + delta * progress)


class StepInterpolator:
    """Discrete interpolation: the value switches once, at ``threshold`` progress.

    ``threshold=1.0`` (default) holds the start value until the segment completes;
    ``threshold=0.0`` switches immediately when the segment begins.
    """

    def __init__(self, threshold: float = 1.0) -> None:
        if not 0.0 <= threshold <= 1.0:
            raise ConfigurationError("step threshold must lie in [0, 1]")
        self.threshold = float(threshold)

    def interpolate(self, start: Any, end: Any, progress: float) -> Any:
        if self.threshold == 0.0:
            return end if progress > 0.0 else start
        return end if progress >= self.threshold else start
