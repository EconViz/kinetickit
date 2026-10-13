from __future__ import annotations

import pytest
from tests.support.smil import Q, animations_for, evaluate, numbers, parse

from kinetickit import ease
from kinetickit.animation import Animation
from kinetickit.errors import ConfigurationError
from kinetickit.geometry.two_d import Bounds2D, Path2D
from kinetickit.guides import Annotation, Axis2D, Legend, LegendEntry
from kinetickit.layout import Viewport, resolve_layout
from kinetickit.scene import Point2D, Scene2D, Text2D
from kinetickit.typography import (
    FontResource,
    GlyphShape,
    TextAsset,
    TextAssetLike,
    TypographyEngine,
    TypographyUnavailableError,
    require_text_factory,
)


def asset(text="Hi", w=12.0):
    return TextAsset(
        text,
        (GlyphShape(Path2D.rect(0, 0, w, 10), text[0], 0),),
        w,
        10.0,
        (FontResource("Demo", b"font-bytes"),),
    )


class Engine:
    def asset(self, text):
        return asset(text)


def test_text_asset_is_an_immutable_neutral_value():
    a = asset()
    assert isinstance(a, TextAssetLike)
    with pytest.raises(AttributeError):
        a.text = "changed"  # type: ignore[misc]
    with pytest.raises(ConfigurationError):
        TextAsset("x", (), -1.0, 1.0)
    with pytest.raises(ConfigurationError):
        FontResource("", b"x")
    with pytest.raises(ConfigurationError):
        FontResource("F", b"x", format="exe")


def test_a_missing_provider_fails_explicitly_never_silently():
    with pytest.raises(TypographyUnavailableError, match="does not choose or substitute fonts"):
        require_text_factory(None, "axis labels")
    assert issubclass(TypographyUnavailableError, ConfigurationError)
    assert isinstance(Engine(), TypographyEngine)
    assert require_text_factory(Engine())("A").text == "A"
    assert require_text_factory(lambda s: asset(s))("B").text == "B"


def test_guides_that_need_text_fail_without_a_provider():
    scene = Scene2D(Point2D(id="p"), Point2D(id="q", position=(5, 5)))
    lay = resolve_layout(Animation(scene), Viewport(200, 200))
    with pytest.raises(TypographyUnavailableError):
        Axis2D("x", "x", (0, 5)).compile(lay, labels=True)
    with pytest.raises(TypographyUnavailableError):
        Legend("l", (LegendEntry("a", "#f00"),)).compile()
    with pytest.raises(TypographyUnavailableError):
        Annotation("n", (1, 1), (2, 2), "peak").compile()
    # explicit opt-outs and ready providers work
    assert Legend("l", (LegendEntry("a", "#f00"),)).compile(labels=False).children
    assert Axis2D("x", "x", (0, 5)).compile(lay, text=Engine(), labels=True).children
    assert Annotation("n", (1, 1), (2, 2)).compile().children


def test_text_assets_animate_as_whole_objects_in_svg_and_gif():
    t = Text2D(id="t", asset=asset("Hi"), position=(1, 1), color="#000000")
    scene = Scene2D(t)
    scene = scene.bind({scene.camera.ref("view"): Bounds2D((0, 0), (10, 10))})
    motion = (
        t.animate.position.to((6, 6), duration=1.0, easing=ease.linear)
        .with_(t.animate.rotation.to(1.0, duration=1.0))
        .with_(t.animate.scale.to(2.0, duration=1.0))
        .with_(t.animate.color.to("#ff0000", duration=1.0))
        .with_(t.animate.opacity.to(0.5, duration=1.0))
    )
    anim = Animation(scene, motion)
    mid = anim.sample(0.5).get("t")
    assert mid.position.x == pytest.approx(3.5) and mid.rotation == pytest.approx(0.5)
    assert mid.scale == pytest.approx(1.5) and mid.opacity == pytest.approx(0.75)
    root = parse(anim.to_svg(width=200, height=200))
    node = next(e for e in root.iter() if e.get("id") == "t")
    layers = [e for e in node.iter() if e.get(f"{Q}x") is None]
    pos = next(a for e in layers for a in e if a.get("type") == "translate")
    assert numbers(evaluate(pos, 0.5)) == pytest.approx([3.5, 3.5], abs=1e-4)
    rot = next(a for e in layers for a in e if a.get("type") == "rotate")
    assert float(evaluate(rot, 1.0)) == pytest.approx(57.2958, abs=1e-3)
    fill = next(a for a in node if a.get("attributeName") == "fill")
    assert evaluate(fill, 1.0) == "#ff0000"
    assert animations_for(root, "t", "opacity")
    pytest.importorskip("PIL")
    pytest.importorskip("matplotlib")
    import io

    from PIL import Image

    gif = Image.open(io.BytesIO(anim.to_bytes("gif", width=100, height=100, fps=4)))
    assert gif.n_frames == 4


def test_fonts_survive_svg_export():
    t = Text2D(id="t", asset=asset("Hi"))
    scene = Scene2D(t)
    svg = Animation(scene).to_svg(width=100, height=100)
    assert "@font-face" in svg and "Demo" in svg
    assert "font-bytes" not in svg  # embedded as base64, not raw
    import base64

    assert base64.b64encode(b"font-bytes").decode() in svg
    bare = Animation(scene).to_svg(width=100, height=100, embed_fonts=False)
    assert "@font-face" not in bare
