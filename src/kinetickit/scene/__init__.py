"""Immutable, backend-neutral scene model."""

from __future__ import annotations

from kinetickit.scene.node import Node, prop
from kinetickit.scene.scene import SceneBase, SceneValues
from kinetickit.scene.three_d import (
    Camera3D,
    DirectionalLight3D,
    Group3D,
    Line3D,
    Mesh3D,
    Node3D,
    Point3D,
    PointCloud3D,
    Polyline3D,
    Scene3D,
    Surface3D,
)
from kinetickit.scene.two_d import (
    Camera2D,
    Group2D,
    Line2D,
    Node2D,
    PathNode2D,
    Point2D,
    Scene2D,
    Shape2D,
    Text2D,
)

__all__ = [
    "Camera2D",
    "Camera3D",
    "DirectionalLight3D",
    "Group2D",
    "Group3D",
    "Line2D",
    "Line3D",
    "Mesh3D",
    "Node",
    "Node2D",
    "Node3D",
    "PathNode2D",
    "Point2D",
    "Point3D",
    "PointCloud3D",
    "Polyline3D",
    "Scene2D",
    "Scene3D",
    "SceneBase",
    "SceneValues",
    "Shape2D",
    "Surface3D",
    "Text2D",
    "prop",
]
