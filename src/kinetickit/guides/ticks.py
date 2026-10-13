"""Tick generation."""

from __future__ import annotations

import math

from kinetickit.errors import ConfigurationError


def nice_ticks(lo: float, hi: float, count: int = 5) -> tuple[float, ...]:
    """Round tick values (steps of 1, 2 or 5 times a power of ten) inside ``[lo, hi]``."""
    if not (math.isfinite(lo) and math.isfinite(hi)) or hi < lo:
        raise ConfigurationError(f"invalid tick range [{lo}, {hi}]")
    if count < 1:
        raise ConfigurationError("tick count must be at least 1")
    if hi == lo:
        return (lo,)
    raw = (hi - lo) / count
    mag = 10 ** math.floor(math.log10(raw))
    step = next(m * mag for m in (1, 2, 5, 10) if m * mag >= raw)
    first = math.ceil(lo / step - 1e-9) * step
    n = math.floor((hi - first) / step + 1e-9) + 1
    return tuple(round(first + i * step, 12) for i in range(n))


def format_tick(value: float) -> str:
    text = f"{value:.10g}"
    return "0" if text in ("-0", "0") else text
