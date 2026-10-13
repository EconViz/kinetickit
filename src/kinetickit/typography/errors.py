"""Typography errors."""

from __future__ import annotations

from kinetickit.errors import ConfigurationError


class TypographyUnavailableError(ConfigurationError):
    """Text was requested but no typography provider is configured.

    KineticKit never substitutes fonts or guesses glyph shapes: pass a provider (for example the
    included GlyphKit adapter) or a ready-made text asset.
    """
