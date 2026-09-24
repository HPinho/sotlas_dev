"""Certify source-stable REGION call contracts against canonical SIR facts.

Each REGION ownership-taking argument must now have an explicit
RegionCallTransferInst immediately before its canonical CallInst. The SIR fact
embeds the source ``call@line:column`` identity plus callee/parameter/argument
position, so downstream analyses no longer need to carry that identity only in
a side certificate.
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
    call_instruction_index: int
    source_identity_embedded: bool = True


@dataclass(frozen=True)
class RegionCallSIRBridge:
    sites: tuple[RegionCallSIRSite, ...]


def _unwrap_sir_module(value: object) -> object:
    module = getattr(value, "module", None)
    if module is not None and hasattr(module, "functions"):
        return module
    if hasattr(value, "functions"):
        return value
    raise RegionCallSIRError(
        "REGION call/SIR bridge requires SIRModule or CheckedOwnershipSIR"
    )


def validate_region_call_sir(
    call_plan: RegionCallLifetimePlan,
    sir_module: object,
) -> RegionCallSIRBridge:
    if not isinstance(call_plan, RegionCallLifetimePlan):
        raise RegionCallSIRError(
            "REGION call/SIR bridge requires a RegionCallLifetimePlan"
        )
    sir = load_canonical_sir()
    module = _unwrap_sir_module(sir_module)
    functions = tuple(getattr(module, "functions", ()) or ())
    sites: list[RegionCallSIRSite] = []

    for transfer in call_plan.transfers:
        function_matches = tuple(
            item for item in functions if getattr(item, "name", None) == transfer.function
        )
        if len(function_matches) != 1:
            raise RegionCallSIRError(
                f"REGION call/SIR bridge requires exactly one function {transfer.function!r}"
            )
        function = function_matches[0]
        matches: list[tuple[str, int, int]] = []
        for block in tuple(getattr(function, "blocks", ()) or ()):
            instructions = tuple(getattr(block, "instructions", ()) or ())
            for index, instruction in enumerate(instructions):
                if not isinstance(instruction, sir.RegionCallTransferInst):
                    continue
                if (
                    instruction.source.name != transfer.binding
                    or instruction.source_name != transfer.binding
                    or instruction.callee != transfer.callee
                    or instruction.parameter != transfer.parameter
                    or instruction.argument_index != transfer.argument_index
                    or instruction.point_id != transfer.point_id
                    or instruction.source.type_name != transfer.type.name
                    or instruction.source_domain != "region"
                    or instruction.target_domain != "region"
                ):
                    continue
                call_index = index + 1
                while (
                    call_index < len(instructions)
                    and isinstance(instructions[call_index], sir.RegionCallTransferInst)
                ):
                    call_index += 1
                if call_index >= len(instructions):
                    raise RegionCallSIRError(
                        "REGION call-transfer fact is not followed by a canonical CallInst"
                    )
                call = instructions[call_index]
                if not isinstance(call, sir.CallInst) or call.callee != transfer.callee:
                    raise RegionCallSIRError(
                        "REGION call-transfer fact diverged from its canonical CallInst"
                    )
                arguments = tuple(call.arguments)
                if transfer.argument_index >= len(arguments):
                    raise RegionCallSIRError(
                        "REGION call-transfer argument index exceeds canonical CallInst"
                    )
                argument = arguments[transfer.argument_index]
                if (
                    argument.name != transfer.binding
                    or argument.type_name != transfer.type.name
                ):
                    raise RegionCallSIRError(
                        "REGION call-transfer source diverged from canonical CallInst argument"
                    )
                matches.append((block.label, index, call_index))
        if len(matches) != 1:
            raise RegionCallSIRError(
                f"REGION call {transfer.function}::{transfer.binding} at {transfer.point_id} "
                f"requires exactly one RegionCallTransferInst, got {len(matches)}"
            )
        block, instruction_index, call_instruction_index = matches[0]
        if not transfer.point_id.startswith("call@"):
            raise RegionCallSIRError(
                "REGION call contract lost source-stable call identity"
            )
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
                call_instruction_index=call_instruction_index,
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
