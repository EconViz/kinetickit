from __future__ import annotations

import math

import numpy as np
import pytest
from tests.support.smil import Q, evaluate, numbers, parse

from kinetickit.animation import Animation
from kinetickit.errors import CapabilityError
from kinetickit.geometry.three_d import MeshData, Quaternion, Transform3D
from kinetickit.renderers import project_scene
from kinetickit.renderers.vector import SvgSettings, VectorRenderer
from kinetickit.scene import (
    Camera3D,
    Group3D,
    Mesh3D,
    Point2D,
    Point3D,
    Polyline3D,
    Scene3D,
    Surface3D,
)

SET = SvgSettings(width=200, height=200, samples=16, precision=5)


def camera(**kw):
    return Camera3D(position=(0, -6, 2), target=(0, 0, 0), fov=math.pi / 3, **kw)


def render(anim, **kw):
    return VectorRenderer().render_document(anim, SvgSettings(**{**SET.__dict__, **kw}))


def tri_mesh(z=0.0):
    return MeshData([(-1, 0, z), (1, 0, z), (0, 0, z + 1.5)], [(0, 1, 2)])


def test_static_3d_scene_is_native_projected_vector():
    scene = Scene3D(
        Mesh3D(id="m", mesh=tri_mesh(), color="#3366ff"),
        Polyline3D(id="axis", points=[(0, 0, 0), (2, 0, 0)]),
        Point3D(id="p", position=(0, 0, 2), size=5),
        overlay=[Point2D(id="hud", position=(10, 10))],
        camera=camera(),
    )
    doc = render(Animation(scene))
    root = parse(doc.text)
    paths = [e for e in root.iter() if e.tag == Q + "path"]
    assert len(paths) >= 3 and not [e for e in root.iter() if e.tag == Q + "image"]
    face = next(e for e in root.iter() if e.get("data-kk-id") == "m")
    assert face.get("d").startswith("M") and face.get("d").endswith("Z")
    assert doc.animation_count == 0 and "m" in doc.element_ids
    assert any(e.get("id") == "hud" for e in root.iter())


def test_projected_coordinates_match_the_shared_projection():
    scene = Scene3D(Mesh3D(id="m", mesh=tri_mesh()), camera=camera())
    root = parse(render(Animation(scene)).text)
    face = next(e for e in root.iter() if e.get("data-kk-id") == "m")
    prim = project_scene(scene, 200, 200)[0]
    assert numbers(face.get("d")) == pytest.approx(prim.points.ravel().tolist(), abs=1e-3)


def test_animated_camera_is_sampled_and_matches_at_sample_times():
    mesh = Mesh3D(id="m", mesh=tri_mesh())
    scene = Scene3D(mesh, camera=camera())
    anim = Animation(scene, scene.camera.animate.position.to((6, 0, 2), duration=2.0))
    doc = render(anim)
    root = parse(doc.text)
    face = next(e for e in root.iter() if e.get("data-kk-id") == "m")
    [d] = [a for a in face if a.get("attributeName") == "d"]
    assert d.get("calcMode") == "linear"
    for t in (0.0, 0.5, 1.0, 2.0):  # sample times of the K=16 grid
        want = project_scene(anim.sample(t), 200, 200)[0].points.ravel().tolist()
        assert numbers(evaluate(d, t)) == pytest.approx(want, abs=0.05)
    assert any("painter" in w for w in doc.warnings)


def test_object_transform_and_mesh_morph_animate():
    g = Group3D(id="g", children=(Mesh3D(id="m", mesh=tri_mesh()),))
    scene = Scene3D(g, camera=camera())
    spin = Transform3D(rotation=Quaternion.from_axis_angle((0, 0, 1), math.pi / 2))
    anim = Animation(scene, g.animate.transform.to(spin, duration=1.0))
    root = parse(render(anim).text)
    face = next(e for e in root.iter() if e.get("data-kk-id") == "m")
    [d] = [a for a in face if a.get("attributeName") == "d"]
    want = project_scene(anim.sample(0.5), 200, 200)[0].points.ravel().tolist()
    assert numbers(evaluate(d, 0.5)) == pytest.approx(want, abs=0.1)
    m = Mesh3D(id="x", mesh=tri_mesh())
    morph = Animation(Scene3D(m, camera=camera()), m.animate.mesh.to(tri_mesh(z=2.0), duration=1.0))
    assert render(morph).animation_count >= 1


def test_color_and_opacity_changes_animate_fill():
    m = Mesh3D(id="m", mesh=tri_mesh(), color="#000000")
    anim = Animation(
        Scene3D(m, camera=camera()),
        m.animate.color.to("#ffffff", duration=1.0).with_(m.animate.opacity.to(0.5, duration=1.0)),
    )
    root = parse(render(anim).text)
    face = next(e for e in root.iter() if e.get("data-kk-id") == "m")
    names = {a.get("attributeName") for a in face}
    assert {"fill", "fill-opacity"} <= names


def test_primitives_entering_or_leaving_the_view_fail_loudly():
    p = Point3D(id="p", position=(0, 0, 0))
    scene = Scene3D(p, camera=Camera3D(position=(0, -6, 0), target=(0, 0, 0), near=1, far=20))
    # the point moves behind the camera, so the set of projected primitives would change
    anim = Animation(scene, p.animate.position.to((0, -10, 0), duration=1.0))
    with pytest.raises(CapabilityError, match="change over time"):
        render(anim)


def test_too_dense_sampling_is_refused_not_truncated():
    p = Point3D(id="p")
    scene = Scene3D(p, camera=camera())
    long = p.animate.position.to((1, 0, 0), duration=1.0).repeat(100)
    with pytest.raises(CapabilityError, match="samples"):
        render(Animation(scene, long), samples=24)


def test_surface_export_via_save(tmp_path):
    s = Surface3D.height_field(
        "s", np.linspace(-1, 1, 6), np.linspace(-1, 1, 6), np.zeros((6, 6)), edge_color="#000000"
    )
    scene = Scene3D(s, camera=camera())
    out = tmp_path / "surface.svg"
    manifest = Animation(scene).save(out, renderer="vector", width=200, height=200)
    assert manifest.format == "svg"
    root = parse(out.read_text())
    assert len([e for e in root.iter() if e.get("data-kk-id") == "s"]) == 50
