"""Document which accessibility semantics each output preserves or degrades."""

from __future__ import annotations

from typing import Any


def semantic_report(
    animation: Any, fmt: str, settings: Any = None
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """(preserved, degraded) accessibility facts for ``animation`` exported as ``fmt``."""
    info = animation.accessibility
    nodes = [
        n for n in animation.scene.walk() if n.semantics is not None and not n.semantics.is_empty
    ]
    has_title = bool((getattr(settings, "title", None)) or (info and info.title))
    has_desc = bool((getattr(settings, "description", None)) or (info and info.description))
    labelled = any(n.semantics.label for n in nodes)
    described = any(n.semantics.description for n in nodes)
    roles = any(n.semantics.role or n.semantics.hidden for n in nodes)
    ordered = any(n.semantics.reading_order is not None for n in nodes)
    kept: list[str] = []
    lost: list[str] = []

    def note(present: bool, name: str, ok: bool, why: str = "") -> None:
        if not present:
            return
        if ok:
            kept.append(name)
        else:
            lost.append(f"{name}: {why}" if why else name)

    if fmt == "svg":
        note(has_title, "title", True)
        note(has_desc, "description", True)
        note(labelled, "object labels", True)
        note(described, "object descriptions", True)
        note(roles, "roles", True)
        note(
            ordered,
            "reading order",
            False,
            "recorded as data-kk-order; SVG document order is z-order",
        )
        if animation.duration > 0:
            kept.append("reduced motion (script; ignored when the SVG is embedded as an image)")
    elif fmt == "html":
        note(has_title, "title", True)
        note(has_desc, "description", True)
        note(labelled, "object labels", True)
        note(described, "object descriptions", True)
        note(roles, "roles", True)
        note(ordered, "reading order", True)
        kept += ["keyboard controls", "reduced motion"]
    elif fmt == "gif":
        note(has_desc or bool(info and info.alt_text), "text alternative", True)
        note(bool(nodes), "object semantics", False, "GIF cannot carry per-object metadata")
        lost.append("alt text is not embedded in the GIF; use the manifest description")
    return tuple(kept), tuple(lost)
