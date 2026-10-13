"""Sampled frames."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class Frame:
    """One evaluated moment: its index, time, normalized progress and scene snapshot."""

    index: int
    time: float
    progress: float
    snapshot: Any
