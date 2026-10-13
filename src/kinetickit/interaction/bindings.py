"""Bindings from events on stable object ids to declarative actions, plus validation."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

from kinetickit.errors import CapabilityError, ConfigurationError
from kinetickit.interaction.actions import (
    Action,
    PlayRange,
    Seek,
    Select,
    SetProperty,
    action_from_data,
)
from kinetickit.interaction.events import Event, Interaction, parse_event

if TYPE_CHECKING:
    from kinetickit.renderers.capabilities import RendererCapabilities


class Degradation(str, Enum):
    """What to do with an optional binding the output cannot support."""

    DROP = "drop"  # remove it and say so in the report
    FAIL = "fail"  # treat every unsupported binding as an error


@dataclass(frozen=True, slots=True)
class Binding:
    """When ``event`` happens on ``target`` run ``actions``.

    ``target`` is a stable scene-node id (``None`` for scene-wide events such as camera changes).
    ``required=True`` makes an unsupported output fail validation instead of dropping the binding.
    """

    event: Event
    actions: tuple[Action, ...]
    target: str | None = None
    required: bool = False

    def __post_init__(self) -> None:
        event = parse_event(self.event)
        object.__setattr__(self, "event", event)
        acts = (self.actions,) if isinstance(self.actions, Action) else tuple(self.actions)
        if not acts or not all(isinstance(a, Action) for a in acts):
            raise ConfigurationError("a binding needs one or more Action values (no callables)")
        object.__setattr__(self, "actions", acts)
        if event.needs_target and self.target is None:
            raise ConfigurationError(f"event {event.value!r} needs a target node id")
        if not event.needs_target and self.target is not None:
            raise ConfigurationError(f"event {event.value!r} is scene-wide and takes no target")

    @property
    def capabilities(self) -> frozenset[Interaction]:
        return frozenset({self.event.capability, *(a.capability for a in self.actions)})

    def to_data(self) -> dict[str, Any]:
        return {
            "event": self.event.value,
            "target": self.target,
            "required": self.required,
            "actions": [a.to_data() for a in self.actions],
        }

    @classmethod
    def from_data(cls, data: Mapping[str, Any]) -> Binding:
        return cls(
            Event(data["event"]),
            tuple(action_from_data(a) for a in data["actions"]),
            data.get("target"),
            bool(data.get("required", False)),
        )


@dataclass(frozen=True)
class InteractionSpec:
    """The complete, serializable interaction description of an animation.

    ``ranges`` names time ranges ("named motions") for :class:`PlayRange`. Interaction state is
    plain data here; it never holds renderer-native event objects.
    """

    bindings: tuple[Binding, ...] = ()
    ranges: Mapping[str, tuple[float, float]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "bindings", tuple(self.bindings))
        ranges: dict[str, tuple[float, float]] = {}
        for name, span in dict(self.ranges).items():
            a, b = float(span[0]), float(span[1])
            if not name or not 0.0 <= a <= b:
                raise ConfigurationError(f"range {name!r} needs 0 <= start <= end")
            ranges[name] = (a, b)
        object.__setattr__(self, "ranges", ranges)

    def required(self) -> frozenset[Interaction]:
        return frozenset(c for b in self.bindings if b.required for c in b.capabilities)

    def optional(self) -> frozenset[Interaction]:
        return (
            frozenset(c for b in self.bindings if not b.required for c in b.capabilities)
            - self.required()
        )

    def to_data(self) -> dict[str, Any]:
        return {
            "bindings": [b.to_data() for b in self.bindings],
            "ranges": {k: list(v) for k, v in self.ranges.items()},
            "required": sorted(c.value for c in self.required()),
            "optional": sorted(c.value for c in self.optional()),
        }

    @classmethod
    def from_data(cls, data: Mapping[str, Any]) -> InteractionSpec:
        return cls(
            tuple(Binding.from_data(b) for b in data.get("bindings", ())),
            {k: tuple(v) for k, v in data.get("ranges", {}).items()},
        )

    # -- validation --------------------------------------------------------------------
    def validate(
        self, scene: Any, markers: Iterable[str] = (), duration: float | None = None
    ) -> None:
        """Check every reference against the scene: ids, properties, markers and ranges."""
        marker_set = set(markers)
        for b in self.bindings:
            targets: list[str | None] = [b.target]
            for a in b.actions:
                if isinstance(a, (Select, SetProperty)):
                    targets.append(a.target)
                if isinstance(a, PlayRange) and a.name not in self.ranges:
                    raise ConfigurationError(f"action references unknown motion {a.name!r}")
                if isinstance(a, Seek) and isinstance(a.to, str) and a.to not in marker_set:
                    raise ConfigurationError(f"action references unknown marker {a.to!r}")
                if (
                    isinstance(a, Seek)
                    and not isinstance(a.to, str)
                    and duration is not None
                    and a.to > duration
                ):
                    raise ConfigurationError(f"seek time {a.to} is past the duration {duration}")
                if isinstance(a, SetProperty):
                    node = scene.find(a.target) if a.target else None
                    if a.target and node is None:
                        raise ConfigurationError(f"action references missing node {a.target!r}")
            for t in targets:
                if t is not None and scene.find(t) is None:
                    raise ConfigurationError(f"binding references missing node {t!r}")
        if duration is not None:
            for name, (_, end) in self.ranges.items():
                if end > duration:
                    raise ConfigurationError(f"range {name!r} ends after the duration {duration}")


@dataclass(frozen=True)
class InteractionPlan:
    """The bindings an output will honour and those it dropped (with reasons)."""

    active: tuple[Binding, ...]
    dropped: tuple[tuple[Binding, str], ...] = ()

    @property
    def preserved(self) -> tuple[str, ...]:
        return tuple(sorted({c.value for b in self.active for c in b.capabilities}))

    @property
    def degraded(self) -> tuple[str, ...]:
        return tuple(f"{b.event.value} on {b.target or 'scene'}: {why}" for b, why in self.dropped)


def plan_interactions(
    spec: InteractionSpec | None,
    capabilities: RendererCapabilities,
    policy: Degradation = Degradation.DROP,
) -> InteractionPlan:
    """Resolve ``spec`` against an output's declared interaction capabilities.

    Unsupported *required* bindings (or any, with ``Degradation.FAIL``) raise
    :class:`CapabilityError` before output is produced; the rest are dropped explicitly.
    """
    if spec is None or not spec.bindings:
        return InteractionPlan(())
    supported = {Interaction(v) for v in capabilities.interactions}
    active: list[Binding] = []
    dropped: list[tuple[Binding, str]] = []
    problems: list[str] = []
    for b in spec.bindings:
        missing = sorted(c.value for c in b.capabilities if c not in supported)
        if not missing:
            active.append(b)
            continue
        why = f"{capabilities.name!r} does not support {', '.join(missing)}"
        if b.required or policy is Degradation.FAIL:
            problems.append(f"{b.event.value} on {b.target or 'scene'}: {why}")
        else:
            dropped.append((b, why))
    if problems:
        raise CapabilityError(
            "unsupported interactions:\n  - " + "\n  - ".join(problems),
            missing=tuple(sorted({f"interaction:{p.split(' ')[0]}" for p in problems})),
        )
    return InteractionPlan(tuple(active), tuple(dropped))
