"""The neutral text-asset contract.

KineticKit never loads fonts or shapes text. A consumer (or an adapter such as a GlyphKit
integration) supplies an already laid-out :class:`TextAsset`; KineticKit only places, styles,
animates and exports it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from kinetickit.errors import ConfigurationError
from kinetickit.geometry.two_d import Path2D


@dataclass(frozen=True, slots=True)
class FontResource:
    """Font bytes a text asset needs so self-contained exports keep its appearance."""

    family: str
    data: bytes
    format: str = "truetype"
    weight: str = "normal"
    style: str = "normal"

    def __post_init__(self) -> None:
        if not self.family:
            raise ConfigurationError("a font resource needs a family name")
        if self.format not in ("truetype", "opentype", "woff", "woff2"):
            raise ConfigurationError(f"unsupported font format {self.format!r}")


@dataclass(frozen=True, slots=True)
class GlyphShape:
    """One laid-out glyph: its outline in asset space (+x right, +y up, baseline at y=0)."""

    outline: Path2D
    character: str = ""
    cluster: int = 0


@runtime_checkable
class TextAssetLike(Protocol):
    """What the scene needs from any external text layout."""

    @property
    def text(self) -> str: ...
    @property
    def glyphs(self) -> tuple[GlyphShape, ...]: ...
    @property
    def width(self) -> float: ...
    @property
    def height(self) -> float: ...
    @property
    def fonts(self) -> tuple[FontResource, ...]: ...


@dataclass(frozen=True, slots=True)
class TextAsset:
    """A plain immutable implementation of :class:`TextAssetLike`."""

    text: str
    glyphs: tuple[GlyphShape, ...]
    width: float
    height: float
    fonts: tuple[FontResource, ...] = ()

    def __post_init__(self) -> None:
        if self.width < 0 or self.height < 0:
            raise ConfigurationError("text asset dimensions must be non-negative")
        object.__setattr__(self, "glyphs", tuple(self.glyphs))
        object.__setattr__(self, "fonts", tuple(self.fonts))
