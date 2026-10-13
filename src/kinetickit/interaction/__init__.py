"""Portable events, declarative actions, playback state and capability-aware degradation."""

from __future__ import annotations

from kinetickit.interaction.actions import (
    Action,
    Pause,
    Play,
    PlayRange,
    ResetCamera,
    Reverse,
    Seek,
    Select,
    SetProperty,
    SetSpeed,
    Toggle,
    action_from_data,
)
from kinetickit.interaction.bindings import (
    Binding,
    Degradation,
    InteractionPlan,
    InteractionSpec,
    plan_interactions,
)
from kinetickit.interaction.controls import ALL_CONTROLS, PlaybackControls
from kinetickit.interaction.events import Event, Interaction, parse_event
from kinetickit.interaction.player import PlayerState

__all__ = [
    "ALL_CONTROLS",
    "Action",
    "Binding",
    "Degradation",
    "Event",
    "Interaction",
    "InteractionPlan",
    "InteractionSpec",
    "Pause",
    "Play",
    "PlayRange",
    "PlaybackControls",
    "PlayerState",
    "ResetCamera",
    "Reverse",
    "Seek",
    "Select",
    "SetProperty",
    "SetSpeed",
    "Toggle",
    "action_from_data",
    "parse_event",
    "plan_interactions",
]
