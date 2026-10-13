# KineticKit

Domain-neutral engine for precise, deterministic 2D and 3D animation.

KineticKit owns its scene model, animation model, rendering ports and animation output. It
does not depend on MosaicKit or any visualization package: any object can take part by being
translated into KineticKit points, lines, paths, shapes, text assets, meshes and surfaces.

One scene and one timeline drive three outputs:

| Output | Capability | Install |
|---|---|---|
| Animated SVG | `vector` | `kinetickit` |
| GIF | `raster` | `kinetickit[raster]` |
| Self-contained HTML | `interactive` | `kinetickit[interactive]` |

`kinetickit[studio]` installs the raster and interactive capabilities together.

## Status

Pre-release. See [`CHANGELOG.md`](CHANGELOG.md) and the policies in
[`docs/compatibility.md`](docs/compatibility.md).

## Development

```bash
uv sync --all-extras
uv run pytest
uv run lint-imports
```
