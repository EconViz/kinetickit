"""KineticKit: a domain-neutral engine for precise, deterministic animation."""

from __future__ import annotations

from kinetickit import easing as ease
from kinetickit.errors import CapabilityError, ConfigurationError, KineticKitError, RenderError

__version__ = "0.1.0.dev0"

__all__ = [
    "CapabilityError",
    "ConfigurationError",
    "KineticKitError",
    "RenderError",
    "__version__",
    "ease",
]
