"""A deterministic playback state machine, the Python reference for the HTML runtime."""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace

from kinetickit.errors import ConfigurationError
from kinetickit.timeline.time import check_duration


@dataclass(frozen=True)
class PlayerState:
    """Immutable playback state. Every transition returns a new state; nothing reads a clock.

    ``tick(dt)`` advances by ``dt`` wall seconds: time moves by ``dt * speed * direction`` and the
    state handles looping, range playback and end-of-timeline pausing.
    """

    duration: float
    time: float = 0.0
    playing: bool = False
    speed: float = 1.0
    direction: int = 1
    loop: bool = False
    range: tuple[float, float] | None = None
    ended: bool = field(default=False, compare=False)

    def __post_init__(self) -> None:
        check_duration(self.duration)
        if not math.isfinite(self.time) or not 0.0 <= self.time <= self.duration:
            raise ConfigurationError(f"time {self.time} outside [0, {self.duration}]")
        if not self.speed > 0 or not math.isfinite(self.speed):
            raise ConfigurationError("speed must be positive")
        if self.direction not in (1, -1):
            raise ConfigurationError("direction must be 1 or -1")

    def _bounds(self) -> tuple[float, float]:
        return self.range if self.range is not None else (0.0, self.duration)

    def seek(self, t: float) -> PlayerState:
        return replace(self, time=min(self.duration, max(0.0, t)), ended=False)

    def play(self) -> PlayerState:
        if self.duration == 0.0:
            return self
        lo, hi = self._bounds()
        t = self.time
        if self.direction == 1 and t >= hi:
            t = lo
        elif self.direction == -1 and t <= lo:
            t = hi
        return replace(self, playing=True, time=t, ended=False)

    def pause(self) -> PlayerState:
        return replace(self, playing=False)

    def toggle(self) -> PlayerState:
        return self.pause() if self.playing else self.play()

    def reverse(self) -> PlayerState:
        return replace(self, direction=-self.direction)

    def with_speed(self, speed: float) -> PlayerState:
        return replace(self, speed=speed)

    def with_loop(self, loop: bool) -> PlayerState:
        return replace(self, loop=loop)

    def play_range(self, start: float, end: float) -> PlayerState:
        """Play ``[start, end]`` once from its start (forward), pausing at its end."""
        if not 0.0 <= start <= end <= self.duration:
            raise ConfigurationError("range must lie within the timeline")
        return replace(
            self, range=(start, end), direction=1, time=start, playing=True, loop=False, ended=False
        )

    def clear_range(self) -> PlayerState:
        return replace(self, range=None)

    def tick(self, dt: float) -> PlayerState:
        if not self.playing or dt < 0:
            return self
        lo, hi = self._bounds()
        t = self.time + dt * self.speed * self.direction
        if lo <= t <= hi:
            return replace(self, time=t)
        span = hi - lo
        if self.loop and span > 0:
            return replace(self, time=lo + (t - lo) % span)
        end = hi if t > hi else lo
        return replace(self, time=end, playing=False, ended=True, range=None)
