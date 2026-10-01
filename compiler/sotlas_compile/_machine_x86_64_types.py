"""Machine-level scalar and pointer type helpers for x86-64 SysV lowering.

M16.4a admits canonical pointer values as opaque 64-bit ABI scalars. M16.4c
extends that transport contract to one-level nominal pointers such as ``Pair*``
without making aggregate pointees directly dereferenceable. M16.4d1 additionally
admits canonical fixed-array pointer spellings such as ``[u32;4]*`` as opaque
GP64 values; element projection remains a separately validated operation.
"""
from __future__ import annotations

import re
from typing import Any

from . import _machine_x86_64_core as _core


_DEREFERENCEABLE_POINTEES = frozenset({
    "u8", "u16", "u32", "u64", "usize",
})
_POINTER_POINTEE_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_FIXED_ARRAY_POINTEE_RE = re.compile(
    r"\[(u8|u16|u32|u64|usize);([1-9][0-9]*)\]"
)


def fixed_array_pointee(type_name: Any) -> tuple[str, int] | None:
    """Return ``(element_type, length)`` for one canonical fixed-array pointer."""
    if (
        not isinstance(type_name, str)
        or not type_name.endswith("*")
        or type_name.count("*") != 1
    ):
        return None
    match = _FIXED_ARRAY_POINTEE_RE.fullmatch(type_name[:-1])
    if match is None:
        return None
    return match.group(1), int(match.group(2))


def pointer_pointee(type_name: Any) -> str | None:
    """Return one canonical first-level scalar, nominal, or fixed-array pointee."""
    if (
        not isinstance(type_name, str)
        or not type_name.endswith("*")
        or type_name.count("*") != 1
    ):
        return None
    pointee = type_name[:-1]
    if _POINTER_POINTEE_RE.fullmatch(pointee) is not None:
        return pointee
    if _FIXED_ARRAY_POINTEE_RE.fullmatch(pointee) is not None:
        return pointee
    return None


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
    "fixed_array_pointee",
    "pointer_pointee",
    "require_abi_scalar",
    "require_pointer_to",
]
