"""Automatic scene-to-scene transitions keyed only by stable node ids."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from kinetickit.easing import Easing, in_out_cubic
from kinetickit.errors import ConfigurationError
from kinetickit.interpolation import DEFAULT_REGISTRY, InterpolatorRegistry
from kinetickit.morph import MorphDiagnostic
from kinetickit.scene.scene import SceneBase
from kinetickit.timeline import Motion
from kinetickit.timeline.time import check_duration

if TYPE_CHECKING:
    from kinetickit.animation import Animation

ENTER_POLICIES = ("fade", "cut", "draw")
EXIT_POLICIES = ("fade", "cut", "hold", "draw")
INCOMING_SUFFIX = ":in"


@dataclass(frozen=True, slots=True)
class TransitionPolicy:
    """What happens to nodes present in only one of the two scenes.

    ``enter``: ``fade`` (default) from opacity 0, ``cut`` (present immediately) or ``draw``
    (``draw_progress`` 0 → target, falling back to fade). ``exit``: ``fade`` (default),
    ``cut`` (removed immediately), ``hold`` (visible until the transition ends) or ``draw``.
    """

    enter: str = "fade"
    exit: str = "fade"

    def __post_init__(self) -> None:
        if self.enter not in ENTER_POLICIES:
            raise ConfigurationError(f"enter policy must be one of {ENTER_POLICIES}")
        if self.exit not in EXIT_POLICIES:
            raise ConfigurationError(f"exit policy must be one of {EXIT_POLICIES}")


@dataclass(frozen=True)
class Transition:
    """The result of :meth:`SceneTransition.between`.

    ``scene`` is the scene to animate: the source scene plus entering nodes (hidden until they
    animate in). ``motion`` plays the transition; ``diagnostics`` explains every automatic
    decision, including ambiguous or fallback ones.
    """

    scene: SceneBase
    motion: Motion
    diagnostics: tuple[MorphDiagnostic, ...] = field(default=())
    duration: float = 0.0

    def animation(self) -> Animation:
        from kinetickit.animation import Animation

        return Animation(self.scene, self.motion)

    @property
    def warnings(self) -> tuple[MorphDiagnostic, ...]:
        return tuple(d for d in self.diagnostics if d.severity != "info")


class SceneTransition:
    """Builds transitions between two scenes of the same dimension.

    Defaults: matched ids animate every changed animatable property over 300 ms with
    ``in_out_cubic``; unmatched nodes fade; a type change cross-fades (the incoming node's id gets
    the ``:in`` suffix during the transition); paths morph only when the normalizer finds a
    compatible pairing, otherwise they cross-fade with a diagnostic. Labels, insertion order,
    geometric proximity and visual similarity are never used for matching.
    """

    @staticmethod
    def between(
        source: SceneBase,
        target: SceneBase,
        *,
        duration: float = 0.3,
        easing: Easing = in_out_cubic,
        policy: TransitionPolicy | None = None,
        overrides: Motion | Iterable[Motion] | None = None,
        morphs: Mapping[str, Any] | None = None,
        registry: InterpolatorRegistry = DEFAULT_REGISTRY,
    ) -> Transition:
        from kinetickit.transitions.compiler import compile_transition

        if type(source) is not type(target):
            raise ConfigurationError(
                f"cannot transition between {type(source).__name__} and {type(target).__name__}"
            )
        if overrides is None:
            override_list: tuple[Motion, ...] = ()
        elif isinstance(overrides, Motion):
            override_list = (overrides,)
        else:
            override_list = tuple(overrides)
        return compile_transition(
            source,
            target,
            duration=check_duration(duration),
            easing=easing,
            policy=policy or TransitionPolicy(),
            overrides=override_list,
            morphs=dict(morphs or {}),
            registry=registry,
        )
