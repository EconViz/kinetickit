"""Exporter lookup by format and the shared ``export`` entry point."""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

from kinetickit.errors import ConfigurationError

ExporterFactory = Callable[..., Any]
_EXPORTERS: dict[str, ExporterFactory] = {}
_RENDERER_FORMAT = {"vector": "svg", "raster": "gif", "interactive": "html"}


def register_exporter(format: str, factory: ExporterFactory, *, replace: bool = False) -> None:
    if format in _EXPORTERS and not replace:
        raise ConfigurationError(f"exporter for {format!r} is already registered")
    _EXPORTERS[format] = factory


def available_formats() -> tuple[str, ...]:
    return tuple(sorted(_EXPORTERS))


def resolve_format(target: Any, renderer: str | None, format: str | None) -> str:
    if format:
        return format.lower().lstrip(".")
    if renderer:
        if renderer not in _RENDERER_FORMAT:
            raise ConfigurationError(f"no default format for renderer {renderer!r}")
        return _RENDERER_FORMAT[renderer]
    if isinstance(target, (str, os.PathLike)):
        suffix = os.path.splitext(os.fspath(target))[1].lower().lstrip(".")
        if suffix:
            return suffix
    raise ConfigurationError("cannot infer the output format; pass renderer= or format=")


def export(
    animation: Any,
    target: Any,
    *,
    renderer: str | None = None,
    format: str | None = None,
    **options: Any,
) -> Any:
    fmt = resolve_format(target, renderer, format)
    if fmt not in _EXPORTERS:
        raise ConfigurationError(
            f"unknown output format {fmt!r}; available: {', '.join(available_formats())}"
        )
    exporter = _EXPORTERS[fmt](**options)
    if renderer is not None and getattr(exporter, "renderer", renderer) != renderer:
        raise ConfigurationError(
            f"format {fmt!r} is produced by the {exporter.renderer!r} renderer, not {renderer!r}"
        )
    return exporter.export(animation, target)
