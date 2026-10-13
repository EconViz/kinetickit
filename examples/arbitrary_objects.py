"""Animate any object model: plain Python satellites, no visualization package involved."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

from kinetickit.adapters import adapt, transition
from kinetickit.animation import Animation
from kinetickit.geometry.two_d import Bounds2D, Vec2
from kinetickit.scene import Line2D, Point2D


@dataclass(frozen=True)
class Satellite:
    """A domain object KineticKit knows nothing about."""

    name: str
    angle: float
    radius: float
    tint: str


def depict(sat: Satellite):
    pos = Vec2(sat.radius * math.cos(sat.angle), sat.radius * math.sin(sat.angle))
    return [
        Point2D(id=f"{sat.name}.body", position=pos, size=7, color=sat.tint),
        Line2D(id=f"{sat.name}.tether", start=Vec2(0, 0), end=pos, width=1.5, color="#9aa5b1"),
    ]


def main(out: Path) -> dict[str, Path]:
    out.mkdir(parents=True, exist_ok=True)
    before = [Satellite("alpha", 0.0, 3.0, "#e4572e"), Satellite("beta", 2.0, 5.0, "#3e7cb1")]
    after = [
        Satellite("alpha", 1.5, 4.0, "#e4572e"),
        Satellite("beta", 4.0, 5.0, "#3e7cb1"),
        Satellite("gamma", 5.5, 2.0, "#2ca02c"),
    ]
    step = transition(before, after, depict, duration=1.5)
    scene = step.scene
    scene = scene.bind({scene.camera.ref("view"): Bounds2D(Vec2(-6, -6), Vec2(6, 6))})
    animation = Animation(scene, step.motion)
    assert adapt(before, depict).ids  # the same adapter builds a plain scene too
    files = {"svg": out / "satellites.svg", "html": out / "satellites.html"}
    animation.save(files["svg"], width=480, height=480)
    animation.save(files["html"], width=480, height=520, title="Satellites")
    return files


if __name__ == "__main__":
    print(main(Path("out")))
