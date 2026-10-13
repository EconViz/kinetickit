"""Deterministic offline schedulers."""

from __future__ import annotations

import math
from collections.abc import Iterable, Iterator
from dataclasses import dataclass

from kinetickit.errors import ConfigurationError
from kinetickit.timeline.time import check_duration, check_time, frame_count


@dataclass(frozen=True, slots=True)
class FixedFPS:
    """Evenly spaced frames at ``fps`` including both ``0`` and the duration."""

    fps: int

    def __post_init__(self) -> None:
        if isinstance(self.fps, bool) or not isinstance(self.fps, int) or self.fps <= 0:
            raise ConfigurationError(f"fps must be a positive integer, got {self.fps!r}")

    def count(self, duration: float) -> int:
        return frame_count(duration, self.fps)

    def times(self, duration: float) -> Iterator[float]:
        d = check_duration(duration)
        n = frame_count(d, self.fps)
        last = n - 1
        for i in range(n):
            yield d if i == last else d * i / last


class Timestamps:
    """Explicit, non-decreasing timestamps; values past the duration are rejected."""

    def __init__(self, stamps: Iterable[float]) -> None:
        self._stamps = tuple(check_time(s, "timestamp") for s in stamps)
        if any(b < a for a, b in zip(self._stamps, self._stamps[1:], strict=False)):
            raise ConfigurationError("timestamps must be non-decreasing")
        if not self._stamps:
            raise ConfigurationError("at least one timestamp is required")

    def times(self, duration: float) -> Iterator[float]:
        d = check_duration(duration)
        for s in self._stamps:
            if s > d and not math.isclose(s, d):
                raise ConfigurationError(f"timestamp {s} exceeds the duration {d}")
            yield min(s, d)
