"""A resolved interpolation interval: the unit the timeline samples."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from kinetickit.easing import Easing, linear
from kinetickit.interpolation import DEFAULT_REGISTRY, Extrapolation, InterpolatorRegistry
from kinetickit.timeline.property import PropertyRef


@dataclass(frozen=True, slots=True)
class Segment:
    """One property moving from ``from_value`` to ``to_value`` over ``[start, end]``.

    ``lo``/``hi`` select the sub-range of raw progress that is displayed and ``flipped``
    plays it backwards; this represents trimmed and time-reversed segments exactly. Reversal
    is equivalent to swapping the endpoints and applying ``reversed_ease``.
    """

    ref: PropertyRef[Any]
    start: float
    end: float
    from_value: Any
    to_value: Any
    easing: Easing = linear
    lo: float = 0.0
    hi: float = 1.0
    flipped: bool = False
    extrapolation: Extrapolation = Extrapolation.CLAMP
    order: int = 0

    def _map(self, u: float) -> float:
        return self.lo + (self.hi - self.lo) * ((1.0 - u) if self.flipped else u)

    def local_progress(self, t: float) -> float:
        d = self.end - self.start
        if d <= 0.0:
            return 1.0 if t >= self.start else 0.0
        u = (t - self.start) / d
        if self.extrapolation is Extrapolation.CLAMP:
            u = min(1.0, max(0.0, u))
        return u

    def value_at(self, t: float, registry: InterpolatorRegistry = DEFAULT_REGISTRY) -> Any:
        p = self.easing(self._map(self.local_progress(t)))
        return registry.interpolate(self.ref.value_type, self.from_value, self.to_value, p)

    def shifted(self, delta: float) -> Segment:
        return replace(self, start=self.start + delta, end=self.end + delta)

    def mirrored(self, duration: float) -> Segment:
        """The segment as seen when its enclosing block of ``duration`` plays backwards."""
        return replace(
            self,
            start=duration - self.end,
            end=duration - self.start,
            flipped=not self.flipped,
        )

    def clipped(self, a: float, b: float) -> Segment | None:
        """Restrict to ``[a, b]``, preserving the displayed curve exactly."""
        if self.end < a or self.start > b:
            return None
        if self.end == self.start:
            return self if a <= self.start <= b else None
        cs, ce = max(self.start, a), min(self.end, b)
        d = self.end - self.start
        lo, hi = self._map((cs - self.start) / d), self._map((ce - self.start) / d)
        return replace(self, start=cs, end=ce, lo=lo, hi=hi, flipped=False)
