"""Reading and focus order."""

from __future__ import annotations

from kinetickit.scene.node import Node
from kinetickit.scene.scene import SceneBase


def reading_order(scene: SceneBase) -> tuple[Node, ...]:
    """Objects that carry semantics, in reading order.

    Ranked objects come first (ascending ``reading_order``, ties in scene order), then the rest in
    scene order. Hidden (decorative) objects are excluded.
    """
    items = [
        (i, n)
        for i, n in enumerate(scene.walk())
        if n.semantics is not None and not n.semantics.hidden and not n.semantics.is_empty
    ]
    ranked = sorted(
        (p for p in items if p[1].semantics.reading_order is not None),
        key=lambda p: (p[1].semantics.reading_order, p[0]),
    )
    rest = [p for p in items if p[1].semantics.reading_order is None]
    return tuple(n for _, n in ranked + rest)
