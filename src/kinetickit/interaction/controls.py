"""Which playback controls an interactive output offers, and its keyboard map."""

from __future__ import annotations

from dataclasses import dataclass

from kinetickit.errors import ConfigurationError

ALL_CONTROLS = ("first", "step", "play", "last", "seek", "speed", "loop", "markers", "reset")
DEFAULT_KEYS = {
    "Space": "toggle play/pause",
    "ArrowLeft": "previous frame",
    "ArrowRight": "next frame",
    "Home": "go to start",
    "End": "go to end",
}


@dataclass(frozen=True, slots=True)
class PlaybackControls:
    """A neutral description of the control surface; renderers decide how to draw it."""

    show: tuple[str, ...] = ALL_CONTROLS
    keyboard: bool = True

    def __post_init__(self) -> None:
        unknown = set(self.show) - set(ALL_CONTROLS)
        if unknown:
            raise ConfigurationError(
                f"unknown controls {sorted(unknown)}; choose from {ALL_CONTROLS}"
            )
        object.__setattr__(self, "show", tuple(dict.fromkeys(self.show)))

    @property
    def keys(self) -> dict[str, str]:
        return dict(DEFAULT_KEYS) if self.keyboard else {}

    def has(self, name: str) -> bool:
        return name in self.show
