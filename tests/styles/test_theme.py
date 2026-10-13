from __future__ import annotations

import pytest

from kinetickit.errors import ConfigurationError
from kinetickit.interpolation import Color
from kinetickit.scene import Line2D, Shape2D
from kinetickit.styles import Fill, MinimalTheme, Stroke


def test_sparse_theme_merge_keeps_other_tokens():
    custom = MinimalTheme.merge(marker="#00ff00", font_size=18)
    assert custom.marker == Color.parse("#00ff00") and custom.font_size == 18
    assert custom.background == MinimalTheme.background
    assert MinimalTheme.marker != custom.marker  # original untouched


def test_unknown_tokens_rejected():
    with pytest.raises(ConfigurationError, match="unknown theme tokens"):
        MinimalTheme.merge(nonsense=1)


def test_theme_has_no_domain_roles():
    names = {f for f in MinimalTheme.__dataclass_fields__}
    assert not names & {"supply", "demand", "profit", "revenue"}


def test_stroke_and_fill_expand_into_node_properties():
    line = Line2D(id="l", **Stroke("#ff0000", 3, cap="butt", dash=(2, 1)).line_props())
    assert line.color.to_hex() == "#ff0000" and line.width == 3 and line.dash == (2.0, 1.0)
    shape = Shape2D(id="s", **Fill("#00ff00", "evenodd").props(), **Stroke(width=1).shape_props())
    assert shape.fill_rule == "evenodd" and shape.stroke_width == 1.0
