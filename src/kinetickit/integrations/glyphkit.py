"""Adapter from GlyphKit layouts to KineticKit text assets.

Requires GlyphKit to be installed separately (it is intentionally not a KineticKit dependency
or extra). GlyphKit owns font loading, shaping,
layout, outlines and subsets; this module only translates its public, immutable data into a
neutral :class:`~kinetickit.typography.TextAsset`. GlyphKit never imports KineticKit, and
KineticKit core never imports GlyphKit.

Coordinates: GlyphKit layouts are y-up with the first baseline at ``y = 0``; the asset keeps them
unchanged, in the same units as the style ``size`` (logical pixels when used for scene text).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from glyphkit import Paragraph, TextLayout, TextSpan, TextStyle, TypographyEngine
from glyphkit.embedding import EmbeddingUse, FontContainer
from glyphkit.math import MathBox, MathStyle, parse_math
from glyphkit.outlines import ClosePath, CubicTo, LineTo, MoveTo, QuadraticTo

from kinetickit.errors import ConfigurationError
from kinetickit.geometry.two_d import Path2D, PathCommand, Vec2
from kinetickit.typography import FontResource, GlyphShape, TextAsset

__all__ = ["GlyphKitTypography", "text_asset_from_layout", "text_asset_from_math"]


def _outline_path(commands: Sequence[Any], scale: float, dx: float, dy: float) -> Path2D | None:
    def pt(p: tuple[float, float]) -> Vec2:
        return Vec2(p[0] * scale + dx, p[1] * scale + dy)

    out: list[PathCommand] = []
    for c in commands:
        if isinstance(c, MoveTo):
            out.append(PathCommand("M", (pt(c.point),)))
        elif isinstance(c, LineTo):
            out.append(PathCommand("L", (pt(c.point),)))
        elif isinstance(c, QuadraticTo):
            out.append(PathCommand("Q", (pt(c.control), pt(c.point))))
        elif isinstance(c, CubicTo):
            out.append(PathCommand("C", (pt(c.control1), pt(c.control2), pt(c.point))))
        elif isinstance(c, ClosePath):
            out.append(PathCommand("Z"))
        else:  # pragma: no cover - defensive against future GlyphKit command types
            raise ConfigurationError(f"unsupported GlyphKit path command {type(c).__name__}")
    return Path2D(tuple(out)) if out else None


class _Collector:
    def __init__(self, engine: TypographyEngine) -> None:
        self.engine = engine
        self.glyphs: list[GlyphShape] = []
        self._cache: dict[tuple[Any, int, float, tuple[Any, ...]], Any] = {}

    def layout(self, layout: TextLayout, ox: float = 0.0, oy: float = 0.0) -> None:
        for line in layout.lines:
            for run in line.runs:
                for g in run.glyphs:
                    key = (g.face_id, g.glyph_id, run.size, g.variation_coordinates)
                    outline = self._cache.get(key)
                    if outline is None:
                        outline = self.engine.outline(g)
                        self._cache[key] = outline
                    scale = run.size / outline.units_per_em
                    path = _outline_path(outline.commands, scale, g.x + ox, g.y + oy)
                    if path is None:
                        continue  # whitespace and other empty glyphs draw nothing
                    char = layout.text[g.cluster.start : g.cluster.end]
                    self.glyphs.append(GlyphShape(path, char, g.cluster.start))


def _fonts(
    engine: TypographyEngine,
    layouts: Sequence[TextLayout],
    use: EmbeddingUse,
    container: FontContainer,
    allow_unknown: bool,
) -> tuple[FontResource, ...]:
    seen: dict[tuple[str, str], FontResource] = {}
    for layout in layouts:
        bundle = engine.subset(
            layout, embedding_use=use, container=container, allow_unknown=allow_unknown
        )
        for f in bundle.fonts:
            if container is FontContainer.WOFF2:
                fmt = "woff2"
            else:
                fmt = "opentype" if f.data[:4] == b"OTTO" else "truetype"
            seen[(f.family, f.subset_tag)] = FontResource(f.family, f.data, fmt)
    return tuple(seen.values())


def text_asset_from_layout(
    engine: TypographyEngine,
    layout: TextLayout,
    *,
    embed: bool = True,
    embedding_use: EmbeddingUse = EmbeddingUse.WEB,
    container: FontContainer = FontContainer.SFNT,
    allow_unknown: bool = False,
) -> TextAsset:
    """Convert a GlyphKit :class:`TextLayout` into a neutral text asset.

    ``embed=True`` also attaches permission-checked font subsets so SVG/HTML exports keep the
    caller's fonts; a restricted font raises GlyphKit's own error rather than being skipped.
    """
    collector = _Collector(engine)
    collector.layout(layout)
    fonts = _fonts(engine, [layout], embedding_use, container, allow_unknown) if embed else ()
    b = layout.logical_bounds
    return TextAsset(layout.text, tuple(collector.glyphs), b.width, b.height, fonts)


def _walk_math(
    box: MathBox, collector: _Collector, layouts: list[TextLayout], ox: float, oy: float
) -> list[GlyphShape]:
    x, y = ox + box.origin[0], oy + box.origin[1]
    rules: list[GlyphShape] = []
    if box.text_layout is not None:
        collector.layout(box.text_layout, x, y)
        layouts.append(box.text_layout)
    elif box.glyph_id is not None:
        raise ConfigurationError("math box has a glyph but no text layout; cannot extract outline")
    for rule in box.rules:
        (x0, y0), (x1, y1) = (
            (x + rule.start[0], y + rule.start[1]),
            (x + rule.end[0], y + rule.end[1]),
        )
        h = rule.thickness / 2.0
        if abs(y1 - y0) <= abs(x1 - x0):  # horizontal bar
            quad = [
                (min(x0, x1), y0 - h),
                (max(x0, x1), y0 - h),
                (max(x0, x1), y0 + h),
                (min(x0, x1), y0 + h),
            ]
        else:  # vertical bar
            quad = [
                (x0 - h, min(y0, y1)),
                (x0 + h, min(y0, y1)),
                (x0 + h, max(y0, y1)),
                (x0 - h, max(y0, y1)),
            ]
        rules.append(GlyphShape(Path2D.polygon(quad), "", -1))
    for child in box.children:
        rules.extend(_walk_math(child, collector, layouts, x, y))
    return rules


def text_asset_from_math(
    engine: TypographyEngine,
    latex: str,
    *,
    families: Sequence[str],
    size: float,
    level: str = "display",
    embed: bool = True,
    embedding_use: EmbeddingUse = EmbeddingUse.WEB,
    allow_unknown: bool = False,
) -> TextAsset:
    """Typeset a math expression with GlyphKit and return it as a text asset."""
    box = engine.layout_math(
        parse_math(latex), style=MathStyle(size=size, families=tuple(families), level=level)
    )
    collector = _Collector(engine)
    layouts: list[TextLayout] = []
    rules = _walk_math(box, collector, layouts, 0.0, 0.0)
    fonts = (
        _fonts(engine, layouts, embedding_use, FontContainer.SFNT, allow_unknown) if embed else ()
    )
    b = box.bounds
    return TextAsset(latex, tuple(collector.glyphs + rules), b.width, b.height, fonts)


class GlyphKitTypography:
    """A :class:`kinetickit.typography.TypographyEngine` backed by a GlyphKit engine.

    >>> typography = GlyphKitTypography(library, families=("Source Sans 3",), size=14)
    >>> Axis2D(...).compile(layout, text=typography, labels=True)
    """

    def __init__(
        self,
        engine: TypographyEngine,
        *,
        families: Sequence[str],
        size: float = 14.0,
        weight: int = 400,
        slant: str = "normal",
        max_width: float | None = None,
        embed: bool = True,
        embedding_use: EmbeddingUse = EmbeddingUse.WEB,
        allow_unknown: bool = False,
    ) -> None:
        if not families:
            raise ConfigurationError("GlyphKitTypography needs at least one font family")
        self.engine = engine
        self.families = tuple(families)
        self.size = size
        self.weight = weight
        self.slant = slant
        self.max_width = max_width
        self.embed = embed
        self.embedding_use = embedding_use
        self.allow_unknown = allow_unknown

    def layout(self, text: str, **style: Any) -> TextLayout:
        params: dict[str, Any] = {
            "families": self.families,
            "size": self.size,
            "weight": self.weight,
            "slant": self.slant,
        } | style
        return self.engine.layout(
            Paragraph((TextSpan(text, TextStyle(**params)),), max_width=self.max_width)
        )

    def asset(self, text: str, **style: Any) -> TextAsset:
        return text_asset_from_layout(
            self.engine,
            self.layout(text, **style),
            embed=self.embed,
            embedding_use=self.embedding_use,
            allow_unknown=self.allow_unknown,
        )

    def math(self, latex: str, **options: Any) -> TextAsset:
        return text_asset_from_math(
            self.engine,
            latex,
            families=options.pop("families", self.families),
            size=options.pop("size", self.size),
            embed=self.embed,
            embedding_use=self.embedding_use,
            allow_unknown=self.allow_unknown,
            **options,
        )

    __call__ = asset
