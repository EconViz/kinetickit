"""The scheduler extension protocol: which times to evaluate, never how to render them."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol, runtime_checkable


@runtime_checkable
class Scheduler(Protocol):
    """Produces an ordered stream of evaluation times for a timeline of a given duration."""

    def times(self, duration: float) -> Iterator[float]: ...
