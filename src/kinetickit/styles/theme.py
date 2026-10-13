"""Design tokens. ``minimal`` is the only built-in theme."""

from __future__ import annotations

from dataclasses import dataclass, fields, replace
from typing import Any

from kinetickit.errors import ConfigurationError
from kinetickit.interpolation import Color


@dataclass(frozen=True, slots=True)
class Theme:
    """Neutral tokens with no domain roles. Every token is a :class:`Color` or a size."""

    background: Color
    text: Color
    text_secondary: Color
    stroke_primary: Color
    stroke_secondary: Color
    fill: Color
    marker: Color
    guide: Color
    grid: Color
    selection: Color
    focus: Color
    overlay: Color
    stroke_width: float = 2.0
    guide_width: float = 1.0
    marker_size: float = 5.0
    font_size: float = 14.0
    margin: float = 48.0

    def merge(self, **overrides: Any) -> Theme:
        """A sparse override: unspecified tokens keep their value."""
        known = {f.name for f in fields(self)}
        unknown = set(overrides) - known
        if unknown:
            raise ConfigurationError(f"unknown theme tokens: {', '.join(sorted(unknown))}")
        conv = {
            k: (Color.parse(v) if k in known and isinstance(getattr(self, k), Color) else v)
            for k, v in overrides.items()
        }
        return replace(self, **conv)  # type: ignore[arg-type]


def _c(value: str) -> Color:
    return Color.parse(value)


MinimalTheme = Theme(
    background=_c("#ffffff"),
    text=_c("#1f2933"),
    text_secondary=_c("#616e7c"),
    stroke_primary=_c("#1f2933"),
    stroke_secondary=_c("#9aa5b1"),
    fill=_c("#3e7cb1"),
    marker=_c("#e4572e"),
    guide=_c("#9aa5b1"),
    grid=_c("#e4e7eb"),
    selection=_c("#e4572e"),
    focus=_c("#0b6bcb"),
    overlay=_c("#ffffffd9"),
)
