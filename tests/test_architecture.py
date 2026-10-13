"""Static boundary checks that complement the import-linter contracts."""

from __future__ import annotations

import ast
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src" / "kinetickit"
FORBIDDEN_ROOTS = {"mosaickit", "bezierkit", "glyphkit"}
BACKEND_ROOTS = {"matplotlib", "plotly", "PIL"}
PRIVATE_BACKEND_MODULES = {
    "renderers/raster/_matplotlib.py",
    "renderers/interactive/_plotly.py",
    "exporters/_gif_stream.py",
}


def _imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".")[0])
    return roots


def _sources() -> list[Path]:
    return sorted(SRC.rglob("*.py"))


INTEGRATION_IMPORTS = {"integrations/glyphkit.py": {"glyphkit"}}


def test_no_module_imports_domain_packages():
    for path in _sources():
        rel = path.relative_to(SRC).as_posix()
        roots = _imported_roots(path) - INTEGRATION_IMPORTS.get(rel, set())
        assert not roots & FORBIDDEN_ROOTS, f"{path} imports a forbidden package"
        assert not any(r.endswith("_viz") for r in roots), f"{path} imports an xx-viz package"


def test_backend_imports_are_confined_to_private_modules():
    for path in _sources():
        rel = path.relative_to(SRC).as_posix()
        if rel in PRIVATE_BACKEND_MODULES:
            continue
        assert not _imported_roots(path) & BACKEND_ROOTS, f"{rel} imports a backend directly"


def test_public_api_names_do_not_mention_backends():
    for path in _sources():
        rel = path.relative_to(SRC).as_posix()
        if rel in PRIVATE_BACKEND_MODULES:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and not node.name.startswith("_"):
                lowered = node.name.lower()
                assert "matplotlib" not in lowered
                assert "plotly" not in lowered


@pytest.mark.skipif(shutil.which("lint-imports") is None, reason="import-linter not installed")
def test_import_linter_contracts_hold():
    exe = shutil.which("lint-imports")
    assert exe is not None
    result = subprocess.run([exe], cwd=SRC.parent.parent, capture_output=True, text=True, env=None)
    assert result.returncode == 0, result.stdout + result.stderr


def test_python_executable_is_supported():
    assert (3, 10) <= sys.version_info[:2] <= (3, 13)
