"""Typography ports and the neutral text-asset contract."""

from __future__ import annotations

from kinetickit.typography.asset import FontResource, GlyphShape, TextAsset, TextAssetLike
from kinetickit.typography.errors import TypographyUnavailableError
from kinetickit.typography.provider import TextFactory, TypographyEngine, require_text_factory

__all__ = [
    "FontResource",
    "GlyphShape",
    "TextAsset",
    "TextAssetLike",
    "TextFactory",
    "TypographyEngine",
    "TypographyUnavailableError",
    "require_text_factory",
]
