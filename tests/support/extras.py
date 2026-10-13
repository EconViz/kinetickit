"""Skip markers for tests that need an optional extra, so the base install stays green."""

from __future__ import annotations

import importlib.util

import pytest


def _has(*modules: str) -> bool:
    return all(importlib.util.find_spec(m) is not None for m in modules)


needs_raster = pytest.mark.skipif(not _has("matplotlib", "PIL"), reason="needs kinetickit[raster]")
needs_interactive = pytest.mark.skipif(not _has("plotly"), reason="needs kinetickit[interactive]")
needs_studio = pytest.mark.skipif(
    not _has("matplotlib", "PIL", "plotly"), reason="needs kinetickit[studio]"
)
