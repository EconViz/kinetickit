from __future__ import annotations

import math

import pytest

from kinetickit.errors import ConfigurationError
from kinetickit.geometry.two_d import Bounds2D, Matrix3, Path2D, PathCommand, Transform2D, Vec2
from kinetickit.interpolation import DEFAULT_REGISTRY


def test_vec2_arithmetic_and_coercion():
    assert Vec2(1, 2) + (3, 4) == Vec2(4, 6)
    assert Vec2(3, 4).length() == 5.0
    assert Vec2.coerce((1, 2)) == Vec2(1, 2)
    assert tuple(Vec2(1, 2)) == (1.0, 2.0)
    assert Vec2(1, 0).cross(Vec2(0, 1)) == 1.0
    for bad in ("ab", (1,), (1, 2, 3), None):
        with pytest.raises(ConfigurationError):
            Vec2.coerce(bad)
    with pytest.raises(ConfigurationError):
        Vec2(float("nan"), 0)


def test_cartesian_y_up_rotation_is_counter_clockwise():
    p = Matrix3.rotation(math.pi / 2).apply(Vec2(1, 0))
    assert p.x == pytest.approx(0.0, abs=1e-12) and p.y == pytest.approx(1.0)


def test_transform_order_is_scale_then_rotate_then_translate():
    t = Transform2D(translate=Vec2(10, 0), rotation=math.pi / 2, scale=Vec2(2, 2))
    p = t.apply(Vec2(1, 0))  # scale -> (2,0); rotate -> (0,2); translate -> (10,2)
    assert (p.x, p.y) == (pytest.approx(10.0), pytest.approx(2.0))


def test_transform_pivot_rotates_about_a_point():
    t = Transform2D(rotation=math.pi, pivot=Vec2(1, 1))
    p = t.apply(Vec2(2, 1))
    assert (p.x, p.y) == (pytest.approx(0.0, abs=1e-12), pytest.approx(1.0))


def test_matrix_inverse_roundtrip_and_singular():
    t = Transform2D(Vec2(3, -2), 0.7, Vec2(2, 0.5)).matrix()
    p = Vec2(1.5, 2.5)
    q = t.inverse().apply(t.apply(p))
    assert (q.x, q.y) == (pytest.approx(p.x), pytest.approx(p.y))
    with pytest.raises(ConfigurationError):
        Transform2D(scale=Vec2(0, 1)).matrix().inverse()


def test_uniform_scalar_scale_is_accepted():
    assert Transform2D(scale=2).scale == Vec2(2, 2)


def test_transform_interpolation():
    a, b = Transform2D(), Transform2D(translate=Vec2(10, 0), rotation=1.0, scale=Vec2(3, 3))
    mid = DEFAULT_REGISTRY.interpolate(Transform2D, a, b, 0.5)
    assert mid.translate == Vec2(5, 0) and mid.rotation == 0.5 and mid.scale == Vec2(2, 2)


def test_bounds_union_and_validation():
    b = Bounds2D((0, 0), (2, 2)).union(Bounds2D((1, -1), (3, 1)))
    assert b == Bounds2D((0, -1), (3, 2))
    assert b.size == Vec2(3, 3) and b.center == Vec2(1.5, 0.5)
    assert b.contains(Vec2(1, 1)) and not b.contains(Vec2(4, 0))
    assert Bounds2D.of([]) is None
    with pytest.raises(ConfigurationError):
        Bounds2D((1, 1), (0, 0))


def test_path_validation():
    with pytest.raises(ConfigurationError):
        Path2D((PathCommand("L", (Vec2(0, 0),)),))
    with pytest.raises(ConfigurationError):
        PathCommand("L", (Vec2(0, 0), Vec2(1, 1)))
    with pytest.raises(ConfigurationError):
        PathCommand("X")
    with pytest.raises(ConfigurationError):
        Path2D((PathCommand("M", (Vec2(0, 0),)), PathCommand("Z"), PathCommand("L", (Vec2(1, 1),))))
    with pytest.raises(ConfigurationError):
        Path2D.polyline([(0, 0)])


def test_path_constructors_and_svg():
    rect = Path2D.rect(0, 0, 2, 1)
    assert rect.kinds == ("M", "L", "L", "L", "Z")
    assert rect.to_svg() == "M0 0 L2 0 L2 1 L0 1 Z"
    assert (
        Path2D.polygon([(0, 0), (4, 0), (4, 4)], [(1, 1), (2, 1), (2, 2)]).subpaths().__len__() == 2
    )
    assert Path2D.polyline([(0, 0), (1, 1)], closed=True).kinds[-1] == "Z"


def test_exact_bounds_include_curve_extrema():
    arc = Path2D(
        (
            PathCommand("M", (Vec2(0, 0),)),
            PathCommand("C", (Vec2(0, 2), Vec2(2, 2), Vec2(2, 0))),
        )
    )
    b = arc.bounds()
    assert b is not None and b.max.y == pytest.approx(1.5) and b.max.x == 2.0
    circle = Path2D.circle(0, 0, 1).bounds()
    assert circle is not None
    assert circle.max.x == pytest.approx(1.0) and circle.max.y == pytest.approx(1.0)
    assert circle.min.x == pytest.approx(-1.0)
    quad = Path2D((PathCommand("M", (Vec2(0, 0),)), PathCommand("Q", (Vec2(1, 2), Vec2(2, 0)))))
    assert quad.bounds().max.y == pytest.approx(1.0)  # type: ignore[union-attr]


def test_path_interpolation_requires_matching_structure():
    a, b = Path2D.polyline([(0, 0), (2, 0)]), Path2D.polyline([(0, 2), (2, 2)])
    mid = DEFAULT_REGISTRY.interpolate(Path2D, a, b, 0.5)
    assert mid == Path2D.polyline([(0, 1), (2, 1)])
    with pytest.raises(ConfigurationError, match="command structure"):
        DEFAULT_REGISTRY.interpolate(Path2D, a, Path2D.polyline([(0, 0), (1, 1), (2, 2)]), 0.5)


def test_path_transform_does_not_mutate():
    p = Path2D.rect(0, 0, 1, 1)
    q = p.transformed(Matrix3.translation(Vec2(5, 5)))
    assert p.bounds() == Bounds2D((0, 0), (1, 1))
    assert q.bounds() == Bounds2D((5, 5), (6, 6))
