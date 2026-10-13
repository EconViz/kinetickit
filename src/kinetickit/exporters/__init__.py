"""Exporters own output orchestration: validation, destinations and manifests."""

from __future__ import annotations

from kinetickit.exporters.animated_svg import AnimatedSVGExporter
from kinetickit.exporters.destination import (
    BytesDestination,
    Destination,
    FileDestination,
    StreamDestination,
    as_destination,
)
from kinetickit.exporters.manifest import ExportManifest
from kinetickit.exporters.registry import available_formats, export, register_exporter

register_exporter("svg", AnimatedSVGExporter.from_options, replace=True)

__all__ = [
    "AnimatedSVGExporter",
    "BytesDestination",
    "Destination",
    "ExportManifest",
    "FileDestination",
    "StreamDestination",
    "as_destination",
    "available_formats",
    "export",
    "register_exporter",
]
