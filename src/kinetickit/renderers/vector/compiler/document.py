"""The SVG compiler: camera world group and document assembly."""

from __future__ import annotations

import base64

from kinetickit.accessibility import ReducedMotion
from kinetickit.errors import CapabilityError
from kinetickit.geometry.two_d import Vec2
from kinetickit.interpolation import Color
from kinetickit.renderers.vector.compiler.encoding import ChannelEncoder
from kinetickit.renderers.vector.compiler.model import (
    SVG_NS,
    Channel,
    LayoutResultView,
    SvgDocument,
    Track,
    _paint,
)
from kinetickit.renderers.vector.compiler.structure import StructureEmitters
from kinetickit.renderers.vector.projected import ProjectedWorld
from kinetickit.renderers.vector.svg import Element, svg_id
from kinetickit.scene import (
    Camera2D,
)


class SvgCompiler(StructureEmitters, ChannelEncoder):
    def world_group(self) -> tuple[Element, Element]:
        """The (outermost, innermost) elements of the world transform stack."""
        cam = self.snapshot.camera
        assert isinstance(cam, Camera2D)
        assert self.layout is not None
        lay = self.layout
        if not any(r.node_id == cam.id for r in self.animated):
            m = lay.world_to_pixel(cam).m
            matrix = " ".join(self.fmt(v) for v in (m[0], m[3], m[1], m[4], m[2], m[5]))
            world = Element("g", {"id": "world", "transform": f"matrix({matrix})"})
            return world, world
        vp = lay.viewport
        cx = vp.margins.left + vp.plot_width / 2.0
        cy = vp.margins.top + vp.plot_height / 2.0
        top = Element(
            "g", {"id": "world", "transform": f"translate({self.fmt(cx)} {self.fmt(cy)})"}
        )
        zoom = top.add(Element("g", {"data-kk-layer": "zoom"}))
        pan = zoom.add(Element("g", {"data-kk-layer": "pan"}))

        def window(c: Camera2D) -> tuple[float, Vec2]:
            view = LayoutResultView(lay, c)
            return view.scale, view.center

        s, ctr = window(cam)
        zoom.set("transform", f"scale({self.fmt(s)} {self.fmt(-s)})")
        pan.set("transform", f"translate({self.fmt(-ctr.x)} {self.fmt(-ctr.y)})")
        self.channels.append(
            Channel(
                cam,
                ("view", "pan", "zoom"),
                [
                    Track(
                        zoom,
                        "transform",
                        lambda n, c: f"{self.fmt(window(n)[0])} {self.fmt(-window(n)[0])}",
                        transform="scale",
                    ),
                    Track(
                        pan,
                        "transform",
                        lambda n, c: f"{self.fmt(-window(n)[1].x)} {self.fmt(-window(n)[1].y)}",
                        transform="translate",
                    ),
                ],
                linear=False,
            )
        )
        return top, pan

    def build(self) -> SvgDocument:
        st = self.settings
        w, h = st.width, st.height
        root = Element(
            "svg",
            {
                "xmlns": SVG_NS,
                "width": self.fmt(w),
                "height": self.fmt(h),
                "viewBox": f"0 0 {self.fmt(w)} {self.fmt(h)}",
                "role": "img",
            },
        )
        info = self.animation.accessibility
        title = st.title or (info.title if info else None)
        description = st.description or (info.description if info else None)
        if info is not None:
            root.set("lang", info.lang)
        if title:
            title_id = svg_id("kk-title", self.ids)
            root.add(Element("title", {"id": title_id}, text=title))
            root.set("aria-labelledby", title_id)
        if description:
            desc_id = svg_id("kk-desc", self.ids)
            root.add(Element("desc", {"id": desc_id}, text=description))
            root.set("aria-describedby", desc_id)
        defs_index = len(root.children)
        if st.background is not None:
            attrs = {"id": "background", "width": "100%", "height": "100%"}
            _paint(attrs, "fill", Color.parse(st.background))
            root.add(Element("rect", attrs))
        if self.is3d:
            top = inner = Element("g", {"id": "world"})
            ProjectedWorld(self).build(inner)
            root.add(top)
        else:
            top, inner = self.world_group()
            root.add(top)
            for node in self.ordered(self.snapshot.nodes):
                el = self.emit(node, False)
                if el is not None:
                    inner.add(el)
        overlay = Element("g", {"id": "overlay"})
        for node in self.ordered(self.snapshot.overlay):
            el = self.emit(node, True)
            if el is not None:
                overlay.add(el)
        if overlay.children:
            root.add(overlay)
        self.encode_all()
        unconsumed = [r for r in self.animated if r not in self.consumed]
        if unconsumed:
            names = ", ".join(sorted(str(r) for r in unconsumed))
            raise CapabilityError(
                f"the vector renderer cannot animate: {names}",
                missing=("feature:property-animation",),
            )
        if self.fonts and st.embed_fonts:
            self.defs.children.insert(
                0, Element("style", {"type": "text/css"}, text=self.font_css())
            )
        if self.defs.children:
            root.children.insert(defs_index, self.defs)
        rm = st.reduced_motion
        if rm == "auto":
            rm = info.reduced_motion if info else ReducedMotion()
        if rm is not None and self.D > 0 and self.count > 0:
            rep = rm.representative_time(self.D)
            js = (
                "(function(){var s=document.currentScript.ownerSVGElement;"
                'if(window.matchMedia&&matchMedia("(prefers-reduced-motion: reduce)").matches'
                f"&&s.pauseAnimations){{s.pauseAnimations();s.setCurrentTime({rep:.6g});}}}})();"
            )
            root.add(Element("script", {"type": "application/ecmascript"}, text=js))
        text = '<?xml version="1.0" encoding="UTF-8"?>\n' + root.serialize(2 if st.pretty else None)
        return SvgDocument(
            root=root,
            text=text,
            width=w,
            height=h,
            duration=self.D,
            element_ids=dict(self.idmap),
            warnings=tuple(self.warnings),
            animation_count=self.count,
            fonts=tuple(sorted({f.family for f in self.fonts.values()})),
        )

    def font_css(self) -> str:
        rules = []
        for f in self.fonts.values():
            kind = {"opentype": "otf", "truetype": "ttf"}.get(f.format, f.format)
            data = base64.b64encode(f.data).decode("ascii")
            rules.append(
                f'@font-face{{font-family:"{f.family}";font-weight:{f.weight};'
                f"font-style:{f.style};src:url(data:font/{kind};base64,{data})}}"
            )
        return "".join(rules)
