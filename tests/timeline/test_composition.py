from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from kinetickit import ease
from kinetickit.errors import ConfigurationError
from kinetickit.keyframes import Keyframe
from kinetickit.timeline import Timeline
from kinetickit.tween import PropertyBuilder, PropertyRef


def ref(name: str = "x", node: str = "n", kind: type = float) -> PropertyRef:
    return PropertyRef(node, name, kind)


def move(name: str, to: float, duration: float = 1.0, **kw):
    return PropertyBuilder(ref(name)).to(to, duration=duration, **kw)


def tl(motion, **base):
    return Timeline(motion, {ref(k): v for k, v in (base or {"x": 0.0}).items()})


def val(timeline, name, t):
    return timeline.value(ref(name), t)


def test_chain_means_a_then_b_and_c_then_d():
    a, b, c, d = (move(n, 1.0) for n in "abcd")
    motion = a.then(b).with_(c).then(d)
    assert motion.stages == ((a,), (b, c), (d,))
    assert motion.duration == 3.0


def test_offsets_gaps_and_parallel_duration():
    a, b, c = move("a", 1, 1), move("b", 1, 2), move("c", 1, 1)
    assert a.with_(b).duration == 2.0
    assert a.with_(c, offset=1.5).duration == 2.5
    assert a.then(b, gap=0.5).duration == 3.5
    assert a.then(b).then(c, gap=1.0).duration == 5.0


def test_start_and_end_semantics_are_exact_when_nested():
    inner = move("x", 10.0).then(move("y", 5.0))
    outer = move("z", 1.0, 0.5).then(inner)
    t = Timeline(outer, {ref("x"): 0.0, ref("y"): 0.0, ref("z"): 0.0})
    assert t.duration == 2.5
    assert val(t, "x", 0.5) == 0.0
    assert val(t, "x", 1.5) == 10.0
    assert val(t, "y", 1.5) == 0.0
    assert val(t, "y", 2.5) == 5.0


def test_tween_samples_endpoints_and_easing():
    t = tl(move("x", 10.0, 2.0, easing=ease.in_quad))
    assert val(t, "x", 0.0) == 0.0
    assert val(t, "x", 1.0) == pytest.approx(2.5)
    assert val(t, "x", 2.0) == 10.0
    assert val(t, "x", 99.0) == 10.0  # past the end clamps to the final state


def test_sampling_is_deterministic_and_random_access():
    motion = move("x", 10, 1, easing=ease.in_out_cubic).then(move("x", 0, 1))
    t1, t2 = tl(motion), tl(motion)
    times = [0.0, 0.3, 1.0, 1.7, 2.0, 0.3]
    assert [t1.sample(s) for s in times] == [t2.sample(s) for s in times]
    assert t1.sample(0.3) == t1.sample(0.3)


def test_implicit_start_follows_previous_motion():
    t = tl(move("x", 10.0).then(move("x", 20.0)))
    assert val(t, "x", 1.0) == 10.0
    assert val(t, "x", 1.5) == 15.0


def test_explicit_from_overrides_implicit_start():
    t = tl(move("x", 10.0, from_=4.0))
    assert val(t, "x", 0.0) == 4.0
    assert val(t, "x", 0.5) == 7.0


def test_delay_holds_initial_value():
    t = tl(move("x", 10.0).delay(1.0))
    assert t.duration == 2.0
    assert val(t, "x", 0.99) == 0.0
    assert val(t, "x", 1.5) == 5.0


def test_repeat_total_count_semantics():
    motion = move("x", 10.0).repeat(3)
    assert motion.duration == 3.0
    t = tl(motion)
    assert val(t, "x", 0.5) == 5.0
    assert val(t, "x", 1.5) == 5.0  # each iteration replays the same resolved motion
    assert val(t, "x", 2.5) == 5.0
    for bad in (0, -1, 1.5, True):
        with pytest.raises(ConfigurationError):
            move("x", 1).repeat(bad)


def test_yoyo_alternates_without_duplicating_turnaround():
    t = tl(move("x", 10.0).yoyo())
    assert t.duration == 2.0
    assert val(t, "x", 1.0) == 10.0
    assert val(t, "x", 1.5) == 5.0
    assert val(t, "x", 2.0) == 0.0
    t3 = tl(move("x", 10.0).repeat(3, yoyo=True))
    assert val(t3, "x", 3.0) == 10.0
    assert val(t3, "x", 2.5) == 5.0


def test_reverse_maps_easing_to_reversed_ease():
    easing = ease.in_cubic
    forward = tl(move("x", 10.0, easing=easing))
    backward = tl(move("x", 10.0, easing=easing).reverse())
    for s in (0.0, 0.2, 0.5, 0.9, 1.0):
        assert val(backward, "x", s) == pytest.approx(val(forward, "x", 1.0 - s))
        assert val(backward, "x", s) == pytest.approx(
            10.0 + (0.0 - 10.0) * ease.reversed_ease(easing)(s)
        )


def test_reverse_of_sequence_reverses_order():
    t = tl(move("x", 10.0).then(move("x", 30.0)).reverse())
    assert val(t, "x", 0.0) == 30.0
    assert val(t, "x", 1.0) == 10.0
    assert val(t, "x", 2.0) == 0.0


def test_reverse_twice_is_identity():
    base = move("x", 10.0, easing=ease.out_cubic).then(move("y", 3.0, 0.5))
    a = Timeline(base, {ref("x"): 0.0, ref("y"): 0.0})
    b = Timeline(base.reverse().reverse(), {ref("x"): 0.0, ref("y"): 0.0})
    for s in (0.0, 0.4, 1.0, 1.3, 1.5):
        assert a.sample(s) == pytest.approx(b.sample(s)) or a.sample(s) == b.sample(s)


def test_keyframes_resolve_across_times_and_hold():
    kf = PropertyBuilder(ref()).keyframes(
        (0.0, 0.0), (1.0, 10.0), Keyframe(2.0, 20.0, hold=True), (3.0, 0.0)
    )
    t = tl(kf)
    assert t.duration == 3.0
    assert val(t, "x", 0.5) == 5.0
    assert val(t, "x", 1.5) == 10.0  # held until the jump at t=2
    assert val(t, "x", 2.0) == 20.0
    assert val(t, "x", 2.5) == 10.0


def test_keyframes_start_from_current_value_when_first_key_is_late():
    kf = PropertyBuilder(ref()).keyframes((1.0, 10.0))
    t = tl(kf, x=2.0)
    assert val(t, "x", 0.5) == 6.0


def test_keyframe_validation():
    builder = PropertyBuilder(ref())
    with pytest.raises(ConfigurationError):
        builder.keyframes((1.0, 1.0), (1.0, 2.0))
    with pytest.raises(ConfigurationError):
        builder.keyframes((2.0, 1.0), (1.0, 2.0))
    with pytest.raises(ConfigurationError):
        builder.keyframes()
    with pytest.raises(ConfigurationError):
        builder.keyframes((-1.0, 1.0))


def test_per_keyframe_easing_applies_to_arriving_segment():
    kf = PropertyBuilder(ref()).keyframes(
        (0.0, 0.0), Keyframe(1.0, 8.0, easing=ease.in_cubic), (2.0, 8.0)
    )
    assert val(tl(kf), "x", 0.5) == pytest.approx(1.0)


def test_overlap_conflict_most_recently_started_wins():
    motion = move("x", 10.0, 2.0).with_(move("x", 100.0, 1.0), offset=1.0)
    t = tl(motion)
    assert val(t, "x", 0.5) == 2.5
    assert val(t, "x", 1.0) == 5.0  # second tween starts from the value at t=1
    assert val(t, "x", 2.0) == 100.0
    assert val(t, "x", 3.0) == 100.0


def test_trim_keeps_the_exact_window():
    full = tl(move("x", 10.0, 4.0, easing=ease.in_quad))
    cut = tl(move("x", 10.0, 4.0, easing=ease.in_quad).trim(1.0, 3.0))
    assert cut.duration == 2.0
    for s in (0.0, 0.5, 1.0, 1.5, 2.0):
        assert val(cut, "x", s) == pytest.approx(val(full, "x", 1.0 + s))


def test_trim_drops_earlier_segments_and_holds_entry_value():
    motion = move("x", 10.0).then(move("x", 30.0)).trim(1.0, 2.0)
    t = tl(motion)
    assert val(t, "x", 0.0) == 10.0
    assert val(t, "x", 0.5) == 20.0
    with pytest.raises(ConfigurationError):
        move("x", 1.0).trim(0.0, 2.0)


def test_hold_and_pause():
    t = tl(move("x", 10.0).hold(2.0))
    assert t.duration == 3.0
    assert val(t, "x", 2.5) == 10.0


def test_markers_survive_composition():
    motion = move("x", 1).mark("a", 0.25).then(move("y", 1).mark("b")).delay(1.0)
    t = Timeline(motion, {ref("x"): 0.0, ref("y"): 0.0})
    assert t.markers == {"a": 1.25, "b": 2.0}
    assert t.marker_time("b") == 2.0
    with pytest.raises(ConfigurationError):
        t.marker_time("zzz")
    with pytest.raises(ConfigurationError):
        Timeline(
            move("x", 1).mark("m").then(move("y", 1).mark("m")), {ref("x"): 0.0, ref("y"): 0.0}
        )


def test_vector_and_color_properties_use_the_registry():
    from kinetickit.interpolation import Color

    pos = PropertyRef("n", "pos", tuple)
    col = PropertyRef("n", "col", Color)
    motion = (
        PropertyBuilder(pos)
        .to((2, 4), duration=1)
        .with_(PropertyBuilder(col).to("#ffffff", duration=1))
    )
    t = Timeline(motion, {pos: (0.0, 0.0), col: Color(0, 0, 0)})
    assert t.value(pos, 0.5) == (1.0, 2.0)
    assert t.value(col, 0.5).to_hex() == "#808080"


def test_unregistered_type_fails_when_the_timeline_is_built():
    class Opaque: ...

    ref_o = PropertyRef("n", "o", Opaque)
    with pytest.raises(ConfigurationError, match="no interpolator"):
        Timeline(PropertyBuilder(ref_o).to(Opaque(), duration=1), {ref_o: Opaque()})


def test_missing_initial_value_and_bad_times():
    with pytest.raises(ConfigurationError, match="no initial value"):
        Timeline(move("x", 1.0), {})
    t = tl(move("x", 1.0))
    for bad in (-0.1, float("nan"), float("inf"), "a"):
        with pytest.raises(ConfigurationError):
            t.sample(bad)


def test_negative_and_invalid_durations_rejected():
    for bad in (-1.0, float("nan"), float("inf")):
        with pytest.raises(ConfigurationError):
            move("x", 1.0, bad)
    with pytest.raises(ConfigurationError):
        move("x", 1.0).delay(-1)
    with pytest.raises(ConfigurationError):
        move("x", 1.0).then(move("y", 1.0), gap=-1)
    with pytest.raises(ConfigurationError):
        move("x", 1.0).then("nope")  # type: ignore[arg-type]


def test_instant_set_jumps_at_its_time():
    t = tl(move("x", 5.0).then(PropertyBuilder(ref()).set(1.0)))
    assert val(t, "x", 0.99) == pytest.approx(4.95)
    assert val(t, "x", 1.0) == 1.0


def test_motion_equality_and_immutability():
    a = move("x", 1.0)
    assert a == move("x", 1.0)
    with pytest.raises(AttributeError):
        a.length = 2.0  # type: ignore[misc]


@given(
    st.floats(min_value=0.0, max_value=5.0),
    st.floats(min_value=0.01, max_value=5.0),
    st.integers(min_value=1, max_value=5),
)
def test_repeat_duration_and_periodicity(delay, length, times):
    motion = move("x", 7.0, length).repeat(times)
    t = tl(motion)
    assert t.duration == pytest.approx(length * times)
    for k in range(times):
        assert val(t, "x", k * length + length / 2) == pytest.approx(3.5)


@given(st.floats(min_value=0.05, max_value=3.0), st.floats(min_value=0.0, max_value=1.0))
def test_yoyo_is_symmetric_about_the_turnaround(length, frac):
    t = tl(move("x", 10.0, length, easing=ease.in_out_cubic).yoyo())
    s = frac * length
    assert val(t, "x", length + s) == pytest.approx(val(t, "x", length - s), abs=1e-9)
