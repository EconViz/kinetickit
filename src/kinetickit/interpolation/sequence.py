"""Element-wise interpolation of equal-length numeric sequences."""

from __future__ import annotations

from collections.abc import Sequence

from kinetickit.errors import ConfigurationError
from kinetickit.interpolation.numeric import NumberInterpolator

_number = NumberInterpolator()


class SequenceInterpolator:
    """Interpolate tuples or lists of numbers element by element."""

    def interpolate(
        self, start: Sequence[float], end: Sequence[float], progress: float
    ) -> tuple[float, ...]:
        if len(start) != len(end):
            raise ConfigurationError(
                f"cannot interpolate sequences of different length ({len(start)} vs {len(end)})"
            )
        return tuple(_number.interpolate(a, b, progress) for a, b in zip(start, end, strict=True))
