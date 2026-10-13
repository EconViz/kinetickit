"""A lit surface with an orbiting camera, exported as GIF, projected SVG and interactive HTML."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from kinetickit.animation import Animation
from kinetickit.geometry.three_d import Vec3
from kinetickit.scene import Camera3D, DirectionalLight3D, Point3D, Scene3D, Surface3D
from kinetickit.styles import ColorScale, Material


def build() -> Animation:
    xs = ys = np.linspace(-2, 2, 28)
    X, Y = np.meshgrid(xs, ys)
    Z = np.sin(np.hypot(X, Y) * 2.2) / (1 + np.hypot(X, Y))
    surface = Surface3D.height_field(
        "surface",
        xs,
        ys,
        Z,
        colorscale=ColorScale.viridis_like(),
        material=Material(0.4, 0.6, 0.2, 24),
    )
    marker = Point3D(id="peak", position=Vec3(0, 0, 1.0), size=6, color="#d62728")
    scene = Scene3D(
        surface,
        marker,
        DirectionalLight3D(id="sun"),
        camera=Camera3D(position=Vec3(5.5, -6.5, 4.2), target=Vec3(0, 0, 0.2)),
    )
    return Animation(scene, scene.camera.animate.position.to(Vec3(-6, -5.5, 4.2), duration=2.0))


def main(out: Path) -> dict[str, Path]:
    out.mkdir(parents=True, exist_ok=True)
    animation = build()
    files = {"svg": out / "surface.svg", "html": out / "surface.html", "gif": out / "surface.gif"}
    animation.save(files["svg"], width=480, height=360)
    animation.save(files["html"], width=640, height=420, fps=12, title="Surface")
    animation.save(files["gif"], width=320, height=240, fps=10)
    return files


if __name__ == "__main__":
    print(main(Path("out")))
