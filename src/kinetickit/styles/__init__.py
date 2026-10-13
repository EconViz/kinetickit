"""Style values and the built-in ``minimal`` theme."""

from __future__ import annotations

from kinetickit.interpolation import DEFAULT_REGISTRY, Color
from kinetickit.styles.material import ColorScale, Material, MaterialInterpolator
from kinetickit.styles.style import Fill, Stroke
from kinetickit.styles.theme import MinimalTheme, Theme

DEFAULT_REGISTRY.register(Material, MaterialInterpolator())

__all__ = ["Color", "ColorScale", "Fill", "Material", "MinimalTheme", "Stroke", "Theme"]
