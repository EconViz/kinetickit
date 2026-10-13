"""Immutable time values, the motion tree, and deterministic timeline sampling."""

from __future__ import annotations

from kinetickit.timeline.motion import Hold, Motion
from kinetickit.timeline.property import PropertyRef
from kinetickit.timeline.segment import Segment
from kinetickit.timeline.time import (
    TimeSpan,
    check_duration,
    check_time,
    frame_count,
    frame_times,
)
from kinetickit.timeline.timeline import Timeline

__all__ = [
    "Hold",
    "Motion",
    "PropertyRef",
    "Segment",
    "TimeSpan",
    "Timeline",
    "check_duration",
    "check_time",
    "frame_count",
    "frame_times",
]
