"""Aggregate-aware physical allocation composition for M16.4g1c1.

The certified scalar allocation remains authoritative. When Target IR carries
logical slice views, this layer attaches the already-certified SysV aggregate
transport plan to each physical function allocation without changing instruction
emission yet.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from . import _machine_x86_64_core as _core
from ._machine_x86_64_aggregate_transport import (
    plan_x86_64_sysv_aggregate_transport,
)
from ._machine_x86_64_call_plan import plan_x86_64_sysv_allocation


def _transport_by_function(plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if (
        not isinstance(plan, dict)
        or plan.get("schema") != "sotlas.aggregate-transport.x86_64-sysv.v1"
    ):
        raise _core.MachineBackendError(
            "aggregate-aware allocation requires the certified SysV transport plan"
        )
    indexed: dict[str, dict[str, Any]] = {}
    for function in plan.get("functions", ()):
        name = function.get("name") if isinstance(function, dict) else None
        if not isinstance(name, str) or not name or name in indexed:
            raise _core.MachineBackendError(
                "aggregate-aware allocation found invalid or duplicate transport function"
            )
        indexed[name] = function
    return indexed


def _incoming_stack_summary(function_transport: dict[str, Any]) -> tuple[int, int]:
    units = 0
    total_bytes = 0
    for parameter in function_transport.get("parameters", ()):
        transport = parameter.get("transport", {}) if isinstance(parameter, dict) else {}
        if transport.get("kind") != "stack":
            continue
        size_bytes = transport.get("size_bytes")
        if (
            not isinstance(size_bytes, int)
            or isinstance(size_bytes, bool)
            or size_bytes < 1
            or size_bytes % 8 != 0
        ):
            raise _core.MachineBackendError(
                "aggregate-aware allocation found malformed incoming stack transport"
            )
        units += 1
        total_bytes += size_bytes
    return units, total_bytes


def plan_x86_64_sysv_aggregate_allocation(
    target_ir: dict[str, Any],
    *,
    register_count: int = 2,
) -> dict[str, Any]:
    """Attach proven aggregate transport to the existing physical allocation.

    M16.4g1c1 deliberately activates only for ``slice_views``. Slices are
    already represented in Target IR as the proven scalar pair ``data + len``,
    so the scalar allocator can remain unchanged while this layer records their
    grouped SysV transport. Nominal structs/enums by value remain fail-closed
    until their SSA and emission contracts are promoted separately.
    """
    allocation = plan_x86_64_sysv_allocation(
        target_ir,
        register_count=register_count,
    )
    if not tuple(target_ir.get("slice_views", ()) or ()):
        return allocation

    transport_plan = plan_x86_64_sysv_aggregate_transport(target_ir)
    transport_by_name = _transport_by_function(transport_plan)
    composed = deepcopy(allocation)

    allocation_names: set[str] = set()
    for function in composed.get("functions", ()):
        name = function.get("name") if isinstance(function, dict) else None
        if not isinstance(name, str) or not name or name in allocation_names:
            raise _core.MachineBackendError(
                "aggregate-aware allocation found invalid or duplicate allocation function"
            )
        allocation_names.add(name)
        function_transport = transport_by_name.pop(name, None)
        if function_transport is None:
            raise _core.MachineBackendError(
                f"aggregate-aware allocation is missing transport for function {name!r}"
            )
        stack_units, stack_bytes = _incoming_stack_summary(function_transport)
        function["abi_transport"] = deepcopy(function_transport)
        function["aggregate_incoming_stack_units"] = stack_units
        function["aggregate_incoming_stack_bytes"] = stack_bytes

    if transport_by_name:
        missing = ", ".join(sorted(transport_by_name))
        raise _core.MachineBackendError(
            "aggregate-aware allocation has transport without physical allocation: "
            + missing
        )

    composed["aggregate_transport_schema"] = transport_plan["schema"]
    composed["aggregate_transport_active"] = True
    return composed


__all__ = ["plan_x86_64_sysv_aggregate_allocation"]
