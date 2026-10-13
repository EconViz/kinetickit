from __future__ import annotations

import numpy as np
import pytest

from kinetickit.animation import Animation
from kinetickit.errors import CapabilityError, ConfigurationError
from kinetickit.geometry.two_d import Bounds2D, Path2D, Transform2D, Vec2
from kinetickit.renderers import get_renderer
from kinetickit.renderers.raster import MAX_DPI, RasterSettings, RenderedFrame
from kinetickit.scene import Group2D, Line2D, Point2D, Scene2D, Shape2D

pytest.importorskip("matplotlib")
VIEW = Bounds2D((0, 0), (10, 10))


def scene_with(*nodes, overlay=()):
    s = Scene2D(*nodes, overlay=overlay)
    return s.bind({s.camera.ref("view"): VIEW})


def render(scene, **kw):
    r = get_renderer("raster")
    st = RasterSettings(width=100, height=100, **kw)
    layout = r.layout_for(Animation(scene), st)
    return r.render_frame(scene, layout, st)


def px(frame, x, y):
    """RGBA at a world point (the view is 0..10 over 100 logical px, y up)."""
    s = frame.width / 10
    return tuple(int(v) for v in frame.pixels[int(frame.height - y * s), int(x * s)])


def test_settings_resolution_and_validation():
    assert RasterSettings(width=100, height=50, dpi=96).resolve().pixel_width == 100
    r = RasterSettings(width=100, height=50, dpi=192).resolve()
    assert (r.pixel_width, r.pixel_height) == (200, 100)
    inch = RasterSettings(size_inches=(2, 1), dpi=300).resolve()
    assert (inch.pixel_width, inch.pixel_height) == (600, 300)
    assert inch.logical_width == pytest.approx(192)
    exact = RasterSettings(pixels=(333, 222), dpi=96).resolve()
    assert (exact.pixel_width, exact.pixel_height) == (333, 222)
    assert RasterSettings(dpi=MAX_DPI).dpi == 1200
    for bad in (0, 1201, 1.5, True):
        with pytest.raises(ConfigurationError):
            RasterSettings(dpi=bad)
    with pytest.raises(ConfigurationError):
        RasterSettings(size_inches=(1, 1), pixels=(10, 10))
    with pytest.raises(ConfigurationError):
        RasterSettings(pixels=(0, 10))


def test_frame_is_rgba_with_the_requested_dimensions():
    frame = render(scene_with(Point2D(id="p", position=(5, 5), size=10)), dpi=192)
    assert isinstance(frame, RenderedFrame)
    assert frame.pixels.shape == (200, 200, 4) and frame.pixels.dtype == np.uint8


def test_point_is_drawn_at_its_world_position_y_up():
    frame = render(scene_with(Point2D(id="p", position=(2, 8), size=8, color="#ff0000")))
    assert px(frame, 2, 8)[:3] == (255, 0, 0)
    assert px(frame, 8, 2)[:3] == (255, 255, 255)
    assert px(frame, 2, 2)[:3] == (255, 255, 255)


def test_shapes_fill_rules_and_holes():
    outer = [(1, 1), (9, 1), (9, 9), (1, 9)]
    inner = [(3, 3), (7, 3), (7, 7), (3, 7)]
    holed = Shape2D(id="s", path=Path2D.polygon(outer, inner), fill="#0000ff", fill_rule="evenodd")
    frame = render(scene_with(holed))
    assert px(frame, 2, 2)[:3] == (0, 0, 255)
    assert px(frame, 5, 5)[:3] == (255, 255, 255)  # the hole
    same_dir = Shape2D(id="s", path=Path2D.polygon(outer, inner), fill="#0000ff")
    assert px(render(scene_with(same_dir)), 5, 5)[:3] == (0, 0, 255)  # nonzero fills it


def test_lines_support_draw_progress_and_opacity():
    line = Line2D(id="l", start=(1, 5), end=(9, 5), width=6, color="#000000", draw_progress=0.5)
    frame = render(scene_with(line))
    assert px(frame, 2, 5)[:3] == (0, 0, 0)
    assert px(frame, 8, 5)[:3] == (255, 255, 255)  # not drawn yet
    faded = render(
        scene_with(Point2D(id="p", position=(5, 5), size=12, color="#000000", opacity=0.5))
    )
    assert 100 < px(faded, 5, 5)[0] < 160


def test_groups_transform_clip_and_z_order():
    child = Shape2D(id="c", path=Path2D.rect(0, 0, 2, 2), fill="#00ff00")
    moved = Group2D(
        id="g",
        children=(child,),
        transform=Transform2D(translate=Vec2(6, 6)),
    )
    frame = render(scene_with(moved))
    assert px(frame, 7, 7)[:3] == (0, 255, 0) and px(frame, 1, 1)[:3] == (255, 255, 255)
    clipped = Group2D(
        id="g",
        children=(Shape2D(id="c", path=Path2D.rect(0, 0, 10, 10), fill="#ff0000"),),
        clip=Bounds2D((0, 0), (4, 10)),
    )
    frame = render(scene_with(clipped))
    assert px(frame, 2, 5)[:3] == (255, 0, 0) and px(frame, 8, 5)[:3] == (255, 255, 255)
    below = Shape2D(id="below", path=Path2D.rect(0, 0, 10, 10), fill="#0000ff", z=-1)
    above = Shape2D(id="above", path=Path2D.rect(0, 0, 10, 10), fill="#ff0000")
    assert px(render(scene_with(above, below)), 5, 5)[:3] == (255, 0, 0)


def test_overlay_is_pixel_space_y_down():
    dot = Point2D(id="hud", position=(20, 10), size=6, color="#ff0000")
    frame = render(scene_with(overlay=[dot]))
    assert tuple(int(v) for v in frame.pixels[10, 20])[:3] == (255, 0, 0)


def test_rendering_is_deterministic():
    scene = scene_with(Point2D(id="p", position=(5, 5), size=9), Line2D(id="l", end=(9, 9)))
    a, b = render(scene), render(scene)
    assert np.array_equal(a.pixels, b.pixels)


def test_antialiasing_can_be_disabled():
    scene = scene_with(Point2D(id="p", position=(5, 5), size=15, color="#000000"))
    aa = render(scene, antialias=True).pixels
    hard = render(scene, antialias=False).pixels
    assert len(np.unique(hard[..., 0])) < len(np.unique(aa[..., 0]))


def test_missing_capabilities_are_reported_early():
    from kinetickit.renderers import require

    r = get_renderer("raster")
    assert r.capabilities.name == "raster"
    with pytest.raises(CapabilityError, match="interaction:drag"):
        r.capabilities.validate(require(interactions=["drag"]))
    with pytest.raises(CapabilityError, match="dimension:native-3d"):
        r.capabilities.validate(require(dimensions=["native-3d"]))
    r.capabilities.validate(require(dimensions=["3d"], geometry=["mesh", "surface"]))
