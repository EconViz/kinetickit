"""Path normalization and correspondence for morphing.

Both paths are converted to a shared structure — per subpath ``M`` followed by the same number
of cubic segments, plus ``Z`` when closed — without changing their shape. Every automatic
choice (subpath pairing, segment count, closed-contour start vertex, direction) can be
overridden through :class:`PathMorph`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from itertools import pairwise
from typing import Any

from kinetickit.errors import ConfigurationError
from kinetickit.geometry.two_d import Path2D, PathCommand, Vec2
from kinetickit.morph.diagnostics import MorphDiagnostic

Cubic = tuple[Vec2, Vec2, Vec2, Vec2]  # p0, c1, c2, p3
_FLATTEN = 16
_TIE = 1e-9


@dataclass(frozen=True, slots=True)
class PathMorph:
    """Explicit overrides for :func:`normalize_paths`. ``None`` means "decide automatically".

    ``pairing[i]`` is the target subpath matched with source subpath ``i`` (a permutation).
    ``segments``, ``shifts`` and ``reverses`` are indexed by source subpath. ``shifts[i]`` rotates a
    closed target contour so that its ``k``-th segment starts the correspondence.
    ``normalizer`` replaces everything with caller-supplied compatible paths.
    """

    pairing: tuple[int, ...] | None = None
    segments: tuple[int | None, ...] | None = None
    shifts: tuple[int | None, ...] | None = None
    reverses: tuple[bool | None, ...] | None = None
    orient: bool = True
    normalizer: Callable[[Path2D, Path2D], tuple[Path2D, Path2D]] | None = None


@dataclass(frozen=True, slots=True)
class NormalizedPair:
    start: Path2D
    end: Path2D
    diagnostics: tuple[MorphDiagnostic, ...] = ()
    compatible: bool = True


@dataclass
class _Contour:
    start: Vec2
    segs: list[Cubic]
    closed: bool
    area: float = field(default=0.0)


# -- cubic helpers ---------------------------------------------------------------------------
def _lerp(a: Vec2, b: Vec2, t: float) -> Vec2:
    return Vec2(a.x + (b.x - a.x) * t, a.y + (b.y - a.y) * t)


def _point(c: Cubic, t: float) -> Vec2:
    a, b, cc, d = c
    ab, bc, cd = _lerp(a, b, t), _lerp(b, cc, t), _lerp(cc, d, t)
    return _lerp(_lerp(ab, bc, t), _lerp(bc, cd, t), t)


def _split(c: Cubic, t: float = 0.5) -> tuple[Cubic, Cubic]:
    a, b, cc, d = c
    ab, bc, cd = _lerp(a, b, t), _lerp(b, cc, t), _lerp(cc, d, t)
    abc, bcd = _lerp(ab, bc, t), _lerp(bc, cd, t)
    m = _lerp(abc, bcd, t)
    return (a, ab, abc, m), (m, bcd, cd, d)


def _length(c: Cubic) -> float:
    pts = [_point(c, i / _FLATTEN) for i in range(_FLATTEN + 1)]
    return sum((q - p).length() for p, q in pairwise(pts))


def _reverse_cubic(c: Cubic) -> Cubic:
    return (c[3], c[2], c[1], c[0])


def _line(a: Vec2, b: Vec2) -> Cubic:
    return (a, _lerp(a, b, 1 / 3), _lerp(a, b, 2 / 3), b)


def _quad(a: Vec2, q: Vec2, b: Vec2) -> Cubic:
    return (a, _lerp(a, q, 2 / 3), _lerp(b, q, 2 / 3), b)


def _signed_area(contour: _Contour) -> float:
    pts: list[Vec2] = []
    for seg in contour.segs:
        pts.extend(_point(seg, i / _FLATTEN) for i in range(_FLATTEN))
    return 0.5 * sum(p.cross(q) for p, q in zip(pts, pts[1:] + pts[:1], strict=True))


def _contours(path: Path2D) -> list[_Contour]:
    out: list[_Contour] = []
    for sub in path.subpaths():
        start = cur = sub[0].points[0]
        segs: list[Cubic] = []
        closed = False
        for c in sub[1:]:
            if c.kind == "L":
                segs.append(_line(cur, c.points[0]))
                cur = c.points[0]
            elif c.kind == "Q":
                segs.append(_quad(cur, *c.points))
                cur = c.points[1]
            elif c.kind == "C":
                segs.append((cur, *c.points))  # type: ignore[arg-type]
                cur = c.points[2]
            elif c.kind == "Z":
                closed = True
                if cur != start:
                    segs.append(_line(cur, start))
                    cur = start
        contour = _Contour(start, segs, closed)
        if closed:
            contour.area = _signed_area(contour)
        out.append(contour)
    return out


def _reversed(contour: _Contour) -> _Contour:
    segs = [_reverse_cubic(s) for s in reversed(contour.segs)]
    start = segs[0][0] if segs else contour.start
    return _Contour(start, segs, contour.closed, -contour.area)


def _resample(contour: _Contour, n: int) -> _Contour:
    segs = list(contour.segs)
    if not segs:
        segs = [_line(contour.start, contour.start)]
    while len(segs) < n:
        i = max(range(len(segs)), key=lambda k: (_length(segs[k]), -k))
        a, b = _split(segs[i])
        segs[i : i + 1] = [a, b]
    return _Contour(contour.start, segs, contour.closed, contour.area)


def _rotate(contour: _Contour, k: int) -> _Contour:
    n = len(contour.segs)
    k %= n
    segs = contour.segs[k:] + contour.segs[:k]
    return _Contour(segs[0][0], segs, contour.closed, contour.area)


def _starts(contour: _Contour) -> list[Vec2]:
    return [s[0] for s in contour.segs]


def _shift_costs(a: _Contour, b: _Contour) -> list[float]:
    pa, pb = _starts(a), _starts(b)
    n = len(pa)
    return [sum((pa[i] - pb[(i + k) % n]).length() ** 2 for i in range(n)) for k in range(n)]


def _start_cost(a: _Contour, b: _Contour) -> float:
    return sum((p - q).length() ** 2 for p, q in zip(_starts(a), _starts(b), strict=True))


def _to_path(contours: list[_Contour]) -> Path2D:
    cmds: list[PathCommand] = []
    for c in contours:
        cmds.append(PathCommand("M", (c.start,)))
        cmds.extend(PathCommand("C", (s[1], s[2], s[3])) for s in c.segs)
        if c.closed:
            cmds.append(PathCommand("Z"))
    return Path2D(tuple(cmds))


def _check_len(name: str, value: tuple[Any, ...] | None, n: int) -> None:
    if value is not None and len(value) != n:
        raise ConfigurationError(f"PathMorph.{name} needs {n} entries, got {len(value)}")


# -- public API ----------------------------------------------------------------------------------
def normalize_paths(
    source: Path2D, target: Path2D, morph: PathMorph | None = None
) -> NormalizedPair:
    """Bring two paths to a shared structure so they can be interpolated.

    Returns ``compatible=False`` (with an ``error`` diagnostic) instead of guessing when the
    paths cannot be paired automatically; callers then cross-fade or pass an explicit
    :class:`PathMorph`.
    """
    morph = morph or PathMorph()
    if morph.normalizer is not None:
        custom_a, custom_b = morph.normalizer(source, target)
        if custom_a.kinds != custom_b.kinds:
            raise ConfigurationError("custom normalizer must return paths with equal structure")
        return NormalizedPair(
            custom_a, custom_b, (MorphDiagnostic("custom-normalizer", "caller-provided"),)
        )

    diags: list[MorphDiagnostic] = []
    src, tgt = _contours(source), _contours(target)
    if len(src) != len(tgt):
        return NormalizedPair(
            source,
            target,
            (
                MorphDiagnostic(
                    "subpath-count-mismatch",
                    f"source has {len(src)} subpath(s) and target has {len(tgt)}",
                    "error",
                ),
            ),
            compatible=False,
        )
    n_sub = len(src)
    for name, value in (
        ("pairing", morph.pairing),
        ("segments", morph.segments),
        ("shifts", morph.shifts),
        ("reverses", morph.reverses),
    ):
        _check_len(name, value, n_sub)

    if morph.pairing is not None:
        if sorted(morph.pairing) != list(range(n_sub)):
            raise ConfigurationError("PathMorph.pairing must be a permutation of subpath indices")
        pairing = list(morph.pairing)
    else:
        order_s = sorted(range(n_sub), key=lambda i: (-abs(src[i].area), i))
        order_t = sorted(range(n_sub), key=lambda i: (-abs(tgt[i].area), i))
        pairing = [0] * n_sub
        for s_idx, t_idx in zip(order_s, order_t, strict=True):
            pairing[s_idx] = t_idx
        if pairing != list(range(n_sub)):
            diags.append(
                MorphDiagnostic(
                    "subpaths-paired-by-area", f"paired subpaths by size order: {pairing}", "info"
                )
            )

    out_s: list[_Contour] = []
    out_t: list[_Contour | None] = [None] * n_sub
    for i in range(n_sub):
        a, b = src[i], tgt[pairing[i]]
        if a.closed != b.closed:
            return NormalizedPair(
                source,
                target,
                (
                    MorphDiagnostic(
                        "open-closed-mismatch",
                        f"subpath {i} is {'closed' if a.closed else 'open'} but its partner is "
                        f"{'closed' if b.closed else 'open'}",
                        "error",
                    ),
                ),
                compatible=False,
            )
        if a.closed and morph.orient:
            if a.area < 0:
                a = _reversed(a)
            if b.area < 0:
                b = _reversed(b)
        n = max(len(a.segs), len(b.segs), 1)
        if morph.segments is not None and morph.segments[i] is not None:
            n = int(morph.segments[i])  # type: ignore[arg-type]
            if n < max(len(a.segs), len(b.segs)):
                raise ConfigurationError(
                    f"PathMorph.segments[{i}]={n} is below the {max(len(a.segs), len(b.segs))} "
                    "segments the paths already have"
                )
        if len(a.segs) != n or len(b.segs) != n:
            diags.append(
                MorphDiagnostic("resampled", f"subpath {i} resampled to {n} segment(s)", "info")
            )
        a, b = _resample(a, n), _resample(b, n)

        reverse = morph.reverses[i] if morph.reverses is not None else None
        if a.closed:
            if reverse:
                b = _reversed(b)
            shift = morph.shifts[i] if morph.shifts is not None else None
            if shift is None:
                costs = _shift_costs(a, b)
                best = min(range(n), key=lambda k: (costs[k], k))
                rest = [c for k, c in enumerate(costs) if k != best]
                if rest and min(rest) - costs[best] <= _TIE * max(1.0, costs[best]):
                    diags.append(
                        MorphDiagnostic(
                            "ambiguous-alignment",
                            f"subpath {i}: several start vertices align equally well; "
                            f"using shift {best} (override with PathMorph.shifts)",
                            "warning",
                        )
                    )
                shift = best
            b = _rotate(b, shift)
        else:
            if reverse is None:
                fwd = sum(
                    (p - q).length() ** 2 for p, q in zip(_starts(a), _starts(b), strict=True)
                )
                rb = _reversed(b)
                rev = sum(
                    (p - q).length() ** 2 for p, q in zip(_starts(a), _starts(rb), strict=True)
                )
                reverse = rev < fwd
                if reverse:
                    diags.append(
                        MorphDiagnostic(
                            "reversed-open-path", f"subpath {i} direction reversed", "info"
                        )
                    )
            if reverse:
                b = _reversed(b)
        out_s.append(a)
        out_t[i] = b

    return NormalizedPair(
        _to_path(out_s), _to_path([c for c in out_t if c is not None]), tuple(diags)
    )
