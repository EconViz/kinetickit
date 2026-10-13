"""Axes, grids, legends, color bars and annotations compiled to ordinary scene nodes."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from kinetickit.errors import ConfigurationError
from kinetickit.geometry.two_d import Path2D, Vec2
from kinetickit.guides.ticks import format_tick, nice_ticks
from kinetickit.interpolation import Color
from kinetickit.layout import LayoutResult
from kinetickit.scene import Group2D, Line2D, Node, Point2D, Shape2D, Text2D
from kinetickit.styles import MinimalTheme, Theme
from kinetickit.typography import TextFactory, TypographyEngine, require_text_factory


@dataclass(frozen=True, slots=True)
class Axis2D:
    """A world-space axis along ``x`` or ``y`` with ticks and optional labels.

    ``at`` is the position on the perpendicular axis (default: the range start). Tick length is
    given in pixels and converted using the layout scale, so guides track the data exactly.
    """

    id: str
    orientation: str
    range: tuple[float, float]
    at: float = 0.0
    tick_count: int = 5
    tick_length: float = 6.0

    def __post_init__(self) -> None:
        if self.orientation not in ("x", "y"):
            raise ConfigurationError("axis orientation must be 'x' or 'y'")
        if self.range[1] < self.range[0]:
            raise ConfigurationError("axis range must be ascending")

    def ticks(self) -> tuple[float, ...]:
        return nice_ticks(self.range[0], self.range[1], self.tick_count)

    def compile(
        self,
        layout: LayoutResult,
        *,
        theme: Theme = MinimalTheme,
        text: TypographyEngine | TextFactory | None = None,
        labels: bool = False,
    ) -> Group2D:
        """Compile to nodes. ``labels=True`` needs ``text`` (a typography provider)."""
        factory = require_text_factory(text, "axis tick labels") if labels else None
        s = layout.scale()
        tick = self.tick_length / s
        children: list[Node] = []
        horizontal = self.orientation == "x"

        def along(v: float) -> Vec2:
            return Vec2(v, self.at) if horizontal else Vec2(self.at, v)

        across = Vec2(0, -tick) if self.orientation == "x" else Vec2(-tick, 0)
        lo, hi = self.range
        children.append(
            Line2D(
                id=f"{self.id}.line",
                start=along(lo),
                end=along(hi),
                color=theme.guide,
                width=theme.guide_width,
                cap="butt",
            )
        )
        for i, value in enumerate(self.ticks()):
            p = along(value)
            children.append(
                Line2D(
                    id=f"{self.id}.tick{i}",
                    start=p,
                    end=p + across,
                    color=theme.guide,
                    width=theme.guide_width,
                    cap="butt",
                )
            )
            if factory is not None:
                asset = factory(format_tick(value))
                gap = 4.0 / s
                if self.orientation == "x":
                    pos = p + across + Vec2(-asset.width / 2 / s, -(gap + asset.height / s))
                else:
                    pos = p + across + Vec2(-(gap + asset.width / s), -asset.height / 2 / s)
                children.append(
                    Text2D(
                        id=f"{self.id}.label{i}",
                        asset=asset,
                        position=pos,
                        scale=1.0 / s,
                        color=theme.text_secondary,
                    )
                )
        return Group2D(id=self.id, children=tuple(children))


@dataclass(frozen=True, slots=True)
class Grid2D:
    """Light grid lines at nice tick positions."""

    id: str
    x_range: tuple[float, float]
    y_range: tuple[float, float]
    tick_count: int = 5

    def compile(self, *, theme: Theme = MinimalTheme) -> Group2D:
        lines: list[Node] = []
        for i, x in enumerate(nice_ticks(*self.x_range, self.tick_count)):
            lines.append(
                Line2D(
                    id=f"{self.id}.v{i}",
                    start=Vec2(x, self.y_range[0]),
                    end=Vec2(x, self.y_range[1]),
                    color=theme.grid,
                    width=theme.guide_width,
                    cap="butt",
                    z=-10,
                )
            )
        for i, y in enumerate(nice_ticks(*self.y_range, self.tick_count)):
            lines.append(
                Line2D(
                    id=f"{self.id}.h{i}",
                    start=Vec2(self.x_range[0], y),
                    end=Vec2(self.x_range[1], y),
                    color=theme.grid,
                    width=theme.guide_width,
                    cap="butt",
                    z=-10,
                )
            )
        return Group2D(id=self.id, children=tuple(lines))


@dataclass(frozen=True, slots=True)
class LegendEntry:
    label: str
    color: Color | str


@dataclass(frozen=True, slots=True)
class Legend:
    """A screen-space overlay legend: one swatch per entry, top-left anchored (y down)."""

    id: str
    entries: tuple[LegendEntry, ...]
    origin: tuple[float, float] = (16.0, 16.0)
    row_height: float = 22.0

    def compile(
        self,
        *,
        theme: Theme = MinimalTheme,
        text: TypographyEngine | TextFactory | None = None,
        labels: bool = True,
    ) -> Group2D:
        if not self.entries:
            raise ConfigurationError("a legend needs at least one entry")
        factory = require_text_factory(text, "legend labels") if labels else None
        x0, y0 = self.origin
        children: list[Node] = []
        for i, entry in enumerate(self.entries):
            y = y0 + i * self.row_height
            children.append(
                Point2D(
                    id=f"{self.id}.swatch{i}",
                    position=Vec2(x0 + 6, y + 6),
                    size=5.0,
                    symbol="square",
                    color=Color.parse(entry.color),
                )
            )
            if factory is not None:
                children.append(
                    Text2D(
                        id=f"{self.id}.label{i}",
                        asset=factory(entry.label),
                        position=Vec2(x0 + 20, y + 12),
                        color=theme.text,
                    )
                )
        return Group2D(id=self.id, children=tuple(children))


@dataclass(frozen=True, slots=True)
class ColorBar:
    """A vertical color scale built from stacked rectangles, in world coordinates."""

    id: str
    origin: tuple[float, float]
    size: tuple[float, float]
    colormap: Callable[[float], Color | str]
    steps: int = 32

    def compile(self) -> Group2D:
        if self.steps < 2:
            raise ConfigurationError("a color bar needs at least two steps")
        (x, y), (w, h) = self.origin, self.size
        step_h = h / self.steps
        slices = tuple(
            Shape2D(
                id=f"{self.id}.s{i}",
                path=Path2D.rect(x, y + i * step_h, w, step_h * 1.02),
                fill=Color.parse(self.colormap(i / (self.steps - 1))),
            )
            for i in range(self.steps)
        )
        return Group2D(id=self.id, children=slices)


@dataclass(frozen=True, slots=True)
class Annotation:
    """A leader line from a world-space target to a label position."""

    id: str
    target: tuple[float, float]
    label_at: tuple[float, float]
    text: Any = None

    def compile(
        self,
        *,
        theme: Theme = MinimalTheme,
        text: TypographyEngine | TextFactory | None = None,
    ) -> Group2D:
        factory = require_text_factory(text, "annotation text") if self.text else None
        kids: list[Node] = [
            Line2D(
                id=f"{self.id}.leader",
                start=Vec2(*self.target),
                end=Vec2(*self.label_at),
                color=theme.text_secondary,
                width=theme.guide_width,
            ),
            Point2D(
                id=f"{self.id}.anchor", position=Vec2(*self.target), size=3.0, color=theme.text
            ),
        ]
        if factory is not None:
            kids.append(
                Text2D(
                    id=f"{self.id}.label",
                    asset=factory(str(self.text)),
                    position=Vec2(*self.label_at),
                    color=theme.text,
                )
            )
        return Group2D(id=self.id, children=tuple(kids))


def stack(*groups: Group2D) -> Sequence[Node]:
    """Return guide groups as plain nodes ready for ``Scene2D(*nodes)``."""
    return tuple(groups)
