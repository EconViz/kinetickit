from __future__ import annotations

import pytest

from kinetickit.animation import Animation
from kinetickit.errors import CapabilityError, ConfigurationError
from kinetickit.geometry.two_d import Bounds2D
from kinetickit.renderers import (
    RendererCapabilities,
    available_renderers,
    get_renderer,
    register_renderer,
    require,
    requirements_for,
)
from kinetickit.renderers.capabilities import DIM_2D, DIM_NATIVE_3D, DIM_PROJECTED_3D
from kinetickit.renderers.protocol import DocumentRenderer, Renderer
from kinetickit.scene import Group2D, Point2D, Scene2D


def test_requirements_follow_scene_content():
    scene = Scene2D(
        Group2D(id="g", clip=Bounds2D((0, 0), (1, 1)), children=(Point2D(id="p"),)),
        overlay=[Point2D(id="hud")],
    )
    req = requirements_for(Animation(scene))
    assert req.dimensions == {DIM_2D}
    assert {"point", "group"} <= req.geometry
    assert {"clip", "overlay"} <= req.features
    assert "camera" not in req.geometry


def test_animated_cameras_and_z_become_features():
    p = Point2D(id="p")
    scene = Scene2D(p)
    cam = scene.camera.animate.zoom.to(2.0, duration=1).with_(p.animate.z.to(1.0, duration=1))
    req = requirements_for(Animation(scene, cam))
    assert {"camera-animation", "z-animation"} <= req.features


def test_validation_lists_every_missing_capability_with_hints():
    caps = RendererCapabilities(
        "tiny", dimensions=frozenset({DIM_2D}), geometry=frozenset({"point"})
    )
    with pytest.raises(CapabilityError) as info:
        caps.validate(require(geometry=["point", "mesh"], features=["clip"], interactions=["drag"]))
    err = info.value
    assert set(err.missing) == {"geometry:mesh", "feature:clip", "interaction:drag"}
    assert "'tiny'" in str(err) and "meshes need a 3D-capable renderer" in str(err)
    caps.validate(require(geometry=["point"]))  # satisfied -> no error


def test_generic_3d_requirement_accepts_projected_or_native():
    projected = RendererCapabilities("a", dimensions=frozenset({DIM_PROJECTED_3D}))
    native = RendererCapabilities("b", dimensions=frozenset({DIM_NATIVE_3D}))
    flat = RendererCapabilities("c", dimensions=frozenset({DIM_2D}))
    need = require(dimensions=["3d"])
    projected.validate(need)
    native.validate(need)
    with pytest.raises(CapabilityError):
        flat.validate(need)
    with pytest.raises(CapabilityError):
        projected.validate(require(dimensions=[DIM_NATIVE_3D]))


def test_vector_is_registered_and_implements_the_protocol():
    assert "vector" in available_renderers()
    renderer = get_renderer("vector")
    assert isinstance(renderer, Renderer) and isinstance(renderer, DocumentRenderer)
    assert renderer.capabilities.name == "vector"


def test_unknown_renderer_and_missing_extra_have_actionable_errors():
    with pytest.raises(ConfigurationError, match="available"):
        get_renderer("nope")

    def broken():
        raise ImportError("No module named 'fancy'")

    register_renderer("fancy", broken, replace=True)
    with pytest.raises(CapabilityError, match="unavailable"):
        get_renderer("fancy")
    with pytest.raises(ConfigurationError):
        register_renderer("vector", broken)


def test_new_renderers_register_without_touching_the_core():
    class Mine:
        capabilities = RendererCapabilities("mine", dimensions=frozenset({DIM_2D}))

    register_renderer("mine", Mine, replace=True)
    assert get_renderer("mine").capabilities.name == "mine"


def test_public_capability_names_do_not_name_third_party_libraries():
    for name in available_renderers():
        assert name.lower() not in {"matplotlib", "plotly", "pillow"}
