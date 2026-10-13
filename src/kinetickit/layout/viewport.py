"""Single-viewport layout resolved once for the whole animation."""

from __future__ import annotations

import math
from dataclasses import dataclass

from kinetickit.animation import Animation
from kinetickit.errors import ConfigurationError
from kinetickit.geometry.two_d import Bounds2D, Matrix3, Vec2
from kinetickit.scene.two_d import Camera2D, Scene2D


@dataclass(frozen=True, slots=True)
class Margins:
    top: float = 0.0
    right: float = 0.0
    bottom: float = 0.0
    left: float = 0.0

    @classmethod
    def uniform(cls, value: float) -> Margins:
        return cls(value, value, value, value)


@dataclass(frozen=True, slots=True)
class Viewport:
    """Logical pixel size of the drawing area and its inner margins."""

    width: float
    height: float
    margins: Margins = Margins()

    def __post_init__(self) -> None:
        for v in (self.width, self.height):
            if not (math.isfinite(v) and v > 0):
                raise ConfigurationError("viewport size must be positive and finite")
        m = self.margins
        if m.left + m.right >= self.width or m.top + m.bottom >= self.height:
            raise ConfigurationError("viewport margins leave no drawing area")

    @property
    def plot_width(self) -> float:
        return self.width - self.margins.left - self.margins.right

    @property
    def plot_height(self) -> float:
        return self.height - self.margins.top - self.margins.bottom


@dataclass(frozen=True, slots=True)
class LayoutResult:
    """Resolved layout: the fixed base view window and the pixel mapping for a camera state."""

    viewport: Viewport
    base_view: Bounds2D

    def window(self, camera: Camera2D) -> Bounds2D:
        """World window shown for ``camera`` (pan and zoom applied to the base view)."""
        c = self.base_view.center + camera.pan
        half = self.base_view.size / (2.0 * camera.zoom)
        return Bounds2D(c - half, c + half)

    def scale(self, camera: Camera2D | None = None) -> float:
        win = self.window(camera or Camera2D())
        s = win.size
        return min(self.viewport.plot_width / s.x, self.viewport.plot_height / s.y)

    def world_to_pixel(self, camera: Camera2D | None = None) -> Matrix3:
        """Matrix mapping world coordinates (y up) to pixels (origin top-left, y down)."""
        cam = camera or Camera2D()
        win = self.window(cam)
        s = self.scale(cam)
        c = win.center
        vp = self.viewport
        cx = vp.margins.left + vp.plot_width / 2.0
        cy = vp.margins.top + vp.plot_height / 2.0
        return Matrix3((s, 0.0, cx - c.x * s, 0.0, -s, cy + c.y * s, 0.0, 0.0, 1.0))

    def project(self, p: Vec2, camera: Camera2D | None = None) -> Vec2:
        return self.world_to_pixel(camera).apply(p)


def animation_bounds(animation: Animation, samples_per_segment: int = 16) -> Bounds2D | None:
    """World bounds over the whole animation (never per frame).

    Samples every segment boundary plus ``samples_per_segment`` interior times so that animated
    geometry cannot leave the fitted view between frames.
    """
    scene = animation.scene
    if not isinstance(scene, Scene2D):
        raise ConfigurationError("animation_bounds needs a 2D animation")
    times = {0.0, animation.duration}
    for ref in animation.timeline.properties:
        for seg in animation.timeline.segments(ref):
            for k in range(samples_per_segment + 1):
                times.add(seg.start + (seg.end - seg.start) * k / samples_per_segment)
    out: Bounds2D | None = None
    for t in sorted(times):
        if t > animation.duration:
            continue
        b = animation.sample(t).bounds()
        if b is not None:
            out = b if out is None else out.union(b)
    return out


def resolve_layout(
    animation: Animation, viewport: Viewport, *, padding: float = 0.05
) -> LayoutResult:
    """Fix the base view for the entire animation.

    An explicit ``Camera2D.view`` wins; otherwise the union of all world bounds over time is
    padded by ``padding`` (a fraction) and given a minimum extent so degenerate content still has
    a valid scale. The view never changes per frame; only an animated camera moves it.
    """
    cam = animation.scene.camera
    assert isinstance(cam, Camera2D)
    view = cam.view
    if view is None:
        fitted = animation_bounds(animation) or Bounds2D(Vec2(0, 0), Vec2(1, 1))
        size = fitted.size
        pad = Vec2(max(size.x, 1e-9) * padding, max(size.y, 1e-9) * padding)
        lo, hi = fitted.min - pad, fitted.max + pad
        if hi.x - lo.x < 1e-9:
            lo, hi = lo - Vec2(0.5, 0), hi + Vec2(0.5, 0)
        if hi.y - lo.y < 1e-9:
            lo, hi = lo - Vec2(0, 0.5), hi + Vec2(0, 0.5)
        view = Bounds2D(lo, hi)
    return LayoutResult(viewport, view)
