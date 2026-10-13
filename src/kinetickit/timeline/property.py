"""Stable references to animatable properties."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from kinetickit.errors import ConfigurationError

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class PropertyRef(Generic[T]):
    """Identifies one property of one object: ``(node_id, path)`` plus its declared type."""

    node_id: str
    path: str
    value_type: type

    def coerce(self, value: Any) -> Any:
        """Convert ``value`` to the declared type using its ``coerce`` hook or constructor."""
        if type(value) is self.value_type:
            return value
        hook = getattr(self.value_type, "coerce", None)
        if callable(hook):
            return hook(value)
        if isinstance(value, self.value_type) and not (
            self.value_type is float and isinstance(value, bool)
        ):
            return value
        if self.value_type in (float, int) and isinstance(value, (int, float)):
            return self.value_type(value)
        try:
            return self.value_type(value)
        except Exception as exc:
            raise ConfigurationError(
                f"cannot use {value!r} for {self.node_id}.{self.path} ({self.value_type.__name__})"
            ) from exc

    def __str__(self) -> str:
        return f"{self.node_id}.{self.path}"
