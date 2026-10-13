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
- `TypographyEngine` port, `TypographyUnavailableError` (guides that need text fail instead of guessing), and the optional `kinetickit.integrations.glyphkit` adapter (GlyphKit layouts, math and permission-checked font subsets → neutral `TextAsset`). GlyphKit is not a dependency of KineticKit and never imports it.
- 3D: `Vec3`, `Quaternion` (w, x, y, z; shortest-arc slerp), `Matrix4`, `Transform3D`, immutable `MeshData`/`SurfaceGrid`/`Vec3Array`, `Material`/`ColorScale`, scene nodes (`Point3D`, `PointCloud3D`, `Line3D`, `Polyline3D`, `Mesh3D`, `Surface3D`, `Group3D`, `DirectionalLight3D`, `Camera3D`, `Scene3D`) with perspective and orthographic cameras, and a shared deterministic projection used by the raster (GIF) and vector (projected SVG) outputs.
- 3D morphing: mesh/surface/point-list normalizers with explicit correspondence (`MeshMorph`, `SurfaceMorph`, bilinear `resample_grid`), topology and degeneracy diagnostics, `Mesh3D.morph_to`/`Surface3D.morph_to`, and 3D scene transitions (compatible meshes interpolate; mismatches cross-fade with diagnostics; camera pose, fov and clipping animate with the shared easing/keyframes).
- `interactive` renderer and self-contained HTML export: 2D embeds the native Animated SVG driven by a dependency-free player (play/pause/seek/step/speed/loop/markers, keyboard operable, pan/zoom, hover/click events, reduced-motion aware); 3D uses a private plotting runtime with pre-sampled frames and native camera interaction. `offline` packaging has no network dependency; `compact` declares its CDN reference in the manifest.
- Portable interaction model: `Event`/`Interaction` semantics, serializable declarative actions (`Play`, `Seek`, `PlayRange`, `Select`, `SetProperty`, ...), `Binding`/`InteractionSpec` validated against stable node ids and markers, a deterministic `PlayerState` machine, `PlaybackControls`, and capability-aware `plan_interactions` (required bindings fail before output; optional ones degrade explicitly and are reported in the manifest). The HTML runtime executes the same bindings.
- Accessibility: `Semantics` (role, label, description, reading order, decorative) on every node, `AccessibilityInfo` and `ReducedMotion` policy; SVG exports titles/descriptions/roles/labels and applies reduced motion (no autoplay, representative state); HTML adds an object list in reading order, a reduced-motion notice and native keyboard-operable controls; GIF requires a description when accessibility output is requested and returns it with a representative PNG (companion PNG/JSON only when asked). Manifests list what each output preserves or degrades.
- Quality: published `kinetickit.conformance` (shared 2D/3D/timing/typography fixtures and a suite every exporter must pass), golden artifacts for GIF, Animated SVG and HTML, performance/size budgets with a CI report (`python -m kinetickit.conformance`), generic examples (objects, chart, surface, external fonts, interactive/accessible) that use only public API, and `kinetickit.adapters` for animating arbitrary object models.
