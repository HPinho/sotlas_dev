"""Machine emission for checked slice indexing (M16.4f3c)."""
from __future__ import annotations

from typing import Any

from . import _machine_x86_64_core as _core
from ._machine_x86_64_call_validation import MachineBackendError
from ._machine_x86_64_types import pointer_pointee
from .target_ir_slices import TargetIRSliceError, validate_target_ir_slice_views

_SLICE_ELEMENT_TYPES = frozenset({"u8", "u16", "u32", "u64", "usize"})


def _slice_view_keys(
    target_ir: dict[str, Any],
) -> dict[str, set[tuple[str, str, str]]]:
    try:
        validate_target_ir_slice_views(target_ir)
    except TargetIRSliceError as error:
        raise MachineBackendError(str(error)) from error

    indexed: dict[str, set[tuple[str, str, str]]] = {}
    for view in target_ir.get("slice_views", ()) or ():
        indexed.setdefault(view["function"], set()).add(
            (view["data"], view["length"], view["element_type"])
        )
    return indexed


def validate_slice_indexing_machine_contract(target_ir: dict[str, Any]) -> None:
    """Require a logical slice view and same-block dominating bounds proof."""
    if not isinstance(target_ir, dict) or target_ir.get("schema") != "sotlas.target-ir.v1":
        raise MachineBackendError("x86-64 slice emission requires Target IR v1")

    views = _slice_view_keys(target_ir)
    for function in target_ir.get("functions", ()):
        name = function.get("name")
        value_types = _core._type_map(function)
        valid_views = views.get(name, set())
        for block in function.get("blocks", ()):
            proven: set[tuple[str, str]] = set()
            for instruction in block.get("instructions", ()):
                op = instruction.get("op")
                operands = tuple(instruction.get("operands", ()))
                if op == "bounds_check":
                    if len(operands) != 2:
                        raise MachineBackendError(
                            f"function {name!r}: bounds_check requires index and length"
                        )
                    index, length = operands
                    if (
                        value_types.get(index) != "usize"
                        or value_types.get(length) != "usize"
                        or not isinstance(
                            instruction.get("attributes", {}).get("can_eliminate"), bool
                        )
                    ):
                        raise MachineBackendError(
                            f"function {name!r}: malformed slice bounds_check"
                        )
                    proven.add((index, length))
                    continue

                if op != "slice_address":
                    continue
                if len(operands) != 3:
                    raise MachineBackendError(
                        f"function {name!r}: slice_address requires base, index and length"
                    )
                base, index, length = operands
                attributes = instruction.get("attributes", {})
                element_type = attributes.get("element_type")
                if (
                    element_type not in _SLICE_ELEMENT_TYPES
                    or value_types.get(base) != f"{element_type}*"
                    or value_types.get(index) != "usize"
                    or value_types.get(length) != "usize"
                    or pointer_pointee(instruction.get("type")) != element_type
                    or attributes.get("bounds_policy") != "checked"
                    or (base, length, element_type) not in valid_views
                    or (index, length) not in proven
                ):
                    raise MachineBackendError(
                        f"function {name!r}: slice_address lacks a matching slice view, dominating bounds proof, or type contract"
                    )


def emit_slice_bounds_check(
    lines: list[str],
    *,
    function: dict[str, Any],
    instruction: dict[str, Any],
    locations: dict[str, dict[str, Any]],
    value_types: dict[str, str],
) -> None:
    """Emit unsigned ``index < length`` with a target trap on failure."""
    name = function["name"]
    operands = tuple(instruction.get("operands", ()))
    if len(operands) != 2:
        raise MachineBackendError(
            f"function {name!r}: bounds_check requires index and length"
        )
    index, length = operands
    if value_types.get(index) != "usize" or value_types.get(length) != "usize":
        raise MachineBackendError(
            f"function {name!r}: slice bounds operands must be usize"
        )
    if not isinstance(
        instruction.get("attributes", {}).get("can_eliminate"), bool
    ):
        raise MachineBackendError(
            f"function {name!r}: slice bounds metadata is malformed"
        )

    _core._load_value(lines, index, "rcx", locations)
    _core._load_value(lines, length, "rdx", locations)
    lines.append("    cmp rcx, rdx")
    lines.append("    jb 1f")
    lines.append("    ud2")
    lines.append("1:")


def emit_slice_address(
    lines: list[str],
    *,
    function: dict[str, Any],
    instruction: dict[str, Any],
    locations: dict[str, dict[str, Any]],
    value_types: dict[str, str],
) -> None:
    """Emit the address projection after module validation proved the check."""
    name = function["name"]
    operands = tuple(instruction.get("operands", ()))
    if len(operands) != 3:
        raise MachineBackendError(
            f"function {name!r}: slice_address requires base, index and length"
        )
    base, index, length = operands
    attributes = instruction.get("attributes", {})
    element_type = attributes.get("element_type")
    if (
        element_type not in _SLICE_ELEMENT_TYPES
        or value_types.get(base) != f"{element_type}*"
        or value_types.get(index) != "usize"
        or value_types.get(length) != "usize"
        or pointer_pointee(instruction.get("type")) != element_type
        or attributes.get("bounds_policy") != "checked"
    ):
        raise MachineBackendError(
            f"function {name!r}: slice_address has inconsistent projection types"
        )

    width_bits = _core._require_machine_scalar(
        element_type,
        context=f"function {name!r}: slice element",
    )
    stride_bytes = width_bits // 8

    _core._load_value(lines, base, "rcx", locations)
    _core._load_value(lines, index, "rdx", locations)
    if stride_bytes == 1:
        lines.append("    lea rax, [rcx+rdx]")
    else:
        lines.append(f"    lea rax, [rcx+rdx*{stride_bytes}]")
    _core._store_value(lines, instruction.get("result"), "rax", locations)


__all__ = [
    "emit_slice_address",
    "emit_slice_bounds_check",
    "validate_slice_indexing_machine_contract",
]
