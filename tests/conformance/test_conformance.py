from __future__ import annotations

import pytest

from kinetickit.conformance import FIXTURES, fixtures, run_suite
from kinetickit.errors import CapabilityError
from kinetickit.renderers import get_renderer, requirements_for


def test_fixtures_cover_2d_3d_timing_and_typography():
    tags = set().union(*(f.tags for f in FIXTURES))
    assert {"2d", "3d", "timing", "typography", "morph", "camera", "overlay"} <= tags
    assert len({f.name for f in FIXTURES}) == len(FIXTURES)
    assert all(f.description for f in FIXTURES)
    assert [f.name for f in fixtures("3d")] == ["surface-orbit", "mesh-morph"]
    assert fixtures("typography")[0].name == "text-asset"


def test_fixtures_use_only_generic_content():
    banned = {"supply", "demand", "utility", "profit", "equilibrium", "mosaickit"}
    for f in FIXTURES:
        anim = f.animation()
        words = {n.id.lower() for n in anim.scene.walk()}
        assert not words & banned


@pytest.mark.parametrize("fx", FIXTURES, ids=lambda f: f.name)
def test_every_fixture_builds_deterministically(fx):
    a, b = fx.animation(), fx.animation()
    assert a.duration == b.duration > 0
    for t in (0.0, a.duration / 3, a.duration):
        assert a.sample(t) == b.sample(t)


def test_svg_conformance():
    report = run_suite("svg")
    report.assert_passed()
    assert report.unsupported == []  # 2D and projected 3D are both supported natively
    assert len(report.checks) > 40


def test_gif_conformance():
    pytest.importorskip("matplotlib")
    pytest.importorskip("PIL")
    report = run_suite("gif")
    report.assert_passed()
    assert report.unsupported == []


def test_html_conformance():
    pytest.importorskip("plotly")
    report = run_suite("html", options={"fps": 4})
    report.assert_passed()
    assert report.unsupported == []


def test_unsupported_capabilities_fail_early_with_diagnostics():
    # a renderer that declares less must be rejected by the suite's contract, not silently accepted
    from kinetickit.renderers import register_renderer
    from kinetickit.renderers.capabilities import DIM_2D, RendererCapabilities

    class Tiny:
        capabilities = RendererCapabilities(
            "tiny", dimensions=frozenset({DIM_2D}), geometry=frozenset({"point"})
        )

    register_renderer("tiny", Tiny, replace=True)
    caps = get_renderer("tiny").capabilities
    for fx in FIXTURES:
        req = requirements_for(fx.animation())
        if caps.missing(req):
            with pytest.raises(CapabilityError) as info:
                caps.validate(req)
            assert info.value.missing


def test_the_suite_detects_nondeterminism_and_broken_exporters():
    import itertools

    counter = itertools.count()

    def flaky(animation, fmt, opts):
        class M:
            format = fmt
            bytes_written = 3

        return f"x{next(counter)}".encode(), M()

    report = run_suite("svg", fixtures=fixtures("timing"), export=flaky)
    assert not report.passed and any(c.name == "deterministic" for c in report.failures)

    def boom(animation, fmt, opts):
        raise RuntimeError("bad exporter")

    report = run_suite("svg", fixtures=fixtures("timing"), export=boom)
    assert not report.passed and "bad exporter" in report.summary()


@pytest.mark.parametrize("fx", [f for f in FIXTURES if "2d" in f.tags], ids=lambda f: f.name)
def test_output_settings_are_deterministic_across_runs_and_processes(fx):
    import subprocess
    import sys
    import textwrap

    here = fx.animation().to_bytes("svg", width=200, height=150)
    code = textwrap.dedent(
        f"""
        import hashlib
        from kinetickit.conformance import fixtures
        fx = {{f.name: f for f in fixtures()}}[{fx.name!r}]
        print(hashlib.sha256(fx.animation().to_bytes("svg", width=200, height=150)).hexdigest())
        """
    )
    other = subprocess.run(
        [sys.executable, "-I", "-c", code], capture_output=True, text=True, check=True
    )
    import hashlib

    assert other.stdout.strip() == hashlib.sha256(here).hexdigest()


def test_gif_and_html_settings_are_recorded_in_the_output():
    pytest.importorskip("PIL")
    pytest.importorskip("matplotlib")
    import io

    from PIL import Image

    fx = fixtures("timing")[0]
    gif = Image.open(
        io.BytesIO(
            fx.animation().to_bytes(
                "gif", width=40, height=30, fps=5, colors=64, dither="floyd-steinberg"
            )
        )
    )
    import json

    comment = json.loads(gif.info["comment"])
    assert (
        comment["colors"] == 64 and comment["dither"] == "floyd-steinberg" and comment["dpi"] == 96
    )
