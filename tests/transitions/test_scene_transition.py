from __future__ import annotations

import pytest

from kinetickit import ease
from kinetickit.errors import ConfigurationError
from kinetickit.geometry.two_d import Path2D, Transform2D, Vec2
from kinetickit.morph import PathMorph
from kinetickit.scene import Group2D, Line2D, PathNode2D, Point2D, Scene2D, Shape2D
from kinetickit.transitions import INCOMING_SUFFIX, SceneTransition, TransitionPolicy
from kinetickit.tween import PropertyBuilder


def run(a, b, t, **kw):
    tr = SceneTransition.between(a, b, **kw)
    return tr, tr.animation().sample(t)


def test_same_id_and_type_tween_changed_properties_with_defaults():
    a = Scene2D(Point2D(id="p", position=(0, 0), size=2))
    b = Scene2D(Point2D(id="p", position=(10, 0), size=2))
    tr, mid = run(a, b, 0.15)
    assert tr.duration == 0.3
    assert mid.get("p").position.x == pytest.approx(10 * ease.in_out_cubic(0.5))
    assert run(a, b, 0.3)[1].get("p").position == Vec2(10, 0)
    assert tr.motion.targets() and len(tr.motion.targets()) == 1  # only changed properties


def test_unchanged_nodes_produce_no_tracks():
    a = Scene2D(Point2D(id="p"))
    tr = SceneTransition.between(a, Scene2D(Point2D(id="p")))
    assert tr.motion.targets() == frozenset() and tr.diagnostics == ()


def test_incoming_unmatched_nodes_fade_in():
    a = Scene2D(Point2D(id="p"))
    b = Scene2D(Point2D(id="p"), Point2D(id="new", opacity=0.8))
    _, start = run(a, b, 0.0)
    assert start.get("new").opacity == 0.0
    assert run(a, b, 0.15)[1].get("new").opacity == pytest.approx(0.4)
    assert run(a, b, 0.3)[1].get("new").opacity == pytest.approx(0.8)


def test_outgoing_unmatched_nodes_fade_out():
    a = Scene2D(Point2D(id="p"), Point2D(id="old"))
    b = Scene2D(Point2D(id="p"))
    assert run(a, b, 0.0)[1].get("old").opacity == 1.0
    assert run(a, b, 0.15)[1].get("old").opacity == pytest.approx(0.5)
    assert run(a, b, 0.3)[1].get("old").opacity == 0.0


def test_enter_and_exit_policies():
    a = Scene2D(Point2D(id="old"), Line2D(id="gone", draw_progress=1.0))
    b = Scene2D(Line2D(id="drawn", draw_progress=1.0))
    cut = SceneTransition.between(a, b, policy=TransitionPolicy(enter="cut", exit="cut"))
    assert "old" not in cut.scene and "drawn" in cut.scene
    assert cut.scene.get("drawn").opacity == 1.0

    hold = SceneTransition.between(a, b, policy=TransitionPolicy(exit="hold"))
    anim = hold.animation()
    assert anim.sample(0.29).get("old").visible is True
    assert anim.sample(0.3).get("old").visible is False

    draw = SceneTransition.between(a, b, policy=TransitionPolicy(enter="draw", exit="draw"))
    anim = draw.animation()
    assert anim.sample(0.0).get("drawn").draw_progress == 0.0
    assert anim.sample(0.3).get("drawn").draw_progress == 1.0
    assert anim.sample(0.3).get("gone").draw_progress == 0.0
    assert anim.sample(0.15).get("old").opacity == pytest.approx(0.5)  # no draw_progress: fade


def test_invalid_policy_names_rejected():
    with pytest.raises(ConfigurationError):
        TransitionPolicy(enter="teleport")
    with pytest.raises(ConfigurationError):
        TransitionPolicy(exit="explode")


def test_type_change_cross_fades_both_nodes():
    a = Scene2D(Point2D(id="x", opacity=1.0))
    b = Scene2D(Shape2D(id="x"))
    tr, mid = run(a, b, 0.15)
    assert mid.get("x").opacity == pytest.approx(0.5)
    assert mid.get("x" + INCOMING_SUFFIX).opacity == pytest.approx(0.5)
    assert any(d.code == "type-change" for d in tr.diagnostics)
    end = run(a, b, 0.3)[1]
    assert end.get("x").opacity == 0.0 and end.get("x" + INCOMING_SUFFIX).opacity == 1.0


def test_compatible_paths_morph():
    a = Scene2D(Shape2D(id="s", path=Path2D.rect(0, 0, 2, 2)))
    b = Scene2D(Shape2D(id="s", path=Path2D.polygon([(0, 0), (4, 0), (2, 3)])))
    _, mid = run(a, b, 0.15)
    assert "s" + INCOMING_SUFFIX not in mid
    assert mid.get("s").path.kinds[0] == "M"
    final = run(a, b, 0.3)[1].get("s").path
    assert final.bounds() == b.get("s").path.bounds()
    assert run(a, b, 0.0)[1].get("s").path.bounds() == a.get("s").path.bounds()


def test_incompatible_paths_cross_fade_with_a_diagnostic():
    two = Path2D.polygon([(0, 0), (4, 0), (4, 4), (0, 4)], [(1, 1), (2, 1), (2, 2)])
    a = Scene2D(Shape2D(id="s", path=Path2D.rect(0, 0, 2, 2)))
    b = Scene2D(Shape2D(id="s", path=two))
    tr, mid = run(a, b, 0.15)
    assert mid.get("s").opacity == pytest.approx(0.5)
    assert mid.get("s" + INCOMING_SUFFIX).opacity == pytest.approx(0.5)
    codes = [d.code for d in tr.diagnostics]
    assert "subpath-count-mismatch" in codes and "incompatible-morph" in codes
    assert tr.warnings
    assert all(d.node_id == "s" for d in tr.diagnostics)


def test_caller_supplied_morph_rescues_an_incompatible_pair():
    two = Path2D.polygon([(0, 0), (4, 0), (4, 4), (0, 4)], [(1, 1), (2, 1), (2, 2)])
    a = Scene2D(Shape2D(id="s", path=Path2D.rect(0, 0, 2, 2)))
    b = Scene2D(Shape2D(id="s", path=two))

    def normalizer(src, tgt):
        return two, two

    tr = SceneTransition.between(a, b, morphs={"s": PathMorph(normalizer=normalizer)})
    assert "s" + INCOMING_SUFFIX not in tr.scene


def test_matching_ignores_order_labels_and_position():
    a = Scene2D(Point2D(id="a", position=(0, 0)), Point2D(id="b", position=(5, 5)))
    b = Scene2D(Point2D(id="b", position=(0, 0)), Point2D(id="a", position=(5, 5)))
    _, end = run(a, b, 0.3)
    assert end.get("a").position == Vec2(5, 5) and end.get("b").position == Vec2(0, 0)
    c = Scene2D(Point2D(id="c", position=(0, 0)))  # same place as 'a', but a different id
    tr = SceneTransition.between(a, c)
    assert {"a", "b", "c"} <= set(tr.scene.ids)  # never merged by proximity


def test_explicit_tracks_override_automatic_behavior():
    a = Scene2D(Point2D(id="p", position=(0, 0)))
    b = Scene2D(Point2D(id="p", position=(10, 0)))
    custom = PropertyBuilder(a.get("p").ref("position")).to(
        (10, 0), duration=0.3, easing=ease.linear
    )
    tr, mid = run(a, b, 0.15, overrides=custom)
    assert mid.get("p").position.x == pytest.approx(5.0)  # linear, not in_out_cubic
    assert len(tr.motion.targets()) == 1
    fade = PropertyBuilder(Point2D(id="new").ref("opacity")).to(0.5, duration=0.3, from_=0.5)
    b2 = Scene2D(Point2D(id="p"), Point2D(id="new"))
    assert run(Scene2D(Point2D(id="p")), b2, 0.15, overrides=fade)[1].get("new").opacity == 0.5


def test_groups_recurse_and_transform_animates():
    a = Scene2D(Group2D(id="g", children=(Point2D(id="c", position=(0, 0)),)))
    b = Scene2D(
        Group2D(
            id="g",
            children=(Point2D(id="c", position=(2, 0)), Point2D(id="d")),
            transform=Transform2D(translate=Vec2(4, 0)),
        )
    )
    _, end = run(a, b, 0.3)
    group = end.get("g")
    assert group.transform.translate == Vec2(4, 0)
    assert end.get("c").position == Vec2(2, 0)
    assert end.get("d").opacity == 1.0 and run(a, b, 0.0)[1].get("d").opacity == 0.0


def test_moving_between_parents_is_an_explicit_error():
    a = Scene2D(Group2D(id="g", children=(Point2D(id="c"),)))
    b = Scene2D(Group2D(id="g"), Point2D(id="c"))
    with pytest.raises(ConfigurationError, match="moves between parents"):
        SceneTransition.between(a, b)


def test_optional_properties_switch_when_the_transition_ends():
    a = Scene2D(Point2D(id="p"))
    b = Scene2D(Point2D(id="p", stroke="#ff0000"))
    tr = SceneTransition.between(a, b)
    anim = tr.animation()
    assert anim.sample(0.29).get("p").stroke is None
    assert anim.sample(0.3).get("p").stroke.to_hex() == "#ff0000"
    assert any(d.code == "optional-switch" for d in tr.diagnostics)


def test_discrete_properties_switch_at_the_end():
    a = Scene2D(Point2D(id="p", symbol="circle"))
    b = Scene2D(Point2D(id="p", symbol="square"))
    anim = SceneTransition.between(a, b).animation()
    assert anim.sample(0.29).get("p").symbol == "circle"
    assert anim.sample(0.3).get("p").symbol == "square"


def test_camera_and_overlay_transition():
    a = Scene2D(overlay=[Point2D(id="hud", position=(0, 0))])
    b = Scene2D(overlay=[Point2D(id="hud", position=(10, 0))])
    b = b.bind({b.camera.ref("zoom"): 2.0})
    _, end = run(a, b, 0.3)
    assert end.get("hud").position == Vec2(10, 0) and end.camera.zoom == 2.0


def test_transition_is_deterministic_and_final_state_matches_target():
    a = Scene2D(Point2D(id="p", position=(0, 0), color="#000000"), Line2D(id="l"))
    b = Scene2D(Point2D(id="p", position=(3, 4), color="#ffffff"), Line2D(id="l", width=6))
    one, two = SceneTransition.between(a, b), SceneTransition.between(a, b)
    for t in (0.0, 0.07, 0.3):
        assert one.animation().sample(t) == two.animation().sample(t)
    end = one.animation().sample(0.3)
    assert end.get("p") == b.get("p") and end.get("l") == b.get("l")


def test_transition_requires_matching_scene_types():
    class Other(Scene2D):
        __slots__ = ()

    with pytest.raises(ConfigurationError):
        SceneTransition.between(Scene2D(), Other())
    with pytest.raises(ConfigurationError):
        SceneTransition.between(Scene2D(), Scene2D(), duration=-1)


def test_explicit_morph_to_and_failure_mode():
    node = Shape2D(id="s", path=Path2D.rect(0, 0, 2, 2))
    motion = node.morph_to(Path2D.polygon([(0, 0), (4, 0), (2, 3)]), duration=1.0)
    from kinetickit.animation import Animation

    anim = Animation(Scene2D(node), motion)
    assert (
        anim.sample(1.0).get("s").path.bounds() == Path2D.polygon([(0, 0), (4, 0), (2, 3)]).bounds()
    )
    two = Path2D.polygon([(0, 0), (4, 0), (4, 4)], [(1, 1), (2, 1), (2, 2)])
    with pytest.raises(ConfigurationError, match="cannot morph"):
        node.morph_to(two, duration=1.0)
    line = PathNode2D.polyline("pl", [(0, 0), (1, 1)])
    assert line.morph_to(Path2D.polyline([(0, 1), (1, 0), (2, 2)]), duration=0.5).duration == 0.5
