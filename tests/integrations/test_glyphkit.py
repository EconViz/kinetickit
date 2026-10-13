from __future__ import annotations

import base64
import subprocess
import sys
import textwrap
from io import BytesIO
from pathlib import Path

import pytest

glyphkit = pytest.importorskip("glyphkit")
fontbuilder = pytest.importorskip("fontTools.fontBuilder")

from fontTools.fontBuilder import FontBuilder  # noqa: E402
from fontTools.pens.ttGlyphPen import TTGlyphPen  # noqa: E402
from glyphkit import FontLibrary, FontSource  # noqa: E402

from kinetickit.animation import Animation  # noqa: E402
from kinetickit.errors import ConfigurationError  # noqa: E402
from kinetickit.geometry.two_d import Bounds2D  # noqa: E402
from kinetickit.guides import Axis2D  # noqa: E402
from kinetickit.integrations.glyphkit import (  # noqa: E402
    GlyphKitTypography,
    text_asset_from_layout,
)
from kinetickit.layout import Viewport, resolve_layout  # noqa: E402
from kinetickit.scene import Point2D, Scene2D, Text2D  # noqa: E402
from kinetickit.typography import TextAssetLike, TypographyEngine  # noqa: E402


def make_font(family="KK Test", fs_type=0) -> bytes:
    """A deterministic caller-provided font: glyphs A, B, digits as triangles."""
    chars = "AB0123456789.- "
    names = [".notdef"] + [f"uni{ord(c):04X}" for c in chars]
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder(names)
    fb.setupCharacterMap({ord(c): f"uni{ord(c):04X}" for c in chars})
    glyphs = {}
    for name in names:
        pen = TTGlyphPen(None)
        if name not in ("uni0020",):
            pen.moveTo((50, 0))
            pen.lineTo((300, 700))
            pen.lineTo((550, 0))
            pen.closePath()
        glyphs[name] = pen.glyph()
    fb.setupGlyf(glyphs)
    fb.setupHorizontalMetrics({n: (600 if n != "uni0020" else 300, 0) for n in names})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable(
        {
            "familyName": family,
            "styleName": "Regular",
            "uniqueFontIdentifier": family,
            "fullName": family,
            "psName": family.replace(" ", ""),
        }
    )
    fb.setupOS2(
        fsType=fs_type,
        sTypoAscender=800,
        sTypoDescender=-200,
        usWinAscent=800,
        usWinDescent=200,
        usWeightClass=400,
    )
    fb.setupPost()
    fb.setupMaxp()
    out = BytesIO()
    fb.save(out)
    return out.getvalue()


@pytest.fixture(scope="module")
def library():
    return FontLibrary.from_sources((FontSource.bytes(make_font(), label="caller-font"),))


def test_engine_satisfies_both_independent_ports(library):
    typography = GlyphKitTypography(library, families=("KK Test",), size=20)
    assert isinstance(typography, TypographyEngine)
    assert isinstance(typography.asset("AB"), TextAssetLike)


def test_layout_becomes_a_neutral_asset_with_exact_geometry(library):
    asset = GlyphKitTypography(library, families=("KK Test",), size=20).asset("AB A")
    assert asset.text == "AB A"
    assert len(asset.glyphs) == 3  # the space has no outline
    first = asset.glyphs[0]
    assert first.character == "A"
    b = first.outline.bounds()
    assert (b.min.x, b.min.y, b.max.x, b.max.y) == pytest.approx((0.0, 0.0, 10.0, 14.0))
    second = asset.glyphs[1].outline.bounds()
    assert second.min.x == pytest.approx(12.0)  # the pen advanced by one 12px glyph
    assert asset.width == pytest.approx(42.0) and asset.height == pytest.approx(20.0)


def test_multi_line_layout_keeps_y_up_baselines(library):
    typography = GlyphKitTypography(library, families=("KK Test",), size=20, max_width=30)
    asset = typography.asset("AB AB AB")
    tops = sorted({round(g.outline.bounds().max.y, 3) for g in asset.glyphs}, reverse=True)
    assert tops == pytest.approx([14.0, -10.0, -34.0])  # each line one 24px step lower


def test_caller_fonts_are_embedded_as_subsets(library):
    asset = GlyphKitTypography(library, families=("KK Test",), size=16).asset("AB")
    assert asset.fonts and asset.fonts[0].family == "KK Test"
    assert asset.fonts[0].data[:4] in (b"\x00\x01\x00\x00", b"OTTO", b"true")
    none = GlyphKitTypography(library, families=("KK Test",), size=16, embed=False).asset("AB")
    assert none.fonts == ()


def test_fonts_survive_the_full_export_pipeline(library):
    typography = GlyphKitTypography(library, families=("KK Test",), size=16)
    text = Text2D(id="label", asset=typography.asset("AB"), position=(1, 1))
    scene = Scene2D(text)
    scene = scene.bind({scene.camera.ref("view"): Bounds2D((0, 0), (40, 20))})
    anim = Animation(scene, text.animate.position.to((10, 5), duration=1.0))
    svg = anim.to_svg(width=300, height=150)
    assert "@font-face" in svg and 'font-family:"KK Test"' in svg
    embedded = text.asset.fonts[0].data
    assert base64.b64encode(embedded).decode() in svg
    assert 'aria-label="AB"' in svg


def test_axis_labels_use_the_glyphkit_provider(library):
    typography = GlyphKitTypography(library, families=("KK Test",), size=12)
    scene = Scene2D(Point2D(id="p"), Point2D(id="q", position=(10, 5)))
    lay = resolve_layout(Animation(scene), Viewport(300, 200))
    axis = Axis2D("x", "x", (0, 10)).compile(lay, text=typography, labels=True)
    assert [c for c in axis.children if c.id.startswith("x.label")]


def test_restricted_fonts_are_never_silently_embedded():
    restricted = FontLibrary.from_sources(
        (FontSource.bytes(make_font("KK Locked", fs_type=0x0002), label="locked"),)
    )
    typography = GlyphKitTypography(restricted, families=("KK Locked",), size=16)
    with pytest.raises(glyphkit.EmbeddingRestrictedError):
        typography.asset("A")
    assert typography.__class__(restricted, families=("KK Locked",), embed=False).asset("A").glyphs


def test_requires_families():
    with pytest.raises(ConfigurationError):
        GlyphKitTypography(object(), families=())  # type: ignore[arg-type]


def test_conversion_uses_only_public_glyphkit_data(library):
    layout = library.layout(
        glyphkit.Paragraph((glyphkit.TextSpan("A", glyphkit.TextStyle(("KK Test",), 10)),))
    )
    asset = text_asset_from_layout(library, layout, embed=False)
    assert asset.glyphs[0].outline.bounds().max.y == pytest.approx(7.0)


def test_glyphkit_never_imports_kinetickit_and_kinetickit_core_never_needs_glyphkit():
    code = textwrap.dedent(
        """
        import sys
        import glyphkit, glyphkit.math, glyphkit.embedding
        assert not [m for m in sys.modules if m.split('.')[0] == 'kinetickit'], 'glyphkit imported kinetickit'
        for m in list(sys.modules):
            if m.split('.')[0] in ('glyphkit',):
                del sys.modules[m]
        sys.modules['glyphkit'] = None
        import kinetickit, kinetickit.typography, kinetickit.scene, kinetickit.exporters
        """
    )
    result = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_integration_imports_only_documented_glyphkit_modules():
    import ast

    src = Path(__file__).resolve().parents[2] / "src/kinetickit/integrations/glyphkit.py"
    modules = {
        n.module
        for n in ast.walk(ast.parse(src.read_text()))
        if isinstance(n, ast.ImportFrom) and n.module and n.module.split(".")[0] == "glyphkit"
    }
    assert modules <= {"glyphkit", "glyphkit.embedding", "glyphkit.math", "glyphkit.outlines"}
