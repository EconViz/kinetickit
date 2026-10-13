"""The ``interactive`` renderer capability: one self-contained HTML document."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any
from xml.sax.saxutils import escape, quoteattr

from kinetickit import __version__
from kinetickit.animation import Animation
from kinetickit.errors import CapabilityError, ConfigurationError
from kinetickit.interaction import Degradation, PlaybackControls, plan_interactions
from kinetickit.interpolation import Color
from kinetickit.renderers.capabilities import (
    DIM_2D,
    DIM_NATIVE_3D,
    OUT_INTERACTIVE_DOCUMENT,
    RendererCapabilities,
)
from kinetickit.renderers.interactive.runtime import RUNTIME_CSS, RUNTIME_JS
from kinetickit.renderers.vector import SvgSettings, VectorRenderer
from kinetickit.scene import Scene2D, Scene3D
from kinetickit.styles import MinimalTheme, Theme

INTERACTIVE_CAPABILITIES = RendererCapabilities(
    name="interactive",
    dimensions=frozenset({DIM_2D, DIM_NATIVE_3D}),
    geometry=frozenset(
        {"point", "line", "path", "shape", "group", "text"}
        | {"point3d", "pointcloud", "line3d", "polyline3d", "mesh", "surface", "group3d", "light"}
    ),
    features=frozenset({"clip", "overlay", "camera-animation", "draw-progress"}),
    outputs=frozenset({OUT_INTERACTIVE_DOCUMENT}),
    interactions=frozenset({"hover", "click", "dblclick", "focus", "select", "camera", "playback"}),
    notes=(
        "2D embeds the native Animated SVG and drives its timeline; 3D uses a private plotting "
        "runtime with pre-sampled frames and native camera interaction.",
    ),
)

PACKAGING = ("offline", "compact")


@dataclass(frozen=True)
class HtmlSettings:
    """Options for the self-contained interactive document (sizes are logical pixels).

    ``packaging``: ``"offline"`` embeds every runtime asset (no network, ever); ``"compact"``
    references a pinned CDN copy of the 3D runtime instead (smaller file, declared network
    dependency; 2D output is always fully self-contained).
    """

    width: float = 800.0
    height: float = 500.0
    packaging: str = "offline"
    autoplay: bool = True
    loop: bool = False
    speed: float = 1.0
    controls: bool | PlaybackControls = True
    degradation: str = "drop"
    fps: int = 30
    max_frames: int = 900
    precision: int = 4
    samples: int = 24
    show_axes: bool = False
    title: str | None = None
    description: str | None = None
    background: Color | str = "#ffffff"
    theme: Theme = MinimalTheme
    lang: str = "en"

    def __post_init__(self) -> None:
        if self.packaging not in PACKAGING:
            raise ConfigurationError(f"packaging must be one of {PACKAGING}")
        if not self.speed > 0:
            raise ConfigurationError("speed must be positive")
        if isinstance(self.fps, bool) or not isinstance(self.fps, int) or self.fps <= 0:
            raise ConfigurationError("fps must be a positive integer")
        if self.width <= 0 or self.height <= 0:
            raise ConfigurationError("width and height must be positive")


@dataclass(frozen=True)
class HtmlDocument:
    text: str
    width: float
    height: float
    duration: float
    dimension: int
    element_ids: dict[str, str] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()
    network_dependencies: tuple[str, ...] = ()
    preserved: tuple[str, ...] = ()
    degraded: tuple[str, ...] = ()

    def to_bytes(self) -> bytes:
        return self.text.encode("utf-8")


def _json(payload: Any) -> str:
    text = json.dumps(payload, separators=(",", ":"), allow_nan=False, ensure_ascii=False)
    # keep the document parseable even if data contains markup-like text
    return (
        text.replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def _controls(duration: float, markers: dict[str, float], controls: PlaybackControls) -> str:
    c = controls
    reset = (
        '<button type="button" data-kk="reset" aria-label="Reset view">Reset view</button>'
        if c.has("reset")
        else ""
    )
    if duration <= 0:
        return (
            f'<div class="kk-controls" role="toolbar" aria-label="View controls">{reset}</div>'
            if reset
            else ""
        )
    parts: list[str] = []
    if c.has("first"):
        parts.append(
            '<button type="button" data-kk="first" aria-label="Go to start">\u23ee</button>'
        )
    if c.has("step"):
        parts.append(
            '<button type="button" data-kk="prev" aria-label="Previous frame">\u25c0</button>'
        )
    if c.has("play"):
        parts.append(
            '<button type="button" data-kk="play" aria-label="Play" aria-pressed="false">\u25b6</button>'
        )
    if c.has("step"):
        parts.append(
            '<button type="button" data-kk="next" aria-label="Next frame">\u25b6\u258f</button>'
        )
    if c.has("last"):
        parts.append('<button type="button" data-kk="last" aria-label="Go to end">\u23ed</button>')
    if c.has("seek"):
        parts.append(
            '<input type="range" data-kk="seek" min="0" value="0" aria-label="Timeline">'
            '<output data-kk="time" aria-live="off">0.00 s</output>'
        )
    if c.has("speed"):
        speeds = "".join(f'<option value="{s}">{s}\u00d7</option>' for s in (0.25, 0.5, 1, 2, 4))
        parts.append(
            f'<label>Speed <select data-kk="speed" aria-label="Playback speed">{speeds}</select></label>'
        )
    if c.has("loop"):
        parts.append('<label><input type="checkbox" data-kk="loop"> Loop</label>')
    parts.append(reset)
    html = (
        '<div class="kk-controls" role="toolbar" aria-label="Animation controls">'
        + "".join(parts)
        + "</div>"
    )
    if markers and c.has("markers"):
        buttons = "".join(
            f'<button type="button" data-kk-marker={quoteattr(name)}>{escape(name)}</button>'
            for name in markers
        )
        html += f'<div class="kk-markers" role="group" aria-label="Markers">{buttons}</div>'
    return html


class InteractiveRenderer:
    """Renders animations to one self-contained interactive HTML document."""

    @property
    def capabilities(self) -> RendererCapabilities:
        return INTERACTIVE_CAPABILITIES

    def render_document(self, animation: Animation, settings: Any = None) -> HtmlDocument:
        st = settings or HtmlSettings()
        if not isinstance(st, HtmlSettings):
            raise ConfigurationError("interactive renderer settings must be an HtmlSettings")
        scene = animation.scene
        if isinstance(scene, Scene3D):
            body, data, warnings, deps, ids, head_scripts = self._three_d(animation, st)
        elif isinstance(scene, Scene2D):
            body, data, warnings, deps, ids, head_scripts = self._two_d(animation, st)
        else:  # pragma: no cover - SceneBase subclasses only
            raise ConfigurationError("unsupported scene type")
        title = st.title or "KineticKit animation"
        label = st.description or title
        markers = dict(animation.timeline.markers)
        data.update(
            {
                "version": 1,
                "generator": f"kinetickit {__version__}",
                "duration": animation.duration,
                "fps": st.fps,
                "speed": st.speed,
                "loop": st.loop,
                "autoplay": st.autoplay,
                "markers": markers,
                "width": st.width,
                "height": st.height,
            }
        )
        ctl = (
            st.controls
            if isinstance(st.controls, PlaybackControls)
            else PlaybackControls(show=() if not st.controls else PlaybackControls().show)
        )
        controls = _controls(animation.duration, markers, ctl)
        plan = plan_interactions(
            animation.interactions, INTERACTIVE_CAPABILITIES, Degradation(st.degradation)
        )
        if animation.interactions is not None:
            data["interactions"] = {
                "bindings": [b.to_data() for b in plan.active],
                "ranges": {k: list(v) for k, v in animation.interactions.ranges.items()},
            }
        caption = (
            f'<figcaption class="kk-sr">{escape(label)}</figcaption>' if st.description else ""
        )
        html = (
            "<!doctype html>\n"
            f'<html lang={quoteattr(st.lang)}>\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            f"<title>{escape(title)}</title>\n<style>{RUNTIME_CSS}</style>\n</head>\n<body>\n"
            f'<figure class="kk-figure" id="kk-root" tabindex="-1" aria-label={quoteattr(label)}>\n'
            f"{body}\n{caption}\n{controls}\n</figure>\n"
            f'<script type="application/json" id="kk-data">{_json(data)}</script>\n'
            f"{head_scripts}<script>{RUNTIME_JS}</script>\n</body>\n</html>\n"
        )
        return HtmlDocument(
            text=html,
            width=st.width,
            height=st.height,
            duration=animation.duration,
            dimension=scene.dimension,
            element_ids=ids,
            warnings=warnings,
            network_dependencies=deps,
            preserved=plan.preserved,
            degraded=plan.degraded,
        )

    # ------------------------------------------------------------------ 2D
    def _two_d(self, animation: Animation, st: HtmlSettings) -> tuple[Any, ...]:
        svg_settings = SvgSettings(
            width=st.width,
            height=st.height,
            background=st.background,
            theme=st.theme,
            loop=False,
            precision=st.precision,
            samples=st.samples,
            title=st.title,
            description=st.description,
            pretty=False,
        )
        doc = VectorRenderer().render_document(animation, svg_settings)
        doc.root.set("class", "kk-svg")
        doc.root.set("preserveAspectRatio", "xMidYMid meet")
        svg = doc.root.serialize(None)
        body = (
            f'<div class="kk-stage">{svg}</div>'
            '<noscript><p class="kk-fallback">Playback controls need JavaScript. The animation '
            "above plays once on its own in browsers that support SVG animation.</p></noscript>"
        )
        data = {
            "dimension": 2,
            "objects": {n.id: n.kind for n in animation.scene.walk() if n.kind != "camera"},
        }
        return body, data, doc.warnings, (), doc.element_ids, ""

    # ------------------------------------------------------------------ 3D
    def _three_d(self, animation: Animation, st: HtmlSettings) -> tuple[Any, ...]:
        from kinetickit.renderers.interactive import _plotly

        scene = animation.scene
        assert isinstance(scene, Scene3D)
        overlay_ids = {n.id for root in scene.overlay for n in _walk(root)}
        if any(r.node_id in overlay_ids for r in animation.timeline.properties):
            raise CapabilityError(
                "animating overlay nodes on a 3D scene is not supported by interactive output",
                missing=("feature:overlay-animation",),
            )
        bg = Color.parse(st.background)
        payload, warnings = _plotly.build_payload(
            animation,
            width=st.width,
            height=st.height,
            fps=st.fps,
            precision=st.precision,
            show_axes=st.show_axes,
            background="#" + bg.to_hex()[1:7],
            max_frames=st.max_frames,
        )
        overlay_html = ""
        if scene.overlay:
            flat = Scene2D(overlay=scene.overlay)
            ov = VectorRenderer().render_document(
                Animation(flat),
                SvgSettings(width=st.width, height=st.height, background=None, pretty=False),
            )
            ov.root.set("class", "kk-svg")
            ov.root.set("aria-hidden", "true")
            for el in ov.root.children:
                if el.attrs.get("id") == "world":
                    ov.root.children.remove(el)
                    break
            overlay_html = f'<div class="kk-overlay-layer">{ov.root.serialize(None)}</div>'
        final = Animation(animation.sample(animation.duration))
        fallback_svg = VectorRenderer().render_document(
            final,
            SvgSettings(
                width=st.width,
                height=st.height,
                background=st.background,
                pretty=False,
                title=st.title,
                description=st.description,
            ),
        )
        fallback_svg.root.set("class", "kk-svg")
        fallback = (
            '<noscript><div class="kk-fallback"><p>Interactive 3D needs JavaScript. A static view of '
            f"the final state is shown instead.</p>{fallback_svg.root.serialize(None)}</div></noscript>"
        )
        body = (
            f'<div class="kk-stage" style="width:{st.width:g}px;max-width:100%">'
            f'<div id="kk-plot" style="width:100%;height:{st.height:g}px"></div>{overlay_html}</div>'
            f"{fallback}"
        )
        if st.packaging == "offline":
            scripts = f"<script>{_plotly.plotly_bundle()}</script>\n"
            deps: tuple[str, ...] = ()
        else:
            scripts = f'<script src="{_plotly.CDN_URL}" charset="utf-8"></script>\n'
            deps = (_plotly.CDN_URL,)
        data = {
            "dimension": 3,
            "traces": payload["traces"],
            "layout": payload["layout"],
            "frames": payload["frames"],
            "objects": {t["meta"]["id"]: t["meta"]["role"] for t in payload["traces"]},
        }
        ids = {t["meta"]["id"]: t["meta"]["id"] for t in payload["traces"]}
        return body, data, warnings, deps, ids, scripts


def _walk(node: Any) -> Any:
    yield node
    for child in node.children_nodes():
        yield from _walk(child)


def make_interactive_renderer() -> InteractiveRenderer:
    """Factory used by the registry; fails with ImportError when the extra is missing."""
    from kinetickit.renderers.interactive import _plotly  # noqa: F401

    return InteractiveRenderer()
