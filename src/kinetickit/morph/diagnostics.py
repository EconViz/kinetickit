"""Diagnostics explaining automatic morph and transition decisions."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MorphDiagnostic:
    """One decision or problem found while matching or normalizing.

    ``severity`` is ``"info"`` (a decision worth recording), ``"warning"`` (ambiguous or lossy)
    or ``"error"`` (the pair cannot be morphed automatically).
    """

    code: str
    message: str
    severity: str = "info"
    node_id: str | None = None
    property: str | None = None

    def __post_init__(self) -> None:
        if self.severity not in ("info", "warning", "error"):
            raise ValueError(f"unknown severity {self.severity!r}")

    def for_target(self, node_id: str, property: str | None = None) -> MorphDiagnostic:
        return MorphDiagnostic(self.code, self.message, self.severity, node_id, property)

    def __str__(self) -> str:
        where = (
            f" [{self.node_id}{'.' + self.property if self.property else ''}]"
            if self.node_id
            else ""
        )
        return f"{self.severity}: {self.code}{where}: {self.message}"
