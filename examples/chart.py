"""A bar-and-line chart built from generic shapes and guides (no chart package)."""

from __future__ import annotations

from pathlib import Path

from kinetickit import ease
from kinetickit.animation import Animation
from kinetickit.geometry.two_d import Bounds2D, Path2D, Vec2
from kinetickit.guides import Axis2D, Grid2D
from kinetickit.layout import Viewport, resolve_layout
from kinetickit.scene import PathNode2D, Scene2D, Shape2D

VALUES = [3.0, 5.5, 4.0, 7.5, 6.0]


def main(out: Path) -> dict[str, Path]:
    out.mkdir(parents=True, exist_ok=True)
    bars = [
        Shape2D(id=f"bar{i}", path=Path2D.rect(i + 0.15, 0, 0.7, 0.0001), fill="#3e7cb1")
        for i, _ in enumerate(VALUES)
    ]
    line = PathNode2D.polyline(
        "trend",
        [(i + 0.5, v) for i, v in enumerate(VALUES)],
        width=3,
        color="#e4572e",
        draw_progress=0.0,
    )
    base = Scene2D(*bars, line)
    base = base.bind({base.camera.ref("view"): Bounds2D(Vec2(-0.5, -1), Vec2(5.5, 9))})
    layout = resolve_layout(Animation(base), Viewport(560, 360))
    guides = [
        Grid2D("grid", (0, 5), (0, 8)).compile(),
        Axis2D("x", "x", (0, 5)).compile(layout),
        Axis2D("y", "y", (0, 8), at=0).compile(layout),
    ]
    scene = Scene2D(*guides, *bars, line, camera=base.camera)
    motion = None
    for i, (bar, v) in enumerate(zip(bars, VALUES, strict=True)):
        grow = bar.morph_to(Path2D.rect(i + 0.15, 0, 0.7, v), duration=0.8, easing=ease.out_cubic)
        motion = grow if motion is None else motion.with_(grow, offset=0.1 * i)
    motion = motion.then(line.animate.draw_progress.to(1.0, duration=1.0))
    animation = Animation(scene, motion)
    files = {"svg": out / "chart.svg", "html": out / "chart.html"}
    animation.save(files["svg"], width=560, height=360)
    animation.save(files["html"], width=560, height=400, title="Chart")
    return files


if __name__ == "__main__":
    print(main(Path("out")))
