"""Immutable time values and (later) the motion tree."""

from __future__ import annotations

from kinetickit.timeline.time import (
    TimeSpan,
    check_duration,
    check_time,
    frame_count,
    frame_times,
)

__all__ = ["TimeSpan", "check_duration", "check_time", "frame_count", "frame_times"]
