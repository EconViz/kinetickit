"""Serializable actions. Actions are data: no callables, no branching, no code."""

from __future__ import annotations

import math
from dataclasses import dataclass, fields
from typing import Any, ClassVar

from kinetickit.errors import ConfigurationError
from kinetickit.interaction.events import Interaction

SETTABLE_PROPERTIES = ("opacity", "visible")
SELECT_MODES = ("toggle", "select", "deselect", "clear")


@dataclass(frozen=True, slots=True)
class Action:
    """Base class. Subclasses are frozen dataclasses of JSON-able values."""

    kind: ClassVar[str] = "action"
    capability: ClassVar[Interaction] = Interaction.PLAYBACK

    def to_data(self) -> dict[str, Any]:
        out: dict[str, Any] = {"kind": self.kind}
        for f in fields(self):
            out[f.name] = getattr(self, f.name)
        return out


@dataclass(frozen=True, slots=True)
class Play(Action):
    kind: ClassVar[str] = "play"


@dataclass(frozen=True, slots=True)
class Pause(Action):
    kind: ClassVar[str] = "pause"


@dataclass(frozen=True, slots=True)
class Toggle(Action):
    """Play when paused, pause when playing."""

    kind: ClassVar[str] = "toggle"


@dataclass(frozen=True, slots=True)
class Reverse(Action):
    """Flip the playback direction."""

    kind: ClassVar[str] = "reverse"


@dataclass(frozen=True, slots=True)
class Seek(Action):
    """Jump to a time in seconds, or to a named marker."""

    kind: ClassVar[str] = "seek"
    to: float | str = 0.0

    def __post_init__(self) -> None:
        if isinstance(self.to, str):
            if not self.to:
                raise ConfigurationError("Seek marker name cannot be empty")
        elif isinstance(self.to, bool) or not math.isfinite(self.to) or self.to < 0:
            raise ConfigurationError("Seek time must be finite and non-negative")


@dataclass(frozen=True, slots=True)
class SetSpeed(Action):
    kind: ClassVar[str] = "set-speed"
    speed: float = 1.0

    def __post_init__(self) -> None:
        if isinstance(self.speed, bool) or not math.isfinite(self.speed) or self.speed <= 0:
            raise ConfigurationError("speed must be a positive number")


@dataclass(frozen=True, slots=True)
class PlayRange(Action):
    """Start a named motion: play its range once from its start and pause at its end."""

    kind: ClassVar[str] = "play-range"
    name: str = ""

    def __post_init__(self) -> None:
        if not self.name:
            raise ConfigurationError("PlayRange needs a motion name")


@dataclass(frozen=True, slots=True)
class Select(Action):
    """Change selection state. ``target=None`` means the object the event came from."""

    kind: ClassVar[str] = "select"
    capability: ClassVar[Interaction] = Interaction.SELECT
    target: str | None = None
    mode: str = "toggle"

    def __post_init__(self) -> None:
        if self.mode not in SELECT_MODES:
            raise ConfigurationError(f"select mode must be one of {SELECT_MODES}")


@dataclass(frozen=True, slots=True)
class SetProperty(Action):
    """Set a declared node property. Only ``opacity`` and ``visible`` are portable."""

    kind: ClassVar[str] = "set-property"
    target: str | None = None
    property: str = "opacity"
    value: float | bool = 1.0

    def __post_init__(self) -> None:
        if self.property not in SETTABLE_PROPERTIES:
            raise ConfigurationError(
                f"only {SETTABLE_PROPERTIES} can be set portably, not {self.property!r}"
            )
        if self.property == "visible" and not isinstance(self.value, bool):
            raise ConfigurationError("visible must be set to True or False")
        if self.property == "opacity" and (
            isinstance(self.value, bool)
            or not isinstance(self.value, (int, float))
            or not 0.0 <= self.value <= 1.0
        ):
            raise ConfigurationError("opacity must be a number in [0, 1]")


@dataclass(frozen=True, slots=True)
class ResetCamera(Action):
    kind: ClassVar[str] = "reset-camera"
    capability: ClassVar[Interaction] = Interaction.CAMERA


ACTIONS: dict[str, type[Action]] = {
    cls.kind: cls
    for cls in (
        Play,
        Pause,
        Toggle,
        Reverse,
        Seek,
        SetSpeed,
        PlayRange,
        Select,
        SetProperty,
        ResetCamera,
    )
}


def action_from_data(data: Any) -> Action:
    """Rebuild an action from ``to_data()`` output, rejecting anything that is not plain data."""
    if not isinstance(data, dict) or "kind" not in data:
        raise ConfigurationError("an action is a mapping with a 'kind'")
    kind = data["kind"]
    if kind not in ACTIONS:
        raise ConfigurationError(f"unknown action kind {kind!r}")
    cls = ACTIONS[kind]
    allowed = {f.name for f in fields(cls)}
    extra = set(data) - allowed - {"kind"}
    if extra:
        raise ConfigurationError(f"action {kind!r} has no field(s) {sorted(extra)}")
    return cls(**{k: v for k, v in data.items() if k != "kind"})
