"""Typed errors raised by KineticKit."""

from __future__ import annotations


class KineticKitError(Exception):
    """Base class for every error raised deliberately by KineticKit."""


class ConfigurationError(KineticKitError, ValueError):
    """An argument, setting, or specification is invalid."""


class CapabilityError(KineticKitError):
    """A requested behavior is not supported by the selected renderer or exporter."""

    def __init__(self, message: str, *, missing: tuple[str, ...] = ()) -> None:
        super().__init__(message)
        self.missing = missing


class RenderError(KineticKitError):
    """A renderer or exporter failed while producing output."""


__all__ = ["CapabilityError", "ConfigurationError", "KineticKitError", "RenderError"]
