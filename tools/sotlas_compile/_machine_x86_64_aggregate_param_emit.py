"""Aggregate-aware x86-64 SysV incoming parameter emission for M16.4g1c2."""
from __future__ import annotations

from typing import Any

from . import _machine_x86_64_core as _core
from ._machine_x86_64_call_validation import MachineBackendError
from ._machine_x86_64_types import pointer_pointee, require_abi_scalar

_STACK_BASE_OFFSET = 16
_STACK_SLOT_BYTES = 8

def _parameter_types(function: dict[str, Any]) -> dict[str, str]:
    typed: dict[str, str] = {}
    for parameter in function.get("parameters", ()):
        name = parameter.get("name") if isinstance(parameter, dict) else None
        type_name = parameter.get("type") if isinstance(parameter, dict) else None
        if not isinstance(name, str) or not name or name in typed:
            raise MachineBackendError(
                f"function {function.get('name')!r}: aggregate parameter emission requires unique named parameters"
            )
        if not isinstance(type_name, str) or not type_name:
            raise MachineBackendError(
                f"function {function.get('name')!r}: parameter {name!r} lacks a type"
            )
        typed[name] = type_name
    return typed

def _load_transport_value(
    lines: list[str],
    *,
    value_name: str,
    type_name: str,
    source: dict[str, Any],
    locations: dict[str, dict[str, Any]],
) -> None:
    kind = source.get("kind")
    if kind == "register":
        register = source.get("register")
        if not isinstance(register, str) or not register:
            raise MachineBackendError(
                f"parameter {value_name!r}: aggregate register transport is malformed"
            )
        lines.append(f"    mov rax, {register}")
    elif kind == "stack":
        offset = source.get("offset_bytes")
        if (
            not isinstance(offset, int)
            or isinstance(offset, bool)
            or offset < _STACK_BASE_OFFSET
            or offset % _STACK_SLOT_BYTES != 0
        ):
            raise MachineBackendError(
                f"parameter {value_name!r}: aggregate stack transport has invalid offset"
            )
        lines.append(f"    mov rax, QWORD PTR [rbp+{offset}]")
    else:
        raise MachineBackendError(
            f"parameter {value_name!r}: unknown aggregate transport source {kind!r}"
        )

    if pointer_pointee(type_name) is None:
        bits = require_abi_scalar(
            type_name,
            context=f"aggregate incoming parameter {value_name!r}",
        )
        _core._truncate_rax(lines, bits)
    _core._store_value(lines, value_name, "rax", locations)

def _stack_component_sources(
    parameters: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    current_offset = _STACK_BASE_OFFSET
    sources: dict[str, dict[str, Any]] = {}
    for unit in parameters:
        transport = unit.get("transport", {}) if isinstance(unit, dict) else {}
        if transport.get("kind") != "stack":
            continue
        kind = unit.get("kind")
        values = list(unit.get("values", ()))
        size_bytes = transport.get("size_bytes")
        alignment_bytes = transport.get("alignment_bytes")
        if (
            kind not in {"scalar", "slice"}
            or not values
            or not isinstance(size_bytes, int)
            or isinstance(size_bytes, bool)
            or size_bytes < _STACK_SLOT_BYTES
            or size_bytes % _STACK_SLOT_BYTES != 0
            or not isinstance(alignment_bytes, int)
            or isinstance(alignment_bytes, bool)
            or alignment_bytes < 1
            or alignment_bytes > _STACK_SLOT_BYTES
        ):
            raise MachineBackendError(
                "aggregate incoming parameter emission only supports scalar/slice stack units with at most eight-byte alignment"
            )
        required_bytes = len(values) * _STACK_SLOT_BYTES
        if kind == "scalar" and len(values) != 1:
            raise MachineBackendError(
                "aggregate incoming scalar stack unit must contain one value"
            )
        if kind == "slice" and len(values) != 2:
            raise MachineBackendError(
                "aggregate incoming slice stack unit must contain data and length"
            )
        if size_bytes != required_bytes:
            raise MachineBackendError(
                f"aggregate incoming {kind} stack size does not match its components"
            )
        for component_index, value_name in enumerate(values):
            if (
                not isinstance(value_name, str)
                or not value_name
                or value_name in sources
            ):
                raise MachineBackendError(
                    "aggregate incoming stack transport has invalid or duplicate values"
                )
            sources[value_name] = {
                "kind": "stack",
                "offset_bytes": current_offset + component_index * _STACK_SLOT_BYTES,
            }
        current_offset += size_bytes
    return sources

def _register_component_sources(
    parameters: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    sources: dict[str, dict[str, Any]] = {}
    for unit in parameters:
        transport = unit.get("transport", {}) if isinstance(unit, dict) else {}
        if transport.get("kind") != "registers":
            continue
        kind = unit.get("kind")
        values = list(unit.get("values", ()))
        registers = list(transport.get("registers", ()))
        if kind not in {"scalar", "slice"} or len(values) != len(registers):
            raise MachineBackendError(
                "aggregate incoming register transport has inconsistent components"
            )
        if kind == "scalar" and len(values) != 1:
            raise MachineBackendError(
                "aggregate incoming scalar register unit must contain one value"
            )
        if kind == "slice" and len(values) != 2:
            raise MachineBackendError(
                "aggregate incoming slice register unit must contain data and length"
            )
        for value_name, register in zip(values, registers, strict=True):
            if (
                not isinstance(value_name, str)
                or not value_name
                or value_name in sources
                or not isinstance(register, str)
                or not register
            ):
                raise MachineBackendError(
                    "aggregate incoming register transport has invalid or duplicate values"
                )
            sources[value_name] = {"kind": "register", "register": register}
    return sources

def validate_aggregate_entry_emission_scope(target_ir: dict[str, Any]) -> None:
    """Keep aggregate-aware emission entry-only until outgoing calls are promoted."""
    if not tuple(target_ir.get("slice_views", ()) or ()):
        return
    for function in target_ir.get("functions", ()):
        for block in function.get("blocks", ()):
            for instruction in block.get("instructions", ()):
                if instruction.get("op") == "call":
                    raise MachineBackendError(
                        "aggregate-aware direct-call emission waits for M16.4g1c3"
                    )


def emit_aggregate_incoming_parameters(
    lines: list[str],
    *,
    function: dict[str, Any],
    function_plan: dict[str, Any],
    locations: dict[str, dict[str, Any]],
) -> None:
    """Materialize scalar/slice parameters from the certified aggregate ABI plan."""
    abi_transport = function_plan.get("abi_transport")
    if not isinstance(abi_transport, dict):
        raise MachineBackendError(
            f"function {function.get('name')!r}: aggregate ABI transport is missing"
        )
    if abi_transport.get("sret"):
        raise MachineBackendError(
            f"function {function.get('name')!r}: sret emission waits for M16.4g1c3"
        )
    units = list(abi_transport.get("parameters", ()))
    parameter_types = _parameter_types(function)
    sources = _register_component_sources(units)
    stack_sources = _stack_component_sources(units)
    overlap = set(sources).intersection(stack_sources)
    if overlap:
        raise MachineBackendError(
            "aggregate incoming parameter cannot be assigned to register and stack"
        )
    sources.update(stack_sources)
    if set(sources) != set(parameter_types):
        missing = sorted(set(parameter_types) - set(sources))
        extra = sorted(set(sources) - set(parameter_types))
        raise MachineBackendError(
            f"function {function.get('name')!r}: aggregate incoming transport does not cover parameters (missing={missing}, extra={extra})"
        )
    for parameter in function.get("parameters", ()):
        name = parameter["name"]
        _load_transport_value(
            lines,
            value_name=name,
            type_name=parameter_types[name],
            source=sources[name],
            locations=locations,
        )

__all__ = ["emit_aggregate_incoming_parameters", "validate_aggregate_entry_emission_scope"]
