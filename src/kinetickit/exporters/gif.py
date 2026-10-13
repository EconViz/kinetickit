"""Streaming GIF export."""

from __future__ import annotations

import json
from dataclasses import dataclass, fields
from typing import Any

from kinetickit import __version__
from kinetickit.animation import Animation
from kinetickit.errors import ConfigurationError
from kinetickit.exporters._gif_stream import GifStreamWriter
from kinetickit.exporters.cost import estimate_cost, warn_if_expensive
from kinetickit.exporters.destination import Destination, as_destination
from kinetickit.exporters.manifest import ExportManifest
from kinetickit.interaction import Degradation, plan_interactions
from kinetickit.interpolation import Color
from kinetickit.renderers import get_renderer, requirements_for
from kinetickit.renderers.capabilities import OUT_RASTER_FRAME
from kinetickit.renderers.raster import RasterRenderer, RasterSettings
from kinetickit.scheduler import FixedFPS, Scheduler, Timestamps

MIN_DELAY_CS = 1


@dataclass(frozen=True)
class GifSettings:
    """GIF encoding options.

    ``fps`` drives a fixed-rate schedule; pass ``timestamps`` (seconds) instead for an explicit
    stream. ``loop``: ``0`` repeats forever, ``None`` plays once, ``n`` repeats ``n`` more times.
    """

    fps: int = 30
    timestamps: tuple[float, ...] | None = None
    loop: int | None = 0
    colors: int = 256
    dither: str = "none"
    palette: str = "adaptive"
    disposal: int = 1
    metadata: bool = True
    degradation: str = "drop"

    def scheduler(self) -> Scheduler:
        return Timestamps(self.timestamps) if self.timestamps is not None else FixedFPS(self.fps)


def frame_delays(times: list[float], duration: float, *, uniform: bool = False) -> list[int]:
    """Centisecond display time per frame, with rounding error spread (never accumulated).

    ``uniform`` (fixed-rate schedules) shows every frame for ``duration / n`` so the total is exactly
    ``duration``. Otherwise frame ``i`` is shown from ``times[i]`` until ``times[i + 1]`` and the last
    frame fills the remaining time to ``duration`` (or repeats the previous interval).
    """
    n = len(times)
    if n == 1:
        return [max(MIN_DELAY_CS, round(duration * 100))]
    if uniform:
        edges = [duration * i / n for i in range(n + 1)]
    else:
        edges = list(times)
        tail = duration - times[-1]
        edges.append(times[-1] + (tail if tail > 1e-9 else times[-1] - times[-2]))
    out: list[int] = []
    prev = round(edges[0] * 100)
    for e in edges[1:]:
        cur = round(e * 100)
        out.append(cur - prev)
        prev = cur
    if min(out) < MIN_DELAY_CS:
        raise ConfigurationError(
            "frame interval is below the 10 ms resolution of GIF; lower the frame rate or "
            "widen the timestamps"
        )
    return out


class GIFExporter:
    format = "gif"
    renderer = "raster"

    def __init__(
        self, raster: RasterSettings | None = None, gif: GifSettings | None = None
    ) -> None:
        self.raster = raster or RasterSettings()
        self.gif = gif or GifSettings()

    @classmethod
    def from_options(cls, **options: Any) -> GIFExporter:
        raster_names = {f.name for f in fields(RasterSettings)}
        gif_names = {f.name for f in fields(GifSettings)}
        unknown = set(options) - raster_names - gif_names
        if unknown:
            raise ConfigurationError(f"unknown GIF options: {', '.join(sorted(unknown))}")
        return cls(
            RasterSettings(**{k: v for k, v in options.items() if k in raster_names}),
            GifSettings(**{k: v for k, v in options.items() if k in gif_names}),
        )

    def plan(self, animation: Animation) -> tuple[list[float], list[int]]:
        times = list(self.gif.scheduler().times(animation.duration))
        if animation.duration == 0.0:
            times = times[:1]
        uniform = self.gif.timestamps is None
        return times, frame_delays(times, animation.duration, uniform=uniform)

    def export(self, animation: Animation, target: Any) -> ExportManifest:
        renderer = get_renderer("raster")
        renderer.capabilities.validate(requirements_for(animation, outputs=(OUT_RASTER_FRAME,)))
        assert isinstance(renderer, RasterRenderer)
        plan = plan_interactions(
            animation.interactions, renderer.capabilities, Degradation(self.gif.degradation)
        )
        size = self.raster.resolve()
        times, delays = self.plan(animation)
        estimate = estimate_cost(size, len(times))
        warn_if_expensive(estimate)
        layout = renderer.layout_for(animation, self.raster)
        bg = Color.parse(self.raster.background)
        background = (round(bg.r * 255), round(bg.g * 255), round(bg.b * 255))
        comment = None
        if self.gif.metadata:
            comment = json.dumps(
                {
                    "generator": f"kinetickit {__version__}",
                    "frames": len(times),
                    "duration_cs": sum(delays),
                    "dpi": size.dpi,
                    "colors": self.gif.colors,
                    "dither": self.gif.dither,
                    "palette": self.gif.palette,
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        dest: Destination = as_destination(target)
        written = 0
        with dest.open_binary() as out:
            counter = _Counting(out)
            writer = GifStreamWriter(
                counter,  # type: ignore[arg-type]
                size.pixel_width,
                size.pixel_height,
                loop=self.gif.loop,
                colors=self.gif.colors,
                dither=self.gif.dither,
                palette=self.gif.palette,
                disposal=self.gif.disposal,
                comment=comment,
                background=background,
            )
            for t, delay in zip(times, delays, strict=True):
                frame = renderer.render_frame(animation.sample(t), layout, self.raster)
                writer.add_frame(frame.pixels, delay)
                del frame  # one frame at a time
            writer.close()
            written = counter.count
        return ExportManifest(
            format="gif",
            renderer="raster",
            destination=dest.description,
            width=size.pixel_width,
            height=size.pixel_height,
            duration=sum(delays) / 100.0,
            frames=len(times),
            bytes_written=written,
            warnings=(estimate.message(),) if estimate.expensive else (),
            preserved=plan.preserved,
            degraded=plan.degraded,
            details={"delays_cs": tuple(delays), "dpi": size.dpi, "times": tuple(times)},
        )


class _Counting:
    def __init__(self, inner: Any) -> None:
        self.inner, self.count = inner, 0

    def write(self, data: bytes) -> int:
        self.count += len(data)
        return int(self.inner.write(data))
