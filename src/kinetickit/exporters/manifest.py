"""What an export produced and what it preserved or degraded."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ExportManifest:
    """The outcome of an export.

    ``preserved`` and ``degraded`` document semantic fidelity (for example accessibility
    metadata); ``warnings`` list lossy or sampled encodings; ``network_dependencies`` lists every
    external URL the artifact needs (empty for fully offline output).
    """

    format: str
    renderer: str
    destination: str | None
    width: float | None = None
    height: float | None = None
    duration: float = 0.0
    frames: int | None = None
    bytes_written: int = 0
    description: str | None = None
    representative_frame: bytes | None = None
    warnings: tuple[str, ...] = ()
    preserved: tuple[str, ...] = ()
    degraded: tuple[str, ...] = ()
    network_dependencies: tuple[str, ...] = ()
    details: dict[str, Any] = field(default_factory=dict)
