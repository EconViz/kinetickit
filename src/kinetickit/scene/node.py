"""Immutable scene nodes with stable identity and declared animatable properties."""

from __future__ import annotations

import math
from dataclasses import dataclass, field, fields, replace
from typing import Any, ClassVar

from kinetickit.easing import Easing, linear
from kinetickit.errors import ConfigurationError
from kinetickit.morph import normalize_pair
from kinetickit.timeline import Motion
from kinetickit.timeline.property import PropertyRef
from kinetickit.tween import Tween
from kinetickit.tween.property import PropertyBuilder


def prop(default: Any, value_type: type, *, optional: bool = False, animatable: bool = True) -> Any:
    """Declare a node field with its value type, optionality and animatability."""
    return field(
        default=default,
        metadata={"type": value_type, "optional": optional, "animatable": animatable},
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class Node:
    """Base of every scene node.

    ``id`` is the stable identity used for animation targeting and scene transitions.
    Fields declared with :func:`prop` are coerced to their declared type on construction.
    """

    kind: ClassVar[str] = "node"
    dimension: ClassVar[int] = 2

    id: str
    opacity: float = prop(1.0, float)
    z: float = prop(0.0, float)
    visible: bool = prop(True, bool)

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id:
            raise ConfigurationError("a node id must be a non-empty string")
        for f in fields(self):
            declared = f.metadata.get("type")
            if declared is None:
                continue
            value = getattr(self, f.name)
            if value is None:
                if not f.metadata.get("optional"):
                    raise ConfigurationError(f"{self.id}.{f.name} cannot be None")
                continue
            ref: PropertyRef[Any] = PropertyRef(self.id, f.name, declared)
            coerced = ref.coerce(value)
            if coerced is not value:
                object.__setattr__(self, f.name, coerced)
            if declared is float and not math.isfinite(coerced):
                raise ConfigurationError(f"{self.id}.{f.name} must be finite, got {value!r}")
        self._validate()

    def _validate(self) -> None:  # pragma: no cover - overridden
        """Hook for subclass invariants."""

    # -- introspection -----------------------------------------------------------------
    @classmethod
    def animatable_properties(cls) -> dict[str, type]:
        return {
            f.name: f.metadata["type"]
            for f in fields(cls)
            if f.metadata.get("animatable") and "type" in f.metadata
        }

    def ref(self, name: str) -> PropertyRef[Any]:
        props = self.animatable_properties()
        if name not in props:
            raise ConfigurationError(
                f"{type(self).__name__} has no animatable property {name!r}; "
                f"available: {', '.join(sorted(props))}"
            )
        return PropertyRef(self.id, name, props[name])

    @property
    def animate(self) -> AnimateProxy:
        """``node.animate.<property>`` returns a builder for immutable motions."""
        return AnimateProxy(self)

    def morph_property(
        self,
        name: str,
        target: Any,
        *,
        duration: float,
        easing: Easing = linear,
        spec: Any = None,
    ) -> Motion:
        """Morph one property to ``target`` or fail loudly; never fall back silently.

        The pair is normalized with the registered normalizer for the property's type; incompatible
        values raise with the diagnostics instead of producing corrupted geometry. ``spec`` carries
        the explicit correspondence (``PathMorph``, ``MeshMorph``, ``SurfaceMorph``).
        """
        ref = self.ref(name)
        end = ref.coerce(target)
        pair = normalize_pair(ref.value_type, getattr(self, name), end, spec)
        if not pair.compatible:
            reasons = "; ".join(d.message for d in pair.diagnostics if d.severity == "error")
            raise ConfigurationError(
                f"cannot morph {self.id}.{name} automatically ({reasons}). Pass an explicit "
                "correspondence spec, or cross-fade with a SceneTransition."
            )
        return Tween(ref, pair.end, duration, easing, pair.start)

    def children_nodes(self) -> tuple[Node, ...]:
        return ()

    def with_children(self, children: tuple[Node, ...]) -> Node:
        raise ConfigurationError(f"{type(self).__name__} cannot hold children")

    def replace(self, **changes: Any) -> Node:
        return replace(self, **changes)


class AnimateProxy:
    __slots__ = ("_node",)

    def __init__(self, node: Node) -> None:
        self._node = node

    def __getattr__(self, name: str) -> PropertyBuilder:
        if name.startswith("_"):
            raise AttributeError(name)
        try:
            return PropertyBuilder(self._node.ref(name))
        except ConfigurationError as exc:
            raise AttributeError(str(exc)) from None

    def __dir__(self) -> list[str]:
        return sorted(self._node.animatable_properties())
