from __future__ import annotations

import importlib
import pkgutil

import pytest

import kinetickit

PUBLIC_PACKAGES = [
    "kinetickit",
    "kinetickit.accessibility",
    "kinetickit.animation",
    "kinetickit.conformance",
    "kinetickit.easing",
    "kinetickit.exporters",
    "kinetickit.geometry.three_d",
    "kinetickit.geometry.two_d",
    "kinetickit.guides",
    "kinetickit.interaction",
    "kinetickit.interpolation",
    "kinetickit.keyframes",
    "kinetickit.layout",
    "kinetickit.morph",
    "kinetickit.renderers",
    "kinetickit.scene",
    "kinetickit.scheduler",
    "kinetickit.styles",
    "kinetickit.timeline",
    "kinetickit.transitions",
    "kinetickit.tween",
    "kinetickit.typography",
]


@pytest.mark.parametrize("name", PUBLIC_PACKAGES)
def test_every_exported_name_exists_and_is_not_private(name):
    module = importlib.import_module(name)
    exported = getattr(module, "__all__", None)
    assert exported, f"{name} defines no __all__"
    for attr in exported:
        assert hasattr(module, attr), f"{name}.{attr}"
        assert not attr.startswith("_") or attr == "__version__"


def test_version_is_the_first_beta_of_one_zero():
    assert kinetickit.__version__ == "1.0.0b1"
    from importlib.metadata import version

    assert version("kinetickit") == "1.0.0b1"


def test_top_level_names_are_unique():
    assert len(kinetickit.__all__) == len(set(kinetickit.__all__))
    for name in kinetickit.__all__:
        assert hasattr(kinetickit, name)


def test_a_hello_world_uses_only_top_level_names(tmp_path):
    from kinetickit import Animation, Bounds2D, Point2D, Scene2D, Vec2, ease

    dot = Point2D(id="dot", position=Vec2(1, 1), size=8)
    scene = Scene2D(dot)
    scene = scene.bind({scene.camera.ref("view"): Bounds2D(Vec2(0, 0), Vec2(10, 10))})
    animation = Animation(
        scene, dot.animate.position.to(Vec2(9, 9), duration=1.0, easing=ease.out_cubic)
    )
    manifest = animation.save(tmp_path / "hello.svg", width=200, height=200)
    assert manifest.format == "svg" and manifest.details["animations"] >= 1


def test_no_public_module_name_is_a_third_party_library():
    banned = {"matplotlib", "plotly", "pillow", "pil"}
    names = {
        m.name.split(".")[-1].lower()
        for m in pkgutil.walk_packages(kinetickit.__path__, "kinetickit.")
    }
    public = {n for n in names if not n.startswith("_")}
    assert not public & banned
