"""Certified REGION callee-return to caller-owner links.

This layer closes the basic interprocedural ownership cycle for the narrow
source shape already preserved by canonical SIR::

    let out: region T = callee(move owner)

It derives topology only.  No runtime ABI, LLVM lowering or C11 behavior is
introduced here.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .canonical_sir import build_canonical_checked_ownership_sir, load_canonical_sir
from .region_boundary_link import (
    RegionBoundaryLinkPlan,
    plan_checked_region_boundary_links,
)
from .region_call import RegionCallLifetimePlan, plan_checked_region_calls
from .region_call_sir import RegionCallSIRBridge, validate_region_call_sir
from .region_interprocedural import (
    RegionInterproceduralLifetimePlan,
    plan_checked_region_interprocedural,
)
from .region_return import RegionReturnLifetimePlan
from .typed_ast import Phase1SemanticError, SemanticType


class RegionReturnLinkError(Phase1SemanticError):
    """Raised when a REGION return cannot be linked to one caller owner."""


@dataclass(frozen=True)
class RegionReturnCallLink:
    caller: str
    point_id: str
    callee: str
    destination: str
    type: SemanticType
    callee_return_bindings: tuple[str, ...]
    block: str
    instruction_index: int

    @property
    def identity(self) -> tuple[str, str, str]:
        return (self.caller, self.point_id, self.destination)


@dataclass(frozen=True)
class RegionReturnLinkPlan:
    links: tuple[RegionReturnCallLink, ...]

    def at_call(self, caller: str, point_id: str) -> RegionReturnCallLink:
        matches = tuple(
            item for item in self.links
            if item.caller == caller and item.point_id == point_id
        )
        if len(matches) != 1:
            raise RegionReturnLinkError(
                f"REGION return-link plan requires exactly one call {caller}::{point_id}"
            )
        return matches[0]

    def destination(self, caller: str, binding: str) -> RegionReturnCallLink:
        matches = tuple(
            item for item in self.links
            if item.caller == caller and item.destination == binding
        )
        if len(matches) != 1:
            raise RegionReturnLinkError(
                f"REGION return-link plan requires exactly one destination {caller}::{binding}"
            )
        return matches[0]


def _stable_call_point(call: object) -> str:
    token = getattr(call, "token", None)
    line = getattr(token, "line", None)
    column = getattr(token, "column", None)
    if not isinstance(line, int) or line <= 0 or not isinstance(column, int) or column <= 0:
        raise RegionReturnLinkError("REGION return call lacks source-stable location")
    return f"call@{line}:{column}"


def _sir_instruction(module: object, function_name: str, block_name: str, index: int):
    sir = load_canonical_sir()
    functions = tuple(
        item for item in getattr(module, "functions", ())
        if getattr(item, "name", None) == function_name
    )
    if len(functions) != 1:
        raise RegionReturnLinkError(
            f"REGION return link requires exactly one SIR function {function_name!r}"
        )
    blocks = tuple(
        item for item in getattr(functions[0], "blocks", ())
        if getattr(item, "label", None) == block_name
    )
    if len(blocks) != 1:
        raise RegionReturnLinkError(
            f"REGION return link requires exactly one SIR block {function_name}::{block_name}"
        )
    instructions = tuple(getattr(blocks[0], "instructions", ()) or ())
    if index < 0 or index >= len(instructions):
        raise RegionReturnLinkError("REGION return link SIR instruction index is out of range")
    instruction = instructions[index]
    if not isinstance(instruction, sir.CallInst):
        raise RegionReturnLinkError("REGION return link target is not a canonical CallInst")
    return instruction


def build_region_return_link_plan(
    parsed_module: object,
    interprocedural: RegionInterproceduralLifetimePlan,
    call_boundaries: RegionBoundaryLinkPlan,
    call_bridge: RegionCallSIRBridge,
    checked_sir: object,
) -> RegionReturnLinkPlan:
    if not isinstance(interprocedural, RegionInterproceduralLifetimePlan):
        raise RegionReturnLinkError(
            "REGION return linking requires a certified interprocedural lifetime plan"
        )
    if not isinstance(call_boundaries, RegionBoundaryLinkPlan):
        raise RegionReturnLinkError(
            "REGION return linking requires certified caller/callee boundaries"
        )
    if not isinstance(call_bridge, RegionCallSIRBridge):
        raise RegionReturnLinkError(
            "REGION return linking requires a certified call/SIR bridge"
        )

    returns: RegionReturnLifetimePlan = interprocedural.returns
    contracts = {item.function: item for item in returns.contracts}
    if len(contracts) != len(returns.contracts):
        raise RegionReturnLinkError("duplicate REGION return contract")

    module = getattr(checked_sir, "module", checked_sir)
    links: list[RegionReturnCallLink] = []
    seen: set[tuple[str, str, str]] = set()

    for parsed_function in tuple(getattr(parsed_module, "functions", ()) or ()):
        caller = getattr(parsed_function, "name", None)
        if not isinstance(caller, str) or not caller:
            continue
        function_plan = interprocedural.function(caller)
        owner_by_binding = {item.binding: item for item in function_plan.local.owners}

        for statement in tuple(getattr(parsed_function, "body", ()) or ()):
            if type(statement).__name__ != "Let":
                continue
            call = getattr(statement, "value", None)
            if type(call).__name__ != "Call":
                continue
            declared_type = getattr(statement, "type", None)
            if getattr(declared_type, "ownership_domain", None) != "region":
                continue

            callee = getattr(call, "callee", None)
            contract = contracts.get(callee)
            if contract is None:
                raise RegionReturnLinkError(
                    f"REGION destination in {caller!r} is bound from callee without REGION return contract"
                )
            if getattr(declared_type, "name", None) != contract.type.name:
                raise RegionReturnLinkError(
                    f"REGION return type mismatch for {caller}->{callee}"
                )

            destination = getattr(statement, "name", None)
            if not isinstance(destination, str) or not destination:
                raise RegionReturnLinkError("REGION return destination lacks binding identity")
            owner = owner_by_binding.get(destination)
            if owner is None or owner.type != contract.type:
                raise RegionReturnLinkError(
                    f"REGION return destination {caller}::{destination} lacks matching local owner"
                )

            point_id = _stable_call_point(call)
            outgoing = call_boundaries.outgoing(caller, point_id)
            if not outgoing or any(item.callee != callee for item in outgoing):
                raise RegionReturnLinkError(
                    f"REGION return call {caller}::{point_id} diverged from caller/callee boundary"
                )

            sites = tuple(
                item for item in call_bridge.sites
                if item.function == caller
                and item.point_id == point_id
                and item.callee == callee
            )
            if not sites:
                raise RegionReturnLinkError(
                    f"REGION return call {caller}::{point_id} lacks certified SIR call site"
                )
            locations = {(item.block, item.instruction_index) for item in sites}
            if len(locations) != 1:
                raise RegionReturnLinkError(
                    f"REGION return call {caller}::{point_id} maps to multiple SIR calls"
                )
            block, instruction_index = next(iter(locations))
            instruction = _sir_instruction(module, caller, block, instruction_index)
            if instruction.callee != callee:
                raise RegionReturnLinkError(
                    f"REGION return call {caller}::{point_id} SIR callee diverged"
                )
            result = instruction.result
            if result is None:
                raise RegionReturnLinkError(
                    f"REGION return call {caller}::{point_id} lost its SIR result"
                )
            if result.name != destination or result.type_name != contract.type.name:
                raise RegionReturnLinkError(
                    f"REGION return call {caller}::{point_id} result diverged from caller owner"
                )

            callee_boundary = call_boundaries.boundaries.function(callee)
            return_transfers = tuple(
                item for item in returns.transfers if item.function == callee
            )
            return_bindings = tuple(item.binding for item in return_transfers)
            if not return_bindings or return_bindings != callee_boundary.return_bindings:
                raise RegionReturnLinkError(
                    f"REGION return boundary for callee {callee!r} diverged from return transfers"
                )
            if any(item.type != contract.type for item in return_transfers):
                raise RegionReturnLinkError(
                    f"REGION return source type diverged for callee {callee!r}"
                )

            link = RegionReturnCallLink(
                caller=caller,
                point_id=point_id,
                callee=callee,
                destination=destination,
                type=contract.type,
                callee_return_bindings=return_bindings,
                block=block,
                instruction_index=instruction_index,
            )
            if link.identity in seen:
                raise RegionReturnLinkError(
                    f"duplicate REGION return-link identity {link.identity!r}"
                )
            seen.add(link.identity)
            links.append(link)

    return RegionReturnLinkPlan(tuple(links))


def plan_checked_region_return_links(checked_module: object) -> RegionReturnLinkPlan:
    parsed_module = getattr(checked_module, "parsed_module", None)
    if parsed_module is None:
        raise RegionReturnLinkError(
            "REGION return linking requires a Phase1CheckedModule parsed snapshot"
        )
    interprocedural = plan_checked_region_interprocedural(checked_module)
    call_boundaries = plan_checked_region_boundary_links(checked_module)
    call_plan: RegionCallLifetimePlan = plan_checked_region_calls(checked_module)
    checked_sir, _ = build_canonical_checked_ownership_sir(checked_module)
    call_bridge = validate_region_call_sir(call_plan, checked_sir)
    return build_region_return_link_plan(
        parsed_module,
        interprocedural,
        call_boundaries,
        call_bridge,
        checked_sir,
    )


__all__ = [
    "RegionReturnLinkError",
    "RegionReturnCallLink",
    "RegionReturnLinkPlan",
    "build_region_return_link_plan",
    "plan_checked_region_return_links",
]
