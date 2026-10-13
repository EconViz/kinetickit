"""Self-contained interactive HTML export."""

from __future__ import annotations

from typing import Any

from kinetickit.animation import Animation
from kinetickit.exporters.destination import Destination, as_destination
from kinetickit.exporters.manifest import ExportManifest
from kinetickit.renderers import get_renderer, requirements_for
from kinetickit.renderers.capabilities import OUT_INTERACTIVE_DOCUMENT
from kinetickit.renderers.interactive import HtmlSettings


class HTMLExporter:
    format = "html"
    renderer = "interactive"

    def __init__(self, settings: HtmlSettings | None = None) -> None:
        self.settings = settings or HtmlSettings()

    @classmethod
    def from_options(cls, **options: Any) -> HTMLExporter:
        return cls(HtmlSettings(**options))

    def export(self, animation: Animation, target: Any) -> ExportManifest:
        renderer = get_renderer("interactive")
        renderer.capabilities.validate(
            requirements_for(animation, outputs=(OUT_INTERACTIVE_DOCUMENT,))
        )
        document = renderer.render_document(animation, self.settings)  # type: ignore[attr-defined]
        dest: Destination = as_destination(target)
        data = document.to_bytes()
        with dest.open_binary() as out:
            out.write(data)
        return ExportManifest(
            format="html",
            renderer="interactive",
            destination=dest.description,
            width=document.width,
            height=document.height,
            duration=document.duration,
            bytes_written=len(data),
            description=self.settings.description,
            warnings=document.warnings,
            network_dependencies=document.network_dependencies,
            preserved=document.preserved,
            degraded=document.degraded,
            details={
                "dimension": document.dimension,
                "packaging": self.settings.packaging,
                "element_ids": document.element_ids,
            },
        )
