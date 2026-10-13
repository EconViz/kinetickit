"""Compile two scenes into a merged scene plus a parallel transition motion."""

from __future__ import annotations

from dataclasses import fields
from typing import Any

from kinetickit.easing import Easing, linear
from kinetickit.errors import ConfigurationError
from kinetickit.interpolation import InterpolatorRegistry, StepInterpolator
from kinetickit.morph import MorphDiagnostic, has_normalizer, normalize_pair
from kinetickit.scene.node import Node
from kinetickit.scene.scene import SceneBase
from kinetickit.timeline import Hold, Motion, PropertyRef
from kinetickit.transitions.transition import INCOMING_SUFFIX, Transition, TransitionPolicy
from kinetickit.tween import Tween


class _Compiler:
    def __init__(
        self,
        duration: float,
        easing: Easing,
        policy: TransitionPolicy,
        overrides: tuple[Motion, ...],
        morphs: dict[str, Any],
        registry: InterpolatorRegistry,
    ) -> None:
        self.duration = duration
        self.easing = easing
        self.policy = policy
        self.morphs = morphs
        self.registry = registry
        self.overridden = frozenset(r for m in overrides for r in m.targets())
        self.tracks: list[Motion] = []
        self.diags: list[MorphDiagnostic] = []

    # -- track helpers -----------------------------------------------------------------
    def tween(
        self, ref: PropertyRef[Any], start: Any, end: Any, easing: Easing | None = None
    ) -> None:
        if ref in self.overridden:
            return
        self.tracks.append(Tween(ref, end, self.duration, easing or self.easing, start))

    def at_end(self, ref: PropertyRef[Any], start: Any, end: Any) -> None:
        """Switch a value exactly when the transition completes."""
        if ref in self.overridden:
            return
        self.tracks.append(Tween(ref, end, 0.0, linear, start).delay(self.duration))

    def note(
        self, code: str, message: str, severity: str, node: Node, prop: str | None = None
    ) -> None:
        self.diags.append(MorphDiagnostic(code, message, severity, node.id, prop))

    # -- matched nodes -----------------------------------------------------------------
    def _static_fields_differ(self, s: Node, t: Node) -> str | None:
        animatable = set(s.animatable_properties())
        for f in fields(s):
            if f.name in animatable or f.name in ("id", "children"):
                continue
            if getattr(s, f.name) != getattr(t, f.name):
                return f.name
        return None

    def _property_tracks(
        self, s: Node, t: Node
    ) -> tuple[bool, list[Motion], list[MorphDiagnostic]]:
        """Tracks for a same-type pair; ``ok`` is False when the pair must cross-fade."""
        outer_tracks, outer_diags = self.tracks, self.diags
        self.tracks, self.diags = [], []
        try:
            ok = self._collect(s, t)
            return ok, self.tracks, self.diags
        finally:
            self.tracks, self.diags = outer_tracks, outer_diags

    def _collect(self, s: Node, t: Node) -> bool:
        changed = self._static_fields_differ(s, t)
        if changed is not None:
            self.note(
                "non-animatable-change",
                f"{changed!r} differs and cannot be interpolated; cross-fading",
                "warning",
                s,
            )
            return False
        for name, kind in s.animatable_properties().items():
            sv, tv = getattr(s, name), getattr(t, name)
            if sv == tv:
                continue
            ref: PropertyRef[Any] = PropertyRef(s.id, name, kind)
            if sv is None or tv is None:
                self.note(
                    "optional-switch",
                    f"{name} switches between unset and set; applied when the transition ends",
                    "info",
                    s,
                    name,
                )
                self.at_end(ref, sv, tv)
            elif has_normalizer(kind):
                pair = normalize_pair(kind, sv, tv, self.morphs.get(s.id))
                for d in pair.diagnostics:
                    self.diags.append(d.for_target(s.id, name))
                if not pair.compatible:
                    self.note(
                        "incompatible-morph",
                        f"{name} cannot be morphed automatically; cross-fading",
                        "warning",
                        s,
                        name,
                    )
                    return False
                self.tween(ref, pair.start, pair.end)
            else:
                if not self.registry.has(kind):
                    raise ConfigurationError(
                        f"no interpolator for {s.id}.{name} ({kind.__name__}); register one or "
                        "override this property explicitly"
                    )
                if isinstance(self.registry.resolve(kind), StepInterpolator):
                    self.note(
                        "discrete-switch",
                        f"{name} switches when the transition ends",
                        "info",
                        s,
                        name,
                    )
                self.tween(ref, sv, tv)
        return True

    def match(self, s: Node, t: Node) -> list[Node]:
        if type(s) is not type(t):
            self.note(
                "type-change",
                f"{type(s).__name__} became {type(t).__name__}; cross-fading",
                "info",
                s,
            )
            return self.crossfade(s, t)
        ok, tracks, diags = self._property_tracks(s, t)
        self.diags.extend(diags)
        if not ok:
            return self.crossfade(s, t)
        self.tracks.extend(tracks)
        merged = s
        kids_s, kids_t = s.children_nodes(), t.children_nodes()
        if kids_s or kids_t:
            merged = s.with_children(tuple(self.merge(list(kids_s), list(kids_t))))
        return [merged]

    def crossfade(self, s: Node, t: Node) -> list[Node]:
        incoming = _rename(t, INCOMING_SUFFIX)
        self.fade_out(s)
        self.fade_in(incoming, t.opacity)
        return [s, incoming.replace(opacity=0.0)]

    # -- enter / exit ------------------------------------------------------------------
    def fade_out(self, node: Node) -> None:
        if node.opacity != 0.0:
            self.tween(PropertyRef(node.id, "opacity", float), node.opacity, 0.0)

    def fade_in(self, node: Node, target_opacity: float) -> None:
        if target_opacity != 0.0:
            self.tween(PropertyRef(node.id, "opacity", float), 0.0, target_opacity)

    def exiting(self, node: Node) -> list[Node]:
        mode = self.policy.exit
        if mode == "cut":
            self.note("exit-cut", "removed immediately", "info", node)
            return []
        if mode == "hold":
            self.at_end(PropertyRef(node.id, "visible", bool), True, False)
        elif mode == "draw" and "draw_progress" in node.animatable_properties():
            current = getattr(node, "draw_progress")
            if current != 0.0:
                self.tween(PropertyRef(node.id, "draw_progress", float), current, 0.0)
        else:
            self.fade_out(node)
        return [node]

    def entering(self, node: Node) -> list[Node]:
        mode = self.policy.enter
        if mode == "cut":
            self.note("enter-cut", "present immediately", "info", node)
            return [node]
        if mode == "draw" and "draw_progress" in node.animatable_properties():
            target = getattr(node, "draw_progress")
            if target != 0.0:
                self.tween(PropertyRef(node.id, "draw_progress", float), 0.0, target)
            return [node.replace(draw_progress=0.0)]
        self.fade_in(node, node.opacity)
        return [node.replace(opacity=0.0)]

    # -- lists -------------------------------------------------------------------------
    def merge(self, src: list[Node], tgt: list[Node]) -> list[Node]:
        by_id = {n.id: n for n in tgt}
        out: list[Node] = []
        used: set[str] = set()
        for s in src:
            t = by_id.get(s.id)
            if t is None:
                out.extend(self.exiting(s))
            else:
                used.add(s.id)
                out.extend(self.match(s, t))
        for t in tgt:
            if t.id not in used:
                out.extend(self.entering(t))
        return out


def _rename(node: Node, suffix: str) -> Node:
    renamed = node.replace(id=node.id + suffix)
    kids = node.children_nodes()
    return renamed.with_children(tuple(_rename(k, suffix) for k in kids)) if kids else renamed


def compile_transition(
    source: SceneBase,
    target: SceneBase,
    *,
    duration: float,
    easing: Easing,
    policy: TransitionPolicy,
    overrides: tuple[Motion, ...],
    morphs: dict[str, Any],
    registry: InterpolatorRegistry,
) -> Transition:
    c = _Compiler(duration, easing, policy, overrides, morphs, registry)

    src_ids = {n.id for n in source.walk()}
    tgt_ids = {n.id for n in target.walk()}
    for root_s, root_t in ((source.nodes, target.nodes), (source.overlay, target.overlay)):
        _reject_moves(root_s, root_t, src_ids, tgt_ids)

    world = c.merge(list(source.nodes), list(target.nodes))
    overlay = c.merge(list(source.overlay), list(target.overlay))
    camera = c.match(source.camera, target.camera)[0]

    scene = type(source)(*world, overlay=overlay, camera=camera)
    motion: Motion = Hold(duration)
    for track in c.tracks:
        motion = motion.with_(track)
    for extra in overrides:
        motion = motion.with_(extra)
    return Transition(scene, motion, tuple(c.diags), duration)


def _reject_moves(
    src: tuple[Node, ...], tgt: tuple[Node, ...], src_ids: set[str], tgt_ids: set[str]
) -> None:
    """A node may only match within the same parent; moving between parents is an error."""

    def walk(s_list: tuple[Node, ...], t_list: tuple[Node, ...], top: bool) -> None:
        s_here = {n.id for n in s_list}
        t_here = {n.id for n in t_list}
        for n in s_list:
            if n.id not in t_here and n.id in tgt_ids:
                raise ConfigurationError(
                    f"node {n.id!r} moves between parents; automatic transitions match "
                    "within one parent. Keep it under the same group or give it a new id."
                )
        for n in t_list:
            if n.id not in s_here and n.id in src_ids:
                raise ConfigurationError(
                    f"node {n.id!r} moves between parents; automatic transitions match "
                    "within one parent. Keep it under the same group or give it a new id."
                )
        s_by = {n.id: n for n in s_list}
        for n in t_list:
            m = s_by.get(n.id)
            if m is not None and type(m) is type(n):
                walk(m.children_nodes(), n.children_nodes(), False)

    walk(src, tgt, True)
