from __future__ import annotations

import io
import math

import numpy as np
import pytest

from kinetickit.animation import Animation
from kinetickit.geometry.three_d import MeshData
from kinetickit.renderers import get_renderer
from kinetickit.renderers.raster import RasterSettings
from kinetickit.scene import Camera3D, Line3D, Mesh3D, Point2D, Point3D, Scene3D, Surface3D

pytest.importorskip("matplotlib")
PIL = pytest.importorskip("PIL.Image")


def cam(**kw):
    return Camera3D(position=(0, -5, 0), target=(0, 0, 0), fov=math.pi / 2, **kw)


def render(scene, size=100):
    r = get_renderer("raster")
    st = RasterSettings(width=size, height=size)
    return r.render_frame(scene, r.layout_for(Animation(scene), st), st)


def test_projected_points_and_faces_land_where_the_math_says():
    quad = MeshData([(-1, 0, -1), (1, 0, -1), (1, 0, 1), (-1, 0, 1)], [(0, 1, 2), (0, 2, 3)])
    scene = Scene3D(
        Mesh3D(id="m", mesh=quad, color="#0000ff"),
        Point3D(id="p", position=(2, 0, 0), size=6, color="#ff0000"),
        camera=cam(),
    )
    frame = render(scene)
    px = lambda x, y: tuple(int(v) for v in frame.pixels[y, x])[:3]  # noqa: E731
    r, _g, b = px(50, 50)
    assert b > 150 and r < 80  # the blue quad covers the centre
    assert px(70, 50) == (255, 0, 0)  # the red marker at ndc x = 0.4
    assert px(5, 5) == (255, 255, 255)


def test_orbiting_camera_animation_exports_a_gif():
    surface = Surface3D.height_field(
        "s",
        np.linspace(-1, 1, 12),
        np.linspace(-1, 1, 12),
        np.add.outer(np.linspace(-1, 1, 12) ** 2, np.linspace(-1, 1, 12) ** 2) * 0.5,
    )
    scene = Scene3D(surface, camera=Camera3D(position=(0, -6, 3), target=(0, 0, 0)))
    anim = Animation(scene, scene.camera.animate.position.to((6, 0, 3), duration=1.0))
    data = anim.to_bytes("gif", width=64, height=64, fps=4)
    im = PIL.open(io.BytesIO(data))
    assert im.n_frames == 4
    im.seek(0)
    first = np.array(im.convert("RGB"))
    im.seek(3)
    last = np.array(im.convert("RGB"))
    assert (first != 255).any() and not np.array_equal(first, last)  # the view really rotated


def test_overlay_draws_over_3d_content():
    scene = Scene3D(
        Point3D(id="p", size=10, color="#0000ff"),
        overlay=[Point2D(id="hud", position=(20, 20), size=5, color="#ff0000")],
        camera=cam(),
    )
    frame = render(scene)
    assert tuple(int(v) for v in frame.pixels[20, 20])[:3] == (255, 0, 0)


def test_lines_are_drawn_and_unsupported_capabilities_are_reported():
    scene = Scene3D(
        Line3D(id="l", start=(-1, 0, 0), end=(1, 0, 0), width=6, color="#000000"), camera=cam()
    )
    frame = render(scene)
    assert tuple(int(v) for v in frame.pixels[50, 50])[:3] == (0, 0, 0)
    assert "mesh" in get_renderer("raster").capabilities.geometry
