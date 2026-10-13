"""The port through which KineticKit obtains text assets."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, runtime_checkable

from kinetickit.typography.asset import TextAssetLike
from kinetickit.typography.errors import TypographyUnavailableError

TextFactory = Callable[[str], TextAssetLike]
"""Turns a string into a laid-out text asset measured in logical pixels."""


@runtime_checkable
class TypographyEngine(Protocol):
    """Anything that can lay out a string into an immutable text asset.

    KineticKit core ships no implementation; font loading, shaping and measurement belong to the
    provider (GlyphKit, or any engine a consumer wires in).
    """

    def asset(self, text: str) -> TextAssetLike: ...


def require_text_factory(
    provider: TypographyEngine | TextFactory | None, purpose: str = "text"
) -> TextFactory:
    """Return a text factory or fail explicitly when none was configured."""
    if provider is None:
        raise TypographyUnavailableError(
            f"{purpose} needs a typography provider; pass text=<TypographyEngine or factory>. "
            "KineticKit does not choose or substitute fonts."
        )
    if isinstance(provider, TypographyEngine):
        return provider.asset
    return provider
