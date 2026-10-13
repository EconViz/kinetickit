"""A minimal SMIL evaluator used to prove SVG animations match the timeline."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from kinetickit.easing import CubicBezier

NS = {"s": "http://www.w3.org/2000/svg"}
Q = "{http://www.w3.org/2000/svg}"


def parse(text: str) -> ET.Element:
    return ET.fromstring(text.split("?>", 1)[1] if text.startswith("<?xml") else text)


def numbers(s: str) -> list[float]:
    return [float(x) for x in re.findall(r"-?\d*\.?\d+(?:e-?\d+)?", s)]


def _lerp(a: str, b: str, p: float) -> str:
    if a.startswith("#"):
        ra = [int(a[i : i + 2], 16) for i in (1, 3, 5)]
        rb = [int(b[i : i + 2], 16) for i in (1, 3, 5)]
        return "#" + "".join(f"{round(x + (y - x) * p):02x}" for x, y in zip(ra, rb, strict=True))
    # interpolate every number inside the string, keep the command letters of the first
    na, nb = numbers(a), numbers(b)
    if len(na) != len(nb):
        raise AssertionError(f"structure mismatch: {a!r} vs {b!r}")
    out = iter(x + (y - x) * p for x, y in zip(na, nb, strict=True))
    return re.sub(r"-?\d*\.?\d+(?:e-?\d+)?", lambda m: repr(next(out)), a)


def evaluate(anim: ET.Element, t: float) -> str:
    """Value of an <animate>/<animateTransform> at absolute time ``t`` (seconds)."""
    dur = float(anim.get("dur", "0s").rstrip("s"))
    values = anim.get("values", "").split(";")
    times = [float(x) for x in anim.get("keyTimes", "").split(";")]
    u = min(1.0, max(0.0, t / dur)) if dur else 1.0
    if anim.get("calcMode") == "discrete":
        idx = max(i for i, kt in enumerate(times) if kt <= u + 1e-12)
        return values[idx]
    linear = anim.get("calcMode") == "linear"
    splines = (
        []
        if linear
        else [tuple(float(x) for x in s.split()) for s in anim.get("keySplines", "").split(";")]
    )
    if u >= times[-1]:
        return values[-1]
    # the last interval whose start <= u (jumps share a time; the later knot wins)
    i = max(
        k
        for k in range(len(times) - 1)
        if times[k] <= u + 1e-12 and times[k + 1] > times[k] - 1e-12
    )
    while i + 1 < len(times) - 1 and times[i + 1] <= u + 1e-12 and times[i + 1] > times[i]:
        i += 1
    span = times[i + 1] - times[i]
    if span <= 0:
        return values[i + 1]
    local = (u - times[i]) / span
    p = local if linear else CubicBezier(*splines[i])(local)
    return _lerp(values[i], values[i + 1], p)


def animations_for(root: ET.Element, element_id: str, attribute: str) -> list[ET.Element]:
    el = next(e for e in root.iter() if e.get("id") == element_id)
    return [
        a
        for a in el
        if a.tag in (Q + "animate", Q + "animateTransform") and a.get("attributeName") == attribute
    ]


def find(root: ET.Element, element_id: str) -> ET.Element:
    return next(e for e in root.iter() if e.get("id") == element_id)


def layer_animations(el: ET.Element) -> list[ET.Element]:
    return [a for a in el if a.tag in (Q + "animate", Q + "animateTransform")]
