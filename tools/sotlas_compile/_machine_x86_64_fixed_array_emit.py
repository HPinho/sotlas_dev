"""Machine emission for validated fixed-array element address projection."""
from __future__ import annotations

from typing import Any

from . import _machine_x86_64_core as _core
from ._machine_x86_64_call_validation import MachineBackendError
from ._machine_x86_64_types import fixed_array_pointee, pointer_pointee


def _fixed_array_stride(
    *,
    function_name: str,
    instruction: dict[str, Any],
    value_types: dict[str, str],
    base: str,
) -> tuple[str, int, int]:
    attributes = instruction.get("attributes", {})
    element_type = attributes.get("element_type")
    length = attributes.get("length")
    base_array = fixed_array_pointee(value_types.get(base))
    if base_array != (element_type, length):
        raise MachineBackendError(
            f"function {function_name!r}: fixed-array base type does not match projection"
        )
    if pointer_pointee(instruction.get("type")) != element_type:
        raise MachineBackendError(
            f"function {function_name!r}: fixed-array result type does not match element"
        )
    width_bits = _core._require_machine_scalar(
        element_type,
        context=f"function {function_name!r}: fixed-array element",
    )
    return element_type, length, width_bits // 8


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
    _, length, stride_bytes = _fixed_array_stride(
        function_name=name,
        instruction=instruction,
        value_types=value_types,
        base=base,
    )
    index = instruction.get("attributes", {}).get("index")
    if (
        not isinstance(index, int)
        or isinstance(index, bool)
        or index < 0
        or index >= length
    ):
        raise MachineBackendError(
            f"function {name!r}: array_address index is outside the fixed array"
        )

    offset = index * stride_bytes
    _core._load_value(lines, base, "rcx", locations)
    if offset:
        lines.append(f"    lea rax, [rcx+{offset}]")
    else:
        lines.append("    lea rax, [rcx]")
    _core._store_value(
        lines, instruction.get("result"), "rax", locations
    )


def emit_fixed_array_dynamic_address(
    lines: list[str],
    *,
    function: dict[str, Any],
    instruction: dict[str, Any],
    locations: dict[str, dict[str, Any]],
    value_types: dict[str, str],
) -> None:
    """Emit runtime-bounded fixed-array projection with a target trap on OOB."""
    name = function["name"]
    operands = instruction.get("operands", ())
    if len(operands) != 2:
        raise MachineBackendError(
            f"function {name!r}: array_address_dynamic requires base and index"
        )
    base, index_value = operands
    _, length, stride_bytes = _fixed_array_stride(
        function_name=name,
        instruction=instruction,
        value_types=value_types,
        base=base,
    )
    if value_types.get(index_value) != "usize":
        raise MachineBackendError(
            f"function {name!r}: array_address_dynamic index must be usize"
        )
    if instruction.get("attributes", {}).get("bounds_policy") != "trap":
        raise MachineBackendError(
            f"function {name!r}: array_address_dynamic requires trap bounds policy"
        )

    # rcx/rdx are backend scratch registers, distinct from the current r10/r11
    # value-register class.  This keeps base and index intact even when either
    # value was spilled by the generic allocation preview.
    _core._load_value(lines, base, "rcx", locations)
    _core._load_value(lines, index_value, "rdx", locations)
    lines.append(f"    cmp rdx, {length}")
    lines.append("    jb 1f")
    lines.append("    ud2")
    lines.append("1:")
    if stride_bytes == 1:
        lines.append("    lea rax, [rcx+rdx]")
    else:
        lines.append(f"    lea rax, [rcx+rdx*{stride_bytes}]")
    _core._store_value(
        lines, instruction.get("result"), "rax", locations
    )


__all__ = ["emit_fixed_array_address", "emit_fixed_array_dynamic_address"]
