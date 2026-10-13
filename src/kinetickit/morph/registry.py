"""Per-type pair normalizers used by morphs and transitions."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from kinetickit.errors import ConfigurationError
from kinetickit.geometry.three_d import MeshData, SurfaceGrid, Vec3Array
from kinetickit.geometry.two_d import Path2D
from kinetickit.morph.diagnostics import MorphDiagnostic
from kinetickit.morph.mesh import (
    MeshMorph,
    SurfaceMorph,
    normalize_meshes,
    normalize_points,
    normalize_surfaces,
)
from kinetickit.morph.path import NormalizedPair, PathMorph, normalize_paths

Normalizer = Callable[[Any, Any, Any], NormalizedPair]
_NORMALIZERS: dict[type, Normalizer] = {}


def register_normalizer(value_type: type, normalizer: Normalizer) -> None:
    """Register how two values of ``value_type`` become interpolation-compatible."""
    _NORMALIZERS[value_type] = normalizer


def has_normalizer(value_type: type) -> bool:
    return any(k in _NORMALIZERS for k in value_type.__mro__)


def normalize_pair(value_type: type, start: Any, end: Any, spec: Any = None) -> NormalizedPair:
    """Normalize ``start``/``end``; types without a normalizer are returned unchanged."""
    for klass in value_type.__mro__:
        fn = _NORMALIZERS.get(klass)
        if fn is not None:
            return fn(start, end, spec)
    return NormalizedPair(start, end, (), True)


def _path(start: Path2D, end: Path2D, spec: PathMorph | None) -> NormalizedPair:
    if start.kinds == end.kinds and spec is None:
        return NormalizedPair(start, end, (), True)
    return normalize_paths(start, end, spec)


def _check_spec(spec: Any, expected: type, kind: str) -> Any:
    if spec is not None and not isinstance(spec, expected):
        raise ConfigurationError(f"a {kind} needs a {expected.__name__}, got {type(spec).__name__}")
    return spec


def _mesh(start: MeshData, end: MeshData, spec: Any) -> NormalizedPair:
    r = normalize_meshes(start, end, _check_spec(spec, MeshMorph, "mesh"))
    return NormalizedPair(r.start, r.end, r.diagnostics, r.compatible)  # type: ignore[arg-type]


def _surface(start: SurfaceGrid, end: SurfaceGrid, spec: Any) -> NormalizedPair:
    r = normalize_surfaces(start, end, _check_spec(spec, SurfaceMorph, "surface"))
    return NormalizedPair(r.start, r.end, r.diagnostics, r.compatible)  # type: ignore[arg-type]


def _points(start: Vec3Array, end: Vec3Array, spec: Any) -> NormalizedPair:
    r = normalize_points(start, end)
    return NormalizedPair(r.start, r.end, r.diagnostics, r.compatible)  # type: ignore[arg-type]


register_normalizer(Path2D, _path)
register_normalizer(MeshData, _mesh)
register_normalizer(SurfaceGrid, _surface)
register_normalizer(Vec3Array, _points)

__all__ = [
    "MorphDiagnostic",
    "Normalizer",
    "has_normalizer",
    "normalize_pair",
    "register_normalizer",
]
