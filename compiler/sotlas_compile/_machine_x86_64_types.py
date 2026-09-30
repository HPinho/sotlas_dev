"""Machine-level scalar type helpers for x86-64 SysV lowering.

M16.4a admits canonical raw/reference pointer values as opaque 64-bit ABI
scalars without treating them as integers.  Dereference support is deliberately
narrow and only exposes unsigned scalar pointees whose memory width is
already defined by the native backend.
"""
from __future__ import annotations

from typing import Any

from . import _machine_x86_64_core as _core


_DEREFERENCEABLE_POINTEES = frozenset({
    "u8", "u16", "u32", "u64", "usize",
})


def pointer_pointee(type_name: Any) -> str | None:
    """Return the canonical pointee for one SIR/Target-IR pointer spelling."""
    if not isinstance(type_name, str) or not type_name.endswith("*"):
        return None
    pointee = type_name[:-1]
    if not pointee or "*" in pointee or pointee not in _DEREFERENCEABLE_POINTEES:
        return None
    return pointee


def require_abi_scalar(type_name: Any, *, context: str) -> int:
    """Accept existing machine scalars plus opaque canonical pointers."""
    if pointer_pointee(type_name) is not None:
        return 64
    return _core._require_machine_scalar(type_name, context=context)


def require_pointer_to(
    type_name: Any,
    pointee_type: Any,
    *,
    context: str,
) -> int:
    """Validate an indirect read and return the pointee width in bits."""
    pointee = pointer_pointee(type_name)
    if pointee is None:
        raise _core.MachineBackendError(
            f"{context}: indirect load source must be a supported pointer type"
        )
    if pointee != pointee_type:
        raise _core.MachineBackendError(
            f"{context}: pointer to {pointee!r} cannot load {pointee_type!r}"
        )
    return _core._require_machine_scalar(pointee, context=context)


__all__ = [
    "pointer_pointee",
    "require_abi_scalar",
    "require_pointer_to",
]
