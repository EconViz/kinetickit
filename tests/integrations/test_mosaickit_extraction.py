"""Feasibility proof: MosaicKit parameter sweeps can drive KineticKit through public adapters.

The adapter below lives in the tests on purpose: KineticKit core never imports MosaicKit. It reads
only public MosaicKit values (``Scene``, layers, their ``id``/geometry/style fields) and produces
ordinary KineticKit nodes, then lets ``kinetickit.adapters.transition`` animate between frames by
the layers' stable ids.
"""

from __future__ import annotations

import pytest

mosaickit = pytest.importorskip("mosaickit")

from mosaickit import Canvas, Fill, FillLayer, MarkerLayer, Parameter, PathLayer, Stroke  # noqa: E402
from tests.support.smil import Q, parse  # noqa: E402

from kinetickit.adapters import adapt, transition  # noqa: E402
from kinetickit.animation import Animation  # noqa: E402
from kinetickit.geometry.two_d import Bounds2D, Path2D, Vec2  # noqa: E402
from kinetickit.interpolation import Color  # noqa: E402
from kinetickit.scene import PathNode2D, Point2D, Shape2D  # noqa: E402


def color_of(c) -> Color:
    return Color(c.red, c.green, c.blue, c.alpha)


def depict(layer):
    """One MosaicKit layer -> KineticKit nodes (ids are the layers' stable ids)."""
    if isinstance(layer, PathLayer):
        stroke = layer.stroke
        return [
            PathNode2D(
                id=layer.id,
                path=Path2D.polyline(layer.path),
                color=color_of(stroke.color) if stroke and stroke.color else "#1f2933",
                width=float(stroke.width) if stroke and stroke.width else 2.0,
                z=layer.z_index,
            )
        ]
    if isinstance(layer, FillLayer):
        fill = layer.fill
        return [
            Shape2D(
                id=layer.id,
                path=Path2D.polygon(layer.boundary),
                fill=color_of(fill.color),
                opacity=fill.opacity if fill.opacity is not None else 1.0,
                z=layer.z_index,
            )
        ]
    if isinstance(layer, MarkerLayer):
        return [
            Point2D(id=f"{layer.id}.{i}", position=Vec2(*p), size=5, z=layer.z_index)
            for i, p in enumerate(layer.points)
        ]
    raise TypeError(f"no depiction for {type(layer).__name__}")


def sweep_canvas():
    t = Parameter("t", float)
    canvas = Canvas()
    canvas.add(
        PathLayer([(0, 0), (4, t), (8, 0)], stroke=Stroke(color="#984EA3", width=3), id="curve")
    )
    canvas.add(MarkerLayer([(4, t)], id="peak"))
    canvas.add(
        FillLayer([(0, 0), (8, 0), (4, t)], fill=Fill(color="#377EB8", opacity=0.3), id="area")
    )
    return [canvas.bind(t, value).snapshot() for value in (1.0, 4.0, 7.0)]


def frames_to_nodes(frames):
    return [[n for layer in f.layers for n in depict(layer)] for f in frames]


def test_a_parameter_sweep_extracts_into_a_kinetickit_animation(tmp_path):
    frames = sweep_canvas()
    assert len(frames) == 3
    scenes = [adapt([layer], depict) for f in frames for layer in f.layers][:3]
    assert scenes  # the same adapter builds plain scenes from any frame

    first = transition(frames[0].layers, frames[1].layers, depict, duration=1.0)
    second = transition(frames[1].layers, frames[2].layers, depict, duration=1.0)
    assert not first.warnings and not second.warnings  # same ids, same structure: pure morphs

    scene = first.scene
    scene = scene.bind({scene.camera.ref("view"): Bounds2D(Vec2(-1, -1), Vec2(9, 8))})
    animation = Animation(scene, first.motion.then(second.motion))
    assert animation.duration == pytest.approx(2.0)

    mid = animation.sample(0.5)  # halfway between t=1 and t=4 (eased)
    peak_first = mid.get("curve").path.vertices()[1]
    assert 1.0 < peak_first.y < 4.0
    end = animation.sample(2.0)
    assert end.get("curve").path.vertices()[1].y == pytest.approx(7.0)
    assert end.get("peak.0").position == Vec2(4, 7)

    svg = tmp_path / "sweep.svg"
    manifest = animation.save(svg, renderer="vector", width=400, height=300)
    root = parse(svg.read_text())
    ids = {e.get("data-kk-id") for e in root.iter() if e.get("data-kk-id")}
    assert {"curve", "peak.0", "area"} <= ids
    assert (
        manifest.animation_count
        if hasattr(manifest, "animation_count")
        else manifest.details["animations"] > 0
    )
    assert not [e for e in root.iter() if e.tag == Q + "image"]
    html = animation.to_bytes("html", width=400, height=300)
    assert b"kinetickit" in html


def test_kinetickit_core_never_imports_mosaickit():
    import subprocess
    import sys
    import textwrap

    code = textwrap.dedent(
        """
        import sys
        sys.modules["mosaickit"] = None
        import kinetickit, kinetickit.scene, kinetickit.exporters, kinetickit.adapters, kinetickit.conformance
        """
    )
    assert subprocess.run([sys.executable, "-I", "-c", code], capture_output=True).returncode == 0
