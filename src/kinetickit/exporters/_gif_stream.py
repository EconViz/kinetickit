"""Private streaming GIF89a writer.

Pillow quantizes each frame and encodes its LZW data; this module splices the encoded frames into
one file as they arrive, so memory use is bounded by a single frame no matter how long the
animation is (Pillow's own multi-frame writer buffers every frame before writing).
"""

from __future__ import annotations

import io
import struct
from typing import BinaryIO

import numpy as np
import numpy.typing as npt
from PIL import Image

from kinetickit.errors import ConfigurationError, RenderError

_DITHER = {
    "none": Image.Dither.NONE,
    "floyd-steinberg": Image.Dither.FLOYDSTEINBERG,
}


def _skip_blocks(data: bytes, pos: int) -> int:
    while data[pos]:
        pos += data[pos] + 1
    return pos + 1


def _extract(gif: bytes) -> tuple[bytes, int, int, bytes]:
    """(palette, size_bits, interlace_bit, lzw) of the only image in a single-frame GIF."""
    packed = gif[10]
    pos = 13
    gct = b""
    if packed & 0x80:
        n = 3 * 2 ** ((packed & 7) + 1)
        gct = gif[pos : pos + n]
        pos += n
    while True:
        marker = gif[pos]
        if marker == 0x21:
            pos = _skip_blocks(gif, pos + 2)
        elif marker == 0x2C:
            lpacked = gif[pos + 9]
            pos += 10
            lct = b""
            if lpacked & 0x80:
                n = 3 * 2 ** ((lpacked & 7) + 1)
                lct = gif[pos : pos + n]
                pos += n
            start = pos
            pos = _skip_blocks(gif, pos + 1)
            palette = lct or gct
            if not palette:
                raise RenderError("encoder produced a GIF frame without a color table")
            bits = (len(palette) // 3).bit_length() - 2
            return palette, bits, lpacked & 0x40, gif[start:pos]
        else:
            raise RenderError(f"unexpected GIF block 0x{marker:02x}")


def _flatten(
    rgba: npt.NDArray[np.uint8], background: tuple[int, int, int]
) -> npt.NDArray[np.uint8]:
    rgb = rgba[..., :3]
    alpha = rgba[..., 3]
    if bool((alpha == 255).all()):
        return np.ascontiguousarray(rgb)
    a = alpha[..., None].astype(np.float32) / 255.0
    bg = np.array(background, dtype=np.float32)
    return np.ascontiguousarray((rgb * a + bg * (1.0 - a)).round().astype(np.uint8))


class GifStreamWriter:
    def __init__(
        self,
        out: BinaryIO,
        width: int,
        height: int,
        *,
        loop: int | None = 0,
        colors: int = 256,
        dither: str = "none",
        palette: str = "adaptive",
        disposal: int = 1,
        comment: bytes | None = None,
        background: tuple[int, int, int] = (255, 255, 255),
    ) -> None:
        if not 2 <= colors <= 256:
            raise ConfigurationError("colors must be between 2 and 256")
        if dither not in _DITHER:
            raise ConfigurationError(f"dither must be one of {sorted(_DITHER)}")
        if palette not in ("adaptive", "global"):
            raise ConfigurationError("palette must be 'adaptive' or 'global'")
        if disposal not in (0, 1, 2, 3):
            raise ConfigurationError("disposal must be 0, 1, 2 or 3")
        if width > 65535 or height > 65535:
            raise ConfigurationError("GIF dimensions are limited to 65535 pixels")
        self.out, self.width, self.height = out, width, height
        self.loop, self.colors, self.dither = loop, colors, dither
        self.palette_mode, self.disposal = palette, disposal
        self.comment, self.background = comment, background
        self._global: Image.Image | None = None
        self._started = False
        self.frames = 0

    def _header(self) -> None:
        w = self.out.write
        w(b"GIF89a")
        w(struct.pack("<HHBBB", self.width, self.height, 0x70, 0, 0))
        if self.loop is not None:
            w(b"\x21\xff\x0bNETSCAPE2.0\x03\x01" + struct.pack("<H", self.loop) + b"\x00")
        if self.comment:
            w(b"\x21\xfe")
            for i in range(0, len(self.comment), 255):
                chunk = self.comment[i : i + 255]
                w(bytes([len(chunk)]) + chunk)
            w(b"\x00")
        self._started = True

    def add_frame(self, rgba: npt.NDArray[np.uint8], delay_cs: int) -> None:
        if rgba.shape[1] != self.width or rgba.shape[0] != self.height:
            raise RenderError("frame size changed during export")
        if not 0 <= delay_cs <= 65535:
            raise ConfigurationError("frame delay out of range")
        rgb = _flatten(rgba, self.background)
        image = Image.fromarray(rgb, "RGB")
        dither = _DITHER[self.dither]
        if self.palette_mode == "global":
            if self._global is None:
                self._global = image.quantize(
                    colors=self.colors, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE
                )
            quantized = image.quantize(palette=self._global, dither=dither)
        else:
            quantized = image.quantize(
                colors=self.colors, method=Image.Quantize.MEDIANCUT, dither=dither
            )
        buf = io.BytesIO()
        quantized.save(buf, format="GIF", optimize=False)
        palette, bits, interlace, lzw = _extract(buf.getvalue())
        if not self._started:
            self._header()
        w = self.out.write
        w(b"\x21\xf9\x04" + bytes([self.disposal << 2]) + struct.pack("<H", delay_cs) + b"\x00\x00")
        w(b"\x2c" + struct.pack("<HHHH", 0, 0, self.width, self.height))
        w(bytes([0x80 | interlace | bits]))
        w(palette)
        w(lzw)
        self.frames += 1

    def close(self) -> None:
        if not self._started:
            raise RenderError("no frames were written")
        self.out.write(b"\x3b")
