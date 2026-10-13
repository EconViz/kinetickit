"""Derive the capability requirements of an animation."""

from __future__ import annotations

from kinetickit.animation import Animation
from kinetickit.renderers.capabilities import DIM_2D, Requirements, require
from kinetickit.scene.scene import SceneBase

Z_ANIMATION = "z-animation"


def requirements_for(animation: Animation, *, outputs: tuple[str, ...] = ()) -> Requirements:
    """What the animation's scene and motion need, plus the requested output kinds."""
    scene: SceneBase = animation.scene
    geometry: set[str] = set()
    features: set[str] = set()
    for node in scene.walk():
        if node.kind != "camera":
            geometry.add(node.kind)
        if node.kind == "group" and getattr(node, "clip", None) is not None:
            features.add("clip")
    if scene.overlay:
        features.add("overlay")
    for ref in animation.timeline.properties:
        if ref.node_id == scene.camera.id:
            features.add("camera-animation")
        if ref.path == "z":
            features.add(Z_ANIMATION)
        if ref.path == "clip":
            features.add("clip-animation")
    dims = {DIM_2D} if scene.dimension == 2 else {"3d"}
    return require(dimensions=dims, geometry=geometry, features=features, outputs=outputs)
