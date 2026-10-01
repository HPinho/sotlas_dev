"""Machine emission for validated fixed-array element address projection."""
from __future__ import annotations

from typing import Any

from . import _machine_x86_64_core as _core
from ._machine_x86_64_call_validation import MachineBackendError
from ._machine_x86_64_types import fixed_array_pointee, pointer_pointee


def emit_fixed_array_address(
    lines: list[str],
    *,
    function: dict[str, Any],
    instruction: dict[str, Any],
    locations: dict[str, dict[str, Any]],
    value_types: dict[str, str],
) -> None:
    """Emit one constant-index fixed-array projection after Target IR validation."""
    name = function["name"]
    operands = instruction.get("operands", ())
    if len(operands) != 1:
        raise MachineBackendError(
            f"function {name!r}: array_address requires one fixed-array pointer"
        )
    base = operands[0]
    attributes = instruction.get("attributes", {})
    element_type = attributes.get("element_type")
    length = attributes.get("length")
    index = attributes.get("index")
    base_array = fixed_array_pointee(value_types.get(base))
    if base_array != (element_type, length):
        raise MachineBackendError(
            f"function {name!r}: array_address base type does not match fixed array"
        )
    if (
        not isinstance(index, int)
        or isinstance(index, bool)
        or index < 0
        or index >= length
    ):
        raise MachineBackendError(
            f"function {name!r}: array_address index is outside the fixed array"
        )
    if pointer_pointee(instruction.get("type")) != element_type:
        raise MachineBackendError(
            f"function {name!r}: array_address result type does not match element"
        )

    width_bits = _core._require_machine_scalar(
        element_type,
        context=f"function {name!r}: fixed-array element",
    )
    stride_bytes = width_bits // 8
    offset = index * stride_bytes
    _core._load_value(lines, base, "rcx", locations)
    if offset:
        lines.append(f"    lea rax, [rcx+{offset}]")
    else:
        lines.append("    lea rax, [rcx]")
    _core._store_value(
        lines, instruction.get("result"), "rax", locations
    )


__all__ = ["emit_fixed_array_address"]
