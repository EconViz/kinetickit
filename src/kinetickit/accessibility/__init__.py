"""Accessibility metadata, reduced-motion policy and reading order."""

from __future__ import annotations

from kinetickit.accessibility.focus import reading_order
from kinetickit.accessibility.info import AccessibilityInfo, ReducedMotion
from kinetickit.accessibility.report import semantic_report
from kinetickit.accessibility.semantics import ROLES, Semantics

__all__ = [
    "ROLES",
    "AccessibilityInfo",
    "ReducedMotion",
    "Semantics",
    "reading_order",
    "semantic_report",
]
