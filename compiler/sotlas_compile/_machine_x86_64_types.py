"""Machine-level scalar and pointer type helpers for x86-64 SysV lowering.

M16.4a admits canonical pointer values as opaque 64-bit ABI scalars. M16.4c
extends that transport contract to one-level nominal pointers such as ``Pair*``
without making aggregate pointees directly dereferenceable. Indirect scalar
loads remain restricted to the explicitly supported scalar pointees below.
"""
from __future__ import annotations

import re
from typing import Any

from . import _machine_x86_64_core as _core


_DEREFERENCEABLE_POINTEES = frozenset({
    "u8", "u16", "u32", "u64", "usize",
})
_POINTER_POINTEE_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def pointer_pointee(type_name: Any) -> str | None:
    """Return one canonical first-level scalar or nominal pointer pointee."""
    if (
        not isinstance(type_name, str)
        or not type_name.endswith("*")
        or type_name.count("*") != 1
    ):
        return None
    pointee = type_name[:-1]
    if not pointee or _POINTER_POINTEE_RE.fullmatch(pointee) is None:
        return None
    return pointee


def require_abi_scalar(type_name: Any, *, context: str) -> int:
    """Accept machine scalars plus opaque canonical first-level pointers."""
    if pointer_pointee(type_name) is not None:
        return 64
    return _core._require_machine_scalar(type_name, context=context)


def require_pointer_to(
    type_name: Any,
    pointee_type: Any,
    *,
    context: str,
) -> int:
    """Validate an indirect scalar read and return the pointee width in bits."""
    pointee = pointer_pointee(type_name)
    if pointee is None or pointee not in _DEREFERENCEABLE_POINTEES:
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
