from __future__ import annotations

import itertools
import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from kinetickit.errors import ConfigurationError
from kinetickit.timeline import TimeSpan, check_time, frame_count, frame_times


def test_one_second_at_30_fps_contains_both_endpoints():
    times = frame_times(1.0, 30)
    assert len(times) == 30
    assert times[0] == 0.0
    assert times[-1] == 1.0


def test_frame_count_rounds_half_up_with_minimum_two():
    assert frame_count(1.0, 30) == 30
    assert frame_count(0.5, 5) == 3  # floor(2.5 + .5)
    assert frame_count(0.001, 30) == 2
    assert frame_count(0.0, 30) == 2


def test_zero_duration_frames_all_sample_zero():
    assert frame_times(0.0, 24) == (0.0, 0.0)


@pytest.mark.parametrize("bad", [-1.0, float("nan"), float("inf"), "x", None])
def test_invalid_times_raise(bad):
    with pytest.raises(ConfigurationError):
        check_time(bad)
    with pytest.raises(ConfigurationError):
        frame_times(bad, 30)


@pytest.mark.parametrize("fps", [0, -3, 2.5, True, "30"])
def test_invalid_fps_raises(fps):
    with pytest.raises(ConfigurationError):
        frame_times(1.0, fps)


@given(st.floats(min_value=0.01, max_value=600.0), st.integers(min_value=1, max_value=240))
def test_frame_times_are_strictly_increasing_and_bounded(duration, fps):
    times = frame_times(duration, fps)
    assert times[0] == 0.0 and times[-1] == duration
    assert all(b > a for a, b in itertools.pairwise(times))
    assert frame_times(duration, fps) == times  # deterministic


def test_timespan_progress_and_validation():
    span = TimeSpan(1.0, 3.0)
    assert span.duration == 2.0
    assert span.progress(0.0) == 0.0 and span.progress(2.0) == 0.5 and span.progress(9.0) == 1.0
    assert span.contains(1.0) and span.contains(3.0) and not span.contains(3.1)
    assert span.shifted(1.0) == TimeSpan(2.0, 4.0)
    inst = TimeSpan(2.0, 2.0)
    assert inst.progress(1.9) == 0.0 and inst.progress(2.0) == 1.0
    with pytest.raises(ConfigurationError):
        TimeSpan(2.0, 1.0)
    assert not math.isnan(span.progress(2.5))
