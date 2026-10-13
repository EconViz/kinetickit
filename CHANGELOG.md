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
