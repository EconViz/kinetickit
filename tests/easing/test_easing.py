from __future__ import annotations

import itertools
import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from kinetickit import ease
from kinetickit.errors import ConfigurationError

NAMES = sorted(ease.STANDARD)
MONOTONE = [n for n in NAMES if n != "linear"] + ["linear"]


@pytest.mark.parametrize("name", NAMES)
def test_endpoints_are_exact(name):
    fn = ease.STANDARD[name]
    assert fn(0.0) == 0.0
    assert fn(1.0) == pytest.approx(1.0, abs=1e-12)


@pytest.mark.parametrize("name", MONOTONE)
def test_standard_easings_are_monotone(name):
    fn = ease.STANDARD[name]
    values = [fn(i / 200) for i in range(201)]
    assert all(b >= a - 1e-12 for a, b in itertools.pairwise(values))


@pytest.mark.parametrize("name", [n for n in NAMES if n.startswith("in_out")])
def test_in_out_is_symmetric(name):
    fn = ease.STANDARD[name]
    for p in (0.1, 0.25, 0.4):
        assert fn(p) + fn(1 - p) == pytest.approx(1.0, abs=1e-9)


def test_known_values():
    assert ease.in_quad(0.5) == 0.25
    assert ease.out_quad(0.5) == 0.75
    assert ease.in_out_cubic(0.5) == pytest.approx(0.5)
    assert ease.in_sine(0.5) == pytest.approx(1 - math.cos(math.pi / 4))
    assert ease.step(0.999) == 0.0 and ease.step(1.0) == 1.0


def test_cubic_bezier_matches_linear_and_css_ease():
    lin = ease.cubic_bezier(0.0, 0.0, 1.0, 1.0)
    for p in (0.0, 0.1, 0.5, 0.9, 1.0):
        assert lin(p) == pytest.approx(p, abs=1e-9)
    css = ease.cubic_bezier(0.25, 0.1, 0.25, 1.0)
    assert css(0.5) == pytest.approx(0.8024, abs=1e-3)
    assert css == ease.cubic_bezier(0.25, 0.1, 0.25, 1.0)
    assert hash(css) == hash(ease.cubic_bezier(0.25, 0.1, 0.25, 1.0))


def test_cubic_bezier_validation_and_immutability():
    with pytest.raises(ConfigurationError):
        ease.cubic_bezier(1.5, 0, 0.5, 1)
    with pytest.raises(ConfigurationError):
        ease.cubic_bezier(float("nan"), 0, 0.5, 1)
    with pytest.raises(AttributeError):
        ease.cubic_bezier(0, 0, 1, 1).x1 = 0.5  # type: ignore[misc]


def test_cubic_bezier_is_stable_at_extreme_control_points():
    steep = ease.cubic_bezier(0.0, 1.0, 1.0, 0.0)
    values = [steep(i / 1000) for i in range(1001)]
    assert all(0.0 <= v <= 1.0 for v in values)
    assert all(b >= a - 1e-9 for a, b in itertools.pairwise(values))


def test_bezier_allows_overshoot_in_y():
    back = ease.cubic_bezier(0.34, 1.56, 0.64, 1.0)
    assert max(back(i / 100) for i in range(101)) > 1.0


@given(st.floats(min_value=0.0, max_value=1.0))
def test_reversed_ease_identity(p):
    rev = ease.reversed_ease(ease.in_cubic)
    assert rev(p) == pytest.approx(ease.out_cubic(p), abs=1e-9)
    assert ease.reversed_ease(rev)(p) == pytest.approx(ease.in_cubic(p), abs=1e-9)
