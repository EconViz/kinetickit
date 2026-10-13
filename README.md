# KineticKit

Domain-neutral engine for precise, deterministic 2D and 3D animation.

KineticKit owns its scene model, animation model, rendering ports, interaction model and
animation output. It depends on no visualization package: anything can take part by being
translated into KineticKit points, lines, paths, shapes, text assets, meshes and surfaces.

One scene and one timeline drive three outputs:

| Output | Capability | Install |
|---|---|---|
| Animated SVG (native vector, 2D; 3D as projection) | `vector` | `kinetickit` |
| GIF (streamed, up to 1200 DPI) | `raster` | `kinetickit[raster]` |
| Self-contained interactive HTML (2D and 3D) | `interactive` | `kinetickit[interactive]` |

`kinetickit[studio]` installs the raster and interactive capabilities together. Python 3.10–3.13.
Every installation includes `glyphkit>=1.0.0b2,<2` for font processing.

> **Status: 1.0 beta.** The contracts listed in [`docs/compatibility.md`](docs/compatibility.md)
> are intended to be stable; they may still change between pre-releases, always with a changelog
> entry. See [`CHANGELOG.md`](CHANGELOG.md).

## Quick start

```python
from kinetickit import Animation, Bounds2D, Point2D, Scene2D, Vec2, ease

dot = Point2D(id="dot", position=Vec2(1, 1), size=8, color="#e4572e")
scene = Scene2D(dot)
scene = scene.bind({scene.camera.ref("view"): Bounds2D(Vec2(0, 0), Vec2(10, 10))})

motion = dot.animate.position.to(Vec2(9, 9), duration=1.5, easing=ease.out_cubic)
animation = Animation(scene, motion)

animation.save("dot.svg", width=400, height=400)  # native Animated SVG
animation.save("dot.gif", width=400, height=400, fps=30)  # needs kinetickit[raster]
animation.save("dot.html", width=400, height=440)  # needs kinetickit[interactive]
```

Everything is an immutable value: nodes, scenes, motions and snapshots. A motion is composed with
`.then()` / `.with_()` / `.delay()` / `.repeat()` / `.yoyo()` / `.reverse()` / `.trim()`, and the same
scene and time always give the same state, independent of any renderer or wall clock.

```python
motion = (
    a.animate.position.to(Vec2(5, 5), duration=1.0)
    .then(b.animate.opacity.to(1.0, duration=0.5).with_(c.animate.size.to(9, duration=0.5)))
    .mark("settled")
)
```

3D uses the same builders:

```python
from kinetickit import Camera3D, Scene3D, Surface3D, Vec3

scene = Scene3D(surface, camera=Camera3D(position=Vec3(5, -6, 4), target=Vec3(0, 0, 0)))
Animation(scene, scene.camera.animate.position.to(Vec3(-5, -6, 4), duration=2.0)).save("orbit.html")
```

## What you get

- **Timing**: deterministic frames (`N = max(2, round(D·fps))`, both endpoints included), easing
  families plus cubic Bézier, an extensible interpolator registry, keyframes, markers.
- **Scenes**: precise 2D points, lines, paths, shapes, groups (transform, clip), overlay and
  camera; 3D points, polylines, meshes, surfaces, lights, perspective/orthographic cameras.
- **Morphing**: automatic path normalization, mesh/surface correspondence with explicit
  overrides and diagnostics, and `SceneTransition` between scenes by stable ids.
- **Interaction**: portable events and data-only actions bound to node ids, playback state
  machine, controls; required bindings fail before output, optional ones degrade explicitly.
- **Accessibility**: per-object roles/labels/descriptions/reading order, reduced-motion policy,
  text alternatives and keyboard-operable controls.
- **Typography**: text arrives as a neutral `TextAsset`; the included GlyphKit adapter turns
  caller-provided fonts into assets and embeds permission-checked subsets.
- **Quality**: conformance fixtures and suites, golden artifacts, performance budgets.

Outputs, fallbacks and what each format preserves or degrades: [`docs/outputs.md`](docs/outputs.md).
Migrating from MosaicKit or utility-viz animation: [`docs/migration.md`](docs/migration.md).

## Architecture

| Layer | May know | Must not know |
|---|---|---|
| Motion core (`easing`, `interpolation`, `timeline`, `tween`, `keyframes`) | time, values, protocols | scenes, renderers |
| Scene model (`geometry`, `scene`, `styles`, `morph`, `transitions`) | geometry, styles, object ids | backend objects |
| Renderers (`renderers.vector` / `raster` / `interactive`) | scene snapshots, capabilities | consumer domain models |
| Exporters (`exporters`) | frames, artifacts, destinations | visualization logic |

Boundaries are enforced by import-linter contracts and AST tests. Third-party engines
(Matplotlib, Plotly, Pillow) live only in private `_*` modules and never appear in public API.
GlyphKit owns font loading, matching, shaping, layout, outlines, subsetting and embedding
permissions. Only `kinetickit.integrations.glyphkit` imports it; importing KineticKit's core
does not load GlyphKit. KineticKit retains its neutral text assets and typography protocols,
and GlyphKit remains independent of KineticKit.

## Development

```bash
uv sync --all-extras
uv run pytest
uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run lint-imports
uv run python -m kinetickit.conformance      # shared suites + performance budgets
```

Examples live in [`examples/`](examples) and use only public API.
