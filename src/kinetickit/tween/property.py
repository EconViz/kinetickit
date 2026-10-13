"""Builders that turn a property reference into immutable motions."""

from __future__ import annotations

from typing import Any

from kinetickit.easing import Easing, linear
from kinetickit.interpolation import Extrapolation
from kinetickit.keyframes.keyframe import Keyframe, Keyframes
from kinetickit.timeline.property import PropertyRef
from kinetickit.tween.tween import NO_VALUE, Tween


class PropertyBuilder:
    """Fluent entry point: ``node.animate.position.to((4, 3), duration=1.0)``."""

    __slots__ = ("ref",)

    def __init__(self, ref: PropertyRef[Any]) -> None:
        self.ref = ref

    def to(
        self,
        value: Any,
        *,
        duration: float,
        easing: Easing = linear,
        from_: Any = None,
        extrapolation: Extrapolation = Extrapolation.CLAMP,
    ) -> Tween:
        return Tween(
            self.ref,
            self.ref.coerce(value),
            duration,
            easing,
            NO_VALUE if from_ is None else self.ref.coerce(from_),
            extrapolation,
        )

    def set(self, value: Any) -> Tween:
        """Jump to ``value`` instantly."""
        return self.to(value, duration=0.0)

    def keyframes(self, *frames: Keyframe | tuple[Any, ...], easing: Easing = linear) -> Keyframes:
        built = tuple(
            f if isinstance(f, Keyframe) else Keyframe(f[0], self.ref.coerce(f[1]), *f[2:])
            for f in frames
        )
        coerced = tuple(Keyframe(f.time, self.ref.coerce(f.value), f.easing, f.hold) for f in built)
        return Keyframes(self.ref, coerced, easing)
