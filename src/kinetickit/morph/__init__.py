"""Shape normalization and correspondence for morphing."""

from __future__ import annotations

from kinetickit.morph.diagnostics import MorphDiagnostic
from kinetickit.morph.mesh import (
    MeshMorph,
    SurfaceMorph,
    mesh_diagnostics,
    normalize_meshes,
    normalize_surfaces,
    resample_grid,
)
from kinetickit.morph.path import NormalizedPair, PathMorph, normalize_paths
from kinetickit.morph.registry import has_normalizer, normalize_pair, register_normalizer

__all__ = [
    "MeshMorph",
    "MorphDiagnostic",
    "NormalizedPair",
    "PathMorph",
    "SurfaceMorph",
    "has_normalizer",
    "mesh_diagnostics",
    "normalize_meshes",
    "normalize_pair",
    "normalize_paths",
    "normalize_surfaces",
    "register_normalizer",
    "resample_grid",
]
