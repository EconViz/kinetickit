"""Compile a motion against initial values and sample it at arbitrary times."""

from __future__ import annotations

import math
from bisect import bisect_right
from collections.abc import Mapping
from dataclasses import replace
from typing import Any

from kinetickit.errors import ConfigurationError
from kinetickit.interpolation import DEFAULT_REGISTRY, InterpolatorRegistry
from kinetickit.timeline.motion import Motion
from kinetickit.timeline.property import PropertyRef
from kinetickit.timeline.segment import Segment


class Timeline:
    """A motion resolved against initial property values.

    Sampling is a pure function of ``(motion, base, t)``: the same timeline and time always give
    the same state, independent of wall-clock time. Times past the end clamp to the final state.
    """

    def __init__(
        self,
        motion: Motion,
        base: Mapping[PropertyRef[Any], Any],
        registry: InterpolatorRegistry = DEFAULT_REGISTRY,
    ) -> None:
        self._registry = registry
        self._base = base

        def pre(ref: PropertyRef[Any]) -> Any:
            try:
                value = self._base[ref]
            except KeyError:
                raise ConfigurationError(f"no initial value for property {ref}") from None
            if value is None:
                raise ConfigurationError(f"property {ref} has no value to animate from")
            return value

        compiled = motion._compile(pre, registry)
        grouped: dict[PropertyRef[Any], list[Segment]] = {}
        for order, seg in enumerate(compiled.segments):
            grouped.setdefault(seg.ref, []).append(replace(seg, order=order))
        self._segments = {
            ref: tuple(sorted(segs, key=lambda s: (s.start, s.order)))
            for ref, segs in grouped.items()
        }
        self._starts = {ref: [s.start for s in segs] for ref, segs in self._segments.items()}
        self.duration = motion.duration
        markers: dict[str, float] = {}
        for name, at in compiled.markers:
            if name in markers:
                raise ConfigurationError(f"duplicate marker {name!r}")
            markers[name] = at
        self.markers: Mapping[str, float] = markers

    @property
    def properties(self) -> tuple[PropertyRef[Any], ...]:
        return tuple(self._segments)

    def segments(self, ref: PropertyRef[Any]) -> tuple[Segment, ...]:
        return self._segments.get(ref, ())

    def initial(self, ref: PropertyRef[Any]) -> Any:
        return self._base[ref]

    def _check(self, t: float) -> float:
        try:
            v = float(t)
        except (TypeError, ValueError):
            raise ConfigurationError(f"time must be a number, got {t!r}") from None
        if math.isnan(v) or v < 0.0 or math.isinf(v):
            raise ConfigurationError(f"time must be finite and non-negative, got {t!r}")
        return min(v, self.duration)

    def value(self, ref: PropertyRef[Any], t: float) -> Any:
        t = self._check(t)
        segs = self._segments.get(ref)
        if not segs:
            return self._base[ref]
        i = bisect_right(self._starts[ref], t) - 1
        return self._base[ref] if i < 0 else segs[i].value_at(t, self._registry)

    def governing(self, ref: PropertyRef[Any], t: float) -> Segment | None:
        """The segment that determines ``ref`` at time ``t`` (most recently started)."""
        segs = self._segments.get(ref)
        if not segs:
            return None
        i = bisect_right(self._starts[ref], t) - 1
        return None if i < 0 else segs[i]

    def sample(self, t: float) -> dict[PropertyRef[Any], Any]:
        """Values of every animated property at time ``t``."""
        t = self._check(t)
        return {ref: self.value(ref, t) for ref in self._segments}

    def marker_time(self, name: str) -> float:
        try:
            return self.markers[name]
        except KeyError:
            raise ConfigurationError(f"unknown marker {name!r}") from None
