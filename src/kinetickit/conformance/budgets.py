"""Performance and size budgets, measured on the shared fixtures.

Budgets are deliberately generous ceilings (they must hold on a slow CI runner); the point is to
make *regressions* visible. ``python -m kinetickit.conformance`` prints and records the report.
"""

from __future__ import annotations

import importlib.util
import io
import time
import tracemalloc
import warnings
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from kinetickit.conformance.fixtures import fixtures

FIX = {f.name: f for f in fixtures()}


@dataclass(frozen=True)
class Budget:
    name: str
    limit: float
    unit: str
    description: str


BUDGETS: tuple[Budget, ...] = (
    Budget("frame-eval", 5.0, "ms/frame", "sample one 2D timing frame"),
    Budget("frame-eval-3d", 50.0, "ms/frame", "sample one 3D morph frame"),
    Budget("svg-export-time", 1.0, "s", "export the points/lines/shapes fixture to SVG"),
    Budget("svg-size", 60_000, "bytes", "size of that SVG"),
    Budget("svg-3d-export-time", 3.0, "s", "export the 3D mesh fixture to projected SVG"),
    Budget("svg-3d-size", 400_000, "bytes", "size of the projected 3D SVG"),
    Budget("gif-export-time", 6.0, "s", "export a 64x48, 5 fps GIF"),
    Budget("gif-size", 80_000, "bytes", "size of that GIF"),
    Budget("gif-peak-memory", 25_000_000, "bytes", "peak Python memory while streaming a GIF"),
    Budget("html-2d-size", 80_000, "bytes", "self-contained 2D HTML"),
    Budget("html-3d-size", 8_000_000, "bytes", "self-contained offline 3D HTML (embedded runtime)"),
)


def _time(fn: Callable[[], Any], repeat: int = 1) -> tuple[float, Any]:
    best = float("inf")
    result = None
    for _ in range(repeat):
        t0 = time.perf_counter()
        result = fn()
        best = min(best, time.perf_counter() - t0)
    return best, result


def _available(*modules: str) -> bool:
    return all(importlib.util.find_spec(m) is not None for m in modules)


def measure(*, include_optional: bool = True) -> dict[str, float]:
    """Measure every budget. Optional-extra budgets are skipped when their extra is missing."""
    out: dict[str, float] = {}
    timing = FIX["timing-easing-chain"].animation()
    n = 100
    t, _ = _time(lambda: [timing.sample(timing.duration * i / (n - 1)) for i in range(n)], 3)
    out["frame-eval"] = t / n * 1000

    morph = FIX["mesh-morph"].animation()
    t, _ = _time(lambda: [morph.sample(morph.duration * i / 19) for i in range(20)], 2)
    out["frame-eval-3d"] = t / 20 * 1000

    shapes = FIX["points-lines-shapes"].animation()
    t, svg = _time(lambda: shapes.to_svg(width=400, height=300), 2)
    out["svg-export-time"], out["svg-size"] = t, float(len(svg.encode()))
    t, svg3 = _time(lambda: morph.to_svg(width=400, height=300), 1)
    out["svg-3d-export-time"], out["svg-3d-size"] = t, float(len(svg3.encode()))
    if not include_optional:
        return out
    if _available("matplotlib", "PIL"):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            t, data = _time(lambda: shapes.to_bytes("gif", width=64, height=48, fps=5))
            out["gif-export-time"], out["gif-size"] = t, float(len(data))
            tracemalloc.start()
            shapes.save(io.BytesIO(), format="gif", width=64, height=48, fps=5)
            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            out["gif-peak-memory"] = float(peak)
    if _available("plotly"):
        out["html-2d-size"] = float(len(shapes.to_bytes("html", width=400, height=300)))
        out["html-3d-size"] = float(
            len(FIX["surface-orbit"].animation().to_bytes("html", width=400, height=300, fps=4))
        )
    return out


def check(values: dict[str, float], scale: float = 1.0) -> list[str]:
    """Names of budgets exceeded (limits multiplied by ``scale`` for slow machines)."""
    limits = {b.name: b.limit * scale for b in BUDGETS}
    return [name for name, v in values.items() if v > limits[name]]


def report(values: dict[str, float], scale: float = 1.0) -> str:
    rows = ["| budget | measured | limit | used |", "|---|---:|---:|---:|"]
    for b in BUDGETS:
        if b.name not in values:
            rows.append(f"| {b.name} | n/a | {b.limit:g} {b.unit} | |")
            continue
        v, lim = values[b.name], b.limit * scale
        rows.append(f"| {b.name} | {v:,.2f} {b.unit} | {lim:,.0f} {b.unit} | {v / lim:.0%} |")
    return "\n".join(rows)
