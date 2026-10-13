"""Caller-provided fonts: GlyphKit lays text out, KineticKit animates and embeds it.

Requires the optional GlyphKit package. Pass your own font bytes via ``font_bytes``.
"""

from __future__ import annotations

from pathlib import Path

from kinetickit.animation import Animation
from kinetickit.geometry.two_d import Bounds2D, Vec2
from kinetickit.scene import Scene2D, Text2D


def main(out: Path, font_bytes: bytes | None = None) -> dict[str, Path]:
    from glyphkit import FontLibrary, FontSource

    from kinetickit.integrations.glyphkit import GlyphKitTypography

    if font_bytes is None:
        from _demo_font import make_demo_font

        font_bytes = make_demo_font()
    out.mkdir(parents=True, exist_ok=True)
    library = FontLibrary.from_sources((FontSource.bytes(font_bytes, label="caller-font"),))
    typography = GlyphKitTypography(library, families=("Demo Sans",), size=48)
    title = Text2D(id="title", asset=typography.asset("HELLO 2"), position=Vec2(1, 1), scale=0.05)
    scene = Scene2D(title)
    scene = scene.bind({scene.camera.ref("view"): Bounds2D(Vec2(0, 0), Vec2(10, 6))})
    animation = Animation(scene, title.animate.position.to(Vec2(4, 3), duration=1.5))
    files = {"svg": out / "text.svg", "html": out / "text.html"}
    animation.save(files["svg"], width=480, height=290)
    animation.save(files["html"], width=480, height=330)
    return files


if __name__ == "__main__":
    print(main(Path("out")))
