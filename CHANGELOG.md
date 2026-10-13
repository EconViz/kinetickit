# Changelog

All notable changes are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/) and the project follows
[Semantic Versioning](https://semver.org/) from 1.0.

## Unreleased

### Added
- Package scaffold for Python 3.10–3.13, typed errors and enforced import boundaries.
- Deterministic time values, frame enumeration, standard and cubic-Bézier easing, and an extensible interpolator registry (scalars, sequences, colors, angles, discrete values).
- Tween, keyframes (with hold), and an immutable fluent motion tree (`then`, `with_`, `delay`, `repeat`, `yoyo`, `reverse`, `trim`, `hold`, markers) compiled into a deterministic, random-access `Timeline`.
- `FixedFPS` and `Timestamps` schedulers.
- Immutable 2D geometry (`Vec2`, `Matrix3`, `Transform2D`, `Bounds2D`, `Path2D` with exact bounds) and scene model (`Point2D`, `Line2D`, `PathNode2D`, `Shape2D`, `Group2D`, `Text2D`, `Camera2D`, `Scene2D`) with stable ids, an overlay, and snapshot `bind`.
- Neutral `TextAsset` contract and the `Animation` facade with lazy `frames()`.
- Path normalization (`normalize_paths`, `PathMorph` overrides, diagnostics) and automatic `SceneTransition.between` keyed by stable ids, with enter/exit policies, cross-fade fallbacks and explicit track overrides; `Shape2D/PathNode2D.morph_to`.
- `minimal` theme and `Stroke`/`Fill` helpers, whole-animation single-viewport layout (`resolve_layout`), and guides (axes, grid, legend, color bar, annotation) compiled to ordinary scene nodes.
- Capability-driven renderer contracts (`RendererCapabilities`, `requirements_for`, renderer registry) that fail before any output, KineticKit-owned destinations (atomic files, bytes, streams), `ExportManifest`, and native Animated SVG export (SMIL, exact `keySplines` for linear and cubic-Bézier easing, sampled otherwise) via `Animation.save()` / `to_svg()`.
- `raster` renderer (private Matplotlib adapter, logical size / physical size / pixels, DPI up to 1200) and a truly streaming GIF exporter (palette, dithering, looping, disposal, error-spread frame timing, deterministic metadata, cost warnings).
