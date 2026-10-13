"""Reusable style values that expand into node properties."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from kinetickit.interpolation import Color


@dataclass(frozen=True, slots=True)
class Stroke:
    """Line style: ``line_props()`` expands for lines and paths, ``shape_props()`` for areas."""

    color: Color | str = "#1f2933"
    width: float = 2.0
    cap: str = "round"
    join: str = "round"
    dash: tuple[float, ...] = ()

    def line_props(self) -> dict[str, Any]:
        return {
            "color": Color.parse(self.color),
            "width": self.width,
            "cap": self.cap,
            "join": self.join,
            "dash": self.dash,
        }

    def shape_props(self) -> dict[str, Any]:
        return {
            "stroke": Color.parse(self.color),
            "stroke_width": self.width,
            "join": self.join,
            "dash": self.dash,
        }


@dataclass(frozen=True, slots=True)
class Fill:
    color: Color | str = "#1f2933"
    rule: str = "nonzero"

    def props(self) -> dict[str, Any]:
        return {"fill": Color.parse(self.color), "fill_rule": self.rule}
