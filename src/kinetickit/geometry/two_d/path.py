"""A minimal KineticKit-owned path command model."""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

from kinetickit.errors import ConfigurationError
from kinetickit.geometry.two_d.bounds import Bounds2D
from kinetickit.geometry.two_d.matrix import Matrix3
from kinetickit.geometry.two_d.vector import Vec2

ARITY = {"M": 1, "L": 1, "Q": 2, "C": 3, "Z": 0}
_KAPPA = 4.0 * (math.sqrt(2.0) - 1.0) / 3.0


@dataclass(frozen=True, slots=True)
class PathCommand:
    """``M`` move, ``L`` line, ``Q`` quadratic, ``C`` cubic, ``Z`` close."""

    kind: str
    points: tuple[Vec2, ...] = ()

    def __post_init__(self) -> None:
        if self.kind not in ARITY:
            raise ConfigurationError(f"unknown path command {self.kind!r}")
        pts = tuple(Vec2.coerce(p) for p in self.points)
        if len(pts) != ARITY[self.kind]:
            raise ConfigurationError(
                f"command {self.kind} takes {ARITY[self.kind]} point(s), got {len(pts)}"
            )
        object.__setattr__(self, "points", pts)


@dataclass(frozen=True, slots=True)
class Path2D:
    """An ordered sequence of subpaths. Every subpath begins with ``M``."""

    commands: tuple[PathCommand, ...]

    def __post_init__(self) -> None:
        cmds = tuple(
            c if isinstance(c, PathCommand) else PathCommand(c[0], tuple(c[1:]))
            for c in self.commands
        )
        object.__setattr__(self, "commands", cmds)
        open_subpath = False
        for i, c in enumerate(cmds):
            if c.kind == "M":
                open_subpath = True
            elif not open_subpath:
                raise ConfigurationError(
                    f"command {i} ({c.kind}) must follow a move; start each subpath with M"
                )
            elif c.kind == "Z":
                open_subpath = False

    @classmethod
    def coerce(cls, value: Any) -> Path2D:
        if isinstance(value, Path2D):
            return value
        return cls(tuple(value))

    # -- constructors ---------------------------------------------------------------
    @classmethod
    def polyline(cls, points: Iterable[Any], *, closed: bool = False) -> Path2D:
        pts = [Vec2.coerce(p) for p in points]
        if len(pts) < 2:
            raise ConfigurationError("a polyline needs at least two vertices")
        cmds = [PathCommand("M", (pts[0],))] + [PathCommand("L", (p,)) for p in pts[1:]]
        if closed:
            cmds.append(PathCommand("Z"))
        return cls(tuple(cmds))

    @classmethod
    def polygon(cls, *rings: Iterable[Any]) -> Path2D:
        """Closed rings; extra rings are holes or islands, decided by the fill rule."""
        if not rings:
            raise ConfigurationError("a polygon needs at least one ring")
        cmds: list[PathCommand] = []
        for ring in rings:
            pts = [Vec2.coerce(p) for p in ring]
            if len(pts) < 3:
                raise ConfigurationError("a polygon ring needs at least three vertices")
            cmds.append(PathCommand("M", (pts[0],)))
            cmds.extend(PathCommand("L", (p,)) for p in pts[1:])
            cmds.append(PathCommand("Z"))
        return cls(tuple(cmds))

    @classmethod
    def rect(cls, x: float, y: float, width: float, height: float) -> Path2D:
        return cls.polygon([(x, y), (x + width, y), (x + width, y + height), (x, y + height)])

    @classmethod
    def ellipse(cls, cx: float, cy: float, rx: float, ry: float) -> Path2D:
        k = _KAPPA
        c = Vec2
        return cls(
            (
                PathCommand("M", (c(cx + rx, cy),)),
                PathCommand(
                    "C", (c(cx + rx, cy + k * ry), c(cx + k * rx, cy + ry), c(cx, cy + ry))
                ),
                PathCommand(
                    "C", (c(cx - k * rx, cy + ry), c(cx - rx, cy + k * ry), c(cx - rx, cy))
                ),
                PathCommand(
                    "C", (c(cx - rx, cy - k * ry), c(cx - k * rx, cy - ry), c(cx, cy - ry))
                ),
                PathCommand(
                    "C", (c(cx + k * rx, cy - ry), c(cx + rx, cy - k * ry), c(cx + rx, cy))
                ),
                PathCommand("Z"),
            )
        )

    @classmethod
    def circle(cls, cx: float, cy: float, r: float) -> Path2D:
        return cls.ellipse(cx, cy, r, r)

    # -- queries ----------------------------------------------------------------------
    @property
    def kinds(self) -> tuple[str, ...]:
        return tuple(c.kind for c in self.commands)

    def subpaths(self) -> tuple[tuple[PathCommand, ...], ...]:
        out: list[list[PathCommand]] = []
        for c in self.commands:
            if c.kind == "M":
                out.append([])
            out[-1].append(c)
        return tuple(tuple(s) for s in out)

    def vertices(self) -> tuple[Vec2, ...]:
        """Every on-curve and control point in command order."""
        return tuple(p for c in self.commands for p in c.points)

    def bounds(self) -> Bounds2D | None:
        """Exact bounds, including curve extrema."""
        pts: list[Vec2] = []
        cur = Vec2(0.0, 0.0)
        start = cur
        for c in self.commands:
            if c.kind == "M":
                cur = start = c.points[0]
                pts.append(cur)
            elif c.kind == "L":
                cur = c.points[0]
                pts.append(cur)
            elif c.kind == "Q":
                pts.extend(_quad_extrema(cur, *c.points))
                cur = c.points[1]
            elif c.kind == "C":
                pts.extend(_cubic_extrema(cur, *c.points))
                cur = c.points[2]
            else:
                cur = start
        return Bounds2D.of(pts)

    def transformed(self, matrix: Matrix3) -> Path2D:
        return Path2D(
            tuple(
                PathCommand(c.kind, tuple(matrix.apply(p) for p in c.points)) for c in self.commands
            )
        )

    def to_svg(self, precision: int = 6) -> str:
        """SVG path data in world coordinates (no axis flip)."""

        def num(v: float) -> str:
            s = f"{v:.{precision}f}".rstrip("0").rstrip(".")
            return "0" if s in ("-0", "") else s

        parts = []
        for c in self.commands:
            coords = " ".join(f"{num(p.x)} {num(p.y)}" for p in c.points)
            parts.append(c.kind if not coords else f"{c.kind}{coords}")
        return " ".join(parts)


def _quad_extrema(p0: Vec2, p1: Vec2, p2: Vec2) -> list[Vec2]:
    pts = [p2]
    for axis in ("x", "y"):
        a, b, c = getattr(p0, axis), getattr(p1, axis), getattr(p2, axis)
        denom = a - 2 * b + c
        if denom != 0.0:
            t = (a - b) / denom
            if 0.0 < t < 1.0:
                pts.append(_quad_at(p0, p1, p2, t))
    return pts


def _quad_at(p0: Vec2, p1: Vec2, p2: Vec2, t: float) -> Vec2:
    u = 1.0 - t
    return p0 * (u * u) + p1 * (2 * u * t) + p2 * (t * t)


def _cubic_at(p0: Vec2, p1: Vec2, p2: Vec2, p3: Vec2, t: float) -> Vec2:
    u = 1.0 - t
    return p0 * (u**3) + p1 * (3 * u * u * t) + p2 * (3 * u * t * t) + p3 * (t**3)


def _cubic_extrema(p0: Vec2, p1: Vec2, p2: Vec2, p3: Vec2) -> list[Vec2]:
    pts = [p3]
    for axis in ("x", "y"):
        a, b, c, d = (getattr(p, axis) for p in (p0, p1, p2, p3))
        # derivative coefficients of the cubic: A t^2 + B t + C
        qa = -a + 3 * b - 3 * c + d
        qb = 2 * (a - 2 * b + c)
        qc = b - a
        roots: list[float] = []
        if abs(qa) < 1e-14:
            if qb != 0.0:
                roots.append(-qc / qb)
        else:
            disc = qb * qb - 4 * qa * qc
            if disc >= 0.0:
                r = math.sqrt(disc)
                roots += [(-qb + r) / (2 * qa), (-qb - r) / (2 * qa)]
        pts.extend(_cubic_at(p0, p1, p2, p3, t) for t in roots if 0.0 < t < 1.0)
    return pts


class Path2DInterpolator:
    """Interpolate paths that already share one command structure.

    Incompatible paths must be normalized first (see :mod:`kinetickit.morph`) or cross-faded.
    """

    def interpolate(self, start: Path2D, end: Path2D, progress: float) -> Path2D:
        if progress == 0.0:
            return start
        if progress == 1.0:
            return end
        if start.kinds != end.kinds:
            raise ConfigurationError(
                "paths have different command structure; normalize them with "
                "kinetickit.morph or use a cross-fade"
            )
        return Path2D(
            tuple(
                PathCommand(
                    a.kind,
                    tuple(
                        Vec2(
                            p.x + (q.x - p.x) * progress,
                            p.y + (q.y - p.y) * progress,
                        )
                        for p, q in zip(a.points, b.points, strict=True)
                    ),
                )
                for a, b in zip(start.commands, end.commands, strict=True)
            )
        )


def points_of(commands: Sequence[PathCommand]) -> tuple[Vec2, ...]:
    return tuple(p for c in commands for p in c.points)
