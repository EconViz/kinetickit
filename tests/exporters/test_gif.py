from __future__ import annotations

import io
import warnings

import numpy as np
import pytest

from kinetickit import ease
from kinetickit.animation import Animation
from kinetickit.errors import CapabilityError, ConfigurationError
from kinetickit.exporters import RenderCostWarning
from kinetickit.exporters.cost import estimate_cost
from kinetickit.exporters.gif import frame_delays
from kinetickit.geometry.two_d import Bounds2D
from kinetickit.renderers.raster import RasterSettings
from kinetickit.scene import Group2D, Point2D, Scene2D

Image = pytest.importorskip("PIL.Image")


def anim(duration=1.0):
    p = Point2D(id="p", position=(1, 5), size=8, color="#d62728")
    s = Scene2D(p)
    s = s.bind({s.camera.ref("view"): Bounds2D((0, 0), (10, 10))})
    return Animation(s, p.animate.position.to((9, 5), duration=duration, easing=ease.linear))


def open_gif(data: bytes):
    return Image.open(io.BytesIO(data))


def test_one_second_at_30_fps_is_30_frames_with_exact_total_time():
    data = anim().to_bytes("gif", width=64, height=64, fps=30)
    im = open_gif(data)
    assert im.n_frames == 30
    total = 0
    for i in range(im.n_frames):
        im.seek(i)
        total += im.info["duration"]
    assert total == 1000  # centisecond error is distributed, not accumulated into the last frame


def test_delay_distribution_spreads_rounding_error():
    times = [i / 29 for i in range(30)]
    delays = frame_delays(times, 1.0, uniform=True)
    assert sum(delays) == 100 and set(delays) == {3, 4}
    assert sum(frame_delays(times, 1.0)) > 100  # explicit stamps keep their own gaps
    assert frame_delays([0.0], 0.0)[0] >= 1


def test_sub_centisecond_intervals_are_rejected():
    with pytest.raises(ConfigurationError, match="10 ms"):
        anim().to_bytes("gif", width=32, height=32, fps=120)
    with pytest.raises(ConfigurationError, match="10 ms"):
        anim().to_bytes("gif", width=32, height=32, timestamps=(0.0, 0.004, 1.0))


def test_explicit_timestamps_set_frame_timing():
    data = anim().to_bytes("gif", width=32, height=32, timestamps=(0.0, 0.2, 0.5))
    im = open_gif(data)
    durations = []
    for i in range(im.n_frames):
        im.seek(i)
        durations.append(im.info["duration"])
    assert durations == [200, 300, 500]


def test_endpoints_are_rendered_start_and_end_states():
    im = open_gif(anim().to_bytes("gif", width=100, height=100, fps=10))
    im.seek(0)
    first = np.array(im.convert("RGB"))
    im.seek(im.n_frames - 1)
    last = np.array(im.convert("RGB"))
    red = lambda a: np.argwhere((a[..., 0] > 180) & (a[..., 1] < 80))  # noqa: E731
    assert red(first)[:, 1].mean() < 25 and red(last)[:, 1].mean() > 75


def test_loop_and_metadata_options():
    forever = open_gif(anim().to_bytes("gif", width=32, height=32, fps=5, loop=0))
    assert forever.info.get("loop") == 0
    once = open_gif(anim().to_bytes("gif", width=32, height=32, fps=5, loop=None))
    assert "loop" not in once.info
    twice = open_gif(anim().to_bytes("gif", width=32, height=32, fps=5, loop=2))
    assert twice.info["loop"] == 2
    comment = forever.info["comment"].decode()
    assert '"frames":5' in comment and "kinetickit" in comment
    bare = open_gif(anim().to_bytes("gif", width=32, height=32, fps=5, metadata=False))
    assert "comment" not in bare.info


def test_palette_dither_and_disposal_controls():
    base = dict(width=48, height=48, fps=5)
    adaptive = anim().to_bytes("gif", **base, colors=4)
    assert len(open_gif(adaptive).convert("RGB").getcolors()) <= 4
    glob = anim().to_bytes("gif", **base, palette="global", dither="floyd-steinberg")
    assert open_gif(glob).n_frames == 5
    assert open_gif(anim().to_bytes("gif", **base, disposal=2)).n_frames == 5
    for bad in ({"colors": 1}, {"dither": "x"}, {"palette": "x"}, {"disposal": 9}):
        with pytest.raises(ConfigurationError):
            anim().to_bytes("gif", **base, **bad)
    with pytest.raises(ConfigurationError, match="unknown GIF options"):
        anim().to_bytes("gif", bogus=1)


def test_output_is_byte_deterministic():
    a = anim().to_bytes("gif", width=64, height=64, fps=12)
    b = anim().to_bytes("gif", width=64, height=64, fps=12)
    assert a == b


def test_file_stream_and_bytes_destinations_agree(tmp_path):
    kw = dict(width=40, height=40, fps=6)
    path = tmp_path / "a.gif"
    manifest = anim().save(path, **kw)
    sink = io.BytesIO()
    anim().save(sink, format="gif", **kw)
    assert path.read_bytes() == sink.getvalue() == anim().to_bytes("gif", **kw)
    assert manifest.format == "gif" and manifest.renderer == "raster"
    assert manifest.frames == 6 and manifest.bytes_written == path.stat().st_size
    assert (manifest.width, manifest.height) == (40, 40)
    assert manifest.duration == pytest.approx(1.0)
    assert sum(manifest.details["delays_cs"]) == 100


def test_static_animation_makes_a_single_frame_gif():
    s = Scene2D(Point2D(id="p"))
    im = open_gif(Animation(s).to_bytes("gif", width=32, height=32))
    assert im.n_frames == 1


def test_1200_dpi_export_path():
    data = anim().to_bytes("gif", width=96, height=64, dpi=1200, fps=2)
    im = open_gif(data)
    assert im.size == (1200, 800) and im.n_frames == 2
    manifest = anim().save(io.BytesIO(), format="gif", width=96, height=64, dpi=1200, fps=2)
    assert manifest.details["dpi"] == 1200 and (manifest.width, manifest.height) == (1200, 800)


def test_physical_size_and_dpi():
    im = open_gif(anim().to_bytes("gif", size_inches=(2, 1), dpi=150, fps=2))
    assert im.size == (300, 150)


def test_expensive_jobs_warn_but_do_not_downgrade():
    est = estimate_cost(RasterSettings(width=96, height=96, dpi=1200).resolve(), 3000)
    assert est.expensive and "not reduced" in est.message()
    cheap = estimate_cost(RasterSettings(width=96, height=96).resolve(), 3)
    assert not cheap.expensive
    with pytest.warns(RenderCostWarning):
        # estimate only: do not actually render ~12 gigapixels
        from kinetickit.exporters.cost import warn_if_expensive

        warn_if_expensive(est)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        anim().to_bytes("gif", width=32, height=32, fps=2)


def test_capability_failure_writes_nothing(tmp_path):
    g = Group2D(id="g", clip=Bounds2D((0, 0), (1, 1)))
    s = Scene2D(g)
    bad = Animation(s, g.animate.clip.to(Bounds2D((0, 0), (2, 2)), duration=1.0))
    out = tmp_path / "x.gif"
    with pytest.raises(CapabilityError, match="clip-animation"):
        bad.save(out, width=32, height=32, fps=2)
    assert list(tmp_path.iterdir()) == []


def test_a_failed_encode_leaves_no_file(tmp_path, monkeypatch):
    out = tmp_path / "bad.gif"
    import kinetickit.exporters._gif_stream as gif_module

    def boom(self, rgba, delay_cs):
        raise RuntimeError("encoder exploded")

    monkeypatch.setattr(gif_module.GifStreamWriter, "add_frame", boom)
    with pytest.raises(RuntimeError):
        anim().save(out, width=32, height=32, fps=2)
    assert not out.exists() and list(tmp_path.iterdir()) == []
