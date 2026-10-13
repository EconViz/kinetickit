"""Cost estimation for raster jobs. KineticKit warns; it never silently lowers quality."""

from __future__ import annotations

import warnings
from dataclasses import dataclass

from kinetickit.renderers.raster.settings import ResolvedSize

FRAME_PIXEL_WARNING = 40_000_000
TOTAL_PIXEL_WARNING = 4_000_000_000


class RenderCostWarning(UserWarning):
    """The requested raster export is unusually expensive."""


@dataclass(frozen=True)
class RenderCostEstimate:
    frames: int
    pixels_per_frame: int
    total_pixels: int
    frame_bytes: int
    peak_memory_bytes: int

    @property
    def expensive(self) -> bool:
        return (
            self.pixels_per_frame > FRAME_PIXEL_WARNING or self.total_pixels > TOTAL_PIXEL_WARNING
        )

    def message(self) -> str:
        return (
            f"{self.frames} frames of {self.pixels_per_frame:,} pixels "
            f"(~{self.peak_memory_bytes / 1e6:,.0f} MB peak, {self.total_pixels:,} pixels total); "
            "frames are streamed one at a time and quality is not reduced"
        )


def estimate_cost(size: ResolvedSize, frames: int) -> RenderCostEstimate:
    per_frame = size.pixels
    frame_bytes = per_frame * 4
    # RGBA buffer + RGB copy + palette image + encoder scratch for one frame at a time
    return RenderCostEstimate(frames, per_frame, per_frame * frames, frame_bytes, frame_bytes * 3)


def warn_if_expensive(estimate: RenderCostEstimate) -> None:
    if estimate.expensive:
        warnings.warn(estimate.message(), RenderCostWarning, stacklevel=3)
