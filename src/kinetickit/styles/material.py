"""Portable minimum material and color-scale data."""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass

from kinetickit.errors import ConfigurationError
from kinetickit.interpolation import Color


@dataclass(frozen=True, slots=True)
class Material:
    """Blinn-Phong style surface response, deliberately the smallest portable subset.

    ``ambient`` and ``diffuse`` scale the base color; ``specular`` adds a white highlight with
    exponent ``shininess``. All outputs bake these into flat per-face colors.
    """

    ambient: float = 0.35
    diffuse: float = 0.65
    specular: float = 0.0
    shininess: float = 32.0

    def __post_init__(self) -> None:
        for name in ("ambient", "diffuse", "specular"):
            v = getattr(self, name)
            if not math.isfinite(v) or not 0.0 <= v <= 1.0:
                raise ConfigurationError(f"material {name} must lie in [0, 1], got {v!r}")
        if not math.isfinite(self.shininess) or self.shininess < 1.0:
            raise ConfigurationError("material shininess must be at least 1")


class MaterialInterpolator:
    def interpolate(self, start: Material, end: Material, progress: float) -> Material:
        if progress == 0.0:
            return start
        if progress == 1.0:
            return end

        def lerp(a: float, b: float) -> float:
            return a + (b - a) * progress

        return Material(
            lerp(start.ambient, end.ambient),
            lerp(start.diffuse, end.diffuse),
            lerp(start.specular, end.specular),
            lerp(start.shininess, end.shininess),
        )


@dataclass(frozen=True, slots=True)
class ColorScale:
    """Piecewise-linear color ramp over ``[0, 1]``."""

    stops: tuple[tuple[float, Color | str], ...]

    def __post_init__(self) -> None:
        stops = tuple((float(t), Color.parse(c)) for t, c in self.stops)
        if len(stops) < 2:
            raise ConfigurationError("a color scale needs at least two stops")
        ts = [t for t, _ in stops]
        if ts[0] != 0.0 or ts[-1] != 1.0 or any(b <= a for a, b in itertools.pairwise(ts)):
            raise ConfigurationError("color scale stops must increase strictly from 0 to 1")
        object.__setattr__(self, "stops", stops)

    def at(self, t: float) -> Color:
        t = min(1.0, max(0.0, t))
        for (t0, raw0), (t1, raw1) in zip(self.stops, self.stops[1:], strict=False):
            if t <= t1:
                c0, c1 = Color.parse(raw0), Color.parse(raw1)
                k = (t - t0) / (t1 - t0)
                return Color(
                    *(a + (b - a) * k for a, b in zip(c0.as_tuple(), c1.as_tuple(), strict=True))
                )
        return Color.parse(self.stops[-1][1])

    @classmethod
    def viridis_like(cls) -> ColorScale:
        return cls(((0.0, "#440154"), (0.5, "#21908d"), (1.0, "#fde725")))
