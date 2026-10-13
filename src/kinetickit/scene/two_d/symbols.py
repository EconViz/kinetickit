"""Unit-size marker outlines (y up, radius 1) shared by renderers."""

from __future__ import annotations

from kinetickit.geometry.two_d import Path2D

SYMBOL_PATHS: dict[str, Path2D] = {
    "circle": Path2D.circle(0, 0, 1),
    "square": Path2D.polygon([(-1, -1), (1, -1), (1, 1), (-1, 1)]),
    "diamond": Path2D.polygon([(0, -1.2), (1.2, 0), (0, 1.2), (-1.2, 0)]),
    "triangle": Path2D.polygon([(0, 1.1), (1, -0.7), (-1, -0.7)]),
    "plus": Path2D.polygon(
        [(-0.3, -1), (0.3, -1), (0.3, -0.3), (1, -0.3), (1, 0.3), (0.3, 0.3)]
        + [(0.3, 1), (-0.3, 1), (-0.3, 0.3), (-1, 0.3), (-1, -0.3), (-0.3, -0.3)]
    ),
    "cross": Path2D.polygon(
        [(-0.75, -1), (0, -0.25), (0.75, -1), (1, -0.75), (0.25, 0), (1, 0.75)]
        + [(0.75, 1), (0, 0.25), (-0.75, 1), (-1, 0.75), (-0.25, 0), (-1, -0.75)]
    ),
}
