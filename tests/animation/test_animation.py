from __future__ import annotations

import pytest

from kinetickit import ease
from kinetickit.animation import Animation, Frame
from kinetickit.errors import ConfigurationError
from kinetickit.geometry.two_d import Path2D, Vec2
from kinetickit.scene import Line2D, PathNode2D, Point2D, Scene2D, Shape2D
from kinetickit.scheduler import Timestamps
from kinetickit.timeline import PropertyRef


def build():
    point = Point2D(id="point", position=(0, 0), color="#ff3366")
    line = Line2D(id="line", start=(0, 0), end=(6, 4), draw_progress=0)
    area = Shape2D(id="area", opacity=0)
    scene = Scene2D(point, line, area)
    motion = point.animate.position.to((4, 3), duration=1.0, easing=ease.out_cubic).then(
        line.animate.draw_progress.to(1.0, duration=1.5).with_(
            area.animate.opacity.to(1.0, duration=0.5)
        )
    )
    return scene, motion


def test_sample_binds_a_snapshot_without_touching_the_source_scene():
    scene, motion = build()
    anim = Animation(scene, motion)
    assert anim.duration == 2.5
    mid = anim.sample(0.5)
    assert mid.get("point").position == Vec2(4 * ease.out_cubic(0.5), 3 * ease.out_cubic(0.5))
    assert scene.get("point").position == Vec2(0, 0)
    assert anim.sample(0.0) == scene
    final = anim.sample(2.5)
    assert final.get("line").draw_progress == 1.0 and final.get("area").opacity == 1.0
    assert anim.sample(99) == final


def test_frames_are_lazy_ordered_and_include_both_states():
    scene, motion = build()
    anim = Animation(scene, motion)
    stream = anim.frames(30)
    assert iter(stream) is stream
    frames = list(stream)
    assert len(frames) == 75  # 2.5 s * 30 fps
    assert [f.index for f in frames] == list(range(75))
    assert frames[0].time == 0.0 and frames[-1].time == 2.5
    assert frames[0].progress == 0.0 and frames[-1].progress == 1.0
    assert frames[0].snapshot == scene
    assert isinstance(frames[0], Frame)


def test_custom_scheduler_drives_frame_times():
    scene, motion = build()
    frames = list(Animation(scene, motion).frames(Timestamps([0, 0.5, 1.0])))
    assert [f.time for f in frames] == [0.0, 0.5, 1.0]


def test_static_animation_has_two_frames():
    scene, _ = build()
    anim = Animation(scene)
    assert anim.duration == 0.0
    frames = list(anim.frames(30))
    assert len(frames) == 2 and all(f.snapshot == scene for f in frames)
    assert frames[0].progress == 0.0


def test_sampling_is_deterministic():
    scene, motion = build()
    a, b = Animation(scene, motion), Animation(scene, motion)
    for t in (0.0, 0.3, 1.0, 2.0, 2.5):
        assert a.sample(t) == b.sample(t) == a.sample(t)


def test_construction_validates_targets():
    scene, _ = build()
    ghost = Point2D(id="ghost")
    with pytest.raises(ConfigurationError, match="ghost"):
        Animation(scene, ghost.animate.size.to(5, duration=1))
    wrong = PropertyRef("point", "size", int)
    from kinetickit.tween import PropertyBuilder

    with pytest.raises(ConfigurationError, match="declared"):
        Animation(scene, PropertyBuilder(wrong).to(5, duration=1))
    with pytest.raises(ConfigurationError):
        Animation("not a scene")  # type: ignore[arg-type]


def test_color_and_path_properties_animate():
    shape = Shape2D(id="s", path=Path2D.rect(0, 0, 1, 1), fill="#000000")
    wide = Path2D.rect(0, 0, 3, 1)
    scene = Scene2D(shape)
    anim = Animation(
        scene,
        shape.animate.path.to(wide, duration=1).with_(shape.animate.fill.to("#ffffff", duration=1)),
    )
    snap = anim.sample(0.5)
    assert snap.get("s").path == Path2D.rect(0, 0, 2, 1)
    assert snap.get("s").fill.to_hex() == "#808080"


def test_optional_property_without_value_cannot_be_animated_implicitly():
    point = Point2D(id="p")  # stroke is None
    scene = Scene2D(point)
    with pytest.raises(ConfigurationError, match="no value to animate from"):
        Animation(scene, point.animate.stroke.to("#000000", duration=1))
    ok = Animation(scene, point.animate.stroke.to("#000000", duration=1, from_="#ffffff"))
    assert ok.sample(0.5).get("p").stroke.to_hex() == "#808080"


def test_path_node_polyline_helper():
    node = PathNode2D.polyline("path", [(0, 0), (1, 1), (2, 0)], width=3)
    assert node.width == 3.0 and node.path.kinds == ("M", "L", "L")
