"""The public interpolation extension protocol."""

from __future__ import annotations

from enum import Enum
from typing import Protocol, TypeVar, runtime_checkable

T = TypeVar("T")
T_co = TypeVar("T_co", covariant=True)


class Extrapolation(Enum):
    """How a segment behaves for progress outside ``[0, 1]``."""

    CLAMP = "clamp"
    EXTEND = "extend"


@runtime_checkable
class Interpolator(Protocol[T]):
    """Blend two values of one type.

    Implementations must return ``start`` at ``progress == 0`` and ``end`` at
    ``progress == 1``, and must be pure functions of their arguments.
    """

    def interpolate(self, start: T, end: T, progress: float) -> T: ...
