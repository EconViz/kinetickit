# Migration

KineticKit is a new, independent engine. It does **not** import MosaicKit or any `*-viz` package
and ships no compatibility layer for them; migration means describing your objects as KineticKit
nodes through a small adapter.

## From MosaicKit parameter-sweep animation

MosaicKit's `Animation.sweep(canvas, values)` yields immutable `Scene` frames. Depict each layer
as KineticKit nodes keyed by the layer id, then let KineticKit interpolate between frames:

```python
from kinetickit.adapters import transition
from kinetickit import Animation


def depict(layer):  # public MosaicKit fields only
    ...  # PathLayer -> PathNode2D(id=layer.id, ...), etc.


frames = list(sweep.frames())
steps = [transition(a.layers, b.layers, depict, duration=1.0) for a, b in zip(frames, frames[1:])]
motion = steps[0].motion
for step in steps[1:]:
    motion = motion.then(step.motion)
animation = Animation(steps[0].scene, motion)
```

A working, tested version lives in `tests/integrations/test_mosaickit_extraction.py`. Layers must
keep stable ids across frames; unmatched ids fade in/out, structural changes cross-fade with a
diagnostic (`Transition.diagnostics`).

## From factory-style animators (for example utility-viz `Animator`)

Replace the factory with a depiction function and construct the animation directly:

1. Translate each domain object to nodes (`adapt(objects, depict)`).
2. Express change as motions (`node.animate.<property>.to(...)`) or as `SceneTransition.between`.
3. Export with `animation.save(path)`; the exporter owns file output.

## Typography with GlyphKit

Installing or upgrading KineticKit also installs `glyphkit>=1.0.0b2,<2`. Import
`GlyphKitTypography` from `kinetickit.integrations.glyphkit` and provide your font sources
through GlyphKit. GlyphKit owns font loading, matching, shaping, layout, outlines, subsetting
and embedding permissions; KineticKit places and animates the resulting neutral `TextAsset`.

Existing `Text2D`, `TextAsset`, `GlyphShape`, `FontResource` and typography protocol consumers
keep their contracts. Core imports do not load GlyphKit, and GlyphKit does not import
KineticKit. Raster and interactive output continue to use their existing extras.

## Policies

- No compatibility shims: removed MosaicKit/utility-viz animation APIs are not re-exported.
- Names, deprecation and versioning: [`compatibility.md`](compatibility.md).
- Pre-release (`1.0.0bN`) changes are listed in the changelog before they ship.
