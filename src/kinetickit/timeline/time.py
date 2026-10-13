"""Deterministic time values. Nothing here reads the wall clock."""

from __future__ import annotations

import math
from dataclasses import dataclass

from kinetickit.errors import ConfigurationError


def check_time(value: float, name: str = "time") -> float:
    """Return ``value`` as a float, requiring it to be finite and non-negative."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        raise ConfigurationError(f"{name} must be a number, got {value!r}") from None
    if not math.isfinite(v) or v < 0.0:
        raise ConfigurationError(f"{name} must be finite and non-negative, got {value!r}")
    return v


def check_duration(value: float, name: str = "duration") -> float:
    return check_time(value, name)


@dataclass(frozen=True, slots=True)
class TimeSpan:
    """A closed interval ``[start, end]`` in seconds."""

    start: float
    end: float

    def __post_init__(self) -> None:
        s = check_time(self.start, "start")
        e = check_time(self.end, "end")
        if e < s:
            raise ConfigurationError(f"end ({e}) precedes start ({s})")
        object.__setattr__(self, "start", s)
        object.__setattr__(self, "end", e)

    @property
    def duration(self) -> float:
        return self.end - self.start

    def contains(self, t: float) -> bool:
        return self.start <= t <= self.end

    def shifted(self, delta: float) -> TimeSpan:
        return TimeSpan(self.start + delta, self.end + delta)

    def progress(self, t: float) -> float:
        """Normalized progress of ``t`` through the span, clamped to ``[0, 1]``.

        A zero-length span is instantaneous: it reports ``0`` before and ``1`` from its start.
        """
        d = self.end - self.start
        if d == 0.0:
            return 1.0 if t >= self.start else 0.0
        return min(1.0, max(0.0, (t - self.start) / d))


def frame_count(duration: float, fps: int) -> int:
    """Number of offline frames for ``duration`` seconds at ``fps``: ``max(2, round(D*fps))``."""
    d = check_duration(duration)
    if isinstance(fps, bool) or not isinstance(fps, int) or fps <= 0:
        raise ConfigurationError(f"fps must be a positive integer, got {fps!r}")
    return max(2, math.floor(d * fps + 0.5))


def frame_times(duration: float, fps: int) -> tuple[float, ...]:
    """Frame sample times; both ``0`` and ``duration`` are included without drift."""
    d = check_duration(duration)
    n = frame_count(d, fps)
    if d == 0.0:
        return (0.0,) * n
    last = n - 1
    return tuple(d * i / last if i < last else d for i in range(n))
