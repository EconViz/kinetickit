"""Private 3D adapter: turns scene snapshots into plotting-runtime traces and frames.

Nothing in this module appears in a public signature. It produces plain JSON-able dicts; the only
third-party import is the bundled JavaScript runtime needed for offline documents.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
from plotly.offline import get_plotlyjs

from kinetickit.animation import Animation
from kinetickit.errors import CapabilityError
from kinetickit.geometry.three_d import Vec3
from kinetickit.renderers.projection import face_base_colors
from kinetickit.scene import (
    DirectionalLight3D,
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
from kinetickit.timeline import frame_times

PLOTLY_FOV = math.radians(45.0)  # fixed vertical field of view of the 3D runtime
CDN_URL = "https://cdn.plot.ly/plotly-3.0.1.min.js"

_SYMBOLS = {
    "circle": "circle",
    "square": "square",
    "diamond": "diamond",
    "cross": "x",
    "plus": "cross",
    "triangle": "diamond",  # the 3D runtime has no triangle marker
}


def plotly_bundle() -> str:
    """The complete runtime source, embedded for offline documents."""
    return str(get_plotlyjs())


def _rgba(c: Any, opacity: float = 1.0) -> str:
    r, g, b, a = c.as_tuple() if hasattr(c, "as_tuple") else c
    return f"rgba({round(r * 255)},{round(g * 255)},{round(b * 255)},{max(0.0, min(1.0, a * opacity)):.4g})"


def _round(a: Any, p: int) -> Any:
    return np.round(np.asarray(a, dtype=float), p).tolist()


class _Builder:
    """Builds the trace list for one snapshot; the trace sequence is identical for every frame."""

    def __init__(self, scene: Scene3D, precision: int) -> None:
        self.scene = scene
        self.p = precision
        self.traces: list[dict[str, Any]] = []
        self.lights = scene.lights()
        self.warnings: set[str] = set()

    def build(self) -> list[dict[str, Any]]:
        for n in self.scene.nodes:
            self.visit(n, np.eye(4), 1.0)
        return self.traces

    def world(self, pts: Any, m: Any) -> Any:
        h = np.concatenate([np.asarray(pts, float), np.ones((len(pts), 1))], axis=1) @ m.T
        return h[:, :3]

    def meta(self, node: Node, role: str) -> dict[str, str]:
        return {"id": node.id, "role": role}

    def visit(self, node: Node, m: Any, opacity: float) -> None:
        op = opacity * node.opacity
        vis = node.visible
        if isinstance(node, Group3D):
            gm = m @ node.transform.matrix().array()
            for c in node.children:
                self.visit(c, gm, op)
        elif isinstance(node, (Point3D, PointCloud3D)):
            pts = (
                np.array([node.position.as_tuple()])
                if isinstance(node, Point3D)
                else node.points.data
            )
            w = self.world(pts, m)
            sym = _SYMBOLS[node.symbol]
            if node.symbol == "triangle":
                self.warnings.add("triangle markers are drawn as diamonds in 3D interactive output")
            self.traces.append(
                {
                    "type": "scatter3d",
                    "mode": "markers",
                    "x": _round(w[:, 0], self.p),
                    "y": _round(w[:, 1], self.p),
                    "z": _round(w[:, 2], self.p),
                    "visible": vis,
                    "marker": {
                        "size": node.size * 2.0,
                        "color": _rgba(node.color, op),
                        "symbol": sym,
                        "line": {"width": 0},
                    },
                    "name": node.id,
                    "meta": self.meta(node, "points"),
                    "hoverinfo": "name",
                    "showlegend": False,
                }
            )
        elif isinstance(node, (Line3D, Polyline3D)):
            pts = node.vertices().data
            if isinstance(node, Polyline3D) and node.closed:
                pts = np.concatenate([pts, pts[:1]], axis=0)
            w = self.world(pts, m)
            if node.draw_progress < 1.0:
                from kinetickit.renderers.projection import _trim

                w = _trim(w, node.draw_progress)
            line: dict[str, Any] = {"color": _rgba(node.color, op), "width": node.width}
            if node.dash:
                line["dash"] = "dash"
            self.traces.append(
                {
                    "type": "scatter3d",
                    "mode": "lines",
                    "x": _round(w[:, 0], self.p),
                    "y": _round(w[:, 1], self.p),
                    "z": _round(w[:, 2], self.p),
                    "visible": vis,
                    "line": line,
                    "name": node.id,
                    "meta": self.meta(node, "line"),
                    "hoverinfo": "name",
                    "showlegend": False,
                }
            )
        elif isinstance(node, (Mesh3D, Surface3D)):
            self.surface(node, m, op, vis)
        # lights are scene-level; nothing to draw

    def surface(self, node: Any, m: Any, op: float, vis: bool) -> None:
        mesh = node.mesh_data()
        w = self.world(mesh.vertices, m)
        faces = mesh.faces
        tri = w[faces] if len(faces) else np.zeros((0, 3, 3))
        rgb, alpha = (
            face_base_colors(node, mesh, faces, tri)
            if len(faces)
            else (np.zeros((0, 3)), np.zeros(0))
        )
        mat = node.material
        light: dict[str, Any] = {
            "ambient": mat.ambient,
            "diffuse": mat.diffuse,
            "specular": mat.specular,
            "roughness": min(1.0, 8.0 / max(mat.shininess, 1.0)),
            "fresnel": 0.0,
        }
        trace: dict[str, Any] = {
            "type": "mesh3d",
            "x": _round(w[:, 0], self.p),
            "y": _round(w[:, 1], self.p),
            "z": _round(w[:, 2], self.p),
            "i": faces[:, 0].tolist(),
            "j": faces[:, 1].tolist(),
            "k": faces[:, 2].tolist(),
            "facecolor": [
                f"rgb({round(r * 255)},{round(g * 255)},{round(b * 255)})" for r, g, b in rgb
            ],
            "opacity": float(max(0.0, min(1.0, (alpha.mean() if len(alpha) else 1.0) * op))),
            "flatshading": True,
            "lighting": light,
            "visible": vis,
            "name": node.id,
            "meta": self.meta(node, "faces"),
            "hoverinfo": "name",
            "showlegend": False,
        }
        if self.lights:
            d = np.array(self.lights[0].direction.normalized().as_tuple())
            trace["lightposition"] = {
                "x": float(-d[0] * 1e3),
                "y": float(-d[1] * 1e3),
                "z": float(-d[2] * 1e3),
            }
        self.traces.append(trace)
        # edges are always the same trace slot so frames stay structurally identical
        edge: dict[str, Any] = {
            "type": "scatter3d",
            "mode": "lines",
            "x": [],
            "y": [],
            "z": [],
            "hoverinfo": "skip",
            "showlegend": False,
            "name": node.id + ":edges",
            "meta": self.meta(node, "edges"),
            "visible": vis and node.edge_color is not None,
            "line": {"width": node.edge_width * 2.0},
        }
        if node.edge_color is not None and len(faces):
            idx = np.concatenate([faces, faces[:, :1]], axis=1)
            segs = w[idx]  # (F, 4, 3)
            nan = np.full((len(faces), 1, 3), np.nan)
            flat = np.concatenate([segs, nan], axis=1).reshape(-1, 3)
            edge["x"], edge["y"], edge["z"] = (
                [None if np.isnan(v) else round(float(v), self.p) for v in flat[:, i]]
                for i in range(3)
            )
            edge["line"]["color"] = _rgba(node.edge_color, op)
        self.traces.append(edge)


def _extent(scene: Scene3D, animation: Animation, fps: int) -> tuple[np.ndarray, float]:
    """Centre and largest span of the world content over the whole animation."""
    lo = np.full(3, np.inf)
    hi = np.full(3, -np.inf)
    times = (
        frame_times(animation.duration, max(2, min(fps, 12))) if animation.duration > 0 else (0.0,)
    )
    for t in times:
        snap = animation.sample(t)
        for trace in _Builder(snap, 4).build():
            if trace["type"] == "scatter3d" and not trace["x"]:
                continue
            xyz = np.array(
                [[np.nan if v is None else v for v in trace[a]] for a in ("x", "y", "z")],
                dtype=float,
            )
            if xyz.size == 0 or np.isnan(xyz).all():
                continue
            lo = np.minimum(lo, np.nanmin(xyz, axis=1))
            hi = np.maximum(hi, np.nanmax(xyz, axis=1))
    if not np.isfinite(lo).all():
        return np.zeros(3), 1.0
    span = float(max((hi - lo).max(), 1e-9))
    return (lo + hi) / 2.0, span


def _camera(cam: Any, centre: np.ndarray, span: float) -> dict[str, Any]:
    c = np.array(cam.position.as_tuple())
    t = np.array(cam.target.as_tuple())
    eye_dir = c - t
    dist = float(np.linalg.norm(eye_dir))
    if cam.projection == "perspective":
        k = math.tan(cam.fov / 2.0) / math.tan(PLOTLY_FOV / 2.0)  # keep apparent object size
        eye = t + eye_dir * k
        proj = {"type": "perspective"}
    else:
        d = cam.ortho_height / (2.0 * math.tan(PLOTLY_FOV / 2.0))
        eye = t + eye_dir / max(dist, 1e-12) * d
        proj = {"type": "orthographic"}

    def n(v: Any) -> dict[str, float]:
        return {"x": float(v[0]), "y": float(v[1]), "z": float(v[2])}

    up = np.array(cam.up.as_tuple())
    return {
        "eye": n((eye - centre) / span),
        "center": n((t - centre) / span),
        "up": n(up),
        "projection": proj,
    }


def _vary(frames: list[list[dict[str, Any]]]) -> list[set[str]]:
    """Per trace: the (dotted) keys whose values differ across frames."""
    varying: list[set[str]] = [set() for _ in frames[0]]

    def walk(prefix: str, a: Any, b: Any, out: set[str]) -> None:
        if isinstance(a, dict) and isinstance(b, dict):
            for k in set(a) | set(b):
                walk(f"{prefix}.{k}" if prefix else k, a.get(k), b.get(k), out)
        elif a != b:
            out.add(prefix)

    for i in range(len(varying)):
        for f in frames[1:]:
            walk("", frames[0][i], f[i], varying[i])
    return varying


def _get(d: dict[str, Any], dotted: str) -> Any:
    cur: Any = d
    for part in dotted.split("."):
        cur = cur.get(part) if isinstance(cur, dict) else None
    return cur


def _nest(dotted: str, value: Any, into: dict[str, Any]) -> None:
    parts = dotted.split(".")
    cur = into
    for p in parts[:-1]:
        cur = cur.setdefault(p, {})
    cur[parts[-1]] = value


def build_payload(
    animation: Animation,
    *,
    width: float,
    height: float,
    fps: int,
    precision: int,
    show_axes: bool,
    background: str,
    max_frames: int,
) -> tuple[dict[str, Any], tuple[str, ...]]:
    """Static traces and layout plus compact per-frame diffs for a 3D animation."""
    scene = animation.scene
    assert isinstance(scene, Scene3D)
    D = animation.duration
    times = list(frame_times(D, fps)) if D > 0 else [0.0]
    if len(times) > max_frames:
        raise CapabilityError(
            f"interactive 3D export needs {len(times)} frames (limit {max_frames}); lower fps or "
            "shorten the animation",
            missing=("feature:dense-sampling",),
        )
    centre, span = _extent(scene, animation, fps)
    snapshots = [animation.sample(t) for t in times]
    builders = [_Builder(s, precision) for s in snapshots]
    per_frame = [b.build() for b in builders]
    shape = [(t["type"], t["name"]) for t in per_frame[0]]
    for traces in per_frame[1:]:
        if [(t["type"], t["name"]) for t in traces] != shape:
            raise CapabilityError(
                "the set of 3D traces changes over time", missing=("feature:topology-change",)
            )
    warnings = tuple(sorted({w for b in builders for w in b.warnings}))
    varying = _vary(per_frame)
    base = per_frame[0]
    cam_frames = [_camera(s.camera, centre, span) for s in snapshots]
    cam_varies = any(c != cam_frames[0] for c in cam_frames[1:])
    frames: list[dict[str, Any]] = []
    traces_idx = [i for i, v in enumerate(varying) if v]
    for traces, cam in zip(per_frame, cam_frames, strict=True):
        data: list[dict[str, Any]] = []
        for i in traces_idx:
            d: dict[str, Any] = {}
            for key in sorted(varying[i]):
                _nest(key, _get(traces[i], key), d)
            data.append(d)
        frame: dict[str, Any] = {"data": data, "traces": traces_idx}
        if cam_varies:
            frame["layout"] = {"scene": {"camera": cam}}
        frames.append(frame)
    ranges = {
        a: [float(centre[i] - span / 2 * 1.0), float(centre[i] + span / 2 * 1.0)]
        for i, a in enumerate("xyz")
    }
    axis = {
        "visible": show_axes,
        "showbackground": False,
        "showgrid": show_axes,
        "zeroline": False,
        "showspikes": False,
        "range": None,
    }
    layout = {
        "width": None,
        "height": None,
        "autosize": True,
        "margin": {"l": 0, "r": 0, "t": 0, "b": 0},
        "paper_bgcolor": background,
        "plot_bgcolor": background,
        "showlegend": False,
        "scene": {
            "aspectmode": "manual",
            "aspectratio": {"x": 1, "y": 1, "z": 1},
            "xaxis": dict(axis, range=ranges["x"]),
            "yaxis": dict(axis, range=ranges["y"]),
            "zaxis": dict(axis, range=ranges["z"]),
            "camera": cam_frames[0],
            "dragmode": "orbit",
            "bgcolor": background,
        },
        "hovermode": "closest",
    }
    payload = {"traces": base, "layout": layout, "frames": frames, "times": times}
    return payload, warnings


__all__ = ["CDN_URL", "DirectionalLight3D", "Vec3", "build_payload", "plotly_bundle"]
