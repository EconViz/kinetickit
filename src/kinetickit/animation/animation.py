"""The scene + motion facade."""

from __future__ import annotations

import importlib
from collections.abc import Iterator
from typing import Any

from kinetickit.animation.frame import Frame
from kinetickit.errors import ConfigurationError
from kinetickit.interpolation import DEFAULT_REGISTRY, InterpolatorRegistry
from kinetickit.scene.scene import SceneBase
from kinetickit.scheduler import FixedFPS, Scheduler
from kinetickit.timeline import Hold, Motion, Timeline


def _exporters() -> Any:
    """Late-bound so the animation facade has no static dependency on exporters."""
    return importlib.import_module("kinetickit.exporters")


class Animation:
    """An immutable pairing of a scene and a motion.

    Construction validates that every animated property exists on the scene with the declared
    type, and that an interpolator is available for it. Sampling never mutates the scene or
    creates renderer state.
    """

    def __init__(
        self,
        scene: SceneBase,
        motion: Motion | None = None,
        *,
        registry: InterpolatorRegistry = DEFAULT_REGISTRY,
        interactions: Any = None,
    ) -> None:
        if not isinstance(scene, SceneBase):
            raise ConfigurationError("Animation needs a Scene2D or Scene3D")
        self.scene = scene
        self.motion: Motion = motion if motion is not None else Hold(0.0)
        self.registry = registry
        self.timeline = Timeline(self.motion, scene.values(), registry)
        self.interactions = interactions
        if interactions is not None:
            interactions.validate(scene, self.timeline.markers, self.timeline.duration)
        for ref in self.timeline.properties:
            node = scene.find(ref.node_id)
            if node is None:
                raise ConfigurationError(f"motion targets unknown node {ref.node_id!r}")
            declared = node.animatable_properties().get(ref.path)
            if declared is None:
                raise ConfigurationError(f"{ref} is not an animatable property")
            if declared is not ref.value_type:
                raise ConfigurationError(
                    f"{ref} was declared {ref.value_type.__name__} but the node declares "
                    f"{declared.__name__}"
                )

    @property
    def duration(self) -> float:
        return self.timeline.duration

    def sample(self, t: float) -> Any:
        """The scene snapshot at time ``t`` (clamped to the final state past the end)."""
        return self.scene.bind(self.timeline.sample(t))

    def frames(self, schedule: int | Scheduler = 30) -> Iterator[Frame]:
        """Lazily yield frames. Only the current frame is held."""
        scheduler = FixedFPS(schedule) if isinstance(schedule, int) else schedule
        d = self.duration
        for i, t in enumerate(scheduler.times(d)):
            yield Frame(i, t, (t / d) if d > 0 else 0.0, self.sample(t))

    # -- output ------------------------------------------------------------------------
    def save(self, target: Any, *, renderer: str | None = None, **options: Any) -> Any:
        """Export to ``target`` (path, binary/text stream or destination).

        The format comes from ``renderer`` (``"vector"`` → SVG, ``"raster"`` → GIF,
        ``"interactive"`` → HTML) or the file suffix. Extra keyword arguments are the settings of
        the chosen exporter. Returns an :class:`~kinetickit.exporters.ExportManifest`.
        """
        return _exporters().export(self, target, renderer=renderer, **options)

    def to_bytes(self, format: str, **options: Any) -> bytes:
        """Render in memory and return the encoded bytes."""
        exporters = _exporters()
        dest = exporters.BytesDestination()
        exporters.export(self, dest, format=format, **options)
        data: bytes = dest.getvalue()
        return data

    def to_svg(self, **options: Any) -> str:
        """The native Animated SVG document as text."""
        return self.to_bytes("svg", **options).decode("utf-8")
