"""An immutable RGBA color and its interpolator."""

from __future__ import annotations

import re
from dataclasses import dataclass

from kinetickit.errors import ConfigurationError

_HEX = re.compile(r"^#([0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
_NAMED = {
    "black": "#000000",
    "white": "#ffffff",
    "red": "#ff0000",
    "green": "#008000",
    "blue": "#0000ff",
    "gray": "#808080",
    "grey": "#808080",
    "transparent": "#00000000",
    "none": "#00000000",
}


def _channel(v: float, name: str) -> float:
    f = float(v)
    if not 0.0 <= f <= 1.0:
        raise ConfigurationError(f"color channel {name} must lie in [0, 1], got {v!r}")
    return f


@dataclass(frozen=True, slots=True)
class Color:
    """sRGB color with channels in ``[0, 1]``."""

    r: float
    g: float
    b: float
    a: float = 1.0

    def __post_init__(self) -> None:
        for name in ("r", "g", "b", "a"):
            object.__setattr__(self, name, _channel(getattr(self, name), name))

    @classmethod
    def parse(cls, value: Color | str | tuple[float, ...]) -> Color:
        if isinstance(value, Color):
            return value
        if isinstance(value, str):
            text = _NAMED.get(value.strip().lower(), value.strip())
            m = _HEX.match(text)
            if not m:
                raise ConfigurationError(f"unrecognized color {value!r}")
            digits = m.group(1)
            if len(digits) in (3, 4):
                digits = "".join(c * 2 for c in digits)
            vals = [int(digits[i : i + 2], 16) / 255.0 for i in range(0, len(digits), 2)]
            return cls(*vals)
        return cls(*value)

    coerce = parse

    def to_hex(self) -> str:
        r, g, b, a = (round(c * 255) for c in (self.r, self.g, self.b, self.a))
        return f"#{r:02x}{g:02x}{b:02x}" + ("" if a == 255 else f"{a:02x}")

    def with_alpha(self, alpha: float) -> Color:
        return Color(self.r, self.g, self.b, alpha)

    def as_tuple(self) -> tuple[float, float, float, float]:
        return (self.r, self.g, self.b, self.a)


class ColorInterpolator:
    """Channel-wise linear interpolation in sRGB, clamped to the valid gamut."""

    def interpolate(self, start: Color, end: Color, progress: float) -> Color:
        if progress == 0.0:
            return start
        if progress == 1.0:
            return end
        return Color(
            *(
                min(1.0, max(0.0, a + (b - a) * progress))
                for a, b in zip(start.as_tuple(), end.as_tuple(), strict=True)
            )
        )
