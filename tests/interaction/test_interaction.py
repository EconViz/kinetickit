from __future__ import annotations

import io
import json

import pytest

from kinetickit.animation import Animation
from kinetickit.errors import CapabilityError, ConfigurationError
from kinetickit.geometry.two_d import Bounds2D
from kinetickit.interaction import (
    Binding,
    Degradation,
    Event,
    Interaction,
    InteractionSpec,
    Pause,
    Play,
    PlaybackControls,
    PlayerState,
    PlayRange,
    ResetCamera,
    Reverse,
    Seek,
    Select,
    SetProperty,
    SetSpeed,
    Toggle,
    action_from_data,
    parse_event,
    plan_interactions,
)
from kinetickit.renderers import get_renderer
from kinetickit.scene import Point2D, Scene2D


def anim(spec=None):
    p = Point2D(id="p")
    s = Scene2D(p, Point2D(id="q", position=(5, 5)))
    s = s.bind({s.camera.ref("view"): Bounds2D((0, 0), (10, 10))})
    return Animation(
        s, p.animate.position.to((8, 8), duration=2.0).mark("half", 1.0), interactions=spec
    )


def test_events_map_to_capabilities_and_targets():
    assert Event.HOVER_ENTER.capability is Interaction.HOVER is Event.HOVER_LEAVE.capability
    assert Event.SELECT.capability is Interaction.SELECT is Event.DESELECT.capability
    assert (
        Event.CAMERA_CHANGE.capability is Interaction.CAMERA
        and not Event.CAMERA_CHANGE.needs_target
    )
    assert Event.CLICK.needs_target
    assert parse_event("click") is Event.CLICK
    with pytest.raises(ConfigurationError, match="unknown event"):
        parse_event("swipe")


def test_actions_round_trip_through_plain_data():
    actions = [
        Play(),
        Pause(),
        Toggle(),
        Reverse(),
        Seek(1.5),
        Seek("half"),
        SetSpeed(2.0),
        PlayRange("intro"),
        Select("p", "select"),
        Select(),
        SetProperty("p", "opacity", 0.5),
        SetProperty(None, "visible", False),
        ResetCamera(),
    ]
    for a in actions:
        data = a.to_data()
        assert json.loads(json.dumps(data)) == data
        assert action_from_data(data) == a


def test_actions_reject_code_and_invalid_values():
    for bad in (
        lambda: Seek(-1),
        lambda: Seek(float("nan")),
        lambda: Seek(""),
        lambda: SetSpeed(0),
        lambda: PlayRange(""),
        lambda: Select(mode="all"),
        lambda: SetProperty("p", "color", "red"),
        lambda: SetProperty("p", "opacity", 2),
        lambda: SetProperty("p", "visible", 1),
    ):
        with pytest.raises(ConfigurationError):
            bad()
    for data in ({"kind": "explode"}, {"nokind": 1}, {"kind": "play", "extra": 1}, "play"):
        with pytest.raises(ConfigurationError):
            action_from_data(data)


def test_bindings_need_actions_not_callables_and_correct_targets():
    with pytest.raises(ConfigurationError):
        Binding(Event.CLICK, (lambda: None,), "p")  # type: ignore[arg-type]
    with pytest.raises(ConfigurationError):
        Binding(Event.CLICK, (), "p")
    with pytest.raises(ConfigurationError, match="needs a target"):
        Binding(Event.CLICK, (Play(),))
    with pytest.raises(ConfigurationError, match="scene-wide"):
        Binding(Event.CAMERA_CHANGE, (Play(),), "p")
    b = Binding("click", Toggle(), "p")
    assert b.event is Event.CLICK and b.actions == (Toggle(),)
    assert Binding.from_data(json.loads(json.dumps(b.to_data()))) == b


def test_spec_validates_references_against_the_animation():
    ok = InteractionSpec(
        (Binding(Event.CLICK, (Seek("half"), PlayRange("run"), Select("q")), "p"),),
        {"run": (0.5, 1.5)},
    )
    anim(ok)
    for bad in (
        InteractionSpec((Binding(Event.CLICK, Play(), "ghost"),)),
        InteractionSpec((Binding(Event.CLICK, Seek("nowhere"), "p"),)),
        InteractionSpec((Binding(Event.CLICK, Seek(9.0), "p"),)),
        InteractionSpec((Binding(Event.CLICK, PlayRange("nope"), "p"),)),
        InteractionSpec((Binding(Event.CLICK, Select("ghost"), "p"),)),
        InteractionSpec((), {"late": (1.0, 5.0)}),
    ):
        with pytest.raises(ConfigurationError):
            anim(bad)
    with pytest.raises(ConfigurationError):
        InteractionSpec((), {"x": (2.0, 1.0)})


def test_required_and_optional_capabilities_are_declared():
    spec = InteractionSpec(
        (
            Binding(Event.CLICK, Toggle(), "p", required=True),
            Binding(Event.HOVER_ENTER, Select(), "q"),
        )
    )
    assert spec.required() == {Interaction.CLICK, Interaction.PLAYBACK}
    assert spec.optional() == {Interaction.HOVER, Interaction.SELECT}
    data = spec.to_data()
    assert data["required"] == ["click", "playback"] and data["optional"] == ["hover", "select"]
    assert InteractionSpec.from_data(json.loads(json.dumps(data))).bindings == spec.bindings


def test_same_model_maps_to_html_and_degrades_elsewhere_by_explicit_policy():
    spec = InteractionSpec(
        (Binding(Event.CLICK, Toggle(), "p"), Binding(Event.HOVER_ENTER, Select(), "q"))
    )
    html_plan = plan_interactions(spec, get_renderer("interactive").capabilities)
    assert len(html_plan.active) == 2 and html_plan.dropped == ()
    svg_plan = plan_interactions(spec, get_renderer("vector").capabilities)
    assert svg_plan.active == () and len(svg_plan.dropped) == 2
    assert "does not support" in svg_plan.degraded[0]
    with pytest.raises(CapabilityError, match="unsupported interactions"):
        plan_interactions(spec, get_renderer("vector").capabilities, Degradation.FAIL)


def test_required_bindings_fail_before_any_output(tmp_path):
    spec = InteractionSpec((Binding(Event.CLICK, Toggle(), "p", required=True),))
    a = anim(spec)
    for name in ("m.svg", "m.gif"):
        with pytest.raises(CapabilityError, match="click"):
            a.save(tmp_path / name, width=64, height=64)
    assert list(tmp_path.iterdir()) == []
    assert a.save(tmp_path / "ok.html").preserved == ("click", "playback")


def test_optional_bindings_are_reported_as_degraded_in_manifests():
    spec = InteractionSpec((Binding(Event.CLICK, Toggle(), "p"),))
    svg = anim(spec).save(io.BytesIO(), format="svg")
    assert svg.preserved == () and svg.degraded and "click on p" in svg.degraded[0]
    html = anim(spec).save(io.BytesIO(), format="html")
    assert html.preserved == ("click", "playback") and html.degraded == ()
    drag = InteractionSpec((Binding(Event.CLICK, Toggle(), "p"),))
    assert drag.bindings[0].capabilities == {Interaction.CLICK, Interaction.PLAYBACK}


def test_html_embeds_only_serializable_data_and_active_bindings():
    spec = InteractionSpec(
        (
            Binding(Event.CLICK, (Toggle(), Select(mode="toggle")), "p"),
            Binding(Event.PLAYBACK_END, Seek(0.0)),
        ),
        {"intro": (0.0, 1.0)},
    )
    html = anim(spec).to_bytes("html").decode()
    import re

    data = json.loads(re.search(r'id="kk-data">(.*?)</script>', html, re.S).group(1))
    inter = data["interactions"]
    assert inter["ranges"] == {"intro": [0.0, 1.0]}
    assert [b["event"] for b in inter["bindings"]] == ["click", "playback-end"]
    assert inter["bindings"][0]["actions"][0] == {"kind": "toggle"}
    assert "interactions" not in json.loads(
        re.search(r'id="kk-data">(.*?)</script>', anim().to_bytes("html").decode(), re.S).group(1)
    )


def test_state_machine_is_deterministic_and_independent_of_clocks():
    s = PlayerState(duration=2.0)
    assert not s.playing and s.time == 0.0
    s = s.play().tick(0.5)
    assert s.playing and s.time == 0.5
    assert s.pause().tick(1.0).time == 0.5  # paused states do not advance
    assert s.with_speed(2.0).tick(0.25).time == 1.0
    end = s.tick(5.0)
    assert end.time == 2.0 and not end.playing and end.ended
    assert end.play().time == 0.0  # replay from the start


def test_state_machine_loop_reverse_seek_and_ranges():
    s = PlayerState(2.0).with_loop(True).play().tick(2.5)
    assert s.playing and s.time == pytest.approx(0.5)
    rev = PlayerState(2.0).seek(1.0).reverse().play().tick(0.4)
    assert rev.time == pytest.approx(0.6) and rev.direction == -1
    done = rev.tick(5.0)
    assert done.time == 0.0 and not done.playing and done.ended
    assert done.play().time == 2.0  # replaying a reversed timeline restarts from its end
    r = PlayerState(4.0).play_range(1.0, 2.0)
    assert r.time == 1.0 and r.playing
    over = r.tick(5.0)
    assert over.time == 2.0 and not over.playing and over.range is None
    assert PlayerState(4.0).seek(99).time == 4.0 and PlayerState(4.0).seek(-5).time == 0.0
    for t in (0.0, 0.3, 1.7):
        assert PlayerState(2.0).seek(t).time == t
    assert PlayerState(0.0).play().playing is False
    with pytest.raises(ConfigurationError):
        PlayerState(2.0).play_range(1.0, 5.0)
    with pytest.raises(ConfigurationError):
        PlayerState(2.0, time=3.0)


def test_controls_model_and_html_rendering():
    assert PlaybackControls().has("play") and PlaybackControls().keys["Space"]
    assert PlaybackControls(keyboard=False).keys == {}
    with pytest.raises(ConfigurationError):
        PlaybackControls(show=("teleport",))
    minimal = anim().to_bytes("html", controls=PlaybackControls(show=("play", "seek"))).decode()
    assert 'data-kk="play"' in minimal and 'data-kk="seek"' in minimal
    assert 'data-kk="speed"' not in minimal and 'data-kk="loop"' not in minimal
    assert 'data-kk="play"' not in anim().to_bytes("html", controls=False).decode()
