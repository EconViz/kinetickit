from __future__ import annotations

import ast
import importlib.util
import re
import sys
from pathlib import Path

import pytest
from tests.support.extras import needs_interactive

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "examples"
SCRIPTS = sorted(p for p in EXAMPLES.glob("*.py") if not p.name.startswith("_"))
DOMAIN_WORDS = {"supply", "demand", "utility", "equilibrium", "profit", "mosaickit", "econ"}


def load(path: Path):
    if str(EXAMPLES) not in sys.path:
        sys.path.insert(0, str(EXAMPLES))  # examples import their sibling helper modules
    if True:
        spec = importlib.util.spec_from_file_location(f"example_{path.stem}", path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = mod  # dataclasses resolve annotations through sys.modules
        spec.loader.exec_module(mod)
        return mod


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    mods: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            mods.update(a.name for a in n.names)
        elif isinstance(n, ast.ImportFrom) and n.module and n.level == 0:
            mods.add(n.module)
    return mods


def test_there_are_examples_for_objects_charts_surfaces_and_fonts():
    names = {p.stem for p in SCRIPTS}
    assert {"arbitrary_objects", "chart", "surface", "external_fonts"} <= names


@pytest.mark.parametrize("path", SCRIPTS + [EXAMPLES / "_demo_font.py"], ids=lambda p: p.name)
def test_examples_use_only_public_api(path):
    for mod in imported_modules(path):
        root = mod.split(".")[0]
        if root == "kinetickit":
            assert not any(part.startswith("_") for part in mod.split(".")), mod
        assert root not in {"mosaickit", "bezierkit"} and not root.endswith("_viz"), mod
        assert root != "matplotlib" and root != "plotly" and root != "PIL", mod
    text = path.read_text().lower()
    assert not [w for w in DOMAIN_WORDS if re.search(rf"\b{w}\b", text)]


@pytest.mark.parametrize(
    "path", [p for p in SCRIPTS if p.stem != "external_fonts"], ids=lambda p: p.stem
)
def test_examples_run_and_write_nonempty_outputs(path, tmp_path):
    pytest.importorskip("matplotlib")
    pytest.importorskip("plotly")
    files = load(path).main(tmp_path)
    assert files
    for name, f in files.items():
        assert f.exists() and f.stat().st_size > 0, name


def test_external_font_example_when_glyphkit_is_available(tmp_path):
    pytest.importorskip("glyphkit")
    pytest.importorskip("fontTools")
    files = load(EXAMPLES / "external_fonts.py").main(tmp_path)
    assert set(files) == {"svg"}  # base install must not require the interactive extra
    svg = files["svg"].read_text()
    assert "@font-face" in svg and "Demo Sans" in svg  # the caller's font survives export


@needs_interactive
def test_external_font_example_can_include_interactive_output(tmp_path):
    files = load(EXAMPLES / "external_fonts.py").main(tmp_path, include_interactive=True)
    assert set(files) == {"svg", "html"}
    assert all(path.exists() and path.stat().st_size > 0 for path in files.values())


@needs_interactive
def test_the_adapter_example_proves_generality(tmp_path):
    mod = load(EXAMPLES / "arbitrary_objects.py")
    files = mod.main(tmp_path)
    svg = files["svg"].read_text()
    assert 'data-kk-id="gamma.body"' in svg  # an object only present in the second state
    assert "Satellite" not in svg  # KineticKit never sees the domain class
