"""Raster sizing: logical pixels, physical size and DPI."""

from __future__ import annotations

from dataclasses import dataclass, field

from kinetickit.errors import ConfigurationError
from kinetickit.interpolation import Color
from kinetickit.layout import Margins
from kinetickit.styles import MinimalTheme, Theme

LOGICAL_DPI = 96.0  # one logical pixel is 1/96 inch (the CSS reference pixel)
MAX_DPI = 1200


@dataclass(frozen=True)
class RasterSettings:
    """How big to render. Give at most one of ``size_inches`` or ``pixels``.

    By default the drawing is ``width`` x ``height`` logical pixels (1/96 inch each) and the output
    has ``width * dpi / 96`` by ``height * dpi / 96`` pixels. ``size_inches`` sets the physical size
    instead; ``pixels`` fixes the exact output dimensions and derives the logical size from ``dpi``.
    """

    width: float = 640.0
    height: float = 400.0
    dpi: int = 96
    size_inches: tuple[float, float] | None = None
    pixels: tuple[int, int] | None = None
    background: Color | str = "#ffffff"
    antialias: bool = True
    theme: Theme = MinimalTheme
    margins: Margins = field(default_factory=Margins)
    padding: float = 0.05

    def __post_init__(self) -> None:
        if (
            isinstance(self.dpi, bool)
            or not isinstance(self.dpi, int)
            or not 1 <= self.dpi <= MAX_DPI
        ):
            raise ConfigurationError(f"dpi must be an integer in [1, {MAX_DPI}], got {self.dpi!r}")
        if self.size_inches is not None and self.pixels is not None:
            raise ConfigurationError("give either size_inches or pixels, not both")
        if self.size_inches is not None and not all(v > 0 for v in self.size_inches):
            raise ConfigurationError("size_inches must be positive")
        if self.pixels is not None and not all(isinstance(v, int) and v > 0 for v in self.pixels):
            raise ConfigurationError("pixels must be two positive integers")
        if not (self.width > 0 and self.height > 0):
            raise ConfigurationError("width and height must be positive")

    def resolve(self) -> ResolvedSize:
        if self.pixels is not None:
            px_w, px_h = self.pixels
            return ResolvedSize(
                px_w * LOGICAL_DPI / self.dpi, px_h * LOGICAL_DPI / self.dpi, px_w, px_h, self.dpi
            )
        if self.size_inches is not None:
            lw, lh = self.size_inches[0] * LOGICAL_DPI, self.size_inches[1] * LOGICAL_DPI
        else:
            lw, lh = float(self.width), float(self.height)
        px_w = max(1, round(lw * self.dpi / LOGICAL_DPI))
        px_h = max(1, round(lh * self.dpi / LOGICAL_DPI))
        return ResolvedSize(lw, lh, px_w, px_h, self.dpi)


@dataclass(frozen=True)
class ResolvedSize:
    logical_width: float
    logical_height: float
    pixel_width: int
    pixel_height: int
    dpi: int

    @property
    def pixels(self) -> int:
        return self.pixel_width * self.pixel_height
