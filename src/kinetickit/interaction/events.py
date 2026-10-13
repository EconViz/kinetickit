"""Portable event semantics, independent of any UI framework or renderer event object."""

from __future__ import annotations

from enum import Enum

from kinetickit.errors import ConfigurationError


class Interaction(str, Enum):
    """Interaction capabilities. Renderers declare these; bindings require them."""

    HOVER = "hover"
    CLICK = "click"
    DBLCLICK = "dblclick"
    FOCUS = "focus"
    SELECT = "select"
    DRAG = "drag"
    CAMERA = "camera"
    PLAYBACK = "playback"


class Event(str, Enum):
    """Events a binding can react to, each tied to the capability it needs."""

    HOVER_ENTER = "hover-enter"
    HOVER_LEAVE = "hover-leave"
    CLICK = "click"
    DBLCLICK = "dblclick"
    FOCUS = "focus"
    SELECT = "select"
    DESELECT = "deselect"
    CAMERA_CHANGE = "camera-change"
    PLAYBACK_END = "playback-end"

    @property
    def capability(self) -> Interaction:
        return _CAPABILITY[self]

    @property
    def needs_target(self) -> bool:
        """Whether the event belongs to a scene object (and so needs a stable node id)."""
        return self not in (Event.CAMERA_CHANGE, Event.PLAYBACK_END)


_CAPABILITY = {
    Event.HOVER_ENTER: Interaction.HOVER,
    Event.HOVER_LEAVE: Interaction.HOVER,
    Event.CLICK: Interaction.CLICK,
    Event.DBLCLICK: Interaction.DBLCLICK,
    Event.FOCUS: Interaction.FOCUS,
    Event.SELECT: Interaction.SELECT,
    Event.DESELECT: Interaction.SELECT,
    Event.CAMERA_CHANGE: Interaction.CAMERA,
    Event.PLAYBACK_END: Interaction.PLAYBACK,
}


def parse_event(value: Event | str) -> Event:
    try:
        return Event(value)
    except ValueError:
        raise ConfigurationError(
            f"unknown event {value!r}; choose from {', '.join(e.value for e in Event)}"
        ) from None
