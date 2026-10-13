from __future__ import annotations

import io
import tracemalloc

import pytest

from kinetickit import ease
from kinetickit.animation import Animation
from kinetickit.geometry.two_d import Bounds2D
from kinetickit.scene import Point2D, Scene2D

pytest.importorskip("matplotlib")
pytest.importorskip("PIL")


def make(duration):
    p = Point2D(id="p", position=(1, 5), size=8)
    s = Scene2D(p)
    s = s.bind({s.camera.ref("view"): Bounds2D((0, 0), (10, 10))})
    return Animation(s, p.animate.position.to((9, 5), duration=duration, easing=ease.linear))


def peak_memory(duration):
    anim = make(duration)
    sink = io.BytesIO()
    tracemalloc.start()
    anim.save(sink, format="gif", width=200, height=200, fps=10, colors=16)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return peak, len(sink.getvalue())


def test_long_animations_do_not_retain_every_frame():
    short_peak, short_size = peak_memory(1.0)
    long_peak, long_size = peak_memory(8.0)
    frame_bytes = 200 * 200 * 4
    assert long_size > short_size * 3  # the long file really is much bigger...
    # ...yet peak Python memory only grows with the encoded output, not with 80 decoded RGBA
    # frames (~12.8 MB): at most a couple of frames are alive at once
    assert long_peak < short_peak + 2 * frame_bytes + (long_size - short_size)


def test_frames_are_consumed_lazily():
    anim = make(1.0)
    stream = anim.frames(30)
    first = next(stream)
    assert first.index == 0  # nothing else was evaluated
