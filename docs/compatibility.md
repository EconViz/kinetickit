# Compatibility and deprecation policy

## Supported platforms

- Python 3.10, 3.11, 3.12 and 3.13 (`requires-python = ">=3.10,<3.14"`).
- CI runs the full suite on Linux, macOS and Windows.
- Core and vector output need only NumPy. `raster` and `interactive` capabilities are
  optional extras; their third-party engines are private implementation details and may be
  replaced without a breaking change.

## Versioning

KineticKit follows Semantic Versioning from 1.0.

| Surface | Promise |
|---|---|
| Timeline, tween, keyframes, scheduler | Stable |
| 2D and 3D scene contracts | Stable |
| Renderer and exporter protocols | Stable |
| Private backend adapters (`_*` modules) | Replaceable at any time |
| Visualization semantics | Out of scope |

Names beginning with an underscore, and everything under a module whose name begins with an
underscore, are private.

## Deprecation

1. A deprecated public name keeps working for at least one minor release.
2. It emits `DeprecationWarning` naming the replacement and the removal version.
3. The removal is recorded in `CHANGELOG.md` under *Removed*.
4. Deprecated names are removed only in a major release.

Pre-releases (`1.0.0bN`, `1.0.0rcN`) may change public contracts between pre-release
versions; every change is recorded in the changelog.
