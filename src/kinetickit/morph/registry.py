"""Per-type pair normalizers used by morphs and transitions."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from kinetickit.geometry.two_d import Path2D
from kinetickit.morph.diagnostics import MorphDiagnostic
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


register_normalizer(Path2D, _path)

__all__ = [
    "MorphDiagnostic",
    "Normalizer",
    "has_normalizer",
    "normalize_pair",
    "register_normalizer",
]
