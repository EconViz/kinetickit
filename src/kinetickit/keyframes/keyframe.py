"""Multi-segment value tracks across explicit times."""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Any

from kinetickit.easing import Easing, linear, step
from kinetickit.errors import ConfigurationError
from kinetickit.interpolation import InterpolatorRegistry
from kinetickit.timeline.motion import Compiled, Motion, PreState
from kinetickit.timeline.property import PropertyRef
from kinetickit.timeline.segment import Segment
from kinetickit.timeline.time import check_time


@dataclass(frozen=True, slots=True)
class Keyframe:
    """A value at ``time`` seconds after the track starts.

    ``easing`` shapes the segment *arriving* at this keyframe. ``hold=True`` keeps the previous
    value until ``time`` and then jumps.
    """

    time: float
    value: Any
    easing: Easing | None = None
    hold: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "time", check_time(self.time, "keyframe time"))


@dataclass(frozen=True, slots=True)
class Keyframes(Motion):
    """Resolve a property across explicit keyframe times.

    If the first keyframe is later than ``0`` the property eases from its starting value to it.
    """

    target: PropertyRef[Any]
    frames: tuple[Keyframe, ...]
    easing: Easing = linear

    def __post_init__(self) -> None:
        if not self.frames:
            raise ConfigurationError("keyframes need at least one keyframe")
        times = [f.time for f in self.frames]
        if any(b <= a for a, b in itertools.pairwise(times)):
            raise ConfigurationError(f"keyframe times must be strictly increasing, got {times}")

    @property
    def duration(self) -> float:
        return self.frames[-1].time

    def targets(self) -> frozenset[PropertyRef[Any]]:
        return frozenset({self.target})

    def _compile(self, pre: PreState, registry: InterpolatorRegistry) -> Compiled:
        registry.resolve(self.target.value_type)
        segments: list[Segment] = []
        prev_time, prev_value = 0.0, pre(self.target)
        for frame in self.frames:
            if frame.time > prev_time or frame.time == 0.0:
                easing = step if frame.hold else (frame.easing or self.easing)
                segments.append(
                    Segment(self.target, prev_time, frame.time, prev_value, frame.value, easing)
                )
            prev_time, prev_value = frame.time, frame.value
        return Compiled(tuple(segments))
