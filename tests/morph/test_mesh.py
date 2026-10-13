from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from kinetickit.animation import Animation
from kinetickit.errors import ConfigurationError
from kinetickit.geometry.three_d import Matrix4, MeshData, SurfaceGrid, Vec3, Vec3Array
from kinetickit.interpolation import DEFAULT_REGISTRY
from kinetickit.morph import (
    MeshMorph,
    SurfaceMorph,
    normalize_meshes,
    normalize_surfaces,
    resample_grid,
)
from kinetickit.morph.mesh import normalize_points
from kinetickit.scene import Mesh3D, Scene3D, Surface3D

CUBE_V = [(x, y, z) for x in (0, 1) for y in (0, 1) for z in (0, 1)]
CUBE_Q = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]


def cube(offset=0.0):
    return MeshData.from_quads(np.array(CUBE_V, float) + offset, CUBE_Q)


def test_compatible_meshes_normalize_unchanged():
    a, b = cube(), cube(2.0)
    r = normalize_meshes(a, b)
    assert r.compatible and r.start is a and r.end is b


def test_compatible_meshes_morph_deterministically_at_arbitrary_times():
    a, b = cube(), cube().transformed(Matrix4.scaling(Vec3(2, 2, 2)))
    n = Mesh3D(id="m", mesh=a)
    anim = Animation(Scene3D(n), n.morph_to(b, duration=1.0))
    for t in (0.0, 0.123, 0.5, 0.987, 1.0):
        one, two = anim.sample(t).get("m").mesh, anim.sample(t).get("m").mesh
        assert one == two
        assert one.bounds().max.x == pytest.approx(1.0 + t)  # type: ignore[union-attr]
    assert anim.sample(1.0).get("m").mesh == b


def test_normals_and_colors_morph_with_vertices():
    n0 = np.tile([0.0, 0.0, 1.0], (8, 1))
    n1 = np.tile([1.0, 0.0, 0.0], (8, 1))
    a = MeshData(CUBE_V, cube().faces, normals=n0, colors=np.tile([1.0, 0, 0, 1], (8, 1)))
    b = MeshData(CUBE_V, cube().faces, normals=n1, colors=np.tile([0, 0, 1.0, 1], (8, 1)))
    mid = DEFAULT_REGISTRY.interpolate(MeshData, a, b, 0.5)
    assert np.linalg.norm(mid.normals, axis=1) == pytest.approx(1.0)  # type: ignore[arg-type]
    assert mid.colors[0].tolist() == [0.5, 0.0, 0.5, 1.0]  # type: ignore[index]


def test_topology_mismatch_is_reported_never_silently_fixed():
    a = cube()
    b = MeshData(CUBE_V[:4], [(0, 1, 2), (1, 2, 3)])
    r = normalize_meshes(a, b)
    assert not r.compatible
    err = [d for d in r.diagnostics if d.severity == "error"]
    assert err and err[0].code == "mesh-topology-mismatch" and "8 vertices" in err[0].message
    n = Mesh3D(id="m", mesh=a)
    with pytest.raises(ConfigurationError, match="cannot morph"):
        n.morph_to(b, duration=1.0)
    with pytest.raises(ConfigurationError, match="different topology"):
        DEFAULT_REGISTRY.interpolate(MeshData, a, b, 0.5)


def test_same_counts_but_different_faces_still_need_an_explicit_choice():
    a = cube()
    shuffled = MeshData(CUBE_V, a.faces[::-1])
    assert not normalize_meshes(a, shuffled).compatible
    chosen = normalize_meshes(a, shuffled, MeshMorph(faces="source"))
    assert chosen.compatible and chosen.end.faces.tolist() == a.faces.tolist()
    assert any(d.code == "faces-chosen" for d in chosen.diagnostics)
    with pytest.raises(ConfigurationError):
        MeshMorph(faces="neither")


def test_explicit_vertex_correspondence_reorders_the_target():
    a = cube()
    perm = [3, 0, 1, 2, 7, 4, 5, 6]
    scrambled = MeshData(np.array(CUBE_V, float)[perm], np.argsort(perm)[a.faces])
    to_target = tuple(int(i) for i in np.argsort(perm))  # source vertex i -> its place in target
    r = normalize_meshes(a, scrambled, MeshMorph(vertex_map=to_target))
    assert r.compatible and np.array_equal(r.end.vertices, a.vertices)
    assert any(d.code == "vertex-map" for d in r.diagnostics)
    with pytest.raises(ConfigurationError, match="permutation"):
        normalize_meshes(a, a, MeshMorph(vertex_map=(0, 1, 2)))
    with pytest.raises(ConfigurationError, match="permutation"):
        normalize_meshes(a, a, MeshMorph(vertex_map=(0, 0, 1, 2, 3, 4, 5, 6)))


def test_custom_normalizer_is_validated():
    a, b = cube(), MeshData(CUBE_V[:3], [(0, 1, 2)])
    ok = normalize_meshes(a, b, MeshMorph(normalizer=lambda x, y: (x, x)))
    assert ok.compatible
    with pytest.raises(ConfigurationError, match="equal topology"):
        normalize_meshes(a, b, MeshMorph(normalizer=lambda x, y: (x, y)))


def test_degeneracy_diagnostics_are_exposed():
    flat = MeshData([(0, 0, 0), (1, 0, 0), (2, 0, 0), (0, 1, 0)], [(0, 1, 2), (0, 1, 3)])
    r = normalize_meshes(flat, flat)
    codes = {d.code for d in r.diagnostics}
    assert "degenerate-faces" in codes and "unused-vertices" not in codes
    assert any("source" in d.message for d in r.diagnostics) and any(
        "target" in d.message for d in r.diagnostics
    )
    loose = MeshData(CUBE_V, [(0, 1, 2)])
    assert any(d.code == "unused-vertices" for d in normalize_meshes(loose, loose).diagnostics)


def test_surface_resampling_policies():
    coarse = SurfaceGrid.from_height(np.linspace(0, 1, 3), np.linspace(0, 1, 3), np.zeros((3, 3)))
    fine = SurfaceGrid.from_height(np.linspace(0, 1, 5), np.linspace(0, 1, 5), np.ones((5, 5)))
    r = normalize_surfaces(coarse, fine)
    assert not r.compatible and r.diagnostics[0].code == "surface-sampling-mismatch"
    to_target = normalize_surfaces(coarse, fine, SurfaceMorph(policy="target"))
    assert to_target.compatible and to_target.start.shape == (5, 5) and to_target.end is fine
    to_source = normalize_surfaces(coarse, fine, SurfaceMorph(policy="source"))
    assert to_source.start is coarse and to_source.end.shape == (3, 3)
    forced = normalize_surfaces(coarse, fine, SurfaceMorph(shape=(7, 6)))
    assert forced.start.shape == forced.end.shape == (7, 6)
    with pytest.raises(ConfigurationError):
        SurfaceMorph(policy="smallest")
    with pytest.raises(ConfigurationError):
        SurfaceMorph(shape=(1, 5))


def test_resampling_preserves_corners_and_planar_geometry():
    xs, ys = np.linspace(0, 2, 3), np.linspace(0, 4, 5)
    plane = SurfaceGrid.from_height(xs, ys, np.add.outer(ys, 2 * xs))
    fine = resample_grid(plane, 9, 7)
    assert fine.shape == (9, 7)
    assert fine.points[0, 0].tolist() == plane.points[0, 0].tolist()
    assert fine.points[-1, -1].tolist() == plane.points[-1, -1].tolist()
    x, y, z = fine.points[3, 2]
    assert z == pytest.approx(y + 2 * x)  # a plane stays a plane
    assert resample_grid(plane, 5, 3) is plane


def test_surface_morph_to_follows_the_policy():
    s0 = Surface3D.height_field("s", np.linspace(0, 1, 3), np.linspace(0, 1, 3), np.zeros((3, 3)))
    target = SurfaceGrid.from_height(np.linspace(0, 1, 5), np.linspace(0, 1, 5), np.ones((5, 5)))
    with pytest.raises(ConfigurationError, match="cannot morph"):
        s0.morph_to(target, duration=1.0)
    anim = Animation(
        Scene3D(s0), s0.morph_to(target, duration=1.0, morph=SurfaceMorph(policy="target"))
    )
    assert anim.sample(0.5).get("s").grid.points[..., 2].mean() == pytest.approx(0.5)
    assert anim.sample(0.5).get("s").grid.shape == (5, 5)


def test_point_lists_match_by_index_only():
    a, b = Vec3Array(np.zeros((4, 3))), Vec3Array(np.ones((5, 3)))
    assert normalize_points(a, a).compatible
    r = normalize_points(a, b)
    assert not r.compatible and r.diagnostics[0].code == "point-count-mismatch"


@given(st.floats(min_value=0.0, max_value=1.0))
def test_interpolation_is_pure_in_time(p):
    a, b = cube(), cube(3.0)
    one = DEFAULT_REGISTRY.interpolate(MeshData, a, b, p)
    two = DEFAULT_REGISTRY.interpolate(MeshData, a, b, p)
    assert one == two
    assert one.bounds().min.x == pytest.approx(3.0 * p, abs=1e-12)  # type: ignore[union-attr]
