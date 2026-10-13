"""Native Animated SVG export."""

from __future__ import annotations

from typing import Any

from kinetickit.accessibility import semantic_report
from kinetickit.animation import Animation
from kinetickit.exporters.destination import Destination, as_destination
from kinetickit.exporters.manifest import ExportManifest
from kinetickit.interaction import Degradation, plan_interactions
from kinetickit.renderers import get_renderer, requirements_for
from kinetickit.renderers.capabilities import OUT_ANIMATED_DOCUMENT, OUT_VECTOR_DOCUMENT
from kinetickit.renderers.vector import SvgSettings


class AnimatedSVGExporter:
    """Validates capabilities first, renders natively, then writes atomically."""

    format = "svg"
    renderer = "vector"

    def __init__(self, settings: SvgSettings | None = None) -> None:
        self.settings = settings or SvgSettings()

    @classmethod
    def from_options(cls, **options: Any) -> AnimatedSVGExporter:
        return cls(SvgSettings(**options))

    def export(self, animation: Animation, target: Any) -> ExportManifest:
        renderer = get_renderer("vector")
        outputs = (OUT_ANIMATED_DOCUMENT if animation.duration > 0 else OUT_VECTOR_DOCUMENT,)
        renderer.capabilities.validate(requirements_for(animation, outputs=outputs))
        plan = plan_interactions(
            animation.interactions, renderer.capabilities, Degradation(self.settings.degradation)
        )
        document = renderer.render_document(animation, self.settings)  # type: ignore[attr-defined]
        sem_kept, sem_lost = semantic_report(animation, "svg", self.settings)
        dest: Destination = as_destination(target)
        data = document.to_bytes()
        with dest.open_binary() as out:
            out.write(data)
        return ExportManifest(
            format="svg",
            renderer="vector",
            destination=dest.description,
            width=document.width,
            height=document.height,
            duration=document.duration,
            bytes_written=len(data),
            description=self.settings.description,
            warnings=document.warnings,
            preserved=plan.preserved + sem_kept,
            degraded=plan.degraded + sem_lost,
            details={
                "element_ids": document.element_ids,
                "animations": document.animation_count,
                "fonts": document.fonts,
            },
        )
