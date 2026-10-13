"""Interpolate one property over an interval."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from kinetickit.easing import Easing, linear
from kinetickit.errors import ConfigurationError
from kinetickit.interpolation import Extrapolation, InterpolatorRegistry
from kinetickit.timeline.motion import Compiled, Motion, PreState
from kinetickit.timeline.property import PropertyRef
from kinetickit.timeline.segment import Segment
from kinetickit.timeline.time import check_duration


class _NoValue:
    __slots__ = ()

    def __repr__(self) -> str:
        return "NO_VALUE"


NO_VALUE: Any = _NoValue()


@dataclass(frozen=True, slots=True)
class Tween(Motion):
    """Move ``target`` to ``to_value`` over ``length`` seconds.

    Without ``from_value`` (the ``NO_VALUE`` default) the tween starts from the property's value at
    its start time; ``None`` is a legitimate explicit start for optional properties.
    """

    target: PropertyRef[Any]
    to_value: Any
    length: float
    easing: Easing = linear
    from_value: Any = NO_VALUE
    extrapolation: Extrapolation = Extrapolation.CLAMP

    def __post_init__(self) -> None:
        object.__setattr__(self, "length", check_duration(self.length))
        if not callable(self.easing):
            raise ConfigurationError("easing must be callable")

    @property
    def duration(self) -> float:
        return self.length

    def targets(self) -> frozenset[PropertyRef[Any]]:
        return frozenset({self.target})

    def _compile(self, pre: PreState, registry: InterpolatorRegistry) -> Compiled:
        registry.resolve(self.target.value_type)  # fail early for unregistered types
        start = pre(self.target) if self.from_value is NO_VALUE else self.from_value
        return Compiled(
            (
                Segment(
                    self.target,
                    0.0,
                    self.length,
                    start,
                    self.to_value,
                    self.easing,
                    extrapolation=self.extrapolation,
                ),
            )
        )
