"""Capability declarations and early validation.

Renderers declare *what they can do*, never which library does it. Exporters validate the
requirements of an animation against these declarations before producing any output.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from kinetickit.errors import CapabilityError

# Dimensionality
DIM_2D = "2d"
DIM_PROJECTED_3D = "projected-3d"
DIM_NATIVE_3D = "native-3d"
# Output kinds
OUT_RASTER_FRAME = "raster-frame"
OUT_VECTOR_DOCUMENT = "vector-document"
OUT_ANIMATED_DOCUMENT = "animated-document"
OUT_INTERACTIVE_DOCUMENT = "interactive-document"

_HINTS = {
    "feature:clip": "clipping is not supported by this renderer",
    "feature:camera-animation": "animated cameras are not supported by this renderer",
    "feature:z-animation": "animating z-order is not supported; animate opacity instead",
    "geometry:mesh": "meshes need a 3D-capable renderer such as 'interactive' or 'raster'",
    "geometry:surface": "surfaces need a 3D-capable renderer such as 'interactive' or 'raster'",
    "dimension:native-3d": "native 3D (rotatable) output needs the 'interactive' renderer",
    "interaction:drag": "drag needs the 'interactive' renderer",
    "interaction:camera": "camera interaction needs the 'interactive' renderer",
}


@dataclass(frozen=True, slots=True)
class Requirements:
    """What an animation (plus export request) needs from a renderer."""

    dimensions: frozenset[str] = frozenset()
    geometry: frozenset[str] = frozenset()
    features: frozenset[str] = frozenset()
    outputs: frozenset[str] = frozenset()
    interactions: frozenset[str] = frozenset()

    def tokens(self) -> frozenset[str]:
        return frozenset(
            [f"dimension:{x}" for x in self.dimensions]
            + [f"geometry:{x}" for x in self.geometry]
            + [f"feature:{x}" for x in self.features]
            + [f"output:{x}" for x in self.outputs]
            + [f"interaction:{x}" for x in self.interactions]
        )

    def merged(self, other: Requirements) -> Requirements:
        return Requirements(
            self.dimensions | other.dimensions,
            self.geometry | other.geometry,
            self.features | other.features,
            self.outputs | other.outputs,
            self.interactions | other.interactions,
        )


@dataclass(frozen=True, slots=True)
class RendererCapabilities:
    """The structured capability declaration of one renderer."""

    name: str
    dimensions: frozenset[str] = frozenset()
    geometry: frozenset[str] = frozenset()
    features: frozenset[str] = frozenset()
    outputs: frozenset[str] = frozenset()
    interactions: frozenset[str] = frozenset()
    notes: tuple[str, ...] = field(default=())

    def supports(self, token: str) -> bool:
        kind, _, value = token.partition(":")
        if kind == "dimension":
            if value == "3d":  # any 3D-capable renderer satisfies a generic 3D scene
                return bool({DIM_PROJECTED_3D, DIM_NATIVE_3D} & self.dimensions)
            return value in self.dimensions
        pool = {
            "geometry": self.geometry,
            "feature": self.features,
            "output": self.outputs,
            "interaction": self.interactions,
        }.get(kind)
        return pool is not None and value in pool

    def missing(self, required: Requirements) -> tuple[str, ...]:
        return tuple(sorted(t for t in required.tokens() if not self.supports(t)))

    def validate(self, required: Requirements) -> None:
        """Raise :class:`CapabilityError` listing every missing capability, before any output."""
        missing = self.missing(required)
        if not missing:
            return
        lines = [f"  - {t}: {_HINTS.get(t, 'not supported')}" for t in missing]
        raise CapabilityError(
            f"renderer {self.name!r} cannot satisfy this animation:\n" + "\n".join(lines),
            missing=missing,
        )


def require(
    *,
    dimensions: Iterable[str] = (),
    geometry: Iterable[str] = (),
    features: Iterable[str] = (),
    outputs: Iterable[str] = (),
    interactions: Iterable[str] = (),
) -> Requirements:
    return Requirements(
        frozenset(dimensions),
        frozenset(geometry),
        frozenset(features),
        frozenset(outputs),
        frozenset(interactions),
    )
