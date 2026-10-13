from __future__ import annotations

import pytest

from kinetickit.animation import Animation
from kinetickit.errors import ConfigurationError
from kinetickit.geometry.two_d import Bounds2D, Vec2
from kinetickit.layout import Margins, Viewport, animation_bounds, resolve_layout
from kinetickit.scene import Point2D, Scene2D


def moving():
    p = Point2D(id="p", position=(0, 0))
    scene = Scene2D(p, Point2D(id="q", position=(1, 1)))
    return scene, p.animate.position.to((20, 10), duration=1)


def test_view_covers_the_whole_animation_not_the_first_frame():
    scene, motion = moving()
    anim = Animation(scene, motion)
    bounds = animation_bounds(anim)
    assert bounds == Bounds2D((0, 0), (20, 10))
    lay = resolve_layout(anim, Viewport(400, 200), padding=0.1)
    assert lay.base_view == Bounds2D((-2, -1), (22, 11))


def test_range_is_stable_across_frames():
    scene, motion = moving()
    anim = Animation(scene, motion)
    lay = resolve_layout(anim, Viewport(400, 200))
    views = {lay.window(f.snapshot.camera) for f in anim.frames(10)}
    assert len(views) == 1


def test_explicit_view_wins_and_camera_animation_moves_it():
    cam_scene = Scene2D(Point2D(id="p"))
    scene = cam_scene.bind({cam_scene.camera.ref("view"): Bounds2D((0, 0), (10, 10))})
    zoom = scene.camera.animate.zoom.to(2.0, duration=1)
    anim = Animation(scene, zoom)
    lay = resolve_layout(anim, Viewport(100, 100))
    assert lay.base_view == Bounds2D((0, 0), (10, 10))
    assert lay.window(anim.sample(0).camera) == Bounds2D((0, 0), (10, 10))
    assert lay.window(anim.sample(1).camera) == Bounds2D((2.5, 2.5), (7.5, 7.5))


def test_world_to_pixel_flips_y_and_preserves_aspect():
    scene = Scene2D()
    scene = scene.bind({scene.camera.ref("view"): Bounds2D((0, 0), (10, 10))})
    lay = resolve_layout(Animation(scene), Viewport(200, 100))
    assert lay.scale() == pytest.approx(10.0)  # limited by height
    assert lay.project(Vec2(0, 0)) == Vec2(50.0, 100.0)  # bottom-left of the centred square
    assert lay.project(Vec2(10, 10)) == Vec2(150.0, 0.0)
    pan = scene.camera.replace(pan=Vec2(5, 0))
    assert lay.project(Vec2(5, 5), pan) == Vec2(50.0, 50.0)  # view centre moved to x=10


def test_margins_shrink_the_plot_area():
    vp = Viewport(200, 100, Margins(10, 10, 10, 10))
    assert vp.plot_width == 180 and vp.plot_height == 80
    with pytest.raises(ConfigurationError):
        Viewport(100, 100, Margins.uniform(60))
    with pytest.raises(ConfigurationError):
        Viewport(0, 100)


def test_degenerate_content_still_has_a_valid_view():
    scene = Scene2D(Point2D(id="p", position=(3, 3)))
    lay = resolve_layout(Animation(scene), Viewport(100, 100))
    assert lay.base_view.size.x > 0 and lay.base_view.size.y > 0
    assert lay.scale() > 0
    empty = resolve_layout(Animation(Scene2D()), Viewport(100, 100))
    assert empty.base_view.size == Vec2(1.1, 1.1) or empty.base_view.size.x > 0
