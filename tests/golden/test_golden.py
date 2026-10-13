"""Golden artifacts for GIF, Animated SVG and self-contained HTML.

Run ``KK_UPDATE_GOLDEN=1 pytest tests/golden`` to regenerate after an intentional change, and
review the diff: a golden change is a visible change of output.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
from pathlib import Path

import numpy as np
import pytest
from tests.support.extras import needs_interactive

from kinetickit.conformance import fixtures

DATA = Path(__file__).parent / "data"
UPDATE = os.environ.get("KK_UPDATE_GOLDEN") == "1"
FIX = {f.name: f for f in fixtures()}


def check_text(name: str, text: str) -> None:
    path = DATA / name
    if UPDATE or not path.exists():
        path.write_text(text, encoding="utf-8")
        if not UPDATE:
            pytest.fail(f"created missing golden {name}; review and commit it")
    assert text == path.read_text(encoding="utf-8"), f"golden {name} changed"


def check_json(name: str, data: object) -> None:
    check_text(name, json.dumps(data, indent=2, sort_keys=True) + "\n")


@pytest.mark.parametrize(
    "name", ["points-lines-shapes", "camera-zoom", "path-morph", "timing-easing-chain"]
)
def test_animated_svg_golden(name):
    svg = FIX[name].animation().to_svg(width=200, height=150)
    check_text(f"{name}.svg", svg)


def test_projected_3d_svg_fingerprint():
    svg = FIX["mesh-morph"].animation().to_svg(width=200, height=150)
    root_info = {
        "sha256": hashlib.sha256(svg.encode()).hexdigest(),
        "paths": svg.count("<path"),
        "animate": svg.count("<animate "),
        "bytes": len(svg),
    }
    check_json("mesh-morph.svg.json", root_info)


def gif_fingerprint(animation, **kw):
    from PIL import Image

    data = animation.to_bytes("gif", **kw)
    im = Image.open(io.BytesIO(data))
    frames = []
    for i in range(im.n_frames):
        im.seek(i)
        rgb = im.convert("RGB")
        stat = np.asarray(rgb.resize((4, 4))).reshape(-1, 3).mean(axis=0)
        frames.append({"duration_ms": im.info["duration"], "coarse_rgb": [round(v) for v in stat]})
    return {
        "size": list(im.size),
        "frames": len(frames),
        "loop": im.info.get("loop"),
        "comment": json.loads(im.info["comment"]),
        "per_frame": frames,
    }


@pytest.mark.parametrize("name", ["points-lines-shapes", "surface-orbit"])
def test_gif_structure_golden(name):
    pytest.importorskip("PIL")
    pytest.importorskip("matplotlib")
    fp = gif_fingerprint(FIX[name].animation(), width=80, height=60, fps=4)
    path = DATA / f"{name}.gif.json"
    if UPDATE or not path.exists():
        check_json(f"{name}.gif.json", fp)
        if not UPDATE:
            pytest.fail("created missing golden; review and commit it")
    gold = json.loads(path.read_text())
    for key in ("size", "frames", "loop", "comment"):
        assert fp[key] == gold[key], key
    for got, want in zip(fp["per_frame"], gold["per_frame"], strict=True):
        assert got["duration_ms"] == want["duration_ms"]
        # rendering differs by a few levels across platforms/font stacks: compare coarsely
        assert all(
            abs(a - b) <= 6 for a, b in zip(got["coarse_rgb"], want["coarse_rgb"], strict=True)
        ), (got, want)


def html_skeleton(animation, **kw):
    html = animation.to_bytes("html", **kw).decode()
    data = json.loads(re.search(r'id="kk-data">(.*?)</script>', html, re.S).group(1))
    data.pop("generator", None)  # the version string changes every release
    data.pop("traces", None)
    layout = data.pop("layout", None)
    frames = data.pop("frames", None)
    controls = re.findall(r'data-kk="([a-z]+)"', html)
    out = {
        "data": data,
        "controls": controls,
        "has_runtime": "window.kinetickit" in html,
        "external_refs": sorted(
            set(re.findall(r'<(?:script|link)[^>]+(?:src|href)="([^"]+)"', html))
        ),
    }
    if frames is not None:
        out["frame_count"] = len(frames)
        out["layout_keys"] = sorted(layout)
    return out


@needs_interactive
def test_html_2d_golden():
    check_json(
        "points-lines-shapes.html.json",
        html_skeleton(FIX["points-lines-shapes"].animation(), width=300, height=200),
    )


def test_html_3d_golden():
    pytest.importorskip("plotly")
    check_json(
        "surface-orbit.html.json",
        html_skeleton(FIX["surface-orbit"].animation(), width=300, height=200, fps=4),
    )
