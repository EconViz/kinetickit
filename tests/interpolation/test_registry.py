from __future__ import annotations

import math
from dataclasses import dataclass

import pytest

from kinetickit.errors import ConfigurationError
from kinetickit.interpolation import (
    DEFAULT_REGISTRY,
    Angle,
    Color,
    InterpolatorRegistry,
    StepInterpolator,
)


def test_numbers_have_exact_endpoints_and_blend():
    r = DEFAULT_REGISTRY
    assert r.interpolate(float, 1.0, 3.0, 0.0) == 1.0
    assert r.interpolate(float, 1.0, 3.0, 1.0) == 3.0
    assert r.interpolate(float, 1.0, 3.0, 0.25) == 1.5
    assert r.interpolate(int, 0, 10, 0.5) == 5.0
    assert r.interpolate(float, 0.0, 1.0, 1.5) == 1.5  # extrapolation is allowed


def test_endpoint_exactness_for_awkward_values():
    a, b = 0.1, 0.7
    assert DEFAULT_REGISTRY.interpolate(float, a, b, 1.0) == b


def test_sequences_interpolate_elementwise_and_reject_mismatch():
    assert DEFAULT_REGISTRY.interpolate(tuple, (0, 0), (2, 4), 0.5) == (1.0, 2.0)
    with pytest.raises(ConfigurationError):
        DEFAULT_REGISTRY.interpolate(tuple, (0, 0), (1, 2, 3), 0.5)


def test_colors_blend_and_stay_in_gamut():
    c = DEFAULT_REGISTRY.interpolate(Color, Color.parse("#000000"), Color.parse("#ffffff"), 0.5)
    assert c.to_hex() == "#808080"
    over = DEFAULT_REGISTRY.interpolate(Color, Color(0, 0, 0), Color(1, 1, 1), 1.5)
    assert over.as_tuple() == (1.0, 1.0, 1.0, 1.0)


def test_color_parsing():
    assert Color.parse("#f36") == Color(1.0, 0x33 / 255, 0x66 / 255)
    assert Color.parse("#00000080").a == pytest.approx(128 / 255)
    assert Color.parse("white").to_hex() == "#ffffff"
    assert Color.parse((0.1, 0.2, 0.3)).a == 1.0
    for bad in ("#12", "nonsense", "#gggggg"):
        with pytest.raises(ConfigurationError):
            Color.parse(bad)
    with pytest.raises(ConfigurationError):
        Color(1.2, 0, 0)


def test_angles_take_the_shortest_arc():
    start, end = Angle(math.radians(350)), Angle(math.radians(10))
    mid = DEFAULT_REGISTRY.interpolate(Angle, start, end, 0.5)
    assert math.cos(mid) == pytest.approx(1.0)
    assert DEFAULT_REGISTRY.interpolate(Angle, start, end, 1.0) == end


def test_step_policies():
    end_step, start_step = StepInterpolator(1.0), StepInterpolator(0.0)
    assert (
        end_step.interpolate("a", "b", 0.99) == "a" and end_step.interpolate("a", "b", 1.0) == "b"
    )
    assert (
        start_step.interpolate("a", "b", 0.0) == "a"
        and start_step.interpolate("a", "b", 0.01) == "b"
    )
    with pytest.raises(ConfigurationError):
        StepInterpolator(2.0)


def test_unregistered_type_is_an_explicit_error_never_a_guess():
    class Custom: ...

    with pytest.raises(ConfigurationError, match="no interpolator registered"):
        DEFAULT_REGISTRY.resolve(Custom)


def test_custom_types_register_without_modifying_core():
    @dataclass(frozen=True)
    class Money:
        cents: int

    class MoneyInterpolator:
        def interpolate(self, start, end, progress):
            return Money(round(start.cents + (end.cents - start.cents) * progress))

    registry = InterpolatorRegistry()
    registry.register(Money, MoneyInterpolator())
    assert registry.interpolate(Money, Money(0), Money(100), 0.25) == Money(25)
    assert not DEFAULT_REGISTRY.has(Money)  # registries are isolated
    clone = registry.copy()
    assert clone.has(Money)


def test_subclasses_resolve_through_mro():
    class Meters(float): ...

    assert DEFAULT_REGISTRY.interpolate(Meters, 0.0, 2.0, 0.5) == 1.0


def test_register_rejects_non_interpolators():
    with pytest.raises(ConfigurationError):
        InterpolatorRegistry().register(int, object())


def test_discrete_declaration():
    reg = InterpolatorRegistry()
    reg.register_discrete(str)
    assert reg.interpolate(str, "circle", "square", 0.5) == "circle"
    assert reg.interpolate(str, "circle", "square", 1.0) == "square"
