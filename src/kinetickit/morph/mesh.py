"""Mesh, surface and point-list correspondence for 3D morphing.

Meshes are never reordered, truncated or resampled implicitly. Directly compatible meshes (same
connectivity) interpolate vertex by vertex; everything else needs an explicit choice through
:class:`MeshMorph` / :class:`SurfaceMorph`, or a cross-fade.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from kinetickit.errors import ConfigurationError
from kinetickit.geometry.three_d import MeshData, SurfaceGrid, Vec3Array
from kinetickit.morph.diagnostics import MorphDiagnostic


@dataclass(frozen=True)
class MeshNormalized:
    start: MeshData
    end: MeshData
    diagnostics: tuple[MorphDiagnostic, ...] = ()
    compatible: bool = True


@dataclass(frozen=True, slots=True)
class MeshMorph:
    """Explicit correspondence for meshes that are not directly compatible.

    ``vertex_map[i]`` is the target vertex that corresponds to source vertex ``i`` (a permutation
    of ``range(n)``); the target is reordered to match the source. ``faces`` (``"source"`` or
    ``"target"``) uses one mesh's connectivity for both when the vertex counts already agree.
    ``normalizer`` replaces everything with caller-supplied compatible meshes.
    """

    vertex_map: tuple[int, ...] | None = None
    faces: str | None = None
    normalizer: Callable[[MeshData, MeshData], tuple[MeshData, MeshData]] | None = None

    def __post_init__(self) -> None:
        if self.faces not in (None, "source", "target"):
            raise ConfigurationError("MeshMorph.faces must be 'source', 'target' or None")


def mesh_diagnostics(mesh: MeshData, label: str) -> list[MorphDiagnostic]:
    """Degeneracy diagnostics for one mesh."""
    out: list[MorphDiagnostic] = []
    bad = mesh.degenerate_faces()
    if bad:
        shown = ", ".join(str(i) for i in bad[:5]) + (" ..." if len(bad) > 5 else "")
        out.append(
            MorphDiagnostic(
                "degenerate-faces",
                f"{label} mesh has {len(bad)} degenerate face(s) (zero area or repeated vertex): {shown}",
                "warning",
            )
        )
    used = np.zeros(len(mesh.vertices), dtype=bool)
    used[mesh.faces.ravel()] = True
    if len(mesh.vertices) and not used.all():
        out.append(
            MorphDiagnostic(
                "unused-vertices",
                f"{label} mesh has {int((~used).sum())} vertex(es) not referenced by any face",
                "info",
            )
        )
    return out


def _reorder(mesh: MeshData, vertex_map: tuple[int, ...]) -> MeshData:
    order = np.asarray(vertex_map, dtype=np.int64)
    inverse = np.empty_like(order)
    inverse[order] = np.arange(len(order))
    return MeshData(
        mesh.vertices[order],
        inverse[mesh.faces],
        None if mesh.normals is None else mesh.normals[order],
        None if mesh.colors is None else mesh.colors[order],
    )


def normalize_meshes(
    source: MeshData, target: MeshData, morph: MeshMorph | None = None
) -> MeshNormalized:
    """Make two meshes interpolable, or report precisely why that is not possible."""
    morph = morph or MeshMorph()
    diags = mesh_diagnostics(source, "source") + mesh_diagnostics(target, "target")
    if morph.normalizer is not None:
        a, b = morph.normalizer(source, target)
        if not a.same_topology(b):
            raise ConfigurationError("custom normalizer must return meshes with equal topology")
        return MeshNormalized(
            a, b, (*diags, MorphDiagnostic("custom-normalizer", "caller-provided"))
        )
    if morph.vertex_map is not None:
        n = len(source.vertices)
        if len(target.vertices) != n or sorted(morph.vertex_map) != list(range(n)):
            raise ConfigurationError(
                f"vertex_map must be a permutation of range({n}) for meshes with {n} vertices"
            )
        target = _reorder(target, morph.vertex_map)
        diags.append(MorphDiagnostic("vertex-map", "target vertices reordered explicitly", "info"))
    if source.same_topology(target):
        return MeshNormalized(source, target, tuple(diags))
    if morph.faces is not None and len(source.vertices) == len(target.vertices):
        faces = source.faces if morph.faces == "source" else target.faces
        keep = MeshData(source.vertices, faces, source.normals, source.colors)
        end = MeshData(target.vertices, faces, target.normals, target.colors)
        diags.append(
            MorphDiagnostic("faces-chosen", f"both meshes use the {morph.faces} faces", "info")
        )
        return MeshNormalized(keep, end, tuple(diags))
    diags.append(
        MorphDiagnostic(
            "mesh-topology-mismatch",
            f"source has {len(source.vertices)} vertices / {len(source.faces)} faces and target has "
            f"{len(target.vertices)} / {len(target.faces)}; provide a MeshMorph (vertex_map, faces or "
            "normalizer) or cross-fade",
            "error",
        )
    )
    return MeshNormalized(source, target, tuple(diags), compatible=False)


# -- surfaces ------------------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class SurfaceMorph:
    """How to reconcile surface grids of different sampling.

    ``policy``: ``"target"`` / ``"source"`` resample to the other grid's shape, ``"max"`` to the
    larger of each dimension; ``shape=(ny, nx)`` forces an exact sampling. With neither, different
    shapes are reported as incompatible.
    """

    policy: str | None = None
    shape: tuple[int, int] | None = None

    def __post_init__(self) -> None:
        if self.policy not in (None, "source", "target", "max"):
            raise ConfigurationError("SurfaceMorph.policy must be source, target, max or None")
        if self.shape is not None and (self.shape[0] < 2 or self.shape[1] < 2):
            raise ConfigurationError("SurfaceMorph.shape needs at least 2x2 samples")


def resample_grid(grid: SurfaceGrid, ny: int, nx: int) -> SurfaceGrid:
    """Bilinear resampling in parameter (index) space; corners are preserved exactly."""
    if ny < 2 or nx < 2:
        raise ConfigurationError("resampling needs at least a 2x2 grid")
    if grid.shape == (ny, nx):
        return grid
    src_y = np.linspace(0.0, grid.shape[0] - 1.0, ny)
    src_x = np.linspace(0.0, grid.shape[1] - 1.0, nx)
    pts = grid.points
    rows = np.stack(
        [
            np.stack(
                [np.interp(src_x, np.arange(pts.shape[1]), pts[j, :, k]) for k in range(3)], -1
            )
            for j in range(pts.shape[0])
        ]
    )  # (ny0, nx, 3)
    out = np.stack(
        [
            np.stack(
                [np.interp(src_y, np.arange(pts.shape[0]), rows[:, i, k]) for k in range(3)], -1
            )
            for i in range(nx)
        ],
        axis=1,
    )  # (ny, nx, 3)
    return SurfaceGrid(out)


@dataclass(frozen=True)
class SurfaceNormalized:
    start: SurfaceGrid
    end: SurfaceGrid
    diagnostics: tuple[MorphDiagnostic, ...] = ()
    compatible: bool = True


def normalize_surfaces(
    source: SurfaceGrid, target: SurfaceGrid, morph: SurfaceMorph | None = None
) -> SurfaceNormalized:
    morph = morph or SurfaceMorph()
    if source.shape == target.shape and morph.shape is None:
        return SurfaceNormalized(source, target)
    if morph.shape is not None:
        ny, nx = morph.shape
    elif morph.policy == "target":
        ny, nx = target.shape
    elif morph.policy == "source":
        ny, nx = source.shape
    elif morph.policy == "max":
        ny, nx = max(source.shape[0], target.shape[0]), max(source.shape[1], target.shape[1])
    else:
        return SurfaceNormalized(
            source,
            target,
            (
                MorphDiagnostic(
                    "surface-sampling-mismatch",
                    f"source is sampled {source.shape} and target {target.shape}; choose a "
                    "SurfaceMorph policy/shape or cross-fade",
                    "error",
                ),
            ),
            compatible=False,
        )
    note = MorphDiagnostic("resampled", f"surfaces resampled to {ny}x{nx} (bilinear)", "info")
    return SurfaceNormalized(resample_grid(source, ny, nx), resample_grid(target, ny, nx), (note,))


# -- point lists ---------------------------------------------------------------------------------
@dataclass(frozen=True)
class PointsNormalized:
    start: Vec3Array
    end: Vec3Array
    diagnostics: tuple[MorphDiagnostic, ...] = ()
    compatible: bool = True


def normalize_points(source: Vec3Array, target: Vec3Array) -> PointsNormalized:
    if len(source) == len(target):
        return PointsNormalized(source, target)
    return PointsNormalized(
        source,
        target,
        (
            MorphDiagnostic(
                "point-count-mismatch",
                f"source has {len(source)} points and target {len(target)}; points are matched by "
                "index only, so resample explicitly or cross-fade",
                "error",
            ),
        ),
        compatible=False,
    )


__all__: list[str] = [
    "MeshMorph",
    "MeshNormalized",
    "SurfaceMorph",
    "mesh_diagnostics",
    "normalize_meshes",
    "normalize_points",
    "normalize_surfaces",
    "resample_grid",
]
