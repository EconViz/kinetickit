from __future__ import annotations

import io
import json
import re
from pathlib import Path

import pytest
from tests.support.smil import Q, parse

from kinetickit.accessibility import AccessibilityInfo, ReducedMotion, Semantics, reading_order
from kinetickit.animation import Animation
from kinetickit.errors import ConfigurationError
from kinetickit.geometry.two_d import Bounds2D
from kinetickit.interaction import PlaybackControls
from kinetickit.scene import Group2D, Line2D, Point2D, Scene2D


def sem(**kw):
    return Semantics(**kw)


def build(**anim_kw):
    a = Point2D(
        id="a",
        semantics=sem(
            role="graphics-symbol", label="Start", description="Where it begins", reading_order=2
        ),
    )
    b = Point2D(id="b", position=(5, 5), semantics=sem(label="End", reading_order=1))
    deco = Line2D(id="rule", end=(9, 0), semantics=sem(hidden=True))
    s = Scene2D(a, b, deco)
    s = s.bind({s.camera.ref("view"): Bounds2D((0, 0), (10, 10))})
    return Animation(s, a.animate.position.to((8, 8), duration=2.0), **anim_kw)


def test_semantics_validation():
    assert sem().is_empty
    for bad in (
        {"role": "wizard"},
        {"label": " "},
        {"description": 3},
        {"reading_order": 1.5},
        {"hidden": True, "label": "x"},
    ):
        with pytest.raises(ConfigurationError):
            Semantics(**bad)
    with pytest.raises(ConfigurationError, match="Semantics"):
        Point2D(id="p", semantics="a label")
    assert Point2D(id="p", semantics=sem(label="x")).semantics.label == "x"


def test_semantics_are_independent_of_any_visualization_package():
    import kinetickit.accessibility as acc

    for mod in (acc.semantics, acc.info, acc.focus):
        src = Path(mod.__file__).read_text()
        assert "mosaickit" not in src and "_viz" not in src


def test_reading_order_ranks_then_scene_order_and_skips_decorative_nodes():
    anim = build()
    ids = [n.id for n in reading_order(anim.scene)]
    assert ids == ["b", "a"]  # reading_order 1 then 2; 'rule' is decorative
    unranked = Scene2D(
        Point2D(id="x", semantics=sem(label="X")),
        Point2D(id="y", semantics=sem(label="Y", reading_order=0)),
    )
    assert [n.id for n in reading_order(unranked)] == ["y", "x"]
    assert reading_order(Scene2D(Point2D(id="n"))) == ()


def test_svg_exports_titles_descriptions_roles_and_labels():
    anim = build(
        accessibility=AccessibilityInfo(title="Dot demo", description="A dot travels", lang="en")
    )
    root = parse(anim.to_svg(width=200, height=200))
    assert (
        root.find(Q + "title").text == "Dot demo" and root.find(Q + "desc").text == "A dot travels"
    )
    assert root.get("aria-labelledby") and root.get("aria-describedby") and root.get("lang") == "en"
    a = next(e for e in root.iter() if e.get("id") == "a")
    assert a.get("role") == "graphics-symbol" and a.get("aria-label") == "Start"
    assert a.find(Q + "title").text == "Start" and a.find(Q + "desc").text == "Where it begins"
    assert next(iter(a)).tag == Q + "title"  # <title> must be the first child
    assert a.get("data-kk-order") == "2"
    rule = next(e for e in root.iter() if e.get("id") == "rule")
    assert rule.get("aria-hidden") == "true" and rule.get("role") == "presentation"


def test_explicit_settings_override_animation_level_text():
    anim = build(accessibility=AccessibilityInfo(title="From info"))
    root = parse(anim.to_svg(title="From settings"))
    assert root.find(Q + "title").text == "From settings"


def test_standalone_svg_applies_reduced_motion_without_autoplay():
    root = parse(build().to_svg())
    script = next(e for e in root.iter() if e.tag == Q + "script")
    assert "prefers-reduced-motion: reduce" in script.text and "setCurrentTime(2)" in script.text
    first = parse(
        build(accessibility=AccessibilityInfo(reduced_motion=ReducedMotion("first"))).to_svg()
    )
    assert "setCurrentTime(0)" in next(e for e in first.iter() if e.tag == Q + "script").text
    at = parse(
        build(accessibility=AccessibilityInfo(reduced_motion=ReducedMotion("time", 0.5))).to_svg()
    )
    assert "setCurrentTime(0.5)" in next(e for e in at.iter() if e.tag == Q + "script").text
    assert not [
        e for e in parse(build().to_svg(reduced_motion=None)).iter() if e.tag == Q + "script"
    ]
    static = parse(Animation(Scene2D(Point2D(id="p"))).to_svg())
    assert not [e for e in static.iter() if e.tag == Q + "script"]


def test_reduced_motion_policy_validation_and_times():
    assert ReducedMotion().representative_time(3.0) == 3.0
    assert ReducedMotion("first").representative_time(3.0) == 0.0
    assert ReducedMotion("time", 5.0).representative_time(3.0) == 3.0
    for bad in (("sideways", None), ("time", None), ("time", -1.0), ("final", 1.0)):
        with pytest.raises(ConfigurationError):
            ReducedMotion(*bad)
    with pytest.raises(ConfigurationError):
        AccessibilityInfo(title=" ")


def test_reduced_motion_removes_nonessential_movement_in_html():
    html = build().to_bytes("html").decode()
    data = json.loads(re.search(r'id="kk-data">(.*?)</script>', html, re.S).group(1))
    assert data["reducedTime"] == 2.0  # final state is the representative state
    assert 'data-kk="notice"' in html and "hidden" in html
    assert (
        "if (data.autoplay) play();" in html and "else { show(0);" in html
    )  # autoplay only when motion is fine
    first = (
        build(accessibility=AccessibilityInfo(reduced_motion=ReducedMotion("first")))
        .to_bytes("html")
        .decode()
    )
    assert (
        json.loads(re.search(r'id="kk-data">(.*?)</script>', first, re.S).group(1))["reducedTime"]
        == 0.0
    )
    inline = re.search(r"<svg.*?</svg>", html, re.S).group(0)
    assert "prefers-reduced-motion" not in inline  # the page runtime owns reduced motion


def test_html_exposes_reading_order_and_labels_as_text():
    anim = build(
        accessibility=AccessibilityInfo(title="T", description="D", long_description="Long text")
    )
    html = anim.to_bytes("html").decode()
    items = re.findall(r'<li data-kk-ref="([^"]+)">([^<]*)</li>', html)
    assert [i for i, _ in items] == ["b", "a"]
    assert "Where it begins" in items[1][1] and "(graphics-symbol)" in items[1][1]
    assert 'id="kk-long">Long text<' in html and '<html lang="en">' in html
    assert 'aria-label="D"' in html and "<title>T</title>" in html


def test_interactive_controls_are_native_and_keyboard_operable():
    tags = re.findall(r"<(button|input|select|div|span)([^>]*)>", build().to_bytes("html").decode())
    controls = [(t, a) for t, a in tags if "data-kk=" in a]
    assert controls and all(t in ("button", "input", "select") for t, _ in controls)
    assert not [a for _, a in controls if 'tabindex="-1"' in a]
    assert all("aria-label" in a for t, a in controls if t == "button")
    keys = PlaybackControls().keys
    assert {"Space", "ArrowLeft", "ArrowRight", "Home", "End"} <= set(keys)
    assert 'e.key === " "' in build().to_bytes("html").decode()


def test_state_is_not_communicated_by_color_alone():
    html = build().to_bytes("html").decode()
    selected = re.search(
        r'svg\.kk-svg \[data-kk-selected="true"\] path[^{]*\{([^}]*)\}', html
    ).group(1)
    assert "stroke-width" in selected  # thicker outline, not just a hue change
    assert "aria-selected" in html  # exposed to assistive technology
    focus = re.search(r"\[data-kk-id\]:focus-visible\{([^}]*)\}", html).group(1)
    assert "outline" in focus and "3px" in focus


def test_gif_requires_a_description_and_returns_it_with_a_representative_frame(tmp_path):
    pytest.importorskip("PIL")
    pytest.importorskip("matplotlib")
    anim = build()
    with pytest.raises(ConfigurationError, match="needs a description"):
        anim.save(tmp_path / "x.gif", width=48, height=48, fps=4, accessibility=True)
    assert list(tmp_path.iterdir()) == []
    m = anim.save(
        io.BytesIO(),
        format="gif",
        width=48,
        height=48,
        fps=4,
        accessibility=True,
        description="A dot crosses a square",
    )
    assert m.description == "A dot crosses a square"
    assert m.representative_frame.startswith(b"\x89PNG")
    assert any("text alternative" in p for p in m.preserved)
    assert any("not embedded" in d for d in m.degraded) and any(
        "object semantics" in d for d in m.degraded
    )
    quiet = anim.save(io.BytesIO(), format="gif", width=48, height=48, fps=4)
    assert quiet.representative_frame is None and quiet.description is None


def test_gif_companion_files_are_explicit_never_a_side_effect(tmp_path):
    pytest.importorskip("PIL")
    pytest.importorskip("matplotlib")
    anim = build(accessibility=AccessibilityInfo(alt_text="Dot moving diagonally"))
    out = tmp_path / "a.gif"
    anim.save(out, width=48, height=48, fps=4)
    assert [p.name for p in tmp_path.iterdir()] == ["a.gif"]
    png, meta = tmp_path / "a.png", tmp_path / "a.json"
    m = anim.save(
        out, width=48, height=48, fps=4, accessibility=True, companion_png=png, companion_json=meta
    )
    assert png.read_bytes() == m.representative_frame
    data = json.loads(meta.read_text())
    assert data["description"] == "Dot moving diagonally" and data["frames"] == 8
    first = anim.to_bytes("gif", width=48, height=48, fps=4, accessibility=True)
    assert first  # alt text from AccessibilityInfo satisfies the requirement


def test_first_frame_representative_image():
    pytest.importorskip("PIL")
    pytest.importorskip("matplotlib")
    from PIL import Image

    final = build().save(
        io.BytesIO(), format="gif", width=64, height=64, fps=4, accessibility=True, description="d"
    )
    first = build(accessibility=AccessibilityInfo(reduced_motion=ReducedMotion("first"))).save(
        io.BytesIO(), format="gif", width=64, height=64, fps=4, accessibility=True, description="d"
    )
    a = Image.open(io.BytesIO(final.representative_frame)).convert("RGB")
    b = Image.open(io.BytesIO(first.representative_frame)).convert("RGB")
    assert a.tobytes() != b.tobytes()


def test_manifests_document_preserved_and_degraded_semantics():
    anim = build(accessibility=AccessibilityInfo(title="T", description="D"))
    svg = anim.save(io.BytesIO(), format="svg")
    for fact in ("title", "description", "object labels", "roles"):
        assert fact in svg.preserved
    assert any("reading order" in d for d in svg.degraded)
    html = anim.save(io.BytesIO(), format="html")
    assert (
        "reading order" in html.preserved
        and "keyboard controls" in html.preserved
        and html.degraded == ()
    )


def test_groups_and_nested_nodes_carry_semantics_through_svg():
    g = Group2D(
        id="g",
        semantics=sem(role="group", label="Cluster"),
        children=(Point2D(id="c", semantics=sem(label="Inner")),),
    )
    root = parse(Animation(Scene2D(g)).to_svg())
    group = next(e for e in root.iter() if e.get("id") == "g")
    assert group.get("role") == "group" and group.find(Q + "title").text == "Cluster"
    inner = next(e for e in root.iter() if e.get("id") == "c")
    assert inner.get("aria-label") == "Inner"
