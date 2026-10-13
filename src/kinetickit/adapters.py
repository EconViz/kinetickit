"""Turn any object model into KineticKit scenes through a plain function.

KineticKit never needs to know a consumer's classes. An *adapter* is a callable that maps one
domain object to scene nodes; :func:`adapt` collects them into a scene and :func:`transition`
animates between two states of the same domain model (matching only by the stable ids the adapter
assigns).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any, Protocol, TypeVar, runtime_checkable

from kinetickit.errors import ConfigurationError
from kinetickit.scene.node import Node
from kinetickit.scene.scene import SceneBase
from kinetickit.scene.three_d import Camera3D, Scene3D
from kinetickit.scene.two_d import Scene2D
from kinetickit.transitions import SceneTransition, Transition

T = TypeVar("T")
T_contra = TypeVar("T_contra", contravariant=True)


@runtime_checkable
class SceneAdapter(Protocol[T_contra]):
    """Maps one domain object to the scene nodes that depict it."""

    def __call__(self, obj: T_contra) -> Iterable[Node]: ...


def adapt(
    objects: Iterable[T],
    adapter: Callable[[T], Iterable[Node]],
    *,
    overlay: Iterable[Node] = (),
    camera: Node | None = None,
    dimension: int = 2,
) -> SceneBase:
    """Build a scene from domain objects. Ids must be unique across everything the adapter makes."""
    nodes: list[Node] = []
    for obj in objects:
        produced = adapter(obj)
        if isinstance(produced, Node):
            produced = (produced,)
        nodes.extend(produced)
    if dimension == 2:
        return Scene2D(*nodes, overlay=tuple(overlay), camera=camera)
    if dimension == 3:
        return Scene3D(*nodes, overlay=tuple(overlay), camera=camera or Camera3D())
    raise ConfigurationError("dimension must be 2 or 3")


def transition(
    before: Iterable[T],
    after: Iterable[T],
    adapter: Callable[[T], Iterable[Node]],
    **options: Any,
) -> Transition:
    """Animate between two states of a domain model; objects match by their adapted node ids."""
    dim = options.pop("dimension", 2)
    camera = options.pop("camera", None)
    a = adapt(before, adapter, dimension=dim, camera=camera)
    b = adapt(after, adapter, dimension=dim, camera=camera)
    return SceneTransition.between(a, b, **options)


__all__ = ["SceneAdapter", "adapt", "transition"]
