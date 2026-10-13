from __future__ import annotations

import pytest

from kinetickit.errors import ConfigurationError
from kinetickit.scheduler import FixedFPS, Scheduler, Timestamps
from kinetickit.timeline import frame_times


def test_fixed_fps_matches_frame_times_and_is_lazy():
    sched = FixedFPS(30)
    stream = sched.times(1.0)
    assert iter(stream) is stream  # an iterator, not a materialized list
    assert tuple(stream) == frame_times(1.0, 30)
    assert sched.count(1.0) == 30


def test_fixed_fps_validation():
    for bad in (0, -1, 2.5, True):
        with pytest.raises(ConfigurationError):
            FixedFPS(bad)


def test_explicit_timestamps():
    assert list(Timestamps([0, 0.25, 0.25, 1.0]).times(1.0)) == [0.0, 0.25, 0.25, 1.0]


def test_timestamp_validation():
    with pytest.raises(ConfigurationError):
        Timestamps([0.5, 0.2])
    with pytest.raises(ConfigurationError):
        Timestamps([])
    with pytest.raises(ConfigurationError):
        Timestamps([-1])
    with pytest.raises(ConfigurationError):
        list(Timestamps([0, 2.0]).times(1.0))


def test_schedulers_satisfy_the_protocol():
    assert isinstance(FixedFPS(10), Scheduler)
    assert isinstance(Timestamps([0]), Scheduler)
