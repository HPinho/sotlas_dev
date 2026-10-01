"""x86-64 register-class projection for opaque nominal pointers.

The target-neutral allocation preview intentionally accepts only scalar-pointee
pointer spellings. M16.4c needs pointers such as ``Pair*`` to travel through the
same GP64 register class without teaching the generic preview about target ABI
rules. This module projects pointer result/parameter types to ``usize`` only in
an allocation copy, then restores their canonical source types in the report.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from ._machine_x86_64_types import pointer_pointee
from .target_ir import allocate_target_ir_registers


def allocate_x86_64_register_view(
    target_ir: dict[str, Any], *, register_count: int
) -> dict[str, Any]:
    projected = deepcopy(target_ir)
    original_types: dict[tuple[str, str], str] = {}

    for function in projected.get("functions", ()):
        function_name = function.get("name")
        for parameter in function.get("parameters", ()):
            name = parameter.get("name")
            type_name = parameter.get("type")
            if pointer_pointee(type_name) is not None:
                original_types[(function_name, name)] = type_name
                parameter["type"] = "usize"
        for block in function.get("blocks", ()):
            for instruction in block.get("instructions", ()):
                result = instruction.get("result")
                type_name = instruction.get("type")
                if (
                    isinstance(result, str)
                    and result
                    and pointer_pointee(type_name) is not None
                ):
                    original_types[(function_name, result)] = type_name
                    instruction["type"] = "usize"

    allocation = allocate_target_ir_registers(
        projected, register_count=register_count
    )
    for function in allocation.get("functions", ()):
        function_name = function.get("name")
        for value in function.get("values", ()):
            key = (function_name, value.get("value"))
            original = original_types.get(key)
            if original is not None:
                value["type"] = original
    return allocation


__all__ = ["allocate_x86_64_register_view"]
