"""The immutable motion tree and its fluent composition API.

Public code composes motions with ``then`` / ``with_`` / ``delay`` / ``repeat`` / ``reverse`` /
``yoyo`` / ``trim``. The tree is compiled by :class:`~kinetickit.timeline.timeline.Timeline`
into resolved :class:`~kinetickit.timeline.segment.Segment` values.

Start-value resolution: a tween without an explicit ``from_`` starts from the value the
property has when the tween begins (the end of the previous motion on that property, or the
scene's initial value). ``repeat``, ``yoyo`` and ``reverse`` resolve their child *once*, at the
start of the composed block, so every iteration replays the same resolved motion.

Overlap rule: when several segments of one property overlap, the segment that started most
recently wins (ties go to the one composed later).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from kinetickit.errors import ConfigurationError
from kinetickit.interpolation import InterpolatorRegistry
from kinetickit.timeline.property import PropertyRef
from kinetickit.timeline.segment import Segment
from kinetickit.timeline.time import check_duration, check_time

PreState = Callable[[PropertyRef[Any]], Any]


@dataclass(frozen=True, slots=True)
class Compiled:
    """Segments in the compiled motion's local time, plus named markers."""

    segments: tuple[Segment, ...] = ()
    markers: tuple[tuple[str, float], ...] = ()


def state_at(
    segments: list[Segment], pre: PreState, registry: InterpolatorRegistry, t: float
) -> PreState:
    """Value oracle at local time ``t`` over already-emitted ``segments``."""

    def value(ref: PropertyRef[Any]) -> Any:
        best: Segment | None = None
        for seg in segments:
            if seg.ref == ref and seg.start <= t and (best is None or seg.start >= best.start):
                best = seg
        return pre(ref) if best is None else best.value_at(t, registry)

    return value


class Motion(ABC):
    """An immutable description of change over time."""

    @property
    @abstractmethod
    def duration(self) -> float:
        """Total length in seconds."""

    @abstractmethod
    def _compile(self, pre: PreState, registry: InterpolatorRegistry) -> Compiled:
        """Resolve into local-time segments given the property state at the motion's start."""

    @property
    def stages(self) -> tuple[tuple[Motion, ...], ...]:
        """The sequential stages of this motion; each stage is a tuple of parallel members."""
        return ((self,),)

    def targets(self) -> frozenset[PropertyRef[Any]]:
        """Every property this motion animates."""
        return frozenset()

    # -- fluent composition -------------------------------------------------------------
    def then(self, other: Motion, *, gap: float = 0.0) -> Motion:
        """Start ``other`` after every member of the current stage has finished."""
        _check_motion(other)
        gap = check_time(gap, "gap")
        return Chain((*self._as_stages(), Stage((other,), (0.0,), gap)))

    def with_(self, other: Motion, *, offset: float = 0.0) -> Motion:
        """Start ``other`` with the current stage, ``offset`` seconds after the stage begins."""
        _check_motion(other)
        offset = check_time(offset, "offset")
        stages = self._as_stages()
        last = stages[-1]
        merged = Stage((*last.members, other), (*last.offsets, offset), last.gap)
        return Chain((*stages[:-1], merged))

    def delay(self, seconds: float) -> Motion:
        return Delay(self, check_time(seconds, "delay"))

    def hold(self, seconds: float) -> Motion:
        """Append a pause so the final state is held for ``seconds``."""
        return self.then(Hold(check_duration(seconds, "hold")))

    def repeat(self, times: int, *, yoyo: bool = False) -> Motion:
        """Play the motion exactly ``times`` times in total."""
        return Repeat(self, times, yoyo)

    def yoyo(self) -> Motion:
        """Play forward then backward, sharing the turnaround endpoint."""
        return Repeat(self, 2, True)

    def reverse(self) -> Motion:
        return Reverse(self)

    def trim(self, start: float = 0.0, end: float | None = None) -> Motion:
        """Keep only the ``[start, end]`` window of this motion."""
        return Trim(self, check_time(start, "start"), end)

    def mark(self, name: str, at: float = 0.0) -> Motion:
        """Attach a named marker ``at`` seconds after this motion starts."""
        return Marked(self, name, check_time(at, "at"))

    def _as_stages(self) -> tuple[Stage, ...]:
        return (Stage((self,), (0.0,), 0.0),)


def _check_motion(value: object) -> None:
    if not isinstance(value, Motion):
        raise ConfigurationError(f"expected a Motion, got {type(value).__name__}")


@dataclass(frozen=True, slots=True)
class Stage:
    members: tuple[Motion, ...]
    offsets: tuple[float, ...]
    gap: float = 0.0

    @property
    def span(self) -> float:
        return max(
            (o + m.duration for m, o in zip(self.members, self.offsets, strict=True)), default=0.0
        )


@dataclass(frozen=True, slots=True)
class Chain(Motion):
    """Sequential stages of parallel members (``a -> [b + c] -> d``)."""

    layout: tuple[Stage, ...]

    @property
    def duration(self) -> float:
        return sum(s.gap + s.span for s in self.layout)

    @property
    def stages(self) -> tuple[tuple[Motion, ...], ...]:
        return tuple(s.members for s in self.layout)

    def _as_stages(self) -> tuple[Stage, ...]:
        return self.layout

    def targets(self) -> frozenset[PropertyRef[Any]]:
        return frozenset(t for s in self.layout for m in s.members for t in m.targets())

    def _compile(self, pre: PreState, registry: InterpolatorRegistry) -> Compiled:
        acc: list[Segment] = []
        markers: list[tuple[str, float]] = []
        t = 0.0
        for stage in self.layout:
            t += stage.gap
            stage_end = t
            for member, offset in zip(stage.members, stage.offsets, strict=True):
                s0 = t + offset
                compiled = member._compile(state_at(acc, pre, registry, s0), registry)
                acc.extend(seg.shifted(s0) for seg in compiled.segments)
                markers.extend((n, mt + s0) for n, mt in compiled.markers)
                stage_end = max(stage_end, s0 + member.duration)
            t = stage_end
        return Compiled(tuple(acc), tuple(markers))


@dataclass(frozen=True, slots=True)
class Hold(Motion):
    """A pause with no segments."""

    seconds: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "seconds", check_duration(self.seconds, "hold"))

    @property
    def duration(self) -> float:
        return self.seconds

    def _compile(self, pre: PreState, registry: InterpolatorRegistry) -> Compiled:
        return Compiled()


@dataclass(frozen=True, slots=True)
class Delay(Motion):
    child: Motion
    seconds: float

    def targets(self) -> frozenset[PropertyRef[Any]]:
        return self.child.targets()

    @property
    def duration(self) -> float:
        return self.seconds + self.child.duration

    def _compile(self, pre: PreState, registry: InterpolatorRegistry) -> Compiled:
        inner = self.child._compile(pre, registry)
        return Compiled(
            tuple(s.shifted(self.seconds) for s in inner.segments),
            tuple((n, t + self.seconds) for n, t in inner.markers),
        )


@dataclass(frozen=True, slots=True)
class Repeat(Motion):
    child: Motion
    times: int
    alternate: bool = False

    def __post_init__(self) -> None:
        if isinstance(self.times, bool) or not isinstance(self.times, int) or self.times < 1:
            raise ConfigurationError(f"repeat count must be a positive integer, got {self.times!r}")

    def targets(self) -> frozenset[PropertyRef[Any]]:
        return self.child.targets()

    @property
    def duration(self) -> float:
        return self.child.duration * self.times

    def _compile(self, pre: PreState, registry: InterpolatorRegistry) -> Compiled:
        inner = self.child._compile(pre, registry)
        d = self.child.duration
        out: list[Segment] = []
        for i in range(self.times):
            reverse = self.alternate and i % 2 == 1
            out.extend((s.mirrored(d) if reverse else s).shifted(i * d) for s in inner.segments)
        return Compiled(tuple(out), inner.markers)


@dataclass(frozen=True, slots=True)
class Reverse(Motion):
    child: Motion

    def targets(self) -> frozenset[PropertyRef[Any]]:
        return self.child.targets()

    @property
    def duration(self) -> float:
        return self.child.duration

    def _compile(self, pre: PreState, registry: InterpolatorRegistry) -> Compiled:
        inner = self.child._compile(pre, registry)
        d = self.child.duration
        return Compiled(
            tuple(s.mirrored(d) for s in inner.segments),
            tuple((n, d - t) for n, t in inner.markers),
        )


@dataclass(frozen=True, slots=True)
class Trim(Motion):
    child: Motion
    start: float
    end: float | None = None

    def __post_init__(self) -> None:
        end = self.child.duration if self.end is None else check_time(self.end, "end")
        if not self.start <= end <= self.child.duration:
            raise ConfigurationError(
                f"trim window [{self.start}, {end}] must lie within [0, {self.child.duration}]"
            )
        object.__setattr__(self, "end", end)

    def targets(self) -> frozenset[PropertyRef[Any]]:
        return self.child.targets()

    @property
    def duration(self) -> float:
        assert self.end is not None
        return self.end - self.start

    def _compile(self, pre: PreState, registry: InterpolatorRegistry) -> Compiled:
        assert self.end is not None
        a, b = self.start, self.end
        inner = self.child._compile(pre, registry)
        kept: list[Segment] = []
        for ref in dict.fromkeys(s.ref for s in inner.segments):
            mine = [s for s in inner.segments if s.ref == ref]
            clipped = [c.shifted(-a) for s in mine if (c := s.clipped(a, b)) is not None]
            entry = state_at(list(mine), pre, registry, a)(ref)
            first = min((c.start for c in clipped), default=b - a)
            if first > 0.0:
                kept.append(Segment(ref, 0.0, first, entry, entry))
            kept.extend(clipped)
        markers = tuple((n, t - a) for n, t in inner.markers if a <= t <= b)
        return Compiled(tuple(kept), markers)


@dataclass(frozen=True, slots=True)
class Marked(Motion):
    child: Motion
    name: str
    at: float = 0.0

    def __post_init__(self) -> None:
        if not self.name:
            raise ConfigurationError("a marker needs a non-empty name")

    def targets(self) -> frozenset[PropertyRef[Any]]:
        return self.child.targets()

    @property
    def duration(self) -> float:
        return self.child.duration

    def _compile(self, pre: PreState, registry: InterpolatorRegistry) -> Compiled:
        inner = self.child._compile(pre, registry)
        return Compiled(inner.segments, ((self.name, self.at), *inner.markers))
