"""Aggregate-aware outgoing direct-call emission for M16.4g1c3a."""
from __future__ import annotations

from typing import Any

from . import _machine_x86_64_core as _core
from ._machine_x86_64_call_validation import MachineBackendError
from ._machine_x86_64_types import pointer_pointee, require_abi_scalar

_STACK_SLOT_BYTES = 8
_CALLER_SAVE_BYTES = 16


def _rsp_qword(offset: int) -> str:
    return "QWORD PTR [rsp]" if offset == 0 else f"QWORD PTR [rsp+{offset}]"


def callee_requires_aggregate_call_emission(
    callee_plan: dict[str, Any] | None,
) -> bool:
    if not isinstance(callee_plan, dict):
        return False
    abi = callee_plan.get("abi_transport")
    if not isinstance(abi, dict):
        return False
    if abi.get("sret"):
        return True
    return any(
        isinstance(unit, dict) and unit.get("kind") != "scalar"
        for unit in abi.get("parameters", ())
    )


def _callee_parameters(callee_function: dict[str, Any]) -> dict[str, dict[str, Any]]:
    named: dict[str, dict[str, Any]] = {}
    for parameter in callee_function.get("parameters", ()):
        name = parameter.get("name") if isinstance(parameter, dict) else None
        type_name = parameter.get("type") if isinstance(parameter, dict) else None
        if (
            not isinstance(name, str)
            or not name
            or name in named
            or not isinstance(type_name, str)
            or not type_name
        ):
            raise MachineBackendError(
                f"function {callee_function.get('name')!r}: aggregate call emission requires unique typed parameters"
            )
        named[name] = parameter
    return named


def _operand_bindings(
    *,
    caller: dict[str, Any],
    callee_function: dict[str, Any],
    instruction: dict[str, Any],
    caller_value_types: dict[str, str],
) -> dict[str, str]:
    parameters = list(callee_function.get("parameters", ()))
    operands = list(instruction.get("operands", ()))
    if len(parameters) != len(operands):
        raise MachineBackendError(
            f"function {caller.get('name')!r}: aggregate call argument count does not match callee"
        )
    bindings: dict[str, str] = {}
    for index, (parameter, operand) in enumerate(zip(parameters, operands, strict=True)):
        name = parameter.get("name")
        type_name = parameter.get("type")
        if not isinstance(operand, str) or not operand:
            raise MachineBackendError(
                f"function {caller.get('name')!r}: aggregate call argument {index + 1} is invalid"
            )
        if caller_value_types.get(operand) != type_name:
            raise MachineBackendError(
                f"function {caller.get('name')!r}: aggregate call argument {index + 1} type mismatch"
            )
        bindings[name] = operand
    return bindings


def _load_operand(
    lines: list[str],
    *,
    operand: str,
    type_name: str,
    locations: dict[str, dict[str, Any]],
) -> int:
    _core._load_value(lines, operand, "rax", locations)
    bits = require_abi_scalar(type_name, context=f"aggregate call operand {operand!r}")
    if pointer_pointee(type_name) is None:
        _core._truncate_rax(lines, bits)
    return bits


def _argument_register_view(register: str, bits: int) -> str:
    for views in _core._ARG_REGISTERS:
        if views[64] == register:
            return views[64] if bits == 64 else views[32]
    raise MachineBackendError(
        f"aggregate direct-call transport uses invalid argument register {register!r}"
    )


def _validated_units(
    callee_function: dict[str, Any],
    callee_plan: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    abi = callee_plan.get("abi_transport")
    if not isinstance(abi, dict):
        raise MachineBackendError(
            f"function {callee_function.get('name')!r}: aggregate direct-call transport is missing"
        )
    if abi.get("sret"):
        raise MachineBackendError(
            f"function {callee_function.get('name')!r}: sret direct-call emission waits for M16.4g1c3b"
        )

    parameters = _callee_parameters(callee_function)
    units = list(abi.get("parameters", ()))
    seen_values: set[str] = set()
    stack_ordinals: list[int] = []

    for unit in units:
        if not isinstance(unit, dict):
            raise MachineBackendError("aggregate direct-call transport contains malformed unit")
        kind = unit.get("kind")
        values = list(unit.get("values", ()))
        transport = unit.get("transport", {})
        if kind not in {"scalar", "slice"}:
            raise MachineBackendError(
                f"aggregate direct-call emission does not yet support {kind!r} parameters"
            )
        expected_count = 1 if kind == "scalar" else 2
        if len(values) != expected_count:
            raise MachineBackendError(
                f"aggregate direct-call {kind} unit has inconsistent components"
            )
        for value in values:
            if (
                not isinstance(value, str)
                or not value
                or value not in parameters
                or value in seen_values
            ):
                raise MachineBackendError(
                    "aggregate direct-call transport has invalid or duplicate parameter components"
                )
            seen_values.add(value)

        transport_kind = transport.get("kind") if isinstance(transport, dict) else None
        if transport_kind == "registers":
            registers = list(transport.get("registers", ()))
            if len(registers) != len(values):
                raise MachineBackendError(
                    "aggregate direct-call register transport has inconsistent components"
                )
            for register in registers:
                _argument_register_view(register, 64)
        elif transport_kind == "stack":
            ordinal = transport.get("stack_ordinal")
            size_bytes = transport.get("size_bytes")
            alignment_bytes = transport.get("alignment_bytes")
            if (
                not isinstance(ordinal, int)
                or isinstance(ordinal, bool)
                or ordinal < 0
                or not isinstance(size_bytes, int)
                or isinstance(size_bytes, bool)
                or size_bytes != len(values) * _STACK_SLOT_BYTES
                or not isinstance(alignment_bytes, int)
                or isinstance(alignment_bytes, bool)
                or not 1 <= alignment_bytes <= _STACK_SLOT_BYTES
            ):
                raise MachineBackendError(
                    "aggregate direct-call stack transport is malformed"
                )
            stack_ordinals.append(ordinal)
        else:
            raise MachineBackendError(
                f"aggregate direct-call transport has unsupported kind {transport_kind!r}"
            )

    if seen_values != set(parameters):
        raise MachineBackendError(
            f"function {callee_function.get('name')!r}: aggregate direct-call transport does not cover all parameters"
        )
    if sorted(stack_ordinals) != list(range(len(stack_ordinals))):
        raise MachineBackendError(
            "aggregate direct-call stack ordinals must be contiguous from zero"
        )
    return units, parameters


def emit_aggregate_direct_call(
    lines: list[str],
    *,
    caller: dict[str, Any],
    instruction: dict[str, Any],
    locations: dict[str, dict[str, Any]],
    caller_value_types: dict[str, str],
    callee_function: dict[str, Any],
    callee_plan: dict[str, Any],
) -> None:
    """Emit one slice-aware SysV call while preserving whole-aggregate rollback."""
    callee = instruction.get("attributes", {}).get("callee")
    if callee != callee_function.get("name"):
        raise MachineBackendError(
            f"function {caller.get('name')!r}: aggregate call plan does not match callee"
        )

    units, parameters = _validated_units(callee_function, callee_plan)
    bindings = _operand_bindings(
        caller=caller,
        callee_function=callee_function,
        instruction=instruction,
        caller_value_types=caller_value_types,
    )

    stack_units = sorted(
        (
            unit
            for unit in units
            if unit.get("transport", {}).get("kind") == "stack"
        ),
        key=lambda unit: unit["transport"]["stack_ordinal"],
    )
    stack_bytes = sum(unit["transport"]["size_bytes"] for unit in stack_units)
    call_area_bytes = _core._align(stack_bytes + _CALLER_SAVE_BYTES, 16)
    save_offset = call_area_bytes - _CALLER_SAVE_BYTES

    lines.extend([
        f"    sub rsp, {call_area_bytes}",
        f"    mov {_rsp_qword(save_offset)}, r10",
        f"    mov {_rsp_qword(save_offset + 8)}, r11",
    ])

    stack_offset = 0
    for unit in stack_units:
        for component_index, parameter_name in enumerate(unit["values"]):
            operand = bindings[parameter_name]
            type_name = parameters[parameter_name]["type"]
            _load_operand(
                lines,
                operand=operand,
                type_name=type_name,
                locations=locations,
            )
            offset = stack_offset + component_index * _STACK_SLOT_BYTES
            lines.append(f"    mov {_rsp_qword(offset)}, rax")
        stack_offset += unit["transport"]["size_bytes"]

    for unit in units:
        transport = unit.get("transport", {})
        if transport.get("kind") != "registers":
            continue
        for parameter_name, register in zip(
            unit["values"], transport["registers"], strict=True
        ):
            operand = bindings[parameter_name]
            type_name = parameters[parameter_name]["type"]
            bits = _load_operand(
                lines,
                operand=operand,
                type_name=type_name,
                locations=locations,
            )
            target = _argument_register_view(register, bits)
            source = "rax" if bits == 64 else "eax"
            lines.append(f"    mov {target}, {source}")

    lines.append(f"    call {callee}")

    return_type = callee_function.get("return_type")
    result = instruction.get("result")
    if return_type != "void":
        bits = require_abi_scalar(
            return_type,
            context=f"function {caller.get('name')!r} aggregate call return",
        )
        if pointer_pointee(return_type) is None:
            _core._truncate_rax(lines, bits)
        lines.append("    mov rdx, rax")

    lines.extend([
        f"    mov r10, {_rsp_qword(save_offset)}",
        f"    mov r11, {_rsp_qword(save_offset + 8)}",
        f"    add rsp, {call_area_bytes}",
    ])

    if return_type != "void":
        if not isinstance(result, str) or not result:
            raise MachineBackendError(
                f"function {caller.get('name')!r}: aggregate call return requires a result"
            )
        _core._store_value(lines, result, "rdx", locations)


__all__ = [
    "callee_requires_aggregate_call_emission",
    "emit_aggregate_direct_call",
]
