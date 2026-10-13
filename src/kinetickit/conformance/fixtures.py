"""Shared fixture animations: generic points, lines, paths, meshes, surfaces and text assets.

Fixtures use only public KineticKit API and no domain content, so any renderer or exporter
(built in or third-party) can be checked against the same scenes.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np

from kinetickit import ease
from kinetickit.animation import Animation
from kinetickit.geometry.three_d import MeshData, Quaternion, Transform3D
from kinetickit.geometry.two_d import Bounds2D, Path2D, Transform2D, Vec2
from kinetickit.scene import (
    Camera3D,
    DirectionalLight3D,
    Group2D,
    Group3D,
    Line2D,
    Mesh3D,
    PathNode2D,
    Point2D,
    Point3D,
    Scene2D,
    Scene3D,
    Shape2D,
    Surface3D,
    Text2D,
)
from kinetickit.styles import ColorScale, Material
from kinetickit.typography import FontResource, GlyphShape, TextAsset

VIEW = Bounds2D(Vec2(0, 0), Vec2(10, 10))


@dataclass(frozen=True)
class Fixture:
    name: str
    description: str
    tags: frozenset[str]
    build: Callable[[], Animation]

    def animation(self) -> Animation:
        return self.build()


def _scene2d(*nodes: Any, overlay: Any = ()) -> Scene2D:
    scene = Scene2D(*nodes, overlay=overlay)
    bound: Scene2D = scene.bind({scene.camera.ref("view"): VIEW})
    return bound


def timing_easing_chain() -> Animation:
    a = Point2D(id="a", position=(1, 1), size=6)
    b = Point2D(id="b", position=(1, 5), size=6)
    motion = (
        a.animate.position.to((9, 1), duration=1.0, easing=ease.in_out_cubic)
        .then(a.animate.position.to((9, 9), duration=1.0, easing=ease.out_quad))
        .with_(b.animate.opacity.to(0.2, duration=1.0).delay(0.5))
        .then(b.animate.position.to((5, 5), duration=0.5).yoyo())
        .mark("turn", 1.0)
    )
    return Animation(_scene2d(a, b), motion)


def points_lines_shapes() -> Animation:
    p = Point2D(id="p", position=(2, 2), size=7, color="#e4572e")
    line = Line2D(id="l", start=(0, 0), end=(9, 0), draw_progress=0.0, width=3)
    area = Shape2D(
        id="area",
        path=Path2D.polygon([(5, 5), (9, 5), (9, 9), (5, 9)], [(6, 6), (8, 6), (8, 8), (6, 8)]),
        fill="#3e7cb1",
        fill_rule="evenodd",
        opacity=0.0,
    )
    motion = p.animate.position.to((8, 2), duration=1.0).then(
        line.animate.draw_progress.to(1.0, duration=1.0).with_(
            area.animate.opacity.to(1.0, duration=0.5)
        )
    )
    return Animation(_scene2d(p, line, area), motion)


def path_morph() -> Animation:
    shape = Shape2D(id="shape", path=Path2D.rect(2, 2, 3, 3), fill="#2ca02c")
    target = Path2D.polygon([(3, 2), (8, 2), (5.5, 8)])
    return Animation(
        _scene2d(shape), shape.morph_to(target, duration=1.0, easing=ease.in_out_cubic)
    )


def groups_clip_overlay() -> Animation:
    inner = PathNode2D.polyline("path", [(0, 0), (4, 3), (8, 0)], width=3)
    group = Group2D(
        id="group",
        children=(inner, Point2D(id="dot", position=(4, 3), size=6)),
        transform=Transform2D(translate=Vec2(1, 3)),
    )
    hud = Point2D(id="hud", position=(24, 24), size=5, color="#d62728")
    motion = group.animate.transform.to(
        Transform2D(translate=Vec2(2, 5), rotation=0.5, scale=Vec2(0.8, 0.8)), duration=1.0
    )
    return Animation(_scene2d(group, overlay=[hud]), motion)


def camera_zoom() -> Animation:
    scene = _scene2d(
        Point2D(id="a", position=(3, 3), size=5), Point2D(id="b", position=(7, 7), size=5)
    )
    cam = scene.camera
    return Animation(
        scene,
        cam.animate.zoom.to(2.0, duration=1.0).with_(cam.animate.pan.to((1, 1), duration=1.0)),
    )


def text_asset_object() -> Animation:
    glyph = GlyphShape(Path2D.polygon([(0, 0), (6, 0), (3, 8)]), "A", 0)
    asset = TextAsset("A", (glyph,), 6.0, 8.0, (FontResource("Fixture Sans", b"fixture-font"),))
    label = Text2D(id="label", asset=asset, position=(2, 2), scale=0.5)
    motion = label.animate.position.to((6, 6), duration=1.0).with_(
        label.animate.rotation.to(math.pi / 4, duration=1.0)
    )
    return Animation(_scene2d(label), motion)


def surface_orbit() -> Animation:
    xs = ys = np.linspace(-2, 2, 14)
    X, Y = np.meshgrid(xs, ys)
    surface = Surface3D.height_field(
        "surface",
        xs,
        ys,
        np.sin(np.hypot(X, Y) * 2) / (1 + np.hypot(X, Y)),
        colorscale=ColorScale.viridis_like(),
        material=Material(0.4, 0.6, 0.2, 24),
    )
    marker = Point3D(id="marker", position=(0, 0, 1), size=5, color="#d62728")
    scene = Scene3D(
        surface,
        marker,
        DirectionalLight3D(id="sun"),
        camera=Camera3D(position=(5, -6, 4), target=(0, 0, 0.2)),
    )
    return Animation(scene, scene.camera.animate.position.to((-5, -6, 4), duration=1.0))


def mesh_morph() -> Animation:
    verts = np.array([(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1)], float)
    faces = [(0, 2, 1), (0, 1, 3), (1, 2, 3), (0, 3, 2)]
    body = Mesh3D(id="body", mesh=MeshData(verts, faces), color="#3e7cb1")
    group = Group3D(id="group", children=(body,))
    scene = Scene3D(group, camera=Camera3D(position=(3, -4, 2.5), target=(0.3, 0.3, 0.3)))
    spin = Transform3D(rotation=Quaternion.from_axis_angle((0, 0, 1), math.pi / 2))
    motion = body.morph_to(MeshData(verts * 2.0, faces), duration=1.0).with_(
        group.animate.transform.to(spin, duration=1.0)
    )
    return Animation(scene, motion)


FIXTURES: tuple[Fixture, ...] = (
    Fixture(
        "timing-easing-chain",
        "sequence, parallel, delay, yoyo and markers",
        frozenset({"2d", "timing"}),
        timing_easing_chain,
    ),
    Fixture(
        "points-lines-shapes",
        "points, drawn lines and an even-odd area",
        frozenset({"2d"}),
        points_lines_shapes,
    ),
    Fixture(
        "path-morph", "automatic path normalization morph", frozenset({"2d", "morph"}), path_morph
    ),
    Fixture(
        "groups-clip-overlay",
        "group transform plus screen-space overlay",
        frozenset({"2d", "overlay"}),
        groups_clip_overlay,
    ),
    Fixture(
        "camera-zoom", "animated 2D camera pan and zoom", frozenset({"2d", "camera"}), camera_zoom
    ),
    Fixture(
        "text-asset",
        "an animated pre-laid-out text asset with an embedded font",
        frozenset({"2d", "typography"}),
        text_asset_object,
    ),
    Fixture(
        "surface-orbit",
        "lit height-field surface with an orbiting camera",
        frozenset({"3d", "camera"}),
        surface_orbit,
    ),
    Fixture("mesh-morph", "mesh morph plus group rotation", frozenset({"3d", "morph"}), mesh_morph),
)


def fixtures(*tags: str) -> tuple[Fixture, ...]:
    """All fixtures, or only those carrying every given tag."""
    want = set(tags)
    return tuple(f for f in FIXTURES if want <= f.tags)
