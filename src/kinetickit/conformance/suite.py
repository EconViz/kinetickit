"""A renderer/exporter conformance suite built on the shared fixtures.

``run_suite("svg")`` exports every fixture through the registered exporter and checks the
contracts every output must honour: unsupported fixtures fail with ``CapabilityError`` *before*
output, supported ones export deterministically, keep stable object ids and report a manifest that
agrees with the animation. Third-party renderers register an exporter and run the same suite.
"""

from __future__ import annotations

import json
import re
import warnings
import xml.etree.ElementTree as ET
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

from kinetickit.conformance.fixtures import Fixture
from kinetickit.conformance.fixtures import fixtures as all_fixtures
from kinetickit.errors import CapabilityError

DEFAULT_OPTIONS: dict[str, dict[str, Any]] = {
    "svg": {"width": 160, "height": 120},
    "gif": {"width": 64, "height": 48, "fps": 5},
    "html": {"width": 240, "height": 180, "fps": 5},
}


@dataclass(frozen=True)
class Check:
    fixture: str
    name: str
    passed: bool
    detail: str = ""


@dataclass
class SuiteReport:
    format: str
    checks: list[Check] = field(default_factory=list)
    unsupported: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks)

    @property
    def failures(self) -> list[Check]:
        return [c for c in self.checks if not c.passed]

    def summary(self) -> str:
        ok = len(self.checks) - len(self.failures)
        lines = [f"{self.format}: {ok}/{len(self.checks)} checks passed"]
        lines += [f"  FAIL {c.fixture}/{c.name}: {c.detail}" for c in self.failures]
        lines += [f"  n/a  {name} (capability not declared)" for name in self.unsupported]
        return "\n".join(lines)

    def assert_passed(self) -> None:
        if not self.passed:
            raise AssertionError(self.summary())


# Nodes that never produce an output element of their own: the camera, lights, and 3D groups
# (3D groups are flattened into their drawable children by projection/plotting).
NON_DRAWING = {"camera", "light", "group3d"}


def _node_ids(animation: Any) -> set[str]:
    return {n.id for n in animation.scene.walk() if n.kind not in NON_DRAWING}


def _structural(
    fmt: str, data: bytes, animation: Any, manifest: Any
) -> list[tuple[str, bool, str]]:
    out: list[tuple[str, bool, str]] = []
    ids = _node_ids(animation)
    if fmt == "svg":
        try:
            root = ET.fromstring(data.decode("utf-8").split("?>", 1)[-1])
        except (ET.ParseError, UnicodeDecodeError) as exc:
            return [("well-formed", False, str(exc))]
        found = {e.get("data-kk-id") for e in root.iter() if e.get("data-kk-id")}
        out.append(("well-formed", True, ""))
        out.append(
            (
                "native-vector",
                not [e for e in root.iter() if e.tag.endswith("image")],
                "raster image embedded",
            )
        )
        out.append(("stable-ids", ids <= found, f"missing {sorted(ids - found)[:3]}"))
    elif fmt == "html":
        m = re.search(r'id="kk-data">(.*?)</script>', data.decode("utf-8"), re.S)
        payload = json.loads(m.group(1)) if m else {}
        out.append(("data-embedded", bool(payload), "no kk-data block"))
        out.append(("stable-ids", ids <= set(payload.get("objects", {})), "objects missing"))
        out.append(
            (
                "duration",
                abs(payload.get("duration", -1) - animation.duration) < 1e-9,
                "duration mismatch",
            )
        )
    elif fmt == "gif":
        from kinetickit.exporters._gif_stream import inspect_gif

        n_frames, durations = inspect_gif(data)
        out.append(
            ("decodes", n_frames == manifest.frames, f"{n_frames} frames vs {manifest.frames}")
        )
        out.append(
            (
                "timing",
                abs(sum(durations) / 1000.0 - manifest.duration) < 1e-9,
                "durations disagree",
            )
        )
        out.append(
            (
                "duration-matches-timeline",
                abs(manifest.duration - max(animation.duration, 0.01)) <= 0.011
                or animation.duration == 0,
                f"{manifest.duration} vs {animation.duration}",
            )
        )
    return out


def run_suite(
    fmt: str,
    *,
    fixtures: Iterable[Fixture] | None = None,
    options: dict[str, Any] | None = None,
    export: Callable[[Any, str, dict[str, Any]], tuple[bytes, Any]] | None = None,
) -> SuiteReport:
    """Check the exporter registered for ``fmt`` against the shared fixtures."""
    from kinetickit.exporters import BytesDestination
    from kinetickit.exporters import export as export_to

    opts = {**DEFAULT_OPTIONS.get(fmt, {}), **(options or {})}

    def default_export(animation: Any, f: str, o: dict[str, Any]) -> tuple[bytes, Any]:
        dest = BytesDestination()
        manifest = export_to(animation, dest, format=f, **o)
        return dest.getvalue(), manifest

    do_export = export or default_export
    report = SuiteReport(fmt)
    for fx in fixtures if fixtures is not None else all_fixtures():
        animation = fx.animation()
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                first, manifest = do_export(animation, fmt, opts)
        except CapabilityError as exc:
            report.checks.append(
                Check(
                    fx.name,
                    "fails-early-with-diagnostics",
                    bool(exc.missing) and bool(str(exc)),
                    str(exc)[:120],
                )
            )
            report.unsupported.append(fx.name)
            continue
        except Exception as exc:
            report.checks.append(Check(fx.name, "exports", False, f"{type(exc).__name__}: {exc}"))
            continue
        report.checks.append(Check(fx.name, "exports", len(first) > 0, "empty output"))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            second, _ = do_export(fx.animation(), fmt, opts)
        report.checks.append(Check(fx.name, "deterministic", first == second, "two exports differ"))
        report.checks.append(
            Check(fx.name, "manifest-format", manifest.format == fmt, manifest.format)
        )
        report.checks.append(
            Check(
                fx.name,
                "manifest-bytes",
                manifest.bytes_written == len(first),
                "byte count mismatch",
            )
        )
        for name, ok, detail in _structural(fmt, first, animation, manifest):
            report.checks.append(Check(fx.name, name, ok, detail))
    return report
