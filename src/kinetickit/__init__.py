"""KineticKit: a domain-neutral engine for precise, deterministic 2D and 3D animation.

The names exported here are the everyday API. Capability-specific pieces (guides, layout,
renderers, exporters, conformance) live in their own subpackages.
"""

from __future__ import annotations

from kinetickit import easing as ease
from kinetickit.accessibility import AccessibilityInfo, ReducedMotion, Semantics
from kinetickit.animation import Animation, Frame
from kinetickit.errors import CapabilityError, ConfigurationError, KineticKitError, RenderError
from kinetickit.geometry.three_d import MeshData, Quaternion, SurfaceGrid, Transform3D, Vec3
from kinetickit.geometry.two_d import Bounds2D, Path2D, Transform2D, Vec2
from kinetickit.interaction import Binding, Event, InteractionSpec
from kinetickit.interpolation import Color
from kinetickit.keyframes import Keyframe, Keyframes
from kinetickit.scene import (
    Camera2D,
    Camera3D,
    DirectionalLight3D,
    Group2D,
    Group3D,
    Line2D,
    Line3D,
    Mesh3D,
    PathNode2D,
    Point2D,
    Point3D,
    PointCloud3D,
    Polyline3D,
    Scene2D,
    Scene3D,
    Shape2D,
    Surface3D,
    Text2D,
)
from kinetickit.styles import ColorScale, Material, MinimalTheme
from kinetickit.timeline import Motion, PropertyRef, Timeline
from kinetickit.transitions import SceneTransition, TransitionPolicy
from kinetickit.typography import FontResource, GlyphShape, TextAsset

__version__ = "1.0.0b2"

__all__ = [
    "AccessibilityInfo",
    "Animation",
    "Binding",
    "Bounds2D",
    "Camera2D",
    "Camera3D",
    "CapabilityError",
    "Color",
    "ColorScale",
    "ConfigurationError",
    "DirectionalLight3D",
    "Event",
    "FontResource",
    "Frame",
    "GlyphShape",
    "Group2D",
    "Group3D",
    "InteractionSpec",
    "Keyframe",
    "Keyframes",
    "KineticKitError",
    "Line2D",
    "Line3D",
    "Material",
    "Mesh3D",
    "MeshData",
    "MinimalTheme",
    "Motion",
    "Path2D",
    "PathNode2D",
    "Point2D",
    "Point3D",
    "PointCloud3D",
    "Polyline3D",
    "PropertyRef",
    "Quaternion",
    "ReducedMotion",
    "RenderError",
    "Scene2D",
    "Scene3D",
    "SceneTransition",
    "Semantics",
    "Shape2D",
    "Surface3D",
    "SurfaceGrid",
    "Text2D",
    "TextAsset",
    "Timeline",
    "Transform2D",
    "Transform3D",
    "TransitionPolicy",
    "Vec2",
    "Vec3",
    "__version__",
    "ease",
]
