from __future__ import annotations

import io
import os
import xml.etree.ElementTree as ET

import pytest

from kinetickit.animation import Animation
from kinetickit.errors import CapabilityError, ConfigurationError
from kinetickit.exporters import (
    AnimatedSVGExporter,
    BytesDestination,
    ExportManifest,
    FileDestination,
    StreamDestination,
    as_destination,
    available_formats,
    export,
)
from kinetickit.geometry.two_d import Bounds2D
from kinetickit.scene import Point2D, Scene2D


def make():
    p = Point2D(id="p")
    scene = Scene2D(p)
    scene = scene.bind({scene.camera.ref("view"): Bounds2D((0, 0), (10, 10))})
    return p, Animation(scene, p.animate.position.to((5, 5), duration=1.0))


def test_save_to_a_file_returns_a_manifest(tmp_path):
    _, anim = make()
    out = tmp_path / "motion.svg"
    manifest = anim.save(out, renderer="vector", width=300, height=200)
    assert isinstance(manifest, ExportManifest)
    assert manifest.format == "svg" and manifest.renderer == "vector"
    assert manifest.width == 300 and manifest.height == 200 and manifest.duration == 1.0
    assert manifest.bytes_written == out.stat().st_size > 0
    assert manifest.details["element_ids"] == {"p": "p"}
    ET.parse(out)  # well-formed
    assert [f.name for f in tmp_path.iterdir()] == ["motion.svg"]


def test_format_is_inferred_from_the_suffix_or_renderer():
    _, anim = make()
    assert anim.to_svg().startswith("<?xml")
    sink = io.BytesIO()
    assert anim.save(sink, renderer="vector").format == "svg"
    assert sink.getvalue().startswith(b"<?xml")
    with pytest.raises(ConfigurationError, match="cannot infer"):
        anim.save(io.BytesIO())
    with pytest.raises(ConfigurationError, match="unknown output format"):
        export(anim, io.BytesIO(), format="bmp")
    with pytest.raises(ConfigurationError, match="renderer"):
        anim.save(io.BytesIO(), renderer="interactive", format="svg")


def test_text_and_binary_streams_and_bytes_destinations():
    _, anim = make()
    text = io.StringIO()
    anim.save(text, format="svg")
    assert text.getvalue().startswith("<?xml")
    dest = BytesDestination()
    anim.save(dest, format="svg")
    assert dest.getvalue().decode() == text.getvalue()
    assert anim.to_bytes("svg") == dest.getvalue()


def test_exports_are_byte_identical_across_runs():
    _, anim = make()
    assert anim.to_bytes("svg") == anim.to_bytes("svg")


def test_capability_failure_writes_nothing(tmp_path):
    a, b = Point2D(id="a"), Point2D(id="b")
    scene = Scene2D(a, b)
    anim = Animation(scene, a.animate.z.to(2.0, duration=1.0))
    out = tmp_path / "bad.svg"
    with pytest.raises(CapabilityError):
        anim.save(out, renderer="vector")
    assert list(tmp_path.iterdir()) == []


def test_failed_write_leaves_no_partial_file(tmp_path):
    out = tmp_path / "x.svg"
    out.write_text("original")
    dest = FileDestination(out)
    with pytest.raises(RuntimeError), dest.open_binary() as handle:
        handle.write(b"partial")
        raise RuntimeError("boom")
    assert out.read_text() == "original"
    assert [f.name for f in tmp_path.iterdir()] == ["x.svg"]


def test_missing_directory_is_a_configuration_error(tmp_path):
    with (
        pytest.raises(ConfigurationError, match="directory"),
        FileDestination(tmp_path / "nope" / "a.svg").open_binary(),
    ):
        pass
    with FileDestination(tmp_path / "nope" / "a.svg", make_parents=True).open_binary() as h:
        h.write(b"ok")
    assert (tmp_path / "nope" / "a.svg").read_bytes() == b"ok"


def test_destination_coercion():
    assert isinstance(as_destination("a.svg"), FileDestination)
    assert isinstance(as_destination(os.fspath("a.svg")), FileDestination)
    assert isinstance(as_destination(io.BytesIO()), StreamDestination)
    d = BytesDestination()
    assert as_destination(d) is d
    with pytest.raises(ConfigurationError):
        as_destination(42)
    with pytest.raises(ConfigurationError):
        StreamDestination(object())


def test_exporter_class_is_usable_directly(tmp_path):
    _, anim = make()
    exporter = AnimatedSVGExporter.from_options(width=100, height=100, loop=True)
    manifest = exporter.export(anim, tmp_path / "d.svg")
    assert manifest.width == 100
    assert "repeatCount" in (tmp_path / "d.svg").read_text()


def test_static_animation_exports_a_plain_document():
    scene = Scene2D(Point2D(id="p"))
    svg = Animation(scene).to_svg()
    assert "<animate" not in svg


def test_available_formats_include_svg():
    assert "svg" in available_formats()
