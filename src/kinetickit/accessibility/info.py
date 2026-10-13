"""Animation-level accessibility information and reduced-motion policy."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from kinetickit.errors import ConfigurationError


@dataclass(frozen=True, slots=True)
class ReducedMotion:
    """What to show when the viewer asks for reduced motion.

    The representative state replaces autoplayed movement: ``"final"`` (default), ``"first"`` or
    ``"time"`` (explicit ``time`` in seconds). Playback stays available on explicit request.
    """

    mode: str = "final"
    time: float | None = None

    def __post_init__(self) -> None:
        if self.mode not in ("final", "first", "time"):
            raise ConfigurationError("reduced-motion mode must be final, first or time")
        if self.mode == "time":
            if self.time is None or not math.isfinite(self.time) or self.time < 0:
                raise ConfigurationError("reduced-motion mode 'time' needs a non-negative time")
        elif self.time is not None:
            raise ConfigurationError("a time is only valid with mode='time'")

    def representative_time(self, duration: float) -> float:
        if self.mode == "first":
            return 0.0
        if self.mode == "time":
            assert self.time is not None
            return min(self.time, duration)
        return duration


@dataclass(frozen=True, slots=True)
class AccessibilityInfo:
    """Titles and text alternatives for the whole animation.

    ``alt_text`` is the short alternative (GIF, images); ``long_description`` the full text
    alternative. Outputs reuse these instead of inventing descriptions.
    """

    title: str | None = None
    description: str | None = None
    alt_text: str | None = None
    long_description: str | None = None
    lang: str = "en"
    reduced_motion: ReducedMotion = field(default_factory=ReducedMotion)

    def __post_init__(self) -> None:
        for name in ("title", "description", "alt_text", "long_description"):
            v = getattr(self, name)
            if v is not None and not (isinstance(v, str) and v.strip()):
                raise ConfigurationError(f"{name} must be a non-empty string")

    @property
    def text_alternative(self) -> str | None:
        return self.alt_text or self.description or self.title
