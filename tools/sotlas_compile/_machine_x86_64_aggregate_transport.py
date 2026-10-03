"""x86-64 SysV aggregate argument/return transport planning for M16.4h2e2c2."""
from __future__ import annotations

from typing import Any

from . import _machine_x86_64_core as _core
from ._machine_x86_64_aggregate_abi import classify_x86_64_sysv_aggregates
from ._machine_x86_64_types import require_abi_scalar

_ARGUMENT_REGISTERS = tuple(item[64] for item in _core._ARG_REGISTERS)
_RETURN_REGISTERS = ("rax", "rdx")
_INTEGER_CLASS = "INTEGER"
_MEMORY_CLASS = "MEMORY"


def _align(value: int, alignment: int) -> int:
    return (value + alignment - 1) & -alignment


def _classification_indexes(
    target_ir: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], dict[tuple[str, str], dict[str, Any]]]:
    plan = classify_x86_64_sysv_aggregates(target_ir)
    by_type: dict[str, dict[str, Any]] = {}
    slices: dict[tuple[str, str], dict[str, Any]] = {}

    for item in plan["aggregates"]:
        kind = item["kind"]
        if kind in {"struct", "enum"}:
            name = item["name"]
            previous = by_type.get(name)
            if previous is not None and previous != item:
                raise _core.MachineBackendError(
                    f"x86-64 aggregate transport has conflicting classification for {name!r}"
                )
            by_type[name] = item
            continue
        if kind == "slice":
            key = (item["function"], item["name"])
            if key in slices:
                raise _core.MachineBackendError(
                    f"x86-64 aggregate transport has duplicate slice {item['name']!r}"
                )
            slices[key] = item
            continue
        raise _core.MachineBackendError(
            f"x86-64 aggregate transport found unknown aggregate kind {kind!r}"
        )
    return by_type, slices


def _scalar_unit(name: str, type_name: Any) -> dict[str, Any]:
    bits = require_abi_scalar(type_name, context=f"parameter {name!r}")
    return {
        "kind": "scalar",
        "name": name,
        "logical_type": type_name,
        "values": [name],
        "classes": [_INTEGER_CLASS],
        "size_bytes": 8 if bits > 32 else max(1, bits // 8),
        "alignment_bytes": min(8, max(1, bits // 8)),
    }


def _aggregate_unit(
    *, name: str, type_name: str, classification: dict[str, Any]
) -> dict[str, Any]:
    return {
        "kind": classification["kind"],
        "name": name,
        "logical_type": type_name,
        "values": [name],
        "classes": list(classification["classes"]),
        "size_bytes": classification["size_bytes"],
        "alignment_bytes": classification["alignment_bytes"],
    }


def _parameter_units(
    function: dict[str, Any],
    *,
    by_type: dict[str, dict[str, Any]],
    slices: dict[tuple[str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    function_name = function.get("name")
    parameters = list(function.get("parameters", ()))
    names = [item.get("name") if isinstance(item, dict) else None for item in parameters]
    if any(not isinstance(name, str) or not name for name in names):
        raise _core.MachineBackendError(
            f"function {function_name!r}: aggregate transport requires named parameters"
        )
    if len(names) != len(set(names)):
        raise _core.MachineBackendError(
            f"function {function_name!r}: aggregate transport found duplicate parameters"
        )

    slice_by_data: dict[str, dict[str, Any]] = {}
    claimed: set[str] = set()
    for (owner, logical_name), classification in slices.items():
        if owner != function_name:
            continue
        eightbytes = classification.get("eightbytes", ())
        if len(eightbytes) != 2:
            raise _core.MachineBackendError(
                f"function {function_name!r}: slice {logical_name!r} requires two classified eightbytes"
            )
        data = eightbytes[0].get("value")
        length = eightbytes[1].get("value")
        if (
            eightbytes[0].get("source") != "data"
            or eightbytes[1].get("source") != "length"
            or not isinstance(data, str)
            or not isinstance(length, str)
            or data == length
            or data in claimed
            or length in claimed
        ):
            raise _core.MachineBackendError(
                f"function {function_name!r}: slice {logical_name!r} has malformed transport values"
            )
        try:
            data_index = names.index(data)
            length_index = names.index(length)
        except ValueError as error:
            raise _core.MachineBackendError(
                f"function {function_name!r}: slice {logical_name!r} transport values are not parameters"
            ) from error
        if length_index != data_index + 1:
            raise _core.MachineBackendError(
                f"function {function_name!r}: slice {logical_name!r} data/length parameters must be contiguous"
            )
        data_type = parameters[data_index].get("type")
        length_type = parameters[length_index].get("type")
        logical_type = classification["logical_type"]
        prefix = "&mut [" if logical_type.startswith("&mut [") else "&["
        if not logical_type.startswith(prefix) or not logical_type.endswith("]"):
            raise _core.MachineBackendError(
                f"function {function_name!r}: slice {logical_name!r} has malformed logical type"
            )
        element_type = logical_type[len(prefix):-1]
        if data_type != f"{element_type}*" or length_type != "usize":
            raise _core.MachineBackendError(
                f"function {function_name!r}: slice {logical_name!r} has inconsistent parameter transport types"
            )
        claimed.update((data, length))
        slice_by_data[data] = {
            "kind": "slice",
            "name": logical_name,
            "logical_type": logical_type,
            "values": [data, length],
            "classes": list(classification["classes"]),
            "size_bytes": classification["size_bytes"],
            "alignment_bytes": classification["alignment_bytes"],
        }

    units: list[dict[str, Any]] = []
    skip: set[str] = set()
    for parameter in parameters:
        name = parameter["name"]
        if name in skip:
            continue
        slice_unit = slice_by_data.get(name)
        if slice_unit is not None:
            units.append(slice_unit)
            skip.add(slice_unit["values"][1])
            continue
        if name in claimed:
            raise _core.MachineBackendError(
                f"function {function_name!r}: slice transport component {name!r} is out of order"
            )
        type_name = parameter.get("type")
        classification = by_type.get(type_name)
        if classification is not None:
            units.append(
                _aggregate_unit(
                    name=name,
                    type_name=type_name,
                    classification=classification,
                )
            )
        else:
            units.append(_scalar_unit(name, type_name))
    return units


def _return_unit(
    function: dict[str, Any],
    *,
    by_type: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    return_type = function.get("return_type")
    if return_type == "void":
        return {
            "kind": "void",
            "logical_type": "void",
            "classes": [],
            "transport": {"kind": "none"},
        }

    classification = by_type.get(return_type)
    if classification is None:
        bits = require_abi_scalar(
            return_type,
            context=f"function {function.get('name')!r} return",
        )
        return {
            "kind": "scalar",
            "logical_type": return_type,
            "classes": [_INTEGER_CLASS],
            "size_bytes": 8 if bits > 32 else max(1, bits // 8),
            "alignment_bytes": min(8, max(1, bits // 8)),
        }

    return {
        "kind": classification["kind"],
        "logical_type": return_type,
        "classes": list(classification["classes"]),
        "size_bytes": classification["size_bytes"],
        "alignment_bytes": classification["alignment_bytes"],
    }


def _assign_return_transport(unit: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    classes = unit["classes"]
    if unit["kind"] == "void":
        return unit, False
    if classes == [_MEMORY_CLASS]:
        rendered = dict(unit)
        rendered["transport"] = {
            "kind": "indirect",
            "sret_register": "rdi",
            "returns_pointer_in": "rax",
        }
        return rendered, True
    if not classes or any(item != _INTEGER_CLASS for item in classes):
        raise _core.MachineBackendError(
            "x86-64 aggregate return transport only supports INTEGER or MEMORY classes"
        )
    if len(classes) > len(_RETURN_REGISTERS):
        raise _core.MachineBackendError(
            "x86-64 aggregate return transport exceeds the SysV INTEGER return register set"
        )
    rendered = dict(unit)
    rendered["transport"] = {
        "kind": "registers",
        "registers": list(_RETURN_REGISTERS[: len(classes)]),
    }
    return rendered, False


def _assign_parameter_transport(
    units: list[dict[str, Any]],
    *,
    initial_register_index: int,
) -> list[dict[str, Any]]:
    register_index = initial_register_index
    stack_ordinal = 0
    planned: list[dict[str, Any]] = []

    for unit in units:
        classes = unit["classes"]
        rendered = dict(unit)
        if classes == [_MEMORY_CLASS]:
            rendered["transport"] = {
                "kind": "stack",
                "stack_ordinal": stack_ordinal,
                "size_bytes": _align(unit["size_bytes"], 8),
                "alignment_bytes": max(8, unit["alignment_bytes"]),
                "reason": "memory_class",
            }
            stack_ordinal += 1
            planned.append(rendered)
            continue

        if not classes or any(item != _INTEGER_CLASS for item in classes):
            raise _core.MachineBackendError(
                f"parameter {unit['name']!r}: unsupported aggregate ABI class sequence"
            )

        needed = len(classes)
        available = len(_ARGUMENT_REGISTERS) - register_index
        if needed <= available:
            rendered["transport"] = {
                "kind": "registers",
                "registers": list(
                    _ARGUMENT_REGISTERS[register_index : register_index + needed]
                ),
            }
            register_index += needed
        else:
            rendered["transport"] = {
                "kind": "stack",
                "stack_ordinal": stack_ordinal,
                "size_bytes": _align(unit["size_bytes"], 8),
                "alignment_bytes": max(8, unit["alignment_bytes"]),
                "reason": "register_exhaustion",
            }
            stack_ordinal += 1
        planned.append(rendered)
    return planned


def plan_x86_64_sysv_aggregate_transport(
    target_ir: dict[str, Any],
) -> dict[str, Any]:
    """Plan aggregate-aware SysV transport without emitting instructions."""
    if not isinstance(target_ir, dict) or target_ir.get("schema") != "sotlas.target-ir.v1":
        raise _core.MachineBackendError(
            "x86-64 aggregate transport requires Target IR v1"
        )

    by_type, slices = _classification_indexes(target_ir)
    functions = []
    for function in target_ir.get("functions", ()):
        name = function.get("name") if isinstance(function, dict) else None
        if not isinstance(name, str) or _core._SYMBOL_RE.fullmatch(name) is None:
            raise _core.MachineBackendError(
                f"x86-64 aggregate transport found invalid function name {name!r}"
            )

        return_unit, uses_sret = _assign_return_transport(
            _return_unit(function, by_type=by_type)
        )
        parameter_units = _parameter_units(
            function, by_type=by_type, slices=slices
        )
        parameters = _assign_parameter_transport(
            parameter_units,
            initial_register_index=1 if uses_sret else 0,
        )
        functions.append({
            "name": name,
            "sret": uses_sret,
            "parameters": parameters,
            "return": return_unit,
        })

    return {
        "schema": "sotlas.aggregate-transport.x86_64-sysv.v1",
        "target": "x86_64-unknown-linux-gnu",
        "abi": "sysv",
        "functions": functions,
        "limitations": [
            "This plan assigns ABI transport locations but does not emit machine instructions.",
            "Stack argument byte offsets remain deferred to aggregate machine emission.",
            "Certified INTEGER/MEMORY nominal payload enums receive ABI locations; machine emission and enum construction/extraction remain deferred.",
        ],
    }


__all__ = ["plan_x86_64_sysv_aggregate_transport"]
