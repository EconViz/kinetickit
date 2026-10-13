"""Immutable scene snapshots shared by the 2D and 3D scenes."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Any, ClassVar

from kinetickit.errors import ConfigurationError
from kinetickit.scene.node import Node
from kinetickit.timeline.property import PropertyRef


class SceneValues(Mapping[PropertyRef[Any], Any]):
    """The initial value of every animatable property of a scene, resolved lazily."""

    def __init__(self, scene: SceneBase) -> None:
        self._scene = scene

    def __getitem__(self, ref: PropertyRef[Any]) -> Any:
        node = self._scene.find(ref.node_id)
        if node is None or ref.path not in node.animatable_properties():
            raise KeyError(ref)
        return getattr(node, ref.path)

    def __iter__(self) -> Iterator[PropertyRef[Any]]:
        for node in self._scene.walk():
            for name, kind in node.animatable_properties().items():
                yield PropertyRef(node.id, name, kind)

    def __len__(self) -> int:
        return sum(len(n.animatable_properties()) for n in self._scene.walk())


class SceneBase:
    """World nodes, a screen-space overlay, and a camera.

    Scenes are immutable values: ``bind`` returns a new snapshot. Node ids are unique across the
    world, the overlay, nested groups, and the camera. Snapshots never hold backend objects.
    """

    dimension: ClassVar[int]
    camera_type: ClassVar[type[Node]]
    __slots__ = ("_frozen", "_index", "camera", "nodes", "overlay")
    nodes: tuple[Node, ...]
    overlay: tuple[Node, ...]
    camera: Node
    _index: dict[str, Node]
    _frozen: bool

    def __init__(
        self, *nodes: Node, overlay: tuple[Node, ...] | list[Node] = (), camera: Node | None = None
    ) -> None:
        cam = camera if camera is not None else self.camera_type(id="camera")
        object.__setattr__(self, "nodes", tuple(nodes))
        object.__setattr__(self, "overlay", tuple(overlay))
        object.__setattr__(self, "camera", cam)
        if not isinstance(cam, self.camera_type):
            raise ConfigurationError(f"camera must be a {self.camera_type.__name__}")
        for n in self.nodes:
            self._check_node(n, self.dimension, "world")
        for n in self.overlay:
            self._check_node(n, 2, "overlay")
        index: dict[str, Node] = {}
        for n in self.walk():
            if n.id in index:
                raise ConfigurationError(f"duplicate node id {n.id!r}")
            index[n.id] = n
        object.__setattr__(self, "_index", index)
        object.__setattr__(self, "_frozen", True)

    @staticmethod
    def _check_node(node: Node, dim: int, where: str) -> None:
        if not isinstance(node, Node):
            raise ConfigurationError(f"{type(node).__name__} is not a scene Node")
        if node.dimension != dim:
            raise ConfigurationError(
                f"{type(node).__name__} {node.id!r} is {node.dimension}D and cannot be in the "
                f"{dim}D {where}"
            )
        for child in node.children_nodes():
            SceneBase._check_node(child, dim, where)

    def __setattr__(self, name: str, value: object) -> None:
        if getattr(self, "_frozen", False):
            raise AttributeError(f"{type(self).__name__} is immutable")
        object.__setattr__(self, name, value)

    # -- queries -----------------------------------------------------------------------
    def walk(self) -> Iterator[Node]:
        """Every node: world (depth-first), overlay, then the camera."""

        def visit(node: Node) -> Iterator[Node]:
            yield node
            for child in node.children_nodes():
                yield from visit(child)

        for n in self.nodes:
            yield from visit(n)
        for n in self.overlay:
            yield from visit(n)
        yield self.camera

    @property
    def ids(self) -> tuple[str, ...]:
        return tuple(self._index)

    def find(self, node_id: str) -> Node | None:
        return self._index.get(node_id)

    def get(self, node_id: str) -> Node:
        node = self._index.get(node_id)
        if node is None:
            raise ConfigurationError(f"no node with id {node_id!r}")
        return node

    def __contains__(self, node_id: object) -> bool:
        return node_id in self._index

    def values(self) -> SceneValues:
        return SceneValues(self)

    # -- snapshots ---------------------------------------------------------------------
    def bind(self, values: Mapping[PropertyRef[Any], Any]) -> Any:
        """Return a new snapshot with the given property values applied."""
        if not values:
            return self
        changes: dict[str, dict[str, Any]] = {}
        for ref, value in values.items():
            node = self.find(ref.node_id)
            if node is None:
                raise ConfigurationError(f"cannot bind {ref}: no node {ref.node_id!r}")
            if ref.path not in node.animatable_properties():
                raise ConfigurationError(f"cannot bind {ref}: {ref.path!r} is not animatable")
            changes.setdefault(ref.node_id, {})[ref.path] = value

        def rebuild(node: Node) -> Node:
            kids = node.children_nodes()
            if kids:
                new_kids = tuple(rebuild(k) for k in kids)
                if any(a is not b for a, b in zip(kids, new_kids, strict=True)):
                    node = node.with_children(new_kids)
            if node.id in changes:
                node = node.replace(**changes[node.id])
            return node

        cam = rebuild(self.camera)
        return type(self)(
            *(rebuild(n) for n in self.nodes),
            overlay=tuple(rebuild(n) for n in self.overlay),
            camera=cam,
        )

    def with_nodes(self, *nodes: Node) -> Any:
        return type(self)(*nodes, overlay=self.overlay, camera=self.camera)

    def with_overlay(self, *nodes: Node) -> Any:
        return type(self)(*self.nodes, overlay=nodes, camera=self.camera)

    def __eq__(self, other: object) -> bool:
        return (
            type(other) is type(self)
            and self.nodes == other.nodes
            and self.overlay == other.overlay
            and self.camera == other.camera
        )

    def __hash__(self) -> int:
        return hash((type(self), self.nodes, self.overlay, self.camera))

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}({len(self.nodes)} nodes, {len(self.overlay)} overlay, "
            f"camera={self.camera.id!r})"
        )
