"""M16.4h2e2c1 explicit x86-64 SysV transport for nominal payload enums."""
from __future__ import annotations
from typing import Any
from . import _machine_x86_64_core as _core
from ._machine_x86_64_enum_abi import classify_x86_64_sysv_nominal_enums
from ._machine_x86_64_types import require_abi_scalar

_ARGUMENT_REGISTERS = tuple(item[64] for item in _core._ARG_REGISTERS)
_RETURN_REGISTERS = ("rax", "rdx")
_INTEGER_CLASS = "INTEGER"
_MEMORY_CLASS = "MEMORY"

def _align(value: int, alignment: int) -> int:
    return (value + alignment - 1) & -alignment

def _classification_index(target_ir: dict[str, Any]) -> dict[str, dict[str, Any]]:
    plan = classify_x86_64_sysv_nominal_enums(target_ir)
    indexed: dict[str, dict[str, Any]] = {}
    for item in plan.get("aggregates", ()):
        if not isinstance(item, dict):
            raise _core.MachineBackendError("x86-64 nominal enum transport found malformed ABI classification")
        name = item.get("name")
        if not isinstance(name, str) or not name or name in indexed:
            raise _core.MachineBackendError("x86-64 nominal enum transport requires unique named classifications")
        indexed[name] = item
    return indexed

def _scalar_parameter_unit(name: str, type_name: Any) -> dict[str, Any]:
    bits = require_abi_scalar(type_name, context=f"parameter {name!r}")
    size = 8 if bits > 32 else max(1, bits // 8)
    return {"kind": "scalar", "name": name, "logical_type": type_name, "classes": [_INTEGER_CLASS], "size_bytes": size, "alignment_bytes": min(8, size)}

def _parameter_units(function: dict[str, Any], classifications: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    function_name = function.get("name")
    parameters = function.get("parameters", ())
    if not isinstance(parameters, list):
        raise _core.MachineBackendError(f"function {function_name!r}: nominal enum transport requires parameter list")
    units: list[dict[str, Any]] = []
    seen: set[str] = set()
    for parameter in parameters:
        if not isinstance(parameter, dict):
            raise _core.MachineBackendError(f"function {function_name!r}: malformed parameter")
        name = parameter.get("name")
        type_name = parameter.get("type")
        if not isinstance(name, str) or not name or name in seen:
            raise _core.MachineBackendError(f"function {function_name!r}: nominal enum transport requires unique named parameters")
        seen.add(name)
        classification = classifications.get(type_name)
        if classification is None:
            units.append(_scalar_parameter_unit(name, type_name))
            continue
        units.append({"kind": "enum", "name": name, "logical_type": type_name, "storage": "tagged_union", "classes": list(classification["classes"]), "size_bytes": classification["size_bytes"], "alignment_bytes": classification["alignment_bytes"]})
    return units

def _return_unit(function: dict[str, Any], classifications: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return_type = function.get("return_type")
    if return_type == "void":
        return {"kind": "void", "logical_type": "void", "classes": [], "transport": {"kind": "none"}}
    classification = classifications.get(return_type)
    if classification is not None:
        return {"kind": "enum", "logical_type": return_type, "storage": "tagged_union", "classes": list(classification["classes"]), "size_bytes": classification["size_bytes"], "alignment_bytes": classification["alignment_bytes"]}
    bits = require_abi_scalar(return_type, context=f"function {function.get('name')!r} return")
    size = 8 if bits > 32 else max(1, bits // 8)
    return {"kind": "scalar", "logical_type": return_type, "classes": [_INTEGER_CLASS], "size_bytes": size, "alignment_bytes": min(8, size)}

def _assign_return_transport(unit: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    if unit["kind"] == "void":
        return unit, False
    classes = unit["classes"]
    rendered = dict(unit)
    if classes == [_MEMORY_CLASS]:
        rendered["transport"] = {"kind": "indirect", "sret_register": "rdi", "returns_pointer_in": "rax"}
        return rendered, True
    if not classes or any(item != _INTEGER_CLASS for item in classes):
        raise _core.MachineBackendError("x86-64 nominal enum return transport only supports INTEGER or MEMORY classes")
    if len(classes) > len(_RETURN_REGISTERS):
        raise _core.MachineBackendError("x86-64 nominal enum return transport exceeds SysV INTEGER return registers")
    rendered["transport"] = {"kind": "registers", "registers": list(_RETURN_REGISTERS[:len(classes)])}
    return rendered, False

def _assign_parameter_transport(units: list[dict[str, Any]], *, initial_register_index: int) -> list[dict[str, Any]]:
    register_index = initial_register_index
    stack_ordinal = 0
    planned: list[dict[str, Any]] = []
    for unit in units:
        classes = unit["classes"]
        rendered = dict(unit)
        if classes == [_MEMORY_CLASS]:
            rendered["transport"] = {"kind": "stack", "stack_ordinal": stack_ordinal, "size_bytes": _align(unit["size_bytes"], 8), "alignment_bytes": max(8, unit["alignment_bytes"]), "reason": "memory_class"}
            stack_ordinal += 1
            planned.append(rendered)
            continue
        if not classes or any(item != _INTEGER_CLASS for item in classes):
            raise _core.MachineBackendError(f"parameter {unit['name']!r}: unsupported nominal enum ABI class sequence")
        needed = len(classes)
        available = len(_ARGUMENT_REGISTERS) - register_index
        if needed <= available:
            rendered["transport"] = {"kind": "registers", "registers": list(_ARGUMENT_REGISTERS[register_index:register_index + needed])}
            register_index += needed
        else:
            rendered["transport"] = {"kind": "stack", "stack_ordinal": stack_ordinal, "size_bytes": _align(unit["size_bytes"], 8), "alignment_bytes": max(8, unit["alignment_bytes"]), "reason": "register_exhaustion"}
            stack_ordinal += 1
        planned.append(rendered)
    return planned

def plan_x86_64_sysv_nominal_enum_transport(target_ir: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(target_ir, dict) or target_ir.get("schema") != "sotlas.target-ir.v1":
        raise _core.MachineBackendError("x86-64 nominal enum transport requires Target IR v1")
    classifications = _classification_index(target_ir)
    functions = target_ir.get("functions", ())
    if not isinstance(functions, list):
        raise _core.MachineBackendError("x86-64 nominal enum transport requires function list")
    planned_functions: list[dict[str, Any]] = []
    for function in functions:
        if not isinstance(function, dict):
            raise _core.MachineBackendError("x86-64 nominal enum transport found malformed function")
        name = function.get("name")
        if not isinstance(name, str) or _core._SYMBOL_RE.fullmatch(name) is None:
            raise _core.MachineBackendError(f"x86-64 nominal enum transport found invalid function name {name!r}")
        return_unit, uses_sret = _assign_return_transport(_return_unit(function, classifications))
        parameters = _assign_parameter_transport(_parameter_units(function, classifications), initial_register_index=1 if uses_sret else 0)
        planned_functions.append({"name": name, "sret": uses_sret, "parameters": parameters, "return": return_unit})
    return {"schema": "sotlas.nominal-enum-transport.x86_64-sysv.v1", "target": "x86_64-unknown-linux-gnu", "abi": "sysv", "functions": planned_functions, "limitations": ["This planner assigns nominal payload enum argument/return locations but does not emit machine instructions.", "SSE/other payload classes remain fail-closed through h2e2a.", "The central aggregate planner consumes the same certified INTEGER/MEMORY classifications.", "Machine enum construction and payload extraction remain deferred."]}

__all__ = ["plan_x86_64_sysv_nominal_enum_transport"]
