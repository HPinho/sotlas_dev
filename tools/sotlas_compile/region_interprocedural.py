"""Composed interprocedural REGION lifetime view.

The local lifetime topology, source-stable call contracts and return contracts
are independently certified.  This module composes those proofs without
pretending the prototype SIR already carries interprocedural call ownership
markers.  It is a semantic certificate only; no runtime or backend behavior is
introduced here.
"""
from __future__ import annotations

from dataclasses import dataclass

from .region_call import RegionCallTransfer, plan_checked_region_calls
from .region_frontend import plan_checked_region_lifetime
from .region_lifetime import RegionLifetimePlan
from .region_return import RegionReturnLifetimePlan, plan_checked_region_returns
from .typed_ast import OwnershipDomain, Phase1SemanticError


class RegionInterproceduralLifetimeError(Phase1SemanticError):
    """Raised when certified local/call/return REGION facts disagree."""


@dataclass(frozen=True)
class RegionInterproceduralFunctionPlan:
    function: str
    local: RegionLifetimePlan
    calls: tuple[RegionCallTransfer, ...]


@dataclass(frozen=True)
class RegionInterproceduralLifetimePlan:
    functions: tuple[RegionInterproceduralFunctionPlan, ...]
    returns: RegionReturnLifetimePlan

    def function(self, name: str) -> RegionInterproceduralFunctionPlan:
        matches = tuple(item for item in self.functions if item.function == name)
        if len(matches) != 1:
            raise RegionInterproceduralLifetimeError(
                f"REGION interprocedural plan requires exactly one function {name!r}"
            )
        return matches[0]


def plan_checked_region_interprocedural(
    checked_module: object,
) -> RegionInterproceduralLifetimePlan:
    semantic = getattr(checked_module, "semantic", None)
    if semantic is None:
        raise RegionInterproceduralLifetimeError(
            "REGION interprocedural planning requires a Phase1CheckedModule semantic snapshot"
        )
    graph = getattr(semantic, "ownership_domains", None)
    if graph is None:
        raise RegionInterproceduralLifetimeError(
            "REGION interprocedural planning lacks canonical ownership graph"
        )

    call_plan = plan_checked_region_calls(checked_module)
    return_plan = plan_checked_region_returns(checked_module)
    function_names = tuple(dict.fromkeys(
        node.function
        for node in graph.nodes
        if node.domain is OwnershipDomain.REGION
    ))

    functions: list[RegionInterproceduralFunctionPlan] = []
    return_transfers = {(item.function, item.binding) for item in return_plan.transfers}
    for function_name in function_names:
        local = plan_checked_region_lifetime(
            checked_module,
            function=function_name,
        )
        calls = tuple(
            item for item in call_plan.transfers if item.function == function_name
        )
        local_call_facts = sorted(
            (item.source, item.via)
            for item in local.transfers
            if item.via.startswith("call:")
        )
        certified_call_facts = sorted(
            (item.binding, f"call:{item.callee}") for item in calls
        )
        if local_call_facts != certified_call_facts:
            raise RegionInterproceduralLifetimeError(
                f"REGION call lifetime facts diverged for {function_name!r}"
            )

        local_returns = {
            item.source for item in local.transfers if item.via == "return"
        }
        certified_returns = {
            binding
            for owner_function, binding in return_transfers
            if owner_function == function_name
        }
        if local_returns != certified_returns:
            raise RegionInterproceduralLifetimeError(
                f"REGION return lifetime facts diverged for {function_name!r}"
            )

        local_bindings = set(local.bindings)
        for call in calls:
            if call.binding not in local_bindings:
                raise RegionInterproceduralLifetimeError(
                    f"REGION call source {function_name}::{call.binding} lacks local lifetime owner"
                )

        functions.append(
            RegionInterproceduralFunctionPlan(
                function=function_name,
                local=local,
                calls=calls,
            )
        )

    return RegionInterproceduralLifetimePlan(
        functions=tuple(functions),
        returns=return_plan,
    )


__all__ = [
    "RegionInterproceduralLifetimeError",
    "RegionInterproceduralFunctionPlan",
    "RegionInterproceduralLifetimePlan",
    "plan_checked_region_interprocedural",
]
