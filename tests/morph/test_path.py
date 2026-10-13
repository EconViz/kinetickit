from __future__ import annotations

import pytest

from kinetickit.errors import ConfigurationError
from kinetickit.geometry.two_d import Bounds2D, Path2D, PathCommand, Vec2
from kinetickit.interpolation import DEFAULT_REGISTRY
from kinetickit.morph import PathMorph, normalize_paths

SQUARE = Path2D.polygon([(0, 0), (2, 0), (2, 2), (0, 2)])
TRIANGLE = Path2D.polygon([(0, 0), (4, 0), (2, 3)])


def mid(pair, p):
    return DEFAULT_REGISTRY.interpolate(Path2D, pair.start, pair.end, p)


def test_different_vertex_counts_normalize_to_one_structure():
    pair = normalize_paths(SQUARE, TRIANGLE)
    assert pair.compatible and pair.start.kinds == pair.end.kinds
    assert pair.start.kinds == ("M", "C", "C", "C", "C", "Z")
    assert any(d.code == "resampled" for d in pair.diagnostics)


def test_normalization_preserves_the_shape_exactly():
    pair = normalize_paths(SQUARE, TRIANGLE)
    assert pair.start.bounds() == SQUARE.bounds()
    assert pair.end.bounds() == TRIANGLE.bounds()


def test_endpoints_of_the_morph_are_the_original_shapes():
    pair = normalize_paths(SQUARE, TRIANGLE)
    assert mid(pair, 0.0) == pair.start and mid(pair, 1.0) == pair.end


def test_contour_orientation_is_normalized():
    cw = Path2D.polygon([(0, 0), (0, 2), (2, 2), (2, 0)])
    pair = normalize_paths(SQUARE, cw)
    half = mid(pair, 0.5)
    assert half.bounds() == Bounds2D((0, 0), (2, 2))  # identical shapes do not collapse


def test_start_vertex_alignment_is_chosen_to_minimize_travel():
    shifted = Path2D.polygon([(2, 0), (2, 2), (0, 2), (0, 0)])
    pair = normalize_paths(SQUARE, shifted)
    assert pair.start == pair.end or mid(pair, 0.5).bounds() == Bounds2D((0, 0), (2, 2))
    assert not any(d.code == "ambiguous-alignment" for d in pair.diagnostics)


def test_symmetric_alignment_reports_ambiguity():
    circle = Path2D.circle(0, 0, 1)  # vertices at 0, 90, 180, 270 degrees
    d = 0.5**0.5
    square = Path2D.polygon([(d, d), (-d, d), (-d, -d), (d, -d)])  # vertices at 45, 135, ...
    pair = normalize_paths(circle, square)
    assert pair.compatible
    ambiguous = [x for x in pair.diagnostics if x.code == "ambiguous-alignment"]
    assert ambiguous and ambiguous[0].severity == "warning"
    forced = normalize_paths(circle, square, PathMorph(shifts=(2,)))
    assert not any(x.code == "ambiguous-alignment" for x in forced.diagnostics)


def test_explicit_shift_overrides_the_automatic_choice():
    auto = normalize_paths(SQUARE, SQUARE)
    forced = normalize_paths(SQUARE, SQUARE, PathMorph(shifts=(1,)))
    assert auto.end != forced.end
    assert forced.end.vertices()[0] != auto.end.vertices()[0]


def test_explicit_segment_count_and_validation():
    pair = normalize_paths(SQUARE, SQUARE, PathMorph(segments=(8,)))
    assert pair.start.kinds.count("C") == 8
    with pytest.raises(ConfigurationError):
        normalize_paths(SQUARE, SQUARE, PathMorph(segments=(2,)))
    with pytest.raises(ConfigurationError):
        normalize_paths(SQUARE, SQUARE, PathMorph(shifts=(0, 1)))
    with pytest.raises(ConfigurationError):
        normalize_paths(SQUARE, SQUARE, PathMorph(pairing=(1,)))


def test_subpath_count_mismatch_is_reported_not_guessed():
    two = Path2D.polygon([(0, 0), (4, 0), (4, 4), (0, 4)], [(1, 1), (2, 1), (2, 2)])
    pair = normalize_paths(SQUARE, two)
    assert not pair.compatible
    assert pair.diagnostics[0].code == "subpath-count-mismatch"
    assert pair.diagnostics[0].severity == "error"


def test_open_closed_mismatch_is_incompatible():
    line = Path2D.polyline([(0, 0), (1, 1), (2, 0)])
    closed = Path2D.polyline([(0, 0), (1, 1), (2, 0)], closed=True)
    pair = normalize_paths(line, closed)
    assert not pair.compatible and pair.diagnostics[0].code == "open-closed-mismatch"


def test_open_paths_choose_the_shorter_direction():
    a = Path2D.polyline([(0, 0), (1, 0), (2, 0)])
    b = Path2D.polyline([(2, 1), (1, 1), (0, 1)])
    auto = normalize_paths(a, b)
    assert any(d.code == "reversed-open-path" for d in auto.diagnostics)
    assert auto.end.vertices()[0] == Vec2(0, 1)
    kept = normalize_paths(a, b, PathMorph(reverses=(False,)))
    assert kept.end.vertices()[0] == Vec2(2, 1)


def test_holes_pair_with_holes_by_size():
    outer_a = [(0, 0), (10, 0), (10, 10), (0, 10)]
    hole_a = [(4, 4), (6, 4), (6, 6), (4, 6)]
    a = Path2D.polygon(outer_a, hole_a)
    b = Path2D.polygon(hole_a, outer_a)  # same two rings listed in the opposite order
    pair = normalize_paths(a, b)
    assert pair.compatible
    assert any(d.code == "subpaths-paired-by-area" for d in pair.diagnostics)
    half = mid(pair, 0.5)
    assert half.bounds() == Bounds2D((0, 0), (10, 10))


def test_explicit_pairing_overrides_size_pairing():
    a = Path2D.polygon([(0, 0), (10, 0), (10, 10)], [(4, 4), (6, 4), (6, 6)])
    forced = normalize_paths(a, a, PathMorph(pairing=(1, 0)))
    assert forced.compatible
    assert forced.start != forced.end


def test_custom_normalizer_replaces_everything():
    called = {}

    def norm(a, b):
        called["yes"] = True
        return a, a

    pair = normalize_paths(SQUARE, TRIANGLE, PathMorph(normalizer=norm))
    assert called and pair.start == pair.end
    with pytest.raises(ConfigurationError):
        normalize_paths(SQUARE, TRIANGLE, PathMorph(normalizer=lambda a, b: (a, b)))


def test_morph_is_deterministic():
    runs = [normalize_paths(SQUARE, TRIANGLE) for _ in range(3)]
    assert runs[0] == runs[1] == runs[2]
    for p in (0.0, 0.123, 0.5, 0.987, 1.0):
        assert mid(runs[0], p) == mid(runs[1], p)


def test_curves_and_lines_mix():
    arc = Path2D(
        (
            PathCommand("M", (Vec2(0, 0),)),
            PathCommand("Q", (Vec2(1, 2), Vec2(2, 0))),
            PathCommand("Z"),
        )
    )
    pair = normalize_paths(arc, SQUARE)
    assert pair.compatible and pair.start.bounds().max.y == pytest.approx(1.0)  # type: ignore[union-attr]
