"""Destinations owned by KineticKit: files (atomic), byte buffers and streams."""

from __future__ import annotations

import contextlib
import io
import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, BinaryIO, Protocol, runtime_checkable

from kinetickit.errors import ConfigurationError


@runtime_checkable
class Destination(Protocol):
    """Where an exporter writes. ``open_binary`` commits only if the block completes."""

    @property
    def description(self) -> str: ...

    def open_binary(self) -> contextlib.AbstractContextManager[BinaryIO]: ...


class FileDestination:
    """Write to a file atomically: a temporary sibling is renamed on success, removed on failure."""

    def __init__(self, path: str | os.PathLike[str], *, make_parents: bool = False) -> None:
        self.path = Path(path)
        self.make_parents = make_parents

    @property
    def description(self) -> str:
        return str(self.path)

    @contextmanager
    def open_binary(self) -> Iterator[BinaryIO]:
        if self.make_parents:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        elif not self.path.parent.is_dir():
            raise ConfigurationError(f"directory does not exist: {self.path.parent}")
        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.", suffix=".tmp", dir=self.path.parent
        )
        tmp = Path(tmp_name)
        try:
            with os.fdopen(fd, "wb") as handle:
                yield handle
            os.replace(tmp, self.path)
        except BaseException:
            with contextlib.suppress(OSError):
                tmp.unlink()
            raise


class BytesDestination:
    """Collect output in memory; read it back with :meth:`getvalue`."""

    def __init__(self) -> None:
        self._buffer = io.BytesIO()

    @property
    def description(self) -> str:
        return "<bytes>"

    @contextmanager
    def open_binary(self) -> Iterator[BinaryIO]:
        fresh = io.BytesIO()
        yield fresh
        self._buffer = fresh

    def getvalue(self) -> bytes:
        return self._buffer.getvalue()


class _TextAdapter(io.RawIOBase):
    def __init__(self, stream: Any) -> None:
        self._stream = stream

    def writable(self) -> bool:
        return True

    def write(self, data: Any) -> int:
        self._stream.write(bytes(data).decode("utf-8"))
        return len(data)


class StreamDestination:
    """Write to a caller-owned binary or text stream (it is neither closed nor rewound)."""

    def __init__(self, stream: Any) -> None:
        if not hasattr(stream, "write"):
            raise ConfigurationError("a stream destination needs an object with write()")
        self.stream = stream
        self.text = isinstance(stream, io.TextIOBase)

    @property
    def description(self) -> str:
        return "<text stream>" if self.text else "<binary stream>"

    @contextmanager
    def open_binary(self) -> Iterator[BinaryIO]:
        yield _TextAdapter(self.stream) if self.text else self.stream  # type: ignore[misc]


def as_destination(target: Any) -> Destination:
    """Coerce a path, stream or :class:`Destination` into a destination."""
    if isinstance(target, (FileDestination, BytesDestination, StreamDestination)):
        return target
    if isinstance(target, (str, os.PathLike)):
        return FileDestination(target)
    if hasattr(target, "write"):
        return StreamDestination(target)
    if isinstance(target, Destination):
        return target
    raise ConfigurationError(f"cannot write to {type(target).__name__}")
