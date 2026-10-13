"""Deterministic projection of 3D scenes into depth-sorted 2D primitives.

Raster and vector outputs share this module, so a projected scene has the same geometry in every
format. Shading is flat per face and baked into colors; faces are ordered far-to-near (painter's
algorithm). Everything is a pure function of the scene snapshot and the viewport size.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import numpy.typing as npt

from kinetickit.geometry.three_d import Vec3
from kinetickit.interpolation import Color
from kinetickit.scene import (
    Group3D,
    Line3D,
    Mesh3D,
    Node,
    Point3D,
    PointCloud3D,
    Polyline3D,
    Scene3D,
    Surface3D,
)

RGBA = tuple[float, float, float, float]
Array = npt.NDArray[np.float64]


def _arr(x: Any) -> Array:
    return np.asarray(x, dtype=float)


@dataclass(frozen=True)
class Projected:
    """A 2D drawing primitive in pixel coordinates (origin top-left, y down)."""

    node_id: str
    index: int
    kind: str  # "point" | "polyline" | "polygon"
    points: Array
    depth: float
    fill: RGBA | None = None
    stroke: RGBA | None = None
    stroke_width: float = 1.0
    size: float = 0.0
    symbol: str = "circle"
    dash: tuple[float, ...] = ()
    closed: bool = False

    @property
    def key(self) -> tuple[str, int]:
        return (self.node_id, self.index)


def _rgba(c: Color, opacity: float) -> RGBA:
    return (c.r, c.g, c.b, max(0.0, min(1.0, c.a * opacity)))


class _Projector:
    def __init__(self, scene: Scene3D, width: float, height: float) -> None:
        self.scene = scene
        cam = scene.camera
        self.cam = cam
        self.width, self.height = float(width), float(height)
        aspect = self.width / self.height
        self.view = cam.view_matrix().array()  # type: ignore[attr-defined]
        self.proj = cam.projection_matrix(aspect).array()  # type: ignore[attr-defined]
        self.persp = cam.projection == "perspective"  # type: ignore[attr-defined]
        self.near, self.far = cam.near, cam.far  # type: ignore[attr-defined]
        pos = cam.position  # type: ignore[attr-defined]
        tgt = cam.target  # type: ignore[attr-defined]
        self.eye = np.array([pos.x, pos.y, pos.z])
        self.forward = np.array((tgt - pos).normalized().as_tuple())
        self.lights = scene.lights()
        self.out: list[Projected] = []

    # -- projection ------------------------------------------------------------------------
    def project(self, world: Array) -> tuple[Array, Array]:
        """(N,3) world points → ((N,2) pixels, (N,) view depth)."""
        h = np.concatenate([world, np.ones((len(world), 1))], axis=1)
        view = h @ self.view.T
        depth = -view[:, 2]
        clip = view @ self.proj.T
        w = np.where(clip[:, 3] == 0.0, 1.0, clip[:, 3])
        ndc = clip[:, :3] / w[:, None]
        px = (ndc[:, 0] + 1.0) / 2.0 * self.width
        py = (1.0 - ndc[:, 1]) / 2.0 * self.height
        return np.stack([px, py], axis=1), depth

    def visible(self, depth: Array) -> npt.NDArray[np.bool_]:
        return np.asarray((depth >= self.near) & (depth <= self.far), dtype=bool)

    # -- traversal -------------------------------------------------------------------------
    def run(self) -> list[Projected]:
        for node in self.scene.nodes:
            self.visit(node, np.eye(4), 1.0)
        # far to near; the sort is stable so equal depths keep scene order
        return sorted(self.out, key=lambda p: -p.depth)

    def visit(self, node: Node, m: Array, opacity: float) -> None:
        if not node.visible:
            return
        op = opacity * node.opacity
        if isinstance(node, Group3D):
            gm = m @ node.transform.matrix().array()
            for child in node.children:
                self.visit(child, gm, op)
        elif isinstance(node, Point3D):
            self.point_set(node, np.array([node.position.as_tuple()]), m, op)
        elif isinstance(node, PointCloud3D):
            self.point_set(node, node.points.data, m, op)
        elif isinstance(node, (Line3D, Polyline3D)):
            self.polyline(node, m, op)
        elif isinstance(node, (Mesh3D, Surface3D)):
            self.surface(node, m, op)

    def world(self, pts: Array, m: Array) -> Array:
        h = np.concatenate([pts, np.ones((len(pts), 1))], axis=1) @ m.T
        return _arr(h[:, :3])

    # -- primitives ------------------------------------------------------------------------
    def point_set(self, node: Any, pts: Array, m: Array, op: float) -> None:
        px, depth = self.project(self.world(pts, m))
        ok = self.visible(depth)
        fill = _rgba(node.color, op)
        for i in np.nonzero(ok)[0]:
            self.out.append(
                Projected(
                    node.id,
                    int(i),
                    "point",
                    px[i : i + 1],
                    float(depth[i]),
                    fill=fill,
                    size=float(node.size),
                    symbol=node.symbol,
                )
            )

    def polyline(self, node: Any, m: Array, op: float) -> None:
        pts = node.vertices().data
        if isinstance(node, Polyline3D) and node.closed:
            pts = np.concatenate([pts, pts[:1]], axis=0)
        world = self.world(pts, m)
        if node.draw_progress < 1.0:
            world = _trim(world, node.draw_progress)
        px, depth = self.project(world)
        ok = self.visible(depth)
        stroke = _rgba(node.color, op)
        run: list[int] = []
        runs: list[list[int]] = []
        for i, good in enumerate(ok):
            if good:
                run.append(i)
            elif run:
                runs.append(run)
                run = []
        if run:
            runs.append(run)
        for k, r in enumerate(runs):
            if len(r) >= 2:
                self.out.append(
                    Projected(
                        node.id,
                        k,
                        "polyline",
                        px[r],
                        float(depth[r].mean()),
                        stroke=stroke,
                        stroke_width=float(node.width),
                        dash=node.dash,
                    )
                )

    def surface(self, node: Any, m: Array, op: float) -> None:
        mesh = node.mesh_data()
        if len(mesh.faces) == 0:
            return
        world = self.world(mesh.vertices, m)
        px, depth = self.project(world)
        faces = mesh.faces
        face_ok = self.visible(depth)[faces].all(axis=1)
        tri = world[faces]  # (F,3,3)
        normal = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
        length = np.linalg.norm(normal, axis=1, keepdims=True)
        face_ok &= length[:, 0] > 0.0
        normal = normal / np.where(length == 0.0, 1.0, length)
        center = tri.mean(axis=1)
        to_eye = (self.eye - center) if self.persp else np.tile(-self.forward, (len(faces), 1))
        to_eye = to_eye / np.where(
            np.linalg.norm(to_eye, axis=1, keepdims=True) == 0.0,
            1.0,
            np.linalg.norm(to_eye, axis=1, keepdims=True),
        )
        facing = (normal * to_eye).sum(axis=1)
        if not node.two_sided:
            face_ok &= facing > 0.0
        normal = np.where((facing < 0.0)[:, None], -normal, normal)
        base, alpha = self.base_colors(node, mesh, faces, tri)
        color = self.shade(node.material, base, normal, to_eye)
        face_depth = depth[faces].mean(axis=1)
        edge = None if node.edge_color is None else _rgba(node.edge_color, op)
        for i in np.nonzero(face_ok)[0]:
            r, g, b = color[i]
            self.out.append(
                Projected(
                    node.id,
                    int(i),
                    "polygon",
                    px[faces[i]],
                    float(face_depth[i]),
                    fill=(float(r), float(g), float(b), float(max(0.0, min(1.0, alpha[i] * op)))),
                    stroke=edge,
                    stroke_width=float(node.edge_width),
                    closed=True,
                )
            )

    def base_colors(self, node: Any, mesh: Any, faces: Any, tri: Array) -> tuple[Array, Array]:
        n = len(faces)
        if isinstance(node, Surface3D) and node.colorscale is not None:
            z = tri[:, :, 2].mean(axis=1)
            lo, hi = node.value_range or (
                float(mesh.vertices[:, 2].min()),
                float(mesh.vertices[:, 2].max()),
            )
            t = np.zeros(n) if hi <= lo else np.clip((z - lo) / (hi - lo), 0.0, 1.0)
            rgba = np.array([node.colorscale.at(float(v)).as_tuple() for v in t])
            return _arr(rgba[:, :3]), _arr(rgba[:, 3] * node.color.a)
        if mesh.colors is not None:
            c = mesh.colors[faces].mean(axis=1)
            return _arr(c[:, :3]), _arr(c[:, 3] * node.color.a)
        c = np.array(node.color.as_tuple())
        return _arr(np.tile(c[:3], (n, 1))), _arr(np.full(n, c[3]))

    def shade(self, material: Any, base: Array, normal: Array, to_eye: Array) -> Array:
        if self.lights:
            specs: list[tuple[Any, Array, float]] = [
                (
                    -np.array(light.direction.normalized().as_tuple()),
                    np.array(light.color.as_tuple()[:3]),
                    light.intensity,
                )
                for light in self.lights
            ]
        else:  # a headlight so unlit scenes are still readable
            specs = [(None, np.ones(3), 1.0)]
        diffuse = np.zeros((len(base), 3))
        spec = np.zeros(len(base))
        for direction, col, intensity in specs:
            to_light = to_eye if direction is None else np.tile(direction, (len(base), 1))
            lam = np.clip((normal * to_light).sum(axis=1), 0.0, 1.0)
            diffuse += intensity * lam[:, None] * col
            if material.specular > 0.0:
                half = to_light + to_eye
                half = half / np.where(
                    np.linalg.norm(half, axis=1, keepdims=True) == 0.0,
                    1.0,
                    np.linalg.norm(half, axis=1, keepdims=True),
                )
                spec += (
                    intensity * np.clip((normal * half).sum(axis=1), 0.0, 1.0) ** material.shininess
                )
        out = (
            base * (material.ambient + material.diffuse * diffuse)
            + material.specular * spec[:, None]
        )
        return _arr(np.clip(out, 0.0, 1.0))


def _trim(points: Array, progress: float) -> Array:
    """The first ``progress`` of a polyline by length, keeping the vertex count (tail collapses)."""
    seg = np.linalg.norm(np.diff(points, axis=0), axis=1)
    total = float(seg.sum())
    if total == 0.0 or progress >= 1.0:
        return points
    target = max(0.0, progress) * total
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    out = points.copy()
    k = int(np.searchsorted(cum, target, side="right")) - 1
    k = min(max(k, 0), len(seg) - 1)
    t = 0.0 if seg[k] == 0.0 else (target - cum[k]) / seg[k]
    cut = points[k] + (points[k + 1] - points[k]) * t
    out[k + 1 :] = cut
    return _arr(out)


def project_scene(scene: Scene3D, width: float, height: float) -> list[Projected]:
    """Project every world node of ``scene`` into a viewport of ``width`` by ``height`` pixels."""
    return _Projector(scene, width, height).run()


def project_point(
    scene: Scene3D, point: Vec3, width: float, height: float
) -> tuple[float, float, float]:
    """Pixel position and view depth of one world point (for tests and annotations)."""
    proj = _Projector(scene, width, height)
    px, depth = proj.project(np.array([point.as_tuple()]))
    return float(px[0, 0]), float(px[0, 1]), float(depth[0])
