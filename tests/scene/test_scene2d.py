from __future__ import annotations

import pytest

from kinetickit import ease
from kinetickit.errors import ConfigurationError
from kinetickit.geometry.two_d import Bounds2D, Path2D, Transform2D, Vec2
from kinetickit.interpolation import Color
from kinetickit.scene import (
    Camera2D,
    Group2D,
    Line2D,
    PathNode2D,
    Point2D,
    Scene2D,
    Shape2D,
    Text2D,
)
from kinetickit.timeline import PropertyRef
from kinetickit.typography import GlyphShape, TextAsset


def test_property_builder_targets_stable_node_id():
    point = Point2D(id="p", position=(0, 0))
    motion = point.animate.position.to((4, 3), duration=1)
    assert motion.target == PropertyRef("p", "position", Vec2)
    assert motion.to_value == Vec2(4, 3)


def test_values_are_coerced_to_declared_types():
    p = Point2D(id="p", position=(1, 2), color="#ff3366", size=3)
    assert p.position == Vec2(1, 2)
    assert p.color == Color.parse("#ff3366")
    assert isinstance(p.size, float)


def test_unknown_animate_property_lists_alternatives():
    with pytest.raises(AttributeError, match="available"):
        _ = Point2D(id="p").animate.nope


def test_non_animatable_fields_are_not_exposed():
    with pytest.raises(AttributeError):
        _ = Group2D(id="g").animate.children


def test_validation_of_discrete_and_numeric_fields():
    with pytest.raises(ConfigurationError):
        Point2D(id="p", symbol="blob")
    with pytest.raises(ConfigurationError):
        Point2D(id="p", size=-1)
    with pytest.raises(ConfigurationError):
        Line2D(id="l", cap="flat")
    with pytest.raises(ConfigurationError):
        Line2D(id="l", dash=(0, 0))
    with pytest.raises(ConfigurationError):
        Shape2D(id="s", fill_rule="odd")
    with pytest.raises(ConfigurationError):
        Point2D(id="")
    with pytest.raises(ConfigurationError):
        Point2D(id="p", opacity=float("nan"))
    with pytest.raises(ConfigurationError):
        Camera2D(zoom=0)


def test_nodes_are_immutable_values():
    p = Point2D(id="p")
    with pytest.raises(AttributeError):
        p.size = 9.0  # type: ignore[misc]
    q = p.replace(size=9.0)
    assert q.size == 9.0 and p.size == 4.0
    assert Point2D(id="p") == Point2D(id="p")


def test_scene_enforces_unique_ids_including_nested_and_overlay():
    with pytest.raises(ConfigurationError, match="duplicate"):
        Scene2D(Point2D(id="a"), Line2D(id="a"))
    with pytest.raises(ConfigurationError, match="duplicate"):
        Scene2D(Group2D(id="g", children=(Point2D(id="a"),)), Point2D(id="a"))
    with pytest.raises(ConfigurationError, match="duplicate"):
        Scene2D(Point2D(id="a"), overlay=[Point2D(id="a")])
    with pytest.raises(ConfigurationError, match="duplicate"):
        Scene2D(Point2D(id="camera"))


def test_scene2d_rejects_3d_world_nodes_and_non_nodes():
    class Fake3D(Point2D):
        dimension = 3

    with pytest.raises(ConfigurationError):
        Scene2D(Fake3D(id="x"))
    with pytest.raises(ConfigurationError):
        Scene2D("nope")  # type: ignore[arg-type]
    with pytest.raises(ConfigurationError):
        Scene2D(camera=Point2D(id="c"))


def test_bind_returns_new_snapshot_and_preserves_the_source():
    scene = Scene2D(Point2D(id="p", position=(0, 0)), Line2D(id="l"))
    p = scene.get("p")
    snap = scene.bind({p.ref("position"): Vec2(4, 3), p.ref("opacity"): 0.5})
    assert snap.get("p").position == Vec2(4, 3) and snap.get("p").opacity == 0.5
    assert scene.get("p").position == Vec2(0, 0)
    assert snap.get("l") is scene.get("l")  # untouched nodes are shared, not copied
    assert scene.bind({}) is scene


def test_bind_reaches_nested_group_children():
    scene = Scene2D(Group2D(id="g", children=(Point2D(id="a"), Point2D(id="b"))))
    a = scene.get("a")
    snap = scene.bind({a.ref("size"): 10.0})
    assert snap.get("a").size == 10.0
    assert snap.get("b") is scene.get("b")
    assert snap.get("g").children[0].size == 10.0
    assert scene.get("a").size == 4.0


def test_bind_rejects_unknown_targets():
    scene = Scene2D(Point2D(id="p"))
    with pytest.raises(ConfigurationError):
        scene.bind({PropertyRef("zzz", "size", float): 1.0})
    with pytest.raises(ConfigurationError):
        scene.bind({PropertyRef("p", "id", str): "q"})


def test_scene_is_immutable_and_hashable():
    scene = Scene2D(Point2D(id="p"))
    with pytest.raises(AttributeError):
        scene.nodes = ()  # type: ignore[misc]
    assert scene == Scene2D(Point2D(id="p"))
    assert hash(scene) == hash(Scene2D(Point2D(id="p")))
    assert "p" in scene and "q" not in scene
    assert scene.ids == ("p", "camera")


def test_overlay_and_camera_are_addressable():
    scene = Scene2D(Point2D(id="p"), overlay=[Point2D(id="hud")])
    assert scene.get("hud") in scene.overlay
    zoom = scene.camera.animate.zoom.to(2.0, duration=1, easing=ease.linear)
    assert zoom.target == PropertyRef("camera", "zoom", float)


def test_precise_control_of_points_lines_and_areas():
    area = Shape2D(
        id="area",
        path=Path2D.polygon([(0, 0), (4, 0), (4, 4), (0, 4)], [(1, 1), (3, 1), (3, 3), (1, 3)]),
        fill_rule="evenodd",
        fill="#336699",
    )
    line = Line2D(id="l", start=(0, 0), end=(6, 4), width=1.5, cap="butt", dash=(4, 2))
    assert area.fill == Color.parse("#336699") and area.fill_rule == "evenodd"
    assert line.dash == (4.0, 2.0) and line.bounds() == Bounds2D((0, 0), (6, 4))
    assert len(area.path.subpaths()) == 2


def test_scene_bounds_cover_world_geometry_and_group_transforms():
    scene = Scene2D(
        Point2D(id="p", position=(-1, -2)),
        PathNode2D.polyline("path", [(0, 0), (3, 1)]),
        Group2D(
            id="g",
            children=(Point2D(id="q", position=(1, 1)),),
            transform=Transform2D(translate=Vec2(10, 10)),
        ),
        overlay=[Point2D(id="hud", position=(500, 500))],
    )
    assert scene.bounds() == Bounds2D((-1, -2), (11, 11))
    assert Scene2D().bounds() is None


def test_text_nodes_accept_only_neutral_assets():
    glyph = GlyphShape(Path2D.rect(0, 0, 1, 1), "A")
    asset = TextAsset("A", (glyph,), 1.0, 1.0)
    text = Text2D(id="t", asset=asset, position=(2, 3), scale=2)
    assert text.bounds() == Bounds2D((2, 3), (4, 5))
    with pytest.raises(ConfigurationError):
        Text2D(id="t", asset="plain string")


def test_scene_snapshots_contain_no_backend_objects():
    scene = Scene2D(Point2D(id="p"), Shape2D(id="s"), Group2D(id="g"))
    for node in scene.walk():
        assert type(node).__module__.startswith("kinetickit")
        for value in vars_of(node):
            mod = type(value).__module__
            assert mod.split(".")[0] in {"kinetickit", "builtins"}, (node.id, mod)


def vars_of(node):
    import dataclasses

    return [getattr(node, f.name) for f in dataclasses.fields(node)]
