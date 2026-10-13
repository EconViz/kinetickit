from __future__ import annotations

import subprocess
import sys
import textwrap
from importlib.metadata import metadata

import kinetickit
from kinetickit import errors


def test_supported_python_metadata():
    from packaging.specifiers import SpecifierSet

    assert SpecifierSet(metadata("kinetickit")["Requires-Python"]) == SpecifierSet(">=3.10,<3.14")


def test_package_has_version_and_is_typed():
    import importlib.resources as resources

    assert kinetickit.__version__
    assert resources.files("kinetickit").joinpath("py.typed").is_file()


def test_error_hierarchy():
    assert issubclass(errors.ConfigurationError, errors.KineticKitError)
    assert issubclass(errors.ConfigurationError, ValueError)
    assert issubclass(errors.CapabilityError, errors.KineticKitError)
    assert issubclass(errors.RenderError, errors.KineticKitError)
    err = errors.CapabilityError("nope", missing=("mask",))
    assert err.missing == ("mask",)


def test_optional_extras_are_declared():
    extras = set(metadata("kinetickit").get_all("Provides-Extra") or ())
    assert {"raster", "interactive", "studio"} <= extras


def test_core_imports_without_optional_backends():
    code = textwrap.dedent(
        """
        import sys
        for name in ("matplotlib", "plotly", "PIL", "mosaickit", "bezierkit", "glyphkit"):
            sys.modules[name] = None  # any import now raises ImportError
        import kinetickit
        assert kinetickit.__version__
        """
    )
    result = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_base_install_exports_svg_and_explains_missing_extras():
    """Without Matplotlib, Pillow or Plotly the vector path works and the rest fail helpfully."""
    code = textwrap.dedent(
        """
        import sys
        for name in ("matplotlib", "plotly", "PIL", "mosaickit", "bezierkit", "glyphkit"):
            sys.modules[name] = None
        from kinetickit import Animation, Bounds2D, CapabilityError, Point2D, Scene2D, Vec2
        import kinetickit.exporters, kinetickit.renderers, kinetickit.conformance
        d = Point2D(id="d")
        s = Scene2D(d)
        s = s.bind({s.camera.ref("view"): Bounds2D(Vec2(0, 0), Vec2(10, 10))})
        a = Animation(s, d.animate.position.to(Vec2(5, 5), duration=1.0))
        assert "<animateTransform" in a.to_svg()
        for fmt, extra in (("gif", "raster"), ("html", "interactive")):
            try:
                a.to_bytes(fmt)
            except CapabilityError as exc:
                assert extra in str(exc), str(exc)
            else:
                raise SystemExit("expected CapabilityError for " + fmt)
        """
    )
    result = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr + result.stdout
