from __future__ import annotations

import math

import numpy as np
import pytest

from kinetickit.animation import Animation
from kinetickit.errors import ConfigurationError
from kinetickit.geometry.three_d import Bounds3D, MeshData, Quaternion, Transform3D, Vec3
from kinetickit.scene import (
    Camera3D,
    DirectionalLight3D,
    Group3D,
    Line3D,
    Mesh3D,
    Point2D,
    Point3D,
    PointCloud3D,
    Polyline3D,
    Scene2D,
    Scene3D,
    Surface3D,
)
from kinetickit.styles import ColorScale, Material
from kinetickit.timeline import PropertyRef


def test_scene3d_rejects_2d_world_nodes_and_3d_overlay_nodes():
    with pytest.raises(ConfigurationError, match="2D and cannot be in the 3D"):
        Scene3D(Point2D(id="flat"))
    with pytest.raises(ConfigurationError, match="3D and cannot be in the 2D"):
        Scene3D(overlay=[Point3D(id="deep")])
    with pytest.raises(ConfigurationError, match="3D and cannot be in the 2D"):
        Scene2D(Point3D(id="deep"))
    scene = Scene3D(Point3D(id="p"), overlay=[Point2D(id="hud")])
    assert "hud" in scene and scene.camera.id == "camera"
    with pytest.raises(ConfigurationError):
        Scene3D(camera=Camera3D.__mro__[1](id="x"))  # a non-camera node


def test_every_primitive_is_addressable_and_validated():
    nodes = [
        Point3D(id="p", position=(1, 2, 3), size=5, color="#f00"),
        PointCloud3D(id="cloud", points=np.random.default_rng(1).random((20, 3))),
        Line3D(id="l", start=(0, 0, 0), end=(1, 1, 1), dash=(2, 1)),
        Polyline3D(id="pl", points=[(0, 0, 0), (1, 0, 0), (1, 1, 0)], closed=True),
        Mesh3D(id="m", mesh=MeshData([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [(0, 1, 2)])),
        Surface3D.height_field(
            "s", [0, 1], [0, 1], [[0, 1], [1, 2]], colorscale=ColorScale.viridis_like()
        ),
        DirectionalLight3D(id="sun"),
        Group3D(
            id="g", children=(Point3D(id="inner"),), transform=Transform3D(translate=Vec3(1, 0, 0))
        ),
    ]
    scene = Scene3D(*nodes)
    assert len(scene.ids) == 10  # nodes + nested child + camera
    assert scene.lights() and scene.lights()[0].id == "sun"
    for n in nodes:
        assert n.bounds() is None or isinstance(n.bounds(), Bounds3D)
    with pytest.raises(ConfigurationError):
        Polyline3D(id="x", points=[(0, 0, 0)])
    with pytest.raises(ConfigurationError):
        DirectionalLight3D(id="x", direction=(0, 0, 0))
    with pytest.raises(ConfigurationError):
        Point3D(id="x", symbol="blob")
    with pytest.raises(ConfigurationError):
        Material(ambient=2.0)


def test_scene_values_are_pure_data():
    scene = Scene3D(Mesh3D(id="m", mesh=MeshData([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [(0, 1, 2)])))
    for node in scene.walk():
        for f in node.__dataclass_fields__.values():
            owner = type(getattr(node, f.name)).__module__.split(".")[0]
            assert owner in {"kinetickit", "builtins", "numpy"}, (node.id, f.name, owner)


def test_group_bounds_apply_transform():
    g = Group3D(
        id="g",
        children=(Point3D(id="a", position=(1, 0, 0)), Point3D(id="b", position=(0, 1, 0))),
        transform=Transform3D(translate=Vec3(10, 0, 0), scale=Vec3(2, 2, 2)),
    )
    assert Scene3D(g).bounds() == Bounds3D(Vec3(10, 0, 0), Vec3(12, 2, 0))
    assert Scene3D().bounds() is None


def test_camera_validation_and_fitting():
    with pytest.raises(ConfigurationError):
        Camera3D(position=(0, 0, 0), target=(0, 0, 0))
    with pytest.raises(ConfigurationError):
        Camera3D(fov=0.0)
    with pytest.raises(ConfigurationError):
        Camera3D(near=5, far=1)
    with pytest.raises(ConfigurationError):
        Camera3D(projection="fisheye")
    cam = Camera3D.fitting(Bounds3D(Vec3(-1, -1, -1), Vec3(1, 1, 1)))
    assert cam.target == Vec3(0, 0, 0)
    assert (cam.position - cam.target).length() > math.sqrt(3)  # far enough to see the corners


def test_properties_animate_through_the_same_builders():
    mesh = MeshData([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [(0, 1, 2)])
    node = Mesh3D(id="m", mesh=mesh)
    other = MeshData([(0, 0, 1), (1, 0, 1), (0, 1, 1)], [(0, 1, 2)])
    scene = Scene3D(node)
    motion = (
        node.animate.mesh.to(other, duration=1.0)
        .with_(scene.camera.animate.position.to((0, -9, 2), duration=1.0))
        .with_(node.animate.material.to(Material(ambient=0.8, diffuse=0.2), duration=1.0))
    )
    anim = Animation(scene, motion)
    mid = anim.sample(0.5)
    assert mid.get("m").mesh.bounds().min.z == pytest.approx(0.5)  # type: ignore[union-attr]
    assert mid.get("m").material.ambient == pytest.approx(0.575)
    assert mid.camera.position.y == pytest.approx((-7 + -9) / 2)
    ref = node.ref("mesh")
    assert isinstance(ref, PropertyRef) and ref.value_type is MeshData


def test_camera_paths_use_the_same_easing_and_keyframes():
    scene = Scene3D(Point3D(id="p"))
    cam = scene.camera
    orbit = cam.animate.position.keyframes((0.0, (5, -7, 4)), (1.0, (7, 5, 4)), (2.0, (-5, 7, 4)))
    anim = Animation(scene, orbit)
    assert anim.sample(1.0).camera.position == Vec3(7, 5, 4)
    assert anim.sample(0.5).camera.position == Vec3(6, -1, 4)
    rot = Transform3D(rotation=Quaternion.from_axis_angle((0, 0, 1), math.pi))
    g = Group3D(id="g")
    spin = Animation(Scene3D(g), g.animate.transform.to(rot, duration=1.0))
    half = spin.sample(0.5).get("g").transform.rotation.rotate(Vec3(1, 0, 0))
    assert (half.x, half.y) == pytest.approx((0.0, 1.0), abs=1e-9)
