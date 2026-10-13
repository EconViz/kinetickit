"""4x4 matrices (row-major, acting on column vectors) and decomposed transforms."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np
import numpy.typing as npt

from kinetickit.errors import ConfigurationError
from kinetickit.geometry.three_d.quaternion import Quaternion
from kinetickit.geometry.three_d.vector import Vec3


@dataclass(frozen=True, slots=True)
class Matrix4:
    """Row-major 4x4 matrix; vectors are columns, so ``(A @ B)`` applies ``B`` first."""

    m: tuple[float, ...]

    def __post_init__(self) -> None:
        if len(self.m) != 16 or not all(math.isfinite(v) for v in self.m):
            raise ConfigurationError("Matrix4 needs sixteen finite values")

    @classmethod
    def from_array(cls, a: npt.ArrayLike) -> Matrix4:
        arr = np.asarray(a, dtype=float)
        if arr.shape != (4, 4):
            raise ConfigurationError("expected a 4x4 array")
        return cls(tuple(float(v) for v in arr.ravel()))

    def array(self) -> npt.NDArray[np.float64]:
        return np.array(self.m, dtype=float).reshape(4, 4)

    @classmethod
    def identity(cls) -> Matrix4:
        return cls.from_array(np.eye(4))

    @classmethod
    def translation(cls, t: Vec3) -> Matrix4:
        a = np.eye(4)
        a[:3, 3] = (t.x, t.y, t.z)
        return cls.from_array(a)

    @classmethod
    def scaling(cls, s: Vec3) -> Matrix4:
        return cls.from_array(np.diag([s.x, s.y, s.z, 1.0]))

    @classmethod
    def rotation(cls, q: Quaternion) -> Matrix4:
        w, x, y, z = q.as_tuple()
        a = np.eye(4)
        a[:3, :3] = [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ]
        return cls.from_array(a)

    @classmethod
    def look_at(cls, eye: Vec3, target: Vec3, up: Vec3) -> Matrix4:
        """World → camera space; the camera looks down its own ``-z`` with ``+y`` up."""
        forward = target - eye
        if forward.length() == 0.0:
            raise ConfigurationError("camera position and target coincide")
        f = forward.normalized()
        right = f.cross(up)
        if right.length() < 1e-12:
            raise ConfigurationError("camera up vector is parallel to the view direction")
        r = right.normalized()
        u = r.cross(f)
        a = np.eye(4)
        a[0, :3] = (r.x, r.y, r.z)
        a[1, :3] = (u.x, u.y, u.z)
        a[2, :3] = (-f.x, -f.y, -f.z)
        a[:3, 3] = -a[:3, :3] @ np.array([eye.x, eye.y, eye.z])
        return cls.from_array(a)

    @classmethod
    def perspective(cls, fov: float, aspect: float, near: float, far: float) -> Matrix4:
        if not (0.0 < fov < math.pi) or aspect <= 0 or not (0.0 < near < far):
            raise ConfigurationError("invalid perspective parameters")
        f = 1.0 / math.tan(fov / 2.0)
        a = np.zeros((4, 4))
        a[0, 0], a[1, 1] = f / aspect, f
        a[2, 2], a[2, 3] = (far + near) / (near - far), 2.0 * far * near / (near - far)
        a[3, 2] = -1.0
        return cls.from_array(a)

    @classmethod
    def orthographic(cls, height: float, aspect: float, near: float, far: float) -> Matrix4:
        if height <= 0 or aspect <= 0 or not (near < far):
            raise ConfigurationError("invalid orthographic parameters")
        width = height * aspect
        a = np.eye(4)
        a[0, 0], a[1, 1] = 2.0 / width, 2.0 / height
        a[2, 2], a[2, 3] = -2.0 / (far - near), -(far + near) / (far - near)
        return cls.from_array(a)

    def __matmul__(self, other: Matrix4) -> Matrix4:
        return Matrix4.from_array(self.array() @ other.array())

    def inverse(self) -> Matrix4:
        a = self.array()
        if abs(np.linalg.det(a)) < 1e-14:
            raise ConfigurationError("singular matrix cannot be inverted")
        return Matrix4.from_array(np.linalg.inv(a))

    def apply_point(self, p: Vec3) -> Vec3:
        v = self.array() @ np.array([p.x, p.y, p.z, 1.0])
        w = v[3] if v[3] != 0.0 else 1.0
        return Vec3(v[0] / w, v[1] / w, v[2] / w)

    def apply_direction(self, d: Vec3) -> Vec3:
        v = self.array()[:3, :3] @ np.array([d.x, d.y, d.z])
        return Vec3(*v)

    def transform_points(self, pts: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        """Apply to an ``(N, 3)`` array of points (with perspective divide)."""
        a = self.array()
        h = np.concatenate([pts, np.ones((len(pts), 1))], axis=1) @ a.T
        w = np.where(h[:, 3:4] == 0.0, 1.0, h[:, 3:4])
        out: npt.NDArray[np.float64] = h[:, :3] / w
        return out


@dataclass(frozen=True, slots=True)
class Transform3D:
    """Scale, then rotate, then translate (about an optional pivot)."""

    translate: Vec3 = Vec3(0.0, 0.0, 0.0)
    rotation: Quaternion = Quaternion()
    scale: Vec3 = Vec3(1.0, 1.0, 1.0)
    pivot: Vec3 = Vec3(0.0, 0.0, 0.0)

    def __post_init__(self) -> None:
        object.__setattr__(self, "translate", Vec3.coerce(self.translate))
        object.__setattr__(self, "rotation", Quaternion.coerce(self.rotation))
        s = self.scale
        object.__setattr__(
            self,
            "scale",
            Vec3(s, s, s)
            if isinstance(s, (int, float)) and not isinstance(s, bool)
            else Vec3.coerce(s),
        )
        object.__setattr__(self, "pivot", Vec3.coerce(self.pivot))

    @classmethod
    def coerce(cls, value: Any) -> Transform3D:
        if isinstance(value, Transform3D):
            return value
        raise ConfigurationError(f"cannot interpret {value!r} as a Transform3D")

    @property
    def is_identity(self) -> bool:
        return self == Transform3D()

    def matrix(self) -> Matrix4:
        return (
            Matrix4.translation(self.translate)
            @ Matrix4.translation(self.pivot)
            @ Matrix4.rotation(self.rotation)
            @ Matrix4.scaling(self.scale)
            @ Matrix4.translation(-self.pivot)
        )


class Transform3DInterpolator:
    def interpolate(self, start: Transform3D, end: Transform3D, progress: float) -> Transform3D:
        if progress == 0.0:
            return start
        if progress == 1.0:
            return end
        from kinetickit.geometry.three_d.quaternion import QuaternionInterpolator
        from kinetickit.geometry.three_d.vector import Vec3Interpolator

        v, q = Vec3Interpolator(), QuaternionInterpolator()
        return Transform3D(
            v.interpolate(start.translate, end.translate, progress),
            q.interpolate(start.rotation, end.rotation, progress),
            v.interpolate(start.scale, end.scale, progress),
            v.interpolate(start.pivot, end.pivot, progress),
        )
