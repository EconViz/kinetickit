# GlyphKit Dependency Design

## Intent

KineticKit owns animation, scene placement, rendering, and neutral text assets. GlyphKit owns
font loading, matching, shaping, layout, outlines, subsetting, and embedding permissions. Make
that relationship installable by default instead of requiring users to discover and install a
separate optional integration.

## Requirements

- Declare `glyphkit>=1.0.0b2,<2` as a required KineticKit dependency.
- Keep `Text2D`, `TextAsset`, `GlyphShape`, `FontResource`, and the typography protocols in
  KineticKit; these are renderer/animation contracts, not a font engine.
- Keep GlyphKit imports at the typography integration boundary. Importing `kinetickit` or its
  motion/geometry/scene core must not eagerly import GlyphKit.
- Keep GlyphKit independent: it must never import KineticKit.
- Make `kinetickit.integrations.glyphkit` available on every supported base installation.
- Update distribution tests, lockfile, README/changelog/migration language, and the existing
  integration tests to reflect the required dependency.
- Preserve Python 3.10–3.13 support and the existing raster/interactive extras.

## Non-goals

- Do not merge GlyphKit APIs into KineticKit's top-level namespace.
- Do not move animation or rendering functionality into GlyphKit.
- Do not change text geometry, export output, or the neutral text asset schema.
