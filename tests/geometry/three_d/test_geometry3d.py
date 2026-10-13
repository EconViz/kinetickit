from __future__ import annotations

import math

import numpy as np
import pytest

from kinetickit.errors import ConfigurationError
from kinetickit.geometry.three_d import (
    Bounds3D,
    Matrix4,
    MeshData,
    Quaternion,
    SurfaceGrid,
    Transform3D,
    Vec3,
    Vec3Array,
)
from kinetickit.interpolation import DEFAULT_REGISTRY

CUBE_V = [(x, y, z) for x in (0, 1) for y in (0, 1) for z in (0, 1)]
CUBE_Q = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]


def cube() -> MeshData:
    return MeshData.from_quads(CUBE_V, CUBE_Q)


def test_vec3_basics_and_right_handed_cross_product():
    x, y, z = Vec3(1, 0, 0), Vec3(0, 1, 0), Vec3(0, 0, 1)
    assert x.cross(y) == z and y.cross(z) == x and z.cross(x) == y
    assert Vec3(1, 2, 3) + (1, 1, 1) == Vec3(2, 3, 4)
    assert Vec3(0, 3, 4).length() == 5.0
    assert Vec3(0, 0, 2).normalized() == z
    with pytest.raises(ConfigurationError):
        Vec3(0, 0, 0).normalized()
    with pytest.raises(ConfigurationError):
        Vec3.coerce((1, 2))
    with pytest.raises(ConfigurationError):
        Vec3(float("inf"), 0, 0)


def test_quaternions_are_normalized_wxyz_and_rotate_right_handed():
    q = Quaternion(2, 0, 0, 0)
    assert q.as_tuple() == (1.0, 0.0, 0.0, 0.0)
    quarter = Quaternion.from_axis_angle((0, 0, 1), math.pi / 2)
    r = quarter.rotate(Vec3(1, 0, 0))
    assert (r.x, r.y, r.z) == pytest.approx((0, 1, 0), abs=1e-12)  # x → y about +z
    with pytest.raises(ConfigurationError):
        Quaternion(0, 0, 0, 0)
    composed = quarter * quarter
    assert composed.rotate(Vec3(1, 0, 0)).x == pytest.approx(-1.0)


def test_slerp_takes_the_shortest_arc():
    a = Quaternion.from_axis_angle((0, 0, 1), 0.0)
    b = Quaternion.from_axis_angle((0, 0, 1), math.radians(350))
    mid = DEFAULT_REGISTRY.interpolate(Quaternion, a, b, 0.5)
    angle = 2 * math.acos(abs(mid.w))
    assert angle == pytest.approx(math.radians(5), abs=1e-9)  # via -10°, not +175°
    half = DEFAULT_REGISTRY.interpolate(
        Quaternion, a, Quaternion.from_axis_angle((0, 0, 1), math.pi), 0.5
    )
    r = half.rotate(Vec3(1, 0, 0))
    assert (r.x, r.y) == pytest.approx((0.0, 1.0), abs=1e-12)
    flipped = Quaternion(-a.w, -a.x, -a.y, -a.z)
    same = DEFAULT_REGISTRY.interpolate(Quaternion, a, flipped, 0.5)
    assert abs(same.w) == pytest.approx(1.0)  # q and -q are the same rotation


def test_transform_order_is_scale_rotate_translate_with_pivot():
    t = Transform3D(
        translate=Vec3(10, 0, 0),
        rotation=Quaternion.from_axis_angle((0, 0, 1), math.pi / 2),
        scale=Vec3(2, 2, 2),
    )
    p = t.matrix().apply_point(
        Vec3(1, 0, 0)
    )  # scale → (2,0,0); rotate → (0,2,0); translate → (10,2,0)
    assert (p.x, p.y, p.z) == pytest.approx((10, 2, 0), abs=1e-12)
    pivoted = Transform3D(
        rotation=Quaternion.from_axis_angle((0, 0, 1), math.pi), pivot=Vec3(1, 1, 0)
    )
    q = pivoted.matrix().apply_point(Vec3(2, 1, 0))
    assert (q.x, q.y) == pytest.approx((0, 1), abs=1e-12)
    assert Transform3D(scale=3).scale == Vec3(3, 3, 3)


def test_matrix_row_major_inverse_and_look_at():
    m = Transform3D(translate=Vec3(1, 2, 3), scale=Vec3(2, 2, 2)).matrix()
    assert m.m[3] == 1.0 and m.m[7] == 2.0 and m.m[11] == 3.0  # translation in the last column
    back = m.inverse().apply_point(m.apply_point(Vec3(4, 5, 6)))
    assert (back.x, back.y, back.z) == pytest.approx((4, 5, 6))
    with pytest.raises(ConfigurationError):
        Matrix4.scaling(Vec3(0, 1, 1)).inverse()
    view = Matrix4.look_at(Vec3(0, -5, 0), Vec3(0, 0, 0), Vec3(0, 0, 1))
    origin = view.apply_point(Vec3(0, 0, 0))
    assert (origin.x, origin.y, origin.z) == pytest.approx((0, 0, -5))  # 5 units down -z
    right = view.apply_direction(Vec3(1, 0, 0))
    assert (right.x, right.y, right.z) == pytest.approx((1, 0, 0))  # +x is screen-right
    up = view.apply_direction(Vec3(0, 0, 1))
    assert (up.x, up.y, up.z) == pytest.approx((0, 1, 0))  # +z is screen-up
    with pytest.raises(ConfigurationError):
        Matrix4.look_at(Vec3(0, 0, 0), Vec3(0, 0, 0), Vec3(0, 0, 1))
    with pytest.raises(ConfigurationError):
        Matrix4.look_at(Vec3(0, 0, 5), Vec3(0, 0, 0), Vec3(0, 0, 1))


def test_perspective_and_orthographic_reference_values():
    persp = Matrix4.perspective(math.pi / 2, 1.0, 1.0, 10.0)
    p = persp.apply_point(Vec3(1, 0, -5))  # 90° fov: x_ndc = x / depth
    assert p.x == pytest.approx(0.2)
    near = persp.apply_point(Vec3(0, 0, -1))
    far = persp.apply_point(Vec3(0, 0, -10))
    assert near.z == pytest.approx(-1.0) and far.z == pytest.approx(1.0)
    ortho = Matrix4.orthographic(4.0, 2.0, 1.0, 10.0)
    o = ortho.apply_point(Vec3(2, 1, -5))
    assert (o.x, o.y) == pytest.approx((0.5, 0.5))  # visible size is 8 x 4
    for bad in ((0.0, 1, 1, 10), (math.pi, 1, 1, 10), (1, 0, 1, 10), (1, 1, 0, 10), (1, 1, 5, 2)):
        with pytest.raises(ConfigurationError):
            Matrix4.perspective(*bad)


def test_bounds3d():
    b = Bounds3D.of([Vec3(0, 0, 0), Vec3(2, 4, 6)])
    assert b is not None and b.center == Vec3(1, 2, 3) and b.size == Vec3(2, 4, 6)
    assert len(b.corners()) == 8 and b.radius() == pytest.approx(math.sqrt(56) / 2)
    assert b.union(Bounds3D(Vec3(-1, 0, 0), Vec3(0, 1, 1))).min == Vec3(-1, 0, 0)
    with pytest.raises(ConfigurationError):
        Bounds3D(Vec3(1, 1, 1), Vec3(0, 0, 0))


def test_mesh_is_immutable_validated_and_outward_facing():
    m = cube()
    assert m.vertices.shape == (8, 3) and m.faces.shape == (12, 3)
    with pytest.raises(ValueError):
        m.vertices[0, 0] = 5.0  # read-only
    src = np.array(CUBE_V, float)
    held = MeshData(src, m.faces)
    src[0, 0] = 99.0
    assert held.vertices[0, 0] == 0.0  # the mesh owns a private copy
    with pytest.raises(ConfigurationError):
        MeshData(CUBE_V, [(0, 1, 9)])
    with pytest.raises(ConfigurationError):
        MeshData(CUBE_V, [(0, 1, 2)], normals=np.zeros((3, 3)))
    with pytest.raises(ConfigurationError):
        MeshData(CUBE_V, [(0, 1, 2)], colors=np.full((8, 4), 2.0))
    with pytest.raises(ConfigurationError):
        MeshData([(0, 0)], [(0, 0, 0)])
    assert m == cube() and hash(m) == hash(cube())
    assert m.bounds() == Bounds3D(Vec3(0, 0, 0), Vec3(1, 1, 1))
    assert m.face_areas().sum() == pytest.approx(6.0)


def test_degenerate_faces_and_normals():
    verts = [(0, 0, 0), (1, 0, 0), (0, 1, 0), (2, 0, 0)]
    m = MeshData(verts, [(0, 1, 2), (0, 1, 3), (0, 0, 1)])
    assert m.degenerate_faces() == (1, 2)  # collinear, and a repeated vertex
    n = m.vertex_normals()
    assert n[2] == pytest.approx([0, 0, 1])
    assert (
        MeshData(verts, [(0, 1, 2)], normals=np.tile([0.0, 0.0, -1.0], (4, 1))).vertex_normals()[
            0, 2
        ]
        == -1.0
    )


def test_mesh_topology_and_interpolation():
    a, b = cube(), cube().transformed(Matrix4.translation(Vec3(2, 0, 0)))
    assert a.same_topology(b)
    mid = DEFAULT_REGISTRY.interpolate(MeshData, a, b, 0.5)
    assert mid.bounds() == Bounds3D(Vec3(1, 0, 0), Vec3(2, 1, 1))
    other = MeshData(CUBE_V, [(0, 1, 2)])
    assert not a.same_topology(other)
    with pytest.raises(ConfigurationError, match="different topology"):
        DEFAULT_REGISTRY.interpolate(MeshData, a, other, 0.5)
    assert DEFAULT_REGISTRY.interpolate(MeshData, a, other, 0.0) is a


def test_mesh_transform_updates_normals_by_inverse_transpose():
    m = MeshData(
        [(0, 0, 0), (1, 0, 0), (0, 1, 0)], [(0, 1, 2)], normals=np.tile([0.0, 0.0, 1.0], (3, 1))
    )
    squashed = m.transformed(Matrix4.scaling(Vec3(1, 1, 5)))
    assert squashed.normals is not None
    assert squashed.normals[0] == pytest.approx([0, 0, 1])
    tilted = m.transformed(Matrix4.rotation(Quaternion.from_axis_angle((1, 0, 0), math.pi / 2)))
    assert tilted.normals[0] == pytest.approx([0, -1, 0], abs=1e-12)  # type: ignore[index]


def test_surfaces_are_sampled_once_and_meshed():
    xs, ys = np.linspace(0, 1, 5), np.linspace(0, 2, 3)
    z = np.add.outer(ys, xs)
    s = SurfaceGrid.from_height(xs, ys, z)
    assert s.shape == (3, 5)
    mesh = s.to_mesh()
    assert mesh.vertices.shape == (15, 3) and mesh.faces.shape == (2 * 2 * 4, 3)
    assert s.bounds() == Bounds3D(Vec3(0, 0, 0), Vec3(1, 2, 3))
    with pytest.raises(ConfigurationError):
        SurfaceGrid.from_height(xs, ys, np.zeros((5, 3)))
    calls = []

    def sphere(u, v):
        calls.append(1)
        return (math.sin(v) * math.cos(u), math.sin(v) * math.sin(u), math.cos(v))

    g = SurfaceGrid.parametric(sphere, (0, 2 * math.pi), (0, math.pi), 16, 9)
    n = len(calls)
    assert g.shape == (9, 16) and n == 144
    b = g.bounds()
    assert b.max.z == pytest.approx(1.0) and b.min.z == pytest.approx(-1.0)
    assert len(calls) == n  # no re-sampling later
    with pytest.raises(ConfigurationError):
        SurfaceGrid.parametric(sphere, (0, 1), (0, 1), 1, 5)
    with pytest.raises(ConfigurationError, match="resample"):
        DEFAULT_REGISTRY.interpolate(SurfaceGrid, s, g, 0.5)


def test_vec3_array_value():
    a = Vec3Array([(0, 0, 0), (1, 1, 1)])
    assert len(a) == 2 and a == Vec3Array([(0, 0, 0), (1, 1, 1)])
    mid = DEFAULT_REGISTRY.interpolate(Vec3Array, a, Vec3Array([(2, 2, 2), (3, 3, 3)]), 0.5)
    assert mid.data[1].tolist() == [2.0, 2.0, 2.0]
    with pytest.raises(ConfigurationError):
        DEFAULT_REGISTRY.interpolate(Vec3Array, a, Vec3Array([(0, 0, 0)]), 0.5)
    with pytest.raises(ConfigurationError):
        Vec3Array([[1, 2]])
    assert Vec3Array(np.zeros((0, 3))).bounds() is None
