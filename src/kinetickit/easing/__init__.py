"""Pure progress functions mapping ``[0, 1]`` to eased progress.

Import this package as ``ease``::

    from kinetickit import ease
    ease.out_cubic(0.5)
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

from kinetickit.errors import ConfigurationError

Easing = Callable[[float], float]


def linear(p: float) -> float:
    return p


def _power(n: int) -> tuple[Easing, Easing, Easing]:
    def ease_in(p: float) -> float:
        return p**n

    def ease_out(p: float) -> float:
        return 1.0 - (1.0 - p) ** n

    def ease_in_out(p: float) -> float:
        if p < 0.5:
            return 0.5 * (2.0 * p) ** n
        return 1.0 - 0.5 * (2.0 * (1.0 - p)) ** n

    return ease_in, ease_out, ease_in_out


in_quad, out_quad, in_out_quad = _power(2)
in_cubic, out_cubic, in_out_cubic = _power(3)
in_quart, out_quart, in_out_quart = _power(4)
in_quint, out_quint, in_out_quint = _power(5)


def in_sine(p: float) -> float:
    return 1.0 - math.cos(p * math.pi / 2.0) if 0.0 < p < 1.0 else p


def out_sine(p: float) -> float:
    return math.sin(p * math.pi / 2.0) if 0.0 < p < 1.0 else p


def in_out_sine(p: float) -> float:
    return 0.5 * (1.0 - math.cos(math.pi * p)) if 0.0 < p < 1.0 else p


def in_expo(p: float) -> float:
    return (2.0 ** (10.0 * p) - 1.0) / 1023.0 if 0.0 < p < 1.0 else p


def out_expo(p: float) -> float:
    return 1.0 - in_expo(1.0 - p) if 0.0 < p < 1.0 else p


def in_out_expo(p: float) -> float:
    if not 0.0 < p < 1.0:
        return p
    return 0.5 * in_expo(2.0 * p) if p < 0.5 else 1.0 - 0.5 * in_expo(2.0 * (1.0 - p))


@dataclass(frozen=True, slots=True)
class CubicBezier:
    """CSS-style cubic Bézier easing with control points ``(x1, y1)`` and ``(x2, y2)``."""

    x1: float
    y1: float
    x2: float
    y2: float

    def __post_init__(self) -> None:
        for v in self.control_points:
            if not math.isfinite(v):
                raise ConfigurationError("cubic_bezier control points must be finite")
        if not (0.0 <= self.x1 <= 1.0 and 0.0 <= self.x2 <= 1.0):
            raise ConfigurationError("cubic_bezier x control points must lie in [0, 1]")

    @property
    def control_points(self) -> tuple[float, float, float, float]:
        return (self.x1, self.y1, self.x2, self.y2)

    @staticmethod
    def _axis(a: float, b: float, s: float) -> float:
        return ((1.0 - 3.0 * b + 3.0 * a) * s + (3.0 * b - 6.0 * a)) * s * s + 3.0 * a * s

    def _slope(self, a: float, b: float, s: float) -> float:
        return 3.0 * (1.0 - 3.0 * b + 3.0 * a) * s * s + 2.0 * (3.0 * b - 6.0 * a) * s + 3.0 * a

    def _solve(self, x: float) -> float:
        lo, hi = 0.0, 1.0
        s = x
        for _ in range(8):  # Newton-Raphson
            err = self._axis(self.x1, self.x2, s) - x
            if abs(err) < 1e-14:
                return s
            slope = self._slope(self.x1, self.x2, s)
            if abs(slope) < 1e-9:
                break
            s -= err / slope
            if not 0.0 <= s <= 1.0:
                break
        else:
            return s
        s = x  # bisection fallback: always converges, deterministic iteration count
        for _ in range(64):
            err = self._axis(self.x1, self.x2, s) - x
            if err > 0.0:
                hi = s
            else:
                lo = s
            s = 0.5 * (lo + hi)
        return s

    def __call__(self, p: float) -> float:
        if p <= 0.0:
            return 0.0
        if p >= 1.0:
            return 1.0
        return self._axis(self.y1, self.y2, self._solve(p))


def cubic_bezier(x1: float, y1: float, x2: float, y2: float) -> CubicBezier:
    return CubicBezier(x1, y1, x2, y2)


def reversed_ease(easing: Easing) -> Easing:
    """Return ``p -> 1 - easing(1 - p)``, the easing of a time-reversed motion."""

    def reverse(p: float) -> float:
        return 1.0 - easing(1.0 - p)

    return reverse


def step(p: float) -> float:
    """Discrete easing: stay at the start until progress reaches 1."""
    return 1.0 if p >= 1.0 else 0.0


STANDARD: Final[dict[str, Easing]] = {
    "linear": linear,
    "in_quad": in_quad,
    "out_quad": out_quad,
    "in_out_quad": in_out_quad,
    "in_cubic": in_cubic,
    "out_cubic": out_cubic,
    "in_out_cubic": in_out_cubic,
    "in_quart": in_quart,
    "out_quart": out_quart,
    "in_out_quart": in_out_quart,
    "in_quint": in_quint,
    "out_quint": out_quint,
    "in_out_quint": in_out_quint,
    "in_sine": in_sine,
    "out_sine": out_sine,
    "in_out_sine": in_out_sine,
    "in_expo": in_expo,
    "out_expo": out_expo,
    "in_out_expo": in_out_expo,
}

__all__ = [
    "STANDARD",
    "CubicBezier",
    "Easing",
    "cubic_bezier",
    "in_cubic",
    "in_expo",
    "in_out_cubic",
    "in_out_expo",
    "in_out_quad",
    "in_out_quart",
    "in_out_quint",
    "in_out_sine",
    "in_quad",
    "in_quart",
    "in_quint",
    "in_sine",
    "linear",
    "out_cubic",
    "out_expo",
    "out_quad",
    "out_quart",
    "out_quint",
    "out_sine",
    "reversed_ease",
    "step",
]
