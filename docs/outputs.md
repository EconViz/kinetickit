# Outputs, capabilities and fallbacks

## Output matrix

| Output | Capability | 2D | 3D | Interactive | Vector-preserving |
|---|---|:-:|:-:|:-:|:-:|
| GIF | `raster` | yes | projected | no | no |
| Animated SVG | `vector` | yes | projected (sampled) | no | yes (2D) |
| HTML | `interactive` | yes (native SVG + player) | yes (native 3D, orbit/zoom) | yes | 2D yes |

Every export validates `requirements_for(animation)` against the renderer's declared
capabilities **before** writing anything; unsupported combinations raise `CapabilityError` with
the missing capabilities and a hint. Files are written atomically (a failed export leaves no file).

## Capability notes

- **Vector 3D** is a time-varying 2D projection (flat baked shading, painter's order fixed at
  `t = 0`). It fails if primitives enter or leave the view, instead of guessing.
- **Raster** streams one frame at a time (bounded memory) with DPI up to 1200 and warns, never
  silently degrades, on expensive jobs. GIF timing uses error-diffused centiseconds; frame
  intervals below 10 ms are rejected.
- **Interactive 3D** is pre-sampled (`fps`, default 30) by KineticKit and shown by a private
  plotting runtime; `packaging="offline"` embeds it (no network), `"compact"` references a
  pinned CDN copy and declares it in `ExportManifest.network_dependencies`.
- Not in 1.0.0b1: video encoders, audio, physics, multi-panel layout, implicit surfaces, 3D text,
  drag interaction, animated overlays on 3D scenes.

## Static and no-JavaScript fallbacks

| Case | Behaviour |
|---|---|
| 2D HTML without JavaScript | the embedded SVG still plays once natively (SMIL); controls are inert |
| 3D HTML without JavaScript | a `<noscript>` block shows a static SVG of the **final** state |
| SVG used as an `<img>` | animation plays; scripts (reduced-motion handling) are ignored |
| GIF | no runtime semantics; use the manifest description and representative PNG |
| `prefers-reduced-motion` | no autoplay; the representative state (default: final) is shown; Play still works |

## What each format preserves or degrades

`ExportManifest.preserved` / `.degraded` list this per export.

| Semantics | SVG | HTML | GIF |
|---|---|---|---|
| Title, description | yes | yes | manifest only |
| Object roles, labels, descriptions | yes (`role`, `aria-label`, `<title>`, `<desc>`) | yes | no |
| Reading order | recorded as `data-kk-order` (DOM order is z-order) | yes (ordered text list) | no |
| Keyboard-operable controls | n/a | yes (native buttons, range, select) | n/a |
| Interactions | dropped by policy, or error if `required` | yes | dropped by policy, or error |
| Fonts | embedded subsets as `@font-face` | via the embedded SVG | rendered into pixels |
| Stable object ids | `data-kk-id` | `data-kk-id`, `objects` map | n/a |

Projected 3D output keeps ids of *drawable* nodes; groups and lights have no element of their own.
