"""Renderer lookup by capability name, with lazy loading of optional implementations."""

from __future__ import annotations

from collections.abc import Callable

from kinetickit.errors import CapabilityError, ConfigurationError
from kinetickit.renderers.protocol import Renderer

Factory = Callable[[], Renderer]
_FACTORIES: dict[str, Factory] = {}
_EXTRAS = {"raster": "raster", "interactive": "interactive"}


def register_renderer(name: str, factory: Factory, *, replace: bool = False) -> None:
    """Register a renderer under a capability name; third parties extend KineticKit here."""
    if name in _FACTORIES and not replace:
        raise ConfigurationError(f"renderer {name!r} is already registered")
    _FACTORIES[name] = factory


def available_renderers() -> tuple[str, ...]:
    return tuple(sorted(_FACTORIES))


def get_renderer(name: str) -> Renderer:
    try:
        factory = _FACTORIES[name]
    except KeyError:
        raise ConfigurationError(
            f"unknown renderer {name!r}; available: {', '.join(available_renderers())}"
        ) from None
    try:
        renderer = factory()
    except ImportError as exc:
        extra = _EXTRAS.get(name)
        hint = f" Install it with: pip install 'kinetickit[{extra}]'." if extra else ""
        raise CapabilityError(
            f"the {name!r} renderer is unavailable ({exc}).{hint}", missing=(f"renderer:{name}",)
        ) from exc
    if not isinstance(renderer, Renderer):
        raise ConfigurationError(f"renderer {name!r} does not implement the Renderer protocol")
    return renderer
