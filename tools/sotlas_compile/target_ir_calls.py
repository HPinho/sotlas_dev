"""Typed direct-call, aggregate, layout, and symbol-linkage Target IR bridge.

Target IR v1 historically preserved the SSA result name of ``CallInst`` but did
not copy the result's SIR type into the lowered instruction. That omission was
harmless while the native backend rejected calls, but M16.3 requires call
results to participate in liveness, allocation and ABI validation exactly like
other typed SSA values.

M16.3d preserves source visibility and ABI-export facts. M16.4b2 preserves
non-escaping source-local addresses. M16.4c adds canonical struct-field
projection plus source declaration order/types. M16.4e2 carries explicit
payload-free enum declarations and ``enum_const`` identity while leaving nominal
enum ABI classification for the later aggregate-ABI milestone. M16.4f1 carries
logical slice views as pointer+length facts without selecting physical layout.
M16.4f3b preserves checked slice indexing as explicit Target IR ``bounds_check``
and ``slice_address`` operations without selecting machine ABI or byte stride.
M16.4h1d preserves checked ownership-bearing struct members as semantic Target
IR side facts after their nominal declarations have been materialized.
M16.4h2c2b preserves source-proven nominal enum payload identity as a logical
sidecar before enum ownership projection or tagged-union byte layout is opened.
"""
from __future__ import annotations

from typing import Any

from .aggregate_ownership_h2c2b import (
    attach_target_ir_aggregate_ownership_with_nominal_enums,
)
from .enum_nominal_payloads import attach_target_ir_nominal_enum_payloads
from .local_addressing import attach_target_ir_local_addresses
from .struct_layout import attach_target_ir_struct_layouts
from .symbol_linkage import attach_target_ir_symbol_linkage
from .target_ir import TargetIRLoweringError
from .target_ir_enums import attach_target_ir_enum_declarations
from .target_ir_slice_indexing import lower_sir_to_target_ir_with_slice_indexing
from .target_ir_slices import attach_target_ir_slice_views


def _sir_call_result_types(module: Any) -> dict[tuple[str, str], str]:
    result_types: dict[tuple[str, str], str] = {}
    for function in tuple(getattr(module, "functions", ()) or ()):
        function_name = getattr(function, "name", None)
        if not isinstance(function_name, str) or not function_name:
            raise TargetIRLoweringError("SIR module has an invalid function name")
        for block in tuple(getattr(function, "blocks", ()) or ()):
            for instruction in tuple(getattr(block, "instructions", ()) or ()):
                if type(instruction).__name__ != "CallInst":
                    continue
                result = getattr(instruction, "result", None)
                if result is None:
                    continue
                result_name = getattr(result, "name", None)
                result_type = getattr(result, "type_name", None)
                if (
                    not isinstance(result_name, str)
                    or not result_name
                    or not isinstance(result_type, str)
                    or not result_type
                ):
                    raise TargetIRLoweringError(
                        f"SIR function {function_name!r} has an invalid typed call result"
                    )
                key = (function_name, result_name)
                previous = result_types.get(key)
                if previous is not None and previous != result_type:
                    raise TargetIRLoweringError(
                        f"SIR function {function_name!r} gives call result "
                        f"{result_name!r} conflicting types"
                    )
                result_types[key] = result_type
    return result_types


def attach_direct_call_result_types(
    target_ir: dict[str, Any],
    sir_module: Any,
) -> dict[str, Any]:
    """Attach SIR-proven call-result types to already-lowered Target IR."""
    if not isinstance(target_ir, dict) or target_ir.get("schema") != "sotlas.target-ir.v1":
        raise TargetIRLoweringError("typed call bridge requires Target IR v1")

    result_types = _sir_call_result_types(sir_module)
    seen: set[tuple[str, str]] = set()
    for function in target_ir.get("functions", ()):
        function_name = function.get("name")
        if not isinstance(function_name, str) or not function_name:
            raise TargetIRLoweringError("Target IR contains an invalid function name")
        for block in function.get("blocks", ()):
            for instruction in block.get("instructions", ()):
                if instruction.get("op") != "call":
                    continue
                result = instruction.get("result")
                if result is None:
                    continue
                if not isinstance(result, str) or not result:
                    raise TargetIRLoweringError(
                        f"Target IR function {function_name!r} has an invalid call result"
                    )
                key = (function_name, result)
                source_type = result_types.get(key)
                if source_type is None:
                    raise TargetIRLoweringError(
                        f"Target IR call result {result!r} in {function_name!r} "
                        "has no typed SIR definition"
                    )
                existing_type = instruction.get("type")
                if existing_type not in (None, source_type):
                    raise TargetIRLoweringError(
                        f"Target IR call result {result!r} in {function_name!r} "
                        f"conflicts with SIR type {source_type!r}"
                    )
                instruction["type"] = source_type
                seen.add(key)

    missing = sorted(set(result_types) - seen)
    if missing:
        rendered = ", ".join(
            f"{function}:{result}" for function, result in missing
        )
        raise TargetIRLoweringError(
            "typed SIR call results were not preserved in Target IR: " + rendered
        )
    return target_ir


def lower_sir_to_typed_target_ir(module: Any) -> dict[str, Any]:
    """Lower SIR with typed calls, aggregates, layouts, and source linkage."""
    target_ir = lower_sir_to_target_ir_with_slice_indexing(module)
    attach_target_ir_enum_declarations(target_ir, module)
    attach_target_ir_nominal_enum_payloads(target_ir, module)
    attach_target_ir_slice_views(target_ir, module)
    attach_direct_call_result_types(target_ir, module)
    attach_target_ir_struct_layouts(target_ir, module)
    attach_target_ir_aggregate_ownership_with_nominal_enums(target_ir, module)
    attach_target_ir_local_addresses(target_ir, module)
    attach_target_ir_symbol_linkage(target_ir, module)
    return target_ir


__all__ = [
    "attach_direct_call_result_types",
    "lower_sir_to_typed_target_ir",
]
