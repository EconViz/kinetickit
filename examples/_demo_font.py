"""Builds a tiny deterministic font so the external-font example needs no font files."""

from __future__ import annotations

from io import BytesIO


def make_demo_font(family: str = "Demo Sans") -> bytes:
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.ttGlyphPen import TTGlyphPen

    chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 ."
    names = [".notdef"] + [f"uni{ord(c):04X}" for c in chars]
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder(names)
    fb.setupCharacterMap({ord(c): f"uni{ord(c):04X}" for c in chars})
    glyphs = {}
    for name in names:
        pen = TTGlyphPen(None)
        if name != "uni0020":
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
        fsType=0,
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
