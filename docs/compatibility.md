# Compatibility and deprecation policy

## Supported platforms

- Python 3.10, 3.11, 3.12 and 3.13 (`requires-python = ">=3.10,<3.14"`).
- CI targets Linux, macOS and Windows.
- Base installations include NumPy and GlyphKit. `raster` and `interactive` are optional extras; their
  third-party engines are private implementation details and may be replaced without a breaking
  change. GlyphKit handles font processing through the typography integration boundary and
  is not loaded by core imports.

## Stable surfaces (1.0)

| Surface | Import path |
|---|---|
| Timeline, tween, keyframes, scheduler | `kinetickit.timeline`, `.tween`, `.keyframes`, `.scheduler`, `.easing`, `.interpolation` |
| 2D and 3D scene contracts | `kinetickit.scene`, `.geometry`, `.styles` |
| Morphing and transitions | `kinetickit.morph`, `.transitions` |
| Renderer and exporter protocols | `kinetickit.renderers` (`Renderer`, `RendererCapabilities`, `register_renderer`), `kinetickit.exporters` (`Destination`, `ExportManifest`, `register_exporter`) |
| Interaction and accessibility | `kinetickit.interaction`, `.accessibility` |
| Typography port and text assets | `kinetickit.typography` |
| Conformance fixtures | `kinetickit.conformance` |

Everything exported in a public package's `__all__` is public. Names starting with an underscore,
and everything in modules whose name starts with an underscore (`_matplotlib`, `_plotly`,
`_gif_stream`, ...), are private and replaceable at any time. Visualization semantics are out of
scope.

## Versioning

KineticKit follows Semantic Versioning from 1.0. Pre-releases (`1.0.0bN`, `1.0.0rcN`) may change
public contracts between pre-release versions; each change is recorded in `CHANGELOG.md`.

## Deprecation

1. A deprecated public name keeps working for at least one minor release.
2. It emits `DeprecationWarning` naming the replacement and the removal version.
3. The removal is recorded in `CHANGELOG.md` under *Removed*.
4. Deprecated names are removed only in a major release.

Output formats follow the same rule: a change that alters existing artifacts (for example the
SVG structure) is a changelog-visible change and updates the golden files in the same commit.
