from __future__ import annotations

import math

import numpy as np
import pytest

from kinetickit import ease
from kinetickit.geometry.three_d import MeshData, Quaternion, Transform3D, Vec3
from kinetickit.morph import MeshMorph, SurfaceMorph
from kinetickit.scene import Camera3D, Group3D, Line3D, Mesh3D, Point3D, Scene3D, Surface3D
from kinetickit.transitions import INCOMING_SUFFIX, SceneTransition, TransitionPolicy

V = [(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1)]
F = [(0, 2, 1), (0, 1, 3), (1, 2, 3), (0, 3, 2)]


def tetra(scale=1.0):
    return MeshData(np.array(V, float) * scale, F)


def run(a, b, t, **kw):
    tr = SceneTransition.between(a, b, **kw)
    return tr, tr.animation().sample(t)


def test_compatible_meshes_transition_by_vertex_interpolation():
    a, b = Scene3D(Mesh3D(id="m", mesh=tetra(1))), Scene3D(Mesh3D(id="m", mesh=tetra(3)))
    tr, mid = run(a, b, 0.15)
    assert mid.get("m").mesh.bounds().max.x == pytest.approx(1 + 2 * ease.in_out_cubic(0.5))  # type: ignore[union-attr]
    assert INCOMING_SUFFIX not in "".join(tr.scene.ids)
    assert run(a, b, 0.3)[1].get("m").mesh == tetra(3)
    assert not tr.warnings


def test_topology_mismatch_cross_fades_and_never_corrupts_geometry():
    other = MeshData(V[:3], [(0, 1, 2)])
    a, b = Scene3D(Mesh3D(id="m", mesh=tetra())), Scene3D(Mesh3D(id="m", mesh=other))
    tr, mid = run(a, b, 0.15)
    assert mid.get("m").opacity == pytest.approx(0.5)
    assert mid.get("m" + INCOMING_SUFFIX).opacity == pytest.approx(0.5)
    assert mid.get("m").mesh == tetra() and mid.get("m" + INCOMING_SUFFIX).mesh == other
    codes = [d.code for d in tr.diagnostics]
    assert "mesh-topology-mismatch" in codes and "incompatible-morph" in codes
    assert all(d.node_id == "m" for d in tr.diagnostics)


def test_explicit_mesh_morph_rescues_the_pair():
    other = MeshData(V, F[::-1])
    a, b = Scene3D(Mesh3D(id="m", mesh=tetra())), Scene3D(Mesh3D(id="m", mesh=other))
    assert "m" + INCOMING_SUFFIX in SceneTransition.between(a, b).scene
    ok = SceneTransition.between(a, b, morphs={"m": MeshMorph(faces="target")})
    assert "m" + INCOMING_SUFFIX not in ok.scene


def test_surface_policy_and_camera_dolly():
    s0 = Surface3D.height_field("s", np.linspace(0, 1, 3), np.linspace(0, 1, 3), np.zeros((3, 3)))
    s1 = Surface3D.height_field("s", np.linspace(0, 1, 5), np.linspace(0, 1, 5), np.ones((5, 5)))
    a = Scene3D(s0, camera=Camera3D(position=(0, -5, 0)))
    b = Scene3D(s1, camera=Camera3D(position=(0, -10, 0), projection="orthographic"))
    fade = SceneTransition.between(a, b)
    assert "s" + INCOMING_SUFFIX in fade.scene
    tr = SceneTransition.between(a, b, morphs={"s": SurfaceMorph(policy="target")})
    anim = tr.animation()
    assert anim.sample(0.15).get("s").grid.shape == (5, 5)
    assert anim.sample(0.15).camera.position.y == pytest.approx(
        -7.5
    )  # same easing system as values
    assert anim.sample(0.29).camera.projection == "perspective"
    assert anim.sample(0.3).camera.projection == "orthographic"  # a discrete switch at the end


def test_camera_clipping_values_and_fov_animate():
    a, b = Scene3D(Point3D(id="p")), Scene3D(Point3D(id="p"))
    b = b.bind({b.camera.ref("fov"): 1.2, b.camera.ref("near"): 1.0, b.camera.ref("far"): 50.0})
    _, end = run(a, b, 0.3)
    assert (
        end.camera.fov == pytest.approx(1.2) and end.camera.near == 1.0 and end.camera.far == 50.0
    )
    _, mid = run(a, b, 0.15)
    assert mid.camera.far == pytest.approx((1000 + 50) / 2)


def test_enter_and_exit_behaviour_for_spatial_objects():
    a = Scene3D(Line3D(id="gone", end=(1, 0, 0)), Point3D(id="old"))
    b = Scene3D(Line3D(id="drawn", end=(2, 0, 0)), Mesh3D(id="newmesh", mesh=tetra()))
    tr = SceneTransition.between(a, b)
    anim = tr.animation()
    assert (
        anim.sample(0.0).get("newmesh").opacity == 0.0
        and anim.sample(0.3).get("newmesh").opacity == 1.0
    )
    assert anim.sample(0.3).get("old").opacity == 0.0 and anim.sample(0.0).get("old").opacity == 1.0
    draw = SceneTransition.between(
        a, b, policy=TransitionPolicy(enter="draw", exit="draw")
    ).animation()
    assert draw.sample(0.0).get("drawn").draw_progress == 0.0
    assert draw.sample(0.3).get("drawn").draw_progress == 1.0
    assert draw.sample(0.3).get("gone").draw_progress == 0.0
    cut = SceneTransition.between(a, b, policy=TransitionPolicy(enter="cut", exit="cut"))
    assert "old" not in cut.scene and cut.scene.get("newmesh").opacity == 1.0


def test_groups_transform_by_quaternion_through_transitions():
    child = Point3D(id="c", position=(1, 0, 0))
    a = Scene3D(Group3D(id="g", children=(child,)))
    spun = Transform3D(rotation=Quaternion.from_axis_angle((0, 0, 1), math.pi))
    b = Scene3D(Group3D(id="g", children=(child,), transform=spun))
    _, mid = run(a, b, 0.15)
    r = mid.get("g").transform.rotation.rotate(Vec3(1, 0, 0))
    assert (r.x, r.y) == pytest.approx((0.0, 1.0), abs=1e-9)  # halfway = 90°, shortest arc


def test_3d_transition_is_deterministic():
    a, b = Scene3D(Mesh3D(id="m", mesh=tetra(1))), Scene3D(Mesh3D(id="m", mesh=tetra(2)))
    one, two = SceneTransition.between(a, b).animation(), SceneTransition.between(a, b).animation()
    for t in (0.0, 0.07, 0.19, 0.3):
        assert one.sample(t) == two.sample(t)


def test_2d_and_3d_scenes_cannot_be_mixed():
    from kinetickit.errors import ConfigurationError
    from kinetickit.scene import Scene2D

    with pytest.raises(ConfigurationError):
        SceneTransition.between(Scene2D(), Scene3D())
