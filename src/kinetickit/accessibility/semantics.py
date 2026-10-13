"""Visualization-independent accessibility metadata for scene objects."""

from __future__ import annotations

from dataclasses import dataclass

from kinetickit.errors import ConfigurationError

ROLES = (
    "img",
    "graphics-symbol",
    "graphics-object",
    "graphics-document",
    "figure",
    "group",
    "list",
    "listitem",
    "button",
    "link",
    "heading",
    "presentation",
)


@dataclass(frozen=True, slots=True)
class Semantics:
    """What an object *means*, for assistive technology and text alternatives.

    ``reading_order`` ranks objects for linear reading (lower first; unranked objects follow in
    scene order). ``hidden=True`` marks purely decorative objects.
    """

    role: str | None = None
    label: str | None = None
    description: str | None = None
    reading_order: int | None = None
    hidden: bool = False

    def __post_init__(self) -> None:
        if self.role is not None and self.role not in ROLES:
            raise ConfigurationError(f"unknown role {self.role!r}; choose from {', '.join(ROLES)}")
        for name in ("label", "description"):
            value = getattr(self, name)
            if value is not None and not (isinstance(value, str) and value.strip()):
                raise ConfigurationError(f"semantics {name} must be a non-empty string")
        if self.reading_order is not None and (
            isinstance(self.reading_order, bool) or not isinstance(self.reading_order, int)
        ):
            raise ConfigurationError("reading_order must be an integer")
        if self.hidden and (self.label or self.description):
            raise ConfigurationError(
                "a hidden (decorative) object cannot have a label or description"
            )

    @property
    def is_empty(self) -> bool:
        return self == Semantics()
