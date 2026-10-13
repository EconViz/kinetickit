from __future__ import annotations

import json
import re
from html.parser import HTMLParser

import numpy as np
import pytest

from kinetickit import ease
from kinetickit.animation import Animation
from kinetickit.errors import CapabilityError, ConfigurationError
from kinetickit.geometry.three_d import MeshData
from kinetickit.geometry.two_d import Bounds2D
from kinetickit.renderers import get_renderer, require
from kinetickit.renderers.interactive import HtmlSettings
from kinetickit.scene import (
    Camera3D,
    Group2D,
    Mesh3D,
    Point2D,
    Point3D,
    Scene2D,
    Scene3D,
    Surface3D,
)

pytest.importorskip("plotly")


def scene2d():
    p = Point2D(id="p", position=(1, 1), size=8)
    q = Point2D(id="q <b>&", position=(5, 5))
    s = Scene2D(p, q)
    s = s.bind({s.camera.ref("view"): Bounds2D((0, 0), (10, 10))})
    return p, Animation(
        s, p.animate.position.to((8, 8), duration=2.0, easing=ease.in_out_cubic).mark("half", 1.0)
    )


def scene3d(duration=1.0):
    surf = Surface3D.height_field(
        "s", np.linspace(-1, 1, 6), np.linspace(-1, 1, 6), np.zeros((6, 6)), edge_color="#000000"
    )
    pt = Point3D(id="pt", position=(0, 0, 1), size=6)
    scene = Scene3D(surf, pt, camera=Camera3D(position=(0, -5, 3), target=(0, 0, 0)))
    return Animation(scene, scene.camera.animate.position.to((5, 0, 3), duration=duration))


class Collect(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


def parse(html):
    c = Collect()
    c.feed(html)
    return c.tags


def data_of(html):
    m = re.search(r'<script type="application/json" id="kk-data">(.*?)</script>', html, re.S)
    return json.loads(m.group(1))


def test_2d_document_is_a_single_self_contained_page():
    _, anim = scene2d()
    html = anim.to_bytes(
        "html", width=400, height=300, title="Demo", description="A dot moves"
    ).decode()
    tags = parse(html)
    assert html.startswith("<!doctype html>") and '<html lang="en">' in html
    assert not [a for t, a in tags if t == "script" and "src" in a]
    assert not [a for t, a in tags if t == "link"]
    urls = set(re.findall(r"https?://[^\s\"'<>)]+", html))
    assert urls <= {"http://www.w3.org/2000/svg"}  # only the XML namespace identifier
    assert not re.search(r"@import|url\(\s*https?:", html)
    svg = [a for t, a in tags if t == "svg"]
    assert svg and svg[0]["class"] == "kk-svg" and svg[0]["role"] == "img"
    assert "<title>Demo</title>" in html and "A dot moves" in html


def test_runtime_data_carries_ids_markers_and_playback_options():
    _, anim = scene2d()
    html = anim.to_bytes("html", loop=True, autoplay=False, speed=2.0, fps=24).decode()
    data = data_of(html)
    assert data["dimension"] == 2 and data["duration"] == 2.0 and data["fps"] == 24
    assert data["loop"] is True and data["autoplay"] is False and data["speed"] == 2.0
    assert data["markers"] == {"half": 1.0}
    assert set(data["objects"]) == {"p", "q <b>&"}
    assert data["version"] == 1 and data["generator"].startswith("kinetickit ")


def test_document_data_is_safe_to_embed():
    _, anim = scene2d()
    html = anim.to_bytes("html").decode()
    block = re.search(r'id="kk-data">(.*?)</script>', html, re.S).group(1)
    assert "</" not in block and "<b>" not in block and "\\u003cb\\u003e" in block
    assert data_of(html)["objects"]["q <b>&"] == "point"


def test_elements_keep_stable_ids_and_semantic_metadata():
    _, anim = scene2d()
    html = anim.to_bytes("html").decode()
    ids = {a["data-kk-id"] for t, a in parse(html) if "data-kk-id" in a}
    assert ids == {"p", "q <b>&"}


def test_controls_are_labelled_and_native_form_elements():
    _, anim = scene2d()
    tags = parse(anim.to_bytes("html").decode())
    by = {a.get("data-kk"): (t, a) for t, a in tags if "data-kk" in a}
    assert {"play", "prev", "next", "first", "last", "seek", "speed", "loop", "reset"} <= set(by)
    for name in ("play", "prev", "next", "first", "last", "reset"):
        tag, attrs = by[name]
        assert tag == "button" and attrs["type"] == "button" and attrs["aria-label"]
    assert (
        by["seek"][0] == "input"
        and by["seek"][1]["type"] == "range"
        and by["seek"][1]["aria-label"]
    )
    assert by["speed"][1]["aria-label"] == "Playback speed"
    toolbar = [a for t, a in tags if a.get("role") == "toolbar"]
    assert toolbar and toolbar[0]["aria-label"]
    marker = [a for t, a in tags if "data-kk-marker" in a]
    assert marker and marker[0]["data-kk-marker"] == "half"


def test_controls_can_be_omitted_and_static_documents_hide_playback():
    _, anim = scene2d()
    assert 'data-kk="play"' not in anim.to_bytes("html", controls=False).decode()
    static = Animation(Scene2D(Point2D(id="p"))).to_bytes("html").decode()
    assert 'data-kk="play"' not in static and 'data-kk="reset"' in static
    assert data_of(static)["duration"] == 0.0


def test_runtime_honours_reduced_motion_and_exposes_a_public_api():
    _, anim = scene2d()
    html = anim.to_bytes("html").decode()
    assert "prefers-reduced-motion: reduce" in html
    assert "window.kinetickit" in html and "kinetickit:" in html
    assert "if (reduce) { show(D); }" in html  # final state, no autoplay


def test_noscript_fallback_is_documented_in_the_page():
    _, anim = scene2d()
    assert "<noscript>" in anim.to_bytes("html").decode()


def test_3d_offline_embeds_the_runtime_and_has_no_network_reference():
    html = scene3d().to_bytes("html", width=500, height=400).decode()
    tags = parse(html)
    assert not [a for t, a in tags if t == "script" and "src" in a]
    assert len(html) > 1_000_000  # the 3D runtime is embedded
    assert "cdn.plot.ly/plotly-" not in html  # no pinned remote copy of the runtime
    data = data_of(html)
    assert data["dimension"] == 3 and len(data["frames"]) == 30
    assert data["layout"]["scene"]["camera"]["projection"] == {"type": "perspective"}
    roles = data["objects"]
    assert roles["s"] in {"faces", "edges"} and roles["pt"] == "points"
    assert any(t["meta"]["id"] == "s" and t["type"] == "mesh3d" for t in data["traces"])
    assert "frame" in html and "kk-plot" in html


def test_3d_frames_only_store_what_changes_and_include_the_camera():
    data = data_of(scene3d().to_bytes("html", fps=10).decode())
    assert len(data["frames"]) == 10
    first, last = data["frames"][0], data["frames"][-1]
    assert (
        first["data"] == [] and first["traces"] == []
    )  # geometry is static: only the camera moves
    assert first["layout"]["scene"]["camera"] != last["layout"]["scene"]["camera"]
    eye = last["layout"]["scene"]["camera"]["eye"]
    assert eye["x"] > 0 and abs(eye["y"]) < 1e-6


def test_3d_geometry_changes_become_per_frame_diffs():
    m = Mesh3D(id="m", mesh=MeshData([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [(0, 1, 2)]))
    scene = Scene3D(m, camera=Camera3D(position=(0, -4, 2), target=(0, 0, 0)))
    anim = Animation(
        scene,
        m.animate.mesh.to(MeshData([(0, 0, 1), (1, 0, 1), (0, 1, 1)], [(0, 1, 2)]), duration=1.0),
    )
    data = data_of(anim.to_bytes("html", fps=4).decode())
    assert data["frames"][0]["traces"] == [0] and "layout" not in data["frames"][0]
    z0 = data["frames"][0]["data"][0]["z"]
    z3 = data["frames"][-1]["data"][0]["z"]
    assert z0 == [0.0, 0.0, 0.0] and z3 == [1.0, 1.0, 1.0]


def test_compact_packaging_declares_its_only_network_dependency(tmp_path):
    out = tmp_path / "c.html"
    manifest = scene3d().save(out, renderer="interactive", packaging="compact")
    html = out.read_text()
    assert manifest.network_dependencies and manifest.network_dependencies[0].startswith(
        "https://cdn.plot.ly/"
    )
    assert f'<script src="{manifest.network_dependencies[0]}"' in html
    assert len(html) < 500_000
    offline = scene3d().save(tmp_path / "o.html", renderer="interactive")
    assert offline.network_dependencies == ()
    assert (
        scene2d()[1]
        .save(tmp_path / "t.html", renderer="interactive", packaging="compact")
        .network_dependencies
        == ()
    )


def test_3d_has_a_static_noscript_fallback_of_the_final_state():
    html = scene3d().to_bytes("html").decode()
    m = re.search(r"<noscript>(.*?)</noscript>", html, re.S)
    assert m and "<svg" in m.group(1) and "final state" in m.group(1)


def test_capability_errors_are_explicit_and_leave_no_file(tmp_path):
    a, b = Point2D(id="a"), Point2D(id="b")
    with pytest.raises(CapabilityError, match="z-order"):
        Animation(Scene2D(a, b), a.animate.z.to(2.0, duration=1.0)).save(
            tmp_path / "x.html", renderer="interactive"
        )
    hud = Point2D(id="hud")
    anim = Animation(
        Scene3D(Point3D(id="p"), overlay=[hud]), hud.animate.size.to(9.0, duration=1.0)
    )
    with pytest.raises(CapabilityError, match="overlay"):
        anim.save(tmp_path / "y.html", renderer="interactive")
    with pytest.raises(CapabilityError, match="frames"):
        scene3d(duration=100.0).to_bytes("html", fps=30, max_frames=100)
    assert list(tmp_path.iterdir()) == []


def test_overlay_content_is_layered_over_3d():
    scene = Scene3D(Point3D(id="p"), overlay=[Point2D(id="hud", position=(10, 10))])
    html = Animation(scene).to_bytes("html").decode()
    assert "kk-overlay-layer" in html and 'data-kk-id="hud"' in html


def test_capabilities_and_settings_validation():
    caps = get_renderer("interactive").capabilities
    assert caps.name == "interactive"
    caps.validate(require(dimensions=["native-3d"], interactions=["hover", "click", "camera"]))
    with pytest.raises(CapabilityError):
        caps.validate(require(interactions=["drag"]))
    for bad in ({"packaging": "inline"}, {"speed": 0}, {"fps": 0}, {"width": -1}):
        with pytest.raises(ConfigurationError):
            HtmlSettings(**bad)


def test_group_nodes_and_ids_survive():
    g = Group2D(id="g", children=(Point2D(id="c"),))
    html = Animation(Scene2D(g)).to_bytes("html").decode()
    assert {"g", "c"} <= {a["data-kk-id"] for t, a in parse(html) if "data-kk-id" in a}
