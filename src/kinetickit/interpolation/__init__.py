"""Typed interpolation protocols and the extensible registry."""

from __future__ import annotations

from kinetickit.interpolation.color import Color, ColorInterpolator
from kinetickit.interpolation.numeric import (
    Angle,
    AngleInterpolator,
    NumberInterpolator,
    StepInterpolator,
)
from kinetickit.interpolation.protocol import Extrapolation, Interpolator
from kinetickit.interpolation.registry import (
    DEFAULT_REGISTRY,
    InterpolatorRegistry,
    register_interpolator,
)
from kinetickit.interpolation.sequence import SequenceInterpolator

__all__ = [
    "DEFAULT_REGISTRY",
    "Angle",
    "AngleInterpolator",
    "Color",
    "ColorInterpolator",
    "Extrapolation",
    "Interpolator",
    "InterpolatorRegistry",
    "NumberInterpolator",
    "SequenceInterpolator",
    "StepInterpolator",
    "register_interpolator",
]
