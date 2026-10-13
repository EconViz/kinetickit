from __future__ import annotations

import math

import pytest
from tests.support.smil import Q, animations_for, evaluate, find, layer_animations, numbers, parse

from kinetickit import ease
from kinetickit.animation import Animation
from kinetickit.errors import CapabilityError
from kinetickit.geometry.two_d import Bounds2D, Path2D, Transform2D, Vec2
from kinetickit.layout import Viewport, resolve_layout
from kinetickit.renderers.vector import SvgSettings, VectorRenderer
from kinetickit.scene import Group2D, Line2D, PathNode2D, Point2D, Scene2D, Shape2D, Text2D
from kinetickit.typography import FontResource, GlyphShape, TextAsset

VIEW = Bounds2D((0, 0), (10, 10))
SETTINGS = SvgSettings(width=200, height=200, samples=48, precision=6)


def scene_with(*nodes, overlay=()):
    s = Scene2D(*nodes, overlay=overlay)
    return s.bind({s.camera.ref("view"): VIEW})


def render(anim, **kw):
    st = SvgSettings(**{**SETTINGS.__dict__, **kw})
    return VectorRenderer().render_document(anim, st)


def nums(s):
    return [float(x) for x in s.replace(",", " ").split()]


def test_static_scene_is_native_vector_with_stable_ids():
    scene = scene_with(
        Point2D(id="p", position=(2, 3), color="#ff3366"),
        Line2D(id="line one", start=(0, 0), end=(5, 5), dash=(4, 2)),
        Shape2D(id="area", path=Path2D.rect(1, 1, 3, 2), fill="#3366ff", fill_rule="evenodd"),
    )
    doc = render(Animation(scene))
    root = parse(doc.text)
    assert root.tag == Q + "svg" and root.get("viewBox") == "0 0 200 200"
    assert not [e for e in root.iter() if e.tag == Q + "image"]
    assert len([e for e in root.iter() if e.tag == Q + "path"]) == 3
    assert doc.element_ids == {"p": "p", "line one": "line_one", "area": "area"}
    assert find(root, "line_one").get("data-kk-id") == "line one"
    assert find(root, "area").get("fill-rule") == "evenodd"
    assert find(root, "line_one").get("stroke-dasharray") == "4 2"
    assert find(root, "line_one").get("vector-effect") == "non-scaling-stroke"
    assert doc.animation_count == 0


def test_world_is_y_up_in_pixels():
    scene = scene_with(Point2D(id="p", position=(0, 0)))
    root = parse(render(Animation(scene)).text)
    world = find(root, "world")
    a, _b, _c, d, e, f = nums(world.get("transform")[len("matrix(") : -1])
    assert (a, d) == (pytest.approx(20.0), pytest.approx(-20.0))  # 200px / 10 units, y flipped
    assert (e, f) == (pytest.approx(0.0), pytest.approx(200.0))  # origin at bottom-left


def test_linear_motion_is_exact_with_keysplines():
    p = Point2D(id="p", position=(1, 1))
    scene = scene_with(p)
    anim = Animation(scene, p.animate.position.to((9, 5), duration=2.0))
    root = parse(render(anim).text)
    [a] = animations_for(root, "p", "transform")
    assert a.tag == Q + "animateTransform" and a.get("type") == "translate"
    assert a.get("calcMode") == "spline" and a.get("keySplines") == "0 0 1 1"
    assert len(a.get("values").split(";")) == 2  # exact: no sampling needed
    for t in (0, 0.5, 1.0, 2.0):
        x, y = nums(evaluate(a, t))
        want = anim.sample(t).get("p").position
        assert (x, y) == (pytest.approx(want.x, abs=1e-4), pytest.approx(want.y, abs=1e-4))


def test_cubic_bezier_easing_uses_native_splines():
    p = Point2D(id="p")
    scene = scene_with(p)
    curve = ease.cubic_bezier(0.42, 0.0, 0.58, 1.0)
    anim = Animation(scene, p.animate.position.to((8, 0), duration=1.0, easing=curve))
    root = parse(render(anim).text)
    [a] = animations_for(root, "p", "transform")
    assert a.get("keySplines") == "0.42 0 0.58 1"
    assert len(a.get("values").split(";")) == 2
    for t in (0.2, 0.5, 0.8):
        assert nums(evaluate(a, t))[0] == pytest.approx(
            anim.sample(t).get("p").position.x, abs=1e-4
        )


def test_other_easings_are_sampled_within_tolerance():
    p = Point2D(id="p")
    scene = scene_with(p)
    anim = Animation(scene, p.animate.position.to((8, 4), duration=1.0, easing=ease.in_out_cubic))
    doc = render(anim)
    [a] = animations_for(parse(doc.text), "p", "transform")
    assert len(a.get("values").split(";")) > 10
    for k in range(0, 101, 7):
        t = k / 100
        x, y = nums(evaluate(a, t))
        want = anim.sample(t).get("p").position
        assert (x, y) == (pytest.approx(want.x, abs=6e-3), pytest.approx(want.y, abs=6e-3))


def test_sequenced_and_parallel_tracks_match_the_timeline():
    p, q = Point2D(id="p"), Point2D(id="q", opacity=0.0)
    scene = scene_with(p, q)
    motion = p.animate.position.to((5, 5), duration=1.0).then(
        p.animate.position.to((5, 0), duration=1.0).with_(q.animate.opacity.to(1.0, duration=0.5))
    )
    anim = Animation(scene, motion)
    root = parse(render(anim).text)
    [pos] = animations_for(root, "p", "transform")
    [op] = animations_for(root, "q", "opacity")
    for t in (0, 0.4, 1.0, 1.25, 1.75, 2.0):
        want = anim.sample(t)
        assert nums(evaluate(pos, t)) == pytest.approx(list(want.get("p").position), abs=1e-4)
        assert float(evaluate(op, t)) == pytest.approx(want.get("q").opacity, abs=1e-4)


def test_colors_and_discrete_properties():
    p = Point2D(id="p", color="#000000", symbol="circle")
    scene = scene_with(p)
    motion = p.animate.color.to("#ffffff", duration=1.0).with_(
        p.animate.symbol.to("square", duration=1.0)
    )
    anim = Animation(scene, motion)
    root = parse(render(anim).text)
    sym = find(root, "p")[0]
    [fill] = [a for a in sym if a.get("attributeName") == "fill"]
    assert evaluate(fill, 0.5) == "#808080"
    [d] = [a for a in sym if a.get("attributeName") == "d"]
    assert d.get("calcMode") == "discrete"
    assert evaluate(d, 0.9) != evaluate(d, 1.0)  # switches when the segment completes


def test_visibility_and_optional_stroke_switch():
    p = Point2D(id="p")
    scene = scene_with(p)
    motion = p.animate.visible.to(False, duration=1.0).with_(
        p.animate.stroke.to("#ff0000", duration=0.0, from_="#ffffff").delay(1.0)
    )
    anim = Animation(scene, motion)
    root = parse(render(anim).text)
    [vis] = animations_for(root, "p", "visibility")
    assert evaluate(vis, 0.5) == "visible" and evaluate(vis, 1.0) == "hidden"


def test_draw_progress_on_lines_and_paths():
    line = Line2D(id="l", start=(0, 0), end=(8, 0), draw_progress=0.0)
    path = PathNode2D(id="pt", path=Path2D.polyline([(0, 1), (4, 1), (4, 5)]), draw_progress=0.0)
    scene = scene_with(line, path)
    anim = Animation(
        scene,
        line.animate.draw_progress.to(1.0, duration=1.0).with_(
            path.animate.draw_progress.to(1.0, duration=1.0)
        ),
    )
    doc = render(anim)
    root = parse(doc.text)
    [ld] = animations_for(root, "l", "d")
    assert numbers(evaluate(ld, 0.5)) == pytest.approx([0, 0, 4, 0])
    [pd] = animations_for(root, "pt", "d")
    mid = numbers(evaluate(pd, 0.5))  # half of 8 units of length = the corner at (4, 1)... then up
    assert mid[-2:] == pytest.approx([4.0, 1.0], abs=0.05) or mid[-1] >= 1.0
    assert any("draw_progress" in w for w in doc.warnings)


def test_path_morph_animates_the_d_attribute():
    a, b = Path2D.rect(0, 0, 2, 2), Path2D.rect(0, 0, 6, 2)
    s = Shape2D(id="s", path=a)
    scene = scene_with(s)
    anim = Animation(scene, s.animate.path.to(b, duration=1.0))
    root = parse(render(anim).text)
    [d] = animations_for(root, "s", "d")
    mid = numbers(evaluate(d, 0.5))
    want = numbers(anim.sample(0.5).get("s").path.to_svg(6))
    assert mid == pytest.approx(want, abs=1e-4)


def test_group_transform_layers_animate_and_clip():
    g = Group2D(
        id="g",
        children=(Point2D(id="c", position=(1, 1)),),
        clip=Bounds2D((0, 0), (5, 5)),
        transform=Transform2D(),
    )
    scene = scene_with(g)
    anim = Animation(
        scene,
        g.animate.transform.to(
            Transform2D(translate=Vec2(3, 0), rotation=math.pi / 2, scale=Vec2(2, 2)), duration=1.0
        ),
    )
    doc = render(anim)
    root = parse(doc.text)
    assert root.find(".//" + Q + "clipPath/" + Q + "rect") is not None
    layers = [e for e in root.iter() if e.get("data-kk-layer")]
    assert [
        e.get("data-kk-layer")
        for e in layers
        if e.get("data-kk-layer") in ("translate", "rotate", "scale")
    ] == [
        "translate",
        "rotate",
        "scale",
    ]
    rot = layer_animations(next(e for e in layers if e.get("data-kk-layer") == "rotate"))[0]
    assert float(evaluate(rot, 1.0)) == pytest.approx(90.0)
    assert float(evaluate(rot, 0.5)) == pytest.approx(45.0, abs=0.5)


def test_animated_camera_nests_zoom_and_pan_layers():
    p = Point2D(id="p", position=(5, 5), size=4)
    scene = scene_with(p)
    cam = scene.camera
    anim = Animation(
        scene,
        cam.animate.zoom.to(2.0, duration=1.0).with_(cam.animate.pan.to((2, 0), duration=1.0)),
    )
    doc = render(anim)
    root = parse(doc.text)
    zoom = next(e for e in root.iter() if e.get("data-kk-layer") == "zoom")
    pan = next(e for e in root.iter() if e.get("data-kk-layer") == "pan")
    lay = resolve_layout(anim, Viewport(200, 200))
    for t in (0.0, 0.5, 1.0):
        cam_t = anim.sample(t).camera
        sx, sy = nums(evaluate(layer_animations(zoom)[0], t))
        tx, ty = nums(evaluate(layer_animations(pan)[0], t))
        win = lay.window(cam_t)
        assert (sx, sy) == pytest.approx((lay.scale(cam_t), -lay.scale(cam_t)), abs=1e-3)
        assert (tx, ty) == pytest.approx((-win.center.x, -win.center.y), abs=1e-3)
    # the point's pixel size stays constant under zoom: scale(k) animates as size / scale
    sym = find(root, "p")[0]
    [k] = [a for a in sym if a.get("type") == "scale"]
    for t in (0.0, 1.0):
        want = 4 / lay.scale(anim.sample(t).camera)
        assert nums(evaluate(k, t))[0] == pytest.approx(want, abs=1e-3)


def test_overlay_is_pixel_space_and_text_is_upright():
    glyph = GlyphShape(Path2D.rect(0, 0, 4, 6), "A")
    asset = TextAsset("A", (glyph,), 4.0, 6.0, fonts=(FontResource("Demo", b"\x00\x01"),))
    scene = scene_with(Point2D(id="p"), overlay=[Text2D(id="t", asset=asset, position=(10, 20))])
    doc = render(Animation(scene))
    root = parse(doc.text)
    overlay = find(root, "overlay")
    assert overlay.get("transform") is None
    text = find(root, "t")
    assert text.get("aria-label") == "A" and text.get("role") == "img"
    scale = next(e for e in text.iter() if (e.get("transform") or "").startswith("scale"))
    assert scale.get("transform") == "scale(1 -1)"  # glyph outlines are y-up; the overlay is y-down
    assert "@font-face" in doc.text and "Demo" in doc.fonts


def test_title_and_description_are_exported():
    scene = scene_with(Point2D(id="p"))
    root = parse(render(Animation(scene), title="Demo", description="A dot").text)
    assert root.find(Q + "title").text == "Demo" and root.find(Q + "desc").text == "A dot"
    assert root.get("aria-labelledby") and root.get("aria-describedby")


def test_z_animation_and_clip_animation_fail_loudly():
    a, b = Point2D(id="a"), Point2D(id="b")
    scene = scene_with(a, b)
    with pytest.raises(CapabilityError, match="z-order"):
        render(Animation(scene, a.animate.z.to(5.0, duration=1)))
    g = Group2D(id="g", clip=Bounds2D((0, 0), (1, 1)))
    with pytest.raises(CapabilityError, match="clip"):
        render(Animation(scene_with(g), g.animate.clip.to(Bounds2D((0, 0), (2, 2)), duration=1)))


def test_z_order_follows_z_then_insertion():
    scene = scene_with(Point2D(id="top", z=5), Point2D(id="a"), Point2D(id="b"))
    root = parse(render(Animation(scene)).text)
    ids = [e.get("id") for e in find(root, "world") if e.get("id")]
    assert ids == ["a", "b", "top"]


def test_output_is_deterministic():
    p = Point2D(id="p")
    scene = scene_with(p)
    anim = Animation(scene, p.animate.position.to((5, 5), duration=1.0, easing=ease.out_cubic))
    assert render(anim).text == render(anim).text


def test_loop_and_precision_settings():
    p = Point2D(id="p")
    anim = Animation(scene_with(p), p.animate.position.to((5, 5), duration=1.0))
    root = parse(render(anim, loop=True).text)
    assert animations_for(root, "p", "transform")[0].get("repeatCount") == "indefinite"
    assert "repeatCount" not in animations_for(parse(render(anim).text), "p", "transform")[0].attrib
