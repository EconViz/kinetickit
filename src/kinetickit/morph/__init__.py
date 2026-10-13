"""Shape normalization and correspondence for morphing."""

from __future__ import annotations

from kinetickit.morph.diagnostics import MorphDiagnostic
from kinetickit.morph.path import NormalizedPair, PathMorph, normalize_paths
from kinetickit.morph.registry import has_normalizer, normalize_pair, register_normalizer

__all__ = [
    "MorphDiagnostic",
    "NormalizedPair",
    "PathMorph",
    "has_normalizer",
    "normalize_pair",
    "normalize_paths",
    "register_normalizer",
]
