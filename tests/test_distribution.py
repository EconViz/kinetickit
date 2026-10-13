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
