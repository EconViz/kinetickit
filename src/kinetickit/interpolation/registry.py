"""Explicit type-to-interpolator registry. Lookup never guesses."""

from __future__ import annotations

from typing import Any

from kinetickit.errors import ConfigurationError
from kinetickit.interpolation.color import Color, ColorInterpolator
from kinetickit.interpolation.numeric import (
    Angle,
    AngleInterpolator,
    NumberInterpolator,
    StepInterpolator,
)
from kinetickit.interpolation.sequence import SequenceInterpolator


class InterpolatorRegistry:
    """Maps value types to interpolators; subclasses resolve through the MRO."""

    def __init__(self) -> None:
        self._by_type: dict[type, Any] = {}

    def register(self, value_type: type, interpolator: Any) -> None:
        if not callable(getattr(interpolator, "interpolate", None)):
            raise ConfigurationError("an interpolator must define interpolate(start, end, p)")
        self._by_type[value_type] = interpolator

    def register_discrete(self, value_type: type, threshold: float = 1.0) -> None:
        """Declare ``value_type`` discrete: it switches at ``threshold`` progress."""
        self.register(value_type, StepInterpolator(threshold))

    def resolve(self, value_type: type) -> Any:
        for klass in value_type.__mro__:
            found = self._by_type.get(klass)
            if found is not None:
                return found
        raise ConfigurationError(
            f"no interpolator registered for {value_type.__name__}; register one with "
            "registry.register(...) or declare the type discrete with register_discrete(...)"
        )

    def has(self, value_type: type) -> bool:
        return any(k in self._by_type for k in value_type.__mro__)

    def copy(self) -> InterpolatorRegistry:
        clone = InterpolatorRegistry()
        clone._by_type = dict(self._by_type)
        return clone

    def interpolate(self, value_type: type, start: Any, end: Any, progress: float) -> Any:
        return self.resolve(value_type).interpolate(start, end, progress)


def _default() -> InterpolatorRegistry:
    reg = InterpolatorRegistry()
    number = NumberInterpolator()
    reg.register(int, number)
    reg.register(float, number)
    reg.register(Angle, AngleInterpolator())
    reg.register(Color, ColorInterpolator())
    seq = SequenceInterpolator()
    reg.register(tuple, seq)
    reg.register(list, seq)
    reg.register_discrete(bool)
    reg.register_discrete(str)
    return reg


DEFAULT_REGISTRY = _default()


def register_interpolator(value_type: type, interpolator: Any) -> None:
    """Register an interpolator on the default registry without touching core code."""
    DEFAULT_REGISTRY.register(value_type, interpolator)
