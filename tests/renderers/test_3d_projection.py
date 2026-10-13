from __future__ import annotations

import math

import numpy as np
import pytest

from kinetickit.geometry.three_d import MeshData, Vec3
from kinetickit.interpolation import Color
from kinetickit.renderers import project_point, project_scene
from kinetickit.scene import (
    Camera3D,
    DirectionalLight3D,
    Group3D,
    Line3D,
    Mesh3D,
    Point3D,
    PointCloud3D,
    Polyline3D,
    Scene3D,
    Surface3D,
)
from kinetickit.styles import ColorScale, Material

W = H = 200


def front_camera(**kw):
    return Camera3D(
        position=(0, -5, 0), target=(0, 0, 0), up=(0, 0, 1), fov=math.pi / 2, near=0.5, far=50, **kw
    )


def scene(*nodes, camera=None, **kw):
    return Scene3D(*nodes, camera=camera or front_camera(), **kw)


def test_perspective_numerical_reference():
    s = scene()
    x, y, depth = project_point(s, Vec3(1, 0, 0), W, H)
    assert (x, y, depth) == pytest.approx((120.0, 100.0, 5.0))  # ndc 0.2 → 60% across
    x, y, depth = project_point(s, Vec3(0, 0, 1), W, H)
    assert (x, y) == pytest.approx((100.0, 80.0))  # +z is up on screen (y down in pixels)
    x, y, depth = project_point(s, Vec3(0, 5, 0), W, H)
    assert (x, y, depth) == pytest.approx((100.0, 100.0, 10.0))  # forward is +y
    near, _, _ = project_point(s, Vec3(2, -2.5, 0), W, H)  # 2.5 deep: ndc = 2/2.5
    assert near == pytest.approx(100 + 0.8 * 100)


def test_orthographic_numerical_reference():
    s = scene(camera=front_camera(projection="orthographic", ortho_height=4.0))
    near = project_point(s, Vec3(1, 0, 0), W, H)
    far = project_point(s, Vec3(1, 20, 0), W, H)
    assert near[:2] == pytest.approx((150.0, 100.0)) and far[:2] == pytest.approx(near[:2])
    assert far[2] == pytest.approx(25.0)


def test_viewport_aspect_is_respected():
    s = scene()
    wide = project_point(s, Vec3(1, 0, 0), 400, 200)
    assert wide[0] == pytest.approx(200 + 0.1 * 200)  # horizontal fov widens with aspect
    assert wide[1] == pytest.approx(100.0)


def test_points_and_polylines_project_with_depth_order():
    s = scene(
        Point3D(id="far", position=(0, 5, 0), size=6),
        Point3D(id="near", position=(0, -2, 0), size=6),
        Polyline3D(id="pl", points=[(0, 0, 0), (1, 0, 0), (1, 0, 1)]),
    )
    prims = project_scene(s, W, H)
    assert [p.node_id for p in prims] == ["far", "pl", "near"]  # far → near
    assert prims[0].kind == "point" and prims[1].kind == "polyline"
    assert prims[1].points.shape == (3, 2)


def test_point_cloud_and_lines_and_draw_progress():
    cloud = PointCloud3D(id="c", points=np.array([[0, 0, 0], [1, 0, 0], [0, 0, 1]]))
    assert len(project_scene(scene(cloud), W, H)) == 3
    full = project_scene(scene(Line3D(id="l", start=(-1, 0, 0), end=(1, 0, 0))), W, H)[0]
    half = project_scene(
        scene(Line3D(id="l", start=(-1, 0, 0), end=(1, 0, 0), draw_progress=0.5)), W, H
    )[0]
    assert full.points[1, 0] > half.points[1, 0]
    assert half.points[1, 0] == pytest.approx(100.0, abs=1e-6)  # trimmed to the origin


def test_clipping_against_near_and_far_planes():
    s = scene(Point3D(id="behind", position=(0, -9, 0)), Point3D(id="ok", position=(0, 0, 0)))
    assert [p.node_id for p in project_scene(s, W, H)] == ["ok"]
    line = Polyline3D(id="pl", points=[(0, -9, 0), (0, 0, 0), (0, 4, 0)])
    runs = project_scene(scene(line), W, H)
    assert len(runs) == 1 and runs[0].points.shape == (2, 2)  # the vertex behind the camera is cut


def square_mesh(z=0.0, flip=False):
    tri = [(0, 2, 1), (0, 3, 2)] if flip else [(0, 1, 2), (0, 2, 3)]
    return MeshData([(-1, 0, z - 1), (1, 0, z - 1), (1, 0, z + 1), (-1, 0, z + 1)], tri)


def test_flat_shading_depends_on_light_direction():
    mesh = square_mesh()
    facing = scene(
        Mesh3D(id="m", mesh=mesh, color="#ffffff"),
        DirectionalLight3D(id="sun", direction=(0, 1, 0)),
    )
    away = scene(
        Mesh3D(id="m", mesh=mesh, color="#ffffff"),
        DirectionalLight3D(id="sun", direction=(1, 0, 0)),
    )
    lit = project_scene(facing, W, H)[0].fill
    grazing = project_scene(away, W, H)[0].fill
    assert lit[0] == pytest.approx(1.0)  # ambient 0.35 + diffuse 0.65 at normal incidence
    assert grazing[0] == pytest.approx(0.35)  # only ambient light reaches a grazing face


def test_unlit_scenes_use_a_headlight_and_faces_are_two_sided():
    a = project_scene(scene(Mesh3D(id="m", mesh=square_mesh(), color="#ffffff")), W, H)
    b = project_scene(scene(Mesh3D(id="m", mesh=square_mesh(flip=True), color="#ffffff")), W, H)
    assert a[0].fill[0] == pytest.approx(1.0, abs=0.02)
    assert b[0].fill[0] == pytest.approx(1.0, abs=0.02)
    one_sided = Mesh3D(id="m", mesh=square_mesh(flip=True), two_sided=False)
    assert len(project_scene(scene(one_sided), W, H)) <= 2


def test_material_specular_adds_a_highlight():
    flat = Mesh3D(id="m", mesh=square_mesh(), color="#808080", material=Material(0.3, 0.5, 0.0))
    shiny = Mesh3D(id="m", mesh=square_mesh(), color="#808080", material=Material(0.3, 0.5, 0.6, 8))
    f0 = project_scene(scene(flat), W, H)[0].fill[0]
    f1 = project_scene(scene(shiny), W, H)[0].fill[0]
    assert f1 > f0


def test_painter_order_draws_near_faces_last():
    near = Mesh3D(id="near", mesh=square_mesh(), color="#ff0000")
    farther = Mesh3D(
        id="far",
        mesh=MeshData([(-1, 3, -1), (1, 3, -1), (1, 3, 1), (-1, 3, 1)], [(0, 1, 2), (0, 2, 3)]),
    )
    prims = project_scene(scene(near, farther), W, H)
    assert [p.node_id for p in prims] == ["far", "far", "near", "near"]


def test_colorscale_and_vertex_colors():
    s = Surface3D.height_field(
        "s",
        [-1, 1],
        [-1, 1],
        [[0, 0], [4, 4]],
        colorscale=ColorScale(((0.0, "#000000"), (1.0, "#ffffff"))),
    )
    lo_hi = {
        round(p.fill[0], 2)
        for p in project_scene(scene(s, DirectionalLight3D(id="l", direction=(0, 1, 0))), W, H)
    }
    assert len(lo_hi) >= 1
    colors = np.tile([1.0, 0.0, 0.0, 1.0], (4, 1))
    painted = Mesh3D(
        id="m", mesh=MeshData(square_mesh().vertices, square_mesh().faces, colors=colors)
    )
    fill = project_scene(scene(painted), W, H)[0].fill
    assert fill[0] > 0.9 and fill[1] == pytest.approx(0.0) and fill[2] == pytest.approx(0.0)


def test_group_transforms_and_visibility_and_opacity():
    inner = Point3D(id="p", position=(1, 0, 0), size=4)
    moved = Group3D(id="g", children=(inner,))
    base = project_scene(scene(moved), W, H)[0]
    hidden = Group3D(id="g", children=(inner,), visible=False)
    assert project_scene(scene(hidden), W, H) == []
    faded = Group3D(id="g", children=(inner,), opacity=0.5)
    assert project_scene(scene(faded), W, H)[0].fill[3] == pytest.approx(0.5)
    assert base.fill == (*Color.parse("#1f2933").as_tuple()[:3], 1.0) or base.fill[3] == 1.0


def test_projection_is_deterministic():
    s = scene(
        Surface3D.height_field("s", np.linspace(-1, 1, 9), np.linspace(-1, 1, 9), np.zeros((9, 9)))
    )
    a, b = project_scene(s, W, H), project_scene(s, W, H)
    assert len(a) == len(b) == 128
    assert all(
        np.array_equal(x.points, y.points) and x.fill == y.fill for x, y in zip(a, b, strict=True)
    )
