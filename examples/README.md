# Examples

Every example uses only public KineticKit API and generic content (points, lines, paths, shapes,
meshes, surfaces, text assets). None needs MosaicKit or any visualization package.

| File | Shows |
|---|---|
| `arbitrary_objects.py` | animating a plain Python object model through an adapter |
| `chart.py` | a bar-and-line chart from generic shapes, axes and morphs |
| `surface.py` | a lit 3D surface with an orbiting camera → GIF, SVG, HTML |
| `external_fonts.py` | caller-provided fonts via the optional GlyphKit adapter |
| `interactive_accessible.py` | declarative interactions plus accessibility metadata |

Run one with `uv run python examples/surface.py`; each writes into `out/`.
