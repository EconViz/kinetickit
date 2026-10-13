"""A tiny deterministic XML element builder (stdlib-free of third-party code)."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any
from xml.sax.saxutils import escape, quoteattr

_ID_UNSAFE = re.compile(r"[^A-Za-z0-9_.-]")


def num(value: float, precision: int = 4) -> str:
    """Compact decimal with at most ``precision`` places; never emits ``-0``."""
    text = f"{value:.{precision}f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text in ("-0", "") else text


def svg_id(node_id: str, taken: set[str]) -> str:
    """A valid, unique XML id derived from a node id."""
    base = _ID_UNSAFE.sub("_", node_id)
    if not base or not (base[0].isalpha() or base[0] == "_"):
        base = f"k-{base}"
    candidate, n = base, 2
    while candidate in taken:
        candidate = f"{base}_{n}"
        n += 1
    taken.add(candidate)
    return candidate


class Element:
    """An XML element with insertion-ordered attributes (so output is deterministic)."""

    __slots__ = ("attrs", "children", "tag", "text")

    def __init__(
        self,
        tag: str,
        attrs: dict[str, Any] | None = None,
        children: Iterable[Element] | None = None,
        text: str | None = None,
    ) -> None:
        self.tag = tag
        self.attrs: dict[str, str] = {}
        self.children: list[Element] = list(children or ())
        self.text = text
        for k, v in (attrs or {}).items():
            self.set(k, v)

    def set(self, key: str, value: Any) -> Element:
        if value is not None:
            self.attrs[key] = str(value)
        return self

    def add(self, child: Element) -> Element:
        self.children.append(child)
        return child

    def find_all(self, tag: str) -> list[Element]:
        out = [self] if self.tag == tag else []
        for c in self.children:
            out.extend(c.find_all(tag))
        return out

    def serialize(self, indent: int | None = 2, _level: int = 0) -> str:
        pad = "" if indent is None else " " * (indent * _level)
        nl = "" if indent is None else "\n"
        attrs = "".join(f" {k}={quoteattr(v)}" for k, v in self.attrs.items())
        if not self.children and self.text is None:
            return f"{pad}<{self.tag}{attrs}/>{nl}"
        if not self.children:
            return f"{pad}<{self.tag}{attrs}>{escape(self.text or '')}</{self.tag}>{nl}"
        inner = "".join(c.serialize(indent, _level + 1) for c in self.children)
        text = escape(self.text) if self.text else ""
        return f"{pad}<{self.tag}{attrs}>{text}{nl}{inner}{pad}</{self.tag}>{nl}"
