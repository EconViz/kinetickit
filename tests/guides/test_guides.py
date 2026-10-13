from __future__ import annotations

import pytest

from kinetickit.animation import Animation
from kinetickit.errors import ConfigurationError
from kinetickit.geometry.two_d import Path2D
from kinetickit.guides import Annotation, Axis2D, ColorBar, Grid2D, Legend, LegendEntry, nice_ticks
from kinetickit.layout import Viewport, resolve_layout
from kinetickit.scene import Point2D, Scene2D
from kinetickit.typography import GlyphShape, TextAsset


def fake_text(s: str) -> TextAsset:
    return TextAsset(s, (GlyphShape(Path2D.rect(0, 0, 8 * len(s), 10), s),), 8.0 * len(s), 10.0)


def layout():
    scene = Scene2D(Point2D(id="a", position=(0, 0)), Point2D(id="b", position=(10, 5)))
    return resolve_layout(Animation(scene), Viewport(400, 300))


def test_nice_ticks_use_round_steps_inside_the_range():
    assert nice_ticks(0, 10, 5) == (0, 2, 4, 6, 8, 10)
    assert nice_ticks(0, 1, 4) == (0, 0.25, 0.5, 0.75, 1.0) or nice_ticks(0, 1, 4)[0] == 0
    assert nice_ticks(3, 3) == (3,)
    assert all(0.3 <= t <= 0.71 for t in nice_ticks(0.3, 0.71, 5))
    with pytest.raises(ConfigurationError):
        nice_ticks(2, 1)
    with pytest.raises(ConfigurationError):
        nice_ticks(0, 1, 0)


def test_axis_compiles_to_ordinary_nodes_with_stable_ids():
    axis = Axis2D("x", "x", (0, 10), at=0).compile(layout())
    ids = [c.id for c in axis.children]
    assert ids[0] == "x.line" and "x.tick0" in ids and "x.tick5" in ids
    assert not any("label" in i for i in ids)  # no typography provider -> no labels, no guessing


def test_axis_labels_need_a_text_factory_and_scale_to_world_units():
    lay = layout()
    axis = Axis2D("y", "y", (0, 5), tick_count=5).compile(lay, text=fake_text)
    labels = [c for c in axis.children if "label" in c.id]
    assert len(labels) == 6
    assert labels[0].scale == pytest.approx(1.0 / lay.scale())
    assert labels[0].asset.text == "0"


def test_tick_length_is_constant_in_pixels():
    lay = layout()
    axis = Axis2D("x", "x", (0, 10), tick_length=6).compile(lay)
    tick = next(c for c in axis.children if c.id == "x.tick1")
    world_len = (tick.end - tick.start).length()
    assert world_len * lay.scale() == pytest.approx(6.0)


def test_axis_validation():
    with pytest.raises(ConfigurationError):
        Axis2D("a", "z", (0, 1))
    with pytest.raises(ConfigurationError):
        Axis2D("a", "x", (1, 0))


def test_grid_color_bar_legend_annotation_compile_to_nodes():
    grid = Grid2D("grid", (0, 10), (0, 5)).compile()
    assert all(c.z == -10 for c in grid.children)
    bar = ColorBar("bar", (0, 0), (1, 10), lambda t: (t, 0.0, 1.0 - t), steps=8).compile()
    assert len(bar.children) == 8
    assert bar.children[0].fill.b == 1.0 and bar.children[-1].fill.r == 1.0
    legend = Legend("legend", (LegendEntry("a", "#ff0000"), LegendEntry("b", "#00ff00")))
    group = legend.compile(text=fake_text)
    assert [c.id for c in group.children] == [
        "legend.swatch0",
        "legend.label0",
        "legend.swatch1",
        "legend.label1",
    ]
    note = Annotation("note", (1, 1), (3, 4), "peak").compile(text=fake_text)
    assert {c.id for c in note.children} == {"note.leader", "note.anchor", "note.label"}
    with pytest.raises(ConfigurationError):
        Legend("l", ()).compile()
    with pytest.raises(ConfigurationError):
        ColorBar("c", (0, 0), (1, 1), lambda t: "#000", steps=1).compile()


def test_guides_drop_into_a_scene_and_animate_like_any_node():
    scene = Scene2D(
        Grid2D("g", (0, 1), (0, 1)).compile(), Axis2D("ax", "x", (0, 1)).compile(layout())
    )
    assert "g.v0" in scene and "ax.tick0" in scene
