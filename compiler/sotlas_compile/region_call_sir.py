"""Certify source-stable REGION call contracts against existing SIR CallInsts.

The current prototype SIR does not embed ownership call-site identities in
``CallInst``. This bridge therefore does not claim that it does. It proves that
each certified REGION call transfer maps to exactly one existing SIR call and
argument position, while carrying the source-stable ``call@line:column`` identity
from the semantic contract alongside that SIR location.
"""
from __future__ import annotations

from dataclasses import dataclass

from .canonical_sir import load_canonical_sir
from .region_call import RegionCallLifetimePlan
from .typed_ast import Phase1SemanticError


class RegionCallSIRError(Phase1SemanticError):
    """Raised when a REGION call contract is not represented by canonical SIR."""


@dataclass(frozen=True)
class RegionCallSIRSite:
    function: str
    binding: str
    callee: str
    parameter: str
    argument_index: int
    point_id: str
    block: str
    instruction_index: int
    source_identity_embedded: bool = False


@dataclass(frozen=True)
class RegionCallSIRBridge:
    sites: tuple[RegionCallSIRSite, ...]


def validate_region_call_sir(
    call_plan: RegionCallLifetimePlan,
    sir_module: object,
) -> RegionCallSIRBridge:
    if not isinstance(call_plan, RegionCallLifetimePlan):
        raise RegionCallSIRError(
            "REGION call/SIR bridge requires a RegionCallLifetimePlan"
        )

    sir = load_canonical_sir()
    module = getattr(sir_module, "module", sir_module)
    if not isinstance(module, sir.SIRModule):
        raise RegionCallSIRError(
            "REGION call/SIR bridge requires canonical SIRModule or CheckedOwnershipSIR"
        )

    functions = tuple(module.functions)
    sites: list[RegionCallSIRSite] = []

    for transfer in call_plan.transfers:
        if not transfer.point_id.startswith("call@"):
            raise RegionCallSIRError(
                "REGION call contract lost source-stable call identity"
            )
        function_matches = tuple(
            item for item in functions if getattr(item, "name", None) == transfer.function
        )
        if len(function_matches) != 1:
            raise RegionCallSIRError(
                f"REGION call/SIR bridge requires exactly one function {transfer.function!r}"
            )

        function = function_matches[0]
        matches: list[tuple[str, int]] = []
        for block in tuple(getattr(function, "blocks", ()) or ()):
            for index, instruction in enumerate(
                tuple(getattr(block, "instructions", ()) or ())
            ):
                if not isinstance(instruction, sir.CallInst):
                    continue
                if instruction.callee != transfer.callee:
                    continue
                arguments = tuple(instruction.arguments)
                if transfer.argument_index >= len(arguments):
                    continue
                argument = arguments[transfer.argument_index]
                if (
                    argument.name == transfer.binding
                    and argument.type_name == transfer.type.name
                ):
                    matches.append((block.label, index))

        if len(matches) != 1:
            raise RegionCallSIRError(
                f"REGION call {transfer.function}::{transfer.binding} at {transfer.point_id} "
                f"requires exactly one SIR CallInst argument match, got {len(matches)}"
            )

        block, instruction_index = matches[0]
        sites.append(
            RegionCallSIRSite(
                function=transfer.function,
                binding=transfer.binding,
                callee=transfer.callee,
                parameter=transfer.parameter,
                argument_index=transfer.argument_index,
                point_id=transfer.point_id,
                block=block,
                instruction_index=instruction_index,
            )
        )

    semantic_identities = tuple(
        (item.function, item.point_id, item.parameter, item.argument_index)
        for item in sites
    )
    if len(set(semantic_identities)) != len(semantic_identities):
        raise RegionCallSIRError("duplicate REGION call/SIR semantic identity")

    return RegionCallSIRBridge(tuple(sites))


__all__ = [
    "RegionCallSIRError",
    "RegionCallSIRSite",
    "RegionCallSIRBridge",
    "validate_region_call_sir",
]
