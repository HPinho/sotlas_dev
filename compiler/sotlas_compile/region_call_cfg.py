"""Path-sensitive certification for interprocedural REGION call transfers.

This layer consumes an already validated ``RegionCallSIRBridge`` plus canonical
SIR and proves only control-flow facts. It does not create ownership facts, does
not mutate SIR and does not lower anything to a backend.

Ownership-taking REGION calls inside CFG cycles remain fail-closed until the
canonical model carries iteration identity for call transfers.
"""
from __future__ import annotations

from dataclasses import dataclass

from .canonical_sir import load_canonical_sir
from .region_call_sir import RegionCallSIRBridge
from .region_cfg import _block_is_cyclic, _reachable, _successors
from .typed_ast import Phase1SemanticError


class RegionCallCFGError(Phase1SemanticError):
    """Raised when REGION call transfers cannot be certified on the SIR CFG."""


@dataclass(frozen=True)
class RegionCallCFGPoint:
    function: str
    point_id: str
    callee: str
    block: str
    instruction_index: int
    argument_indices: tuple[int, ...]


@dataclass(frozen=True)
class RegionCallCFGRelation:
    function: str
    first_point_id: str
    second_point_id: str
    relation: str


@dataclass(frozen=True)
class RegionCallCFGCertificate:
    points: tuple[RegionCallCFGPoint, ...]
    relations: tuple[RegionCallCFGRelation, ...]


def _unwrap_module(value: object):
    sir = load_canonical_sir()
    module = getattr(value, "module", value)
    if not isinstance(module, sir.SIRModule):
        raise RegionCallCFGError(
            "REGION call CFG certification requires canonical SIRModule or CheckedOwnershipSIR"
        )
    return sir, module


def certify_region_call_cfg(
    bridge: RegionCallSIRBridge,
    sir_module: object,
) -> RegionCallCFGCertificate:
    if not isinstance(bridge, RegionCallSIRBridge):
        raise RegionCallCFGError(
            "REGION call CFG certification requires a RegionCallSIRBridge"
        )
    sir, module = _unwrap_module(sir_module)
    functions = {item.name: item for item in module.functions}
    if len(functions) != len(module.functions):
        raise RegionCallCFGError("REGION call CFG contains duplicate function names")

    grouped: dict[tuple[str, str], list[object]] = {}
    order: list[tuple[str, str]] = []
    for site in bridge.sites:
        key = (site.function, site.point_id)
        if key not in grouped:
            grouped[key] = []
            order.append(key)
        grouped[key].append(site)

    points: list[RegionCallCFGPoint] = []
    by_function: dict[str, list[RegionCallCFGPoint]] = {}
    for function_name, point_id in order:
        function = functions.get(function_name)
        if function is None:
            raise RegionCallCFGError(
                f"REGION call CFG requires exactly one function {function_name!r}"
            )
        sites = grouped[(function_name, point_id)]
        first = sites[0]
        blocks = {block.label: block for block in function.blocks}
        if len(blocks) != len(function.blocks):
            raise RegionCallCFGError("REGION call CFG contains duplicate block labels")
        block = blocks.get(first.block)
        if block is None:
            raise RegionCallCFGError(
                f"REGION call point {point_id!r} refers to unknown block {first.block!r}"
            )
        if first.instruction_index < 0 or first.instruction_index >= len(block.instructions):
            raise RegionCallCFGError(
                f"REGION call point {point_id!r} has invalid instruction index"
            )
        instruction = block.instructions[first.instruction_index]
        if not isinstance(instruction, sir.CallInst):
            raise RegionCallCFGError(
                f"REGION call point {point_id!r} no longer refers to a CallInst"
            )
        if instruction.callee != first.callee:
            raise RegionCallCFGError(
                f"REGION call point {point_id!r} callee diverges from canonical SIR"
            )

        argument_indices: list[int] = []
        for site in sites:
            if (
                site.block != first.block
                or site.instruction_index != first.instruction_index
                or site.callee != first.callee
            ):
                raise RegionCallCFGError(
                    f"REGION call point {point_id!r} is split across multiple SIR calls"
                )
            if site.argument_index in argument_indices:
                raise RegionCallCFGError(
                    f"REGION call point {point_id!r} repeats argument index {site.argument_index}"
                )
            if site.argument_index < 0 or site.argument_index >= len(instruction.arguments):
                raise RegionCallCFGError(
                    f"REGION call point {point_id!r} has invalid argument index"
                )
            argument = instruction.arguments[site.argument_index]
            if argument.name != site.binding:
                raise RegionCallCFGError(
                    f"REGION call point {point_id!r} binding diverges from canonical SIR"
                )
            argument_indices.append(site.argument_index)

        point = RegionCallCFGPoint(
            function=function_name,
            point_id=point_id,
            callee=first.callee,
            block=first.block,
            instruction_index=first.instruction_index,
            argument_indices=tuple(argument_indices),
        )
        points.append(point)
        by_function.setdefault(function_name, []).append(point)

    relations: list[RegionCallCFGRelation] = []
    for function_name, function_points in by_function.items():
        function = functions[function_name]
        successors = _successors(function)
        for point in function_points:
            if _block_is_cyclic(successors, point.block):
                raise RegionCallCFGError(
                    f"REGION ownership-taking call {point.point_id!r} inside a CFG cycle "
                    "requires iteration identity"
                )

        for first_index, first in enumerate(function_points):
            for second in function_points[first_index + 1 :]:
                if first.block == second.block:
                    if first.instruction_index >= second.instruction_index:
                        raise RegionCallCFGError(
                            "REGION call source order diverges from SIR CFG order"
                        )
                    relation = "ordered_path"
                else:
                    forward = _reachable(successors, first.block, second.block)
                    reverse = _reachable(successors, second.block, first.block)
                    if reverse:
                        raise RegionCallCFGError(
                            "REGION call source order diverges from SIR CFG reachability"
                        )
                    relation = "ordered_path" if forward else "path_disjoint"
                relations.append(
                    RegionCallCFGRelation(
                        function=function_name,
                        first_point_id=first.point_id,
                        second_point_id=second.point_id,
                        relation=relation,
                    )
                )

    return RegionCallCFGCertificate(tuple(points), tuple(relations))


__all__ = [
    "RegionCallCFGError",
    "RegionCallCFGPoint",
    "RegionCallCFGRelation",
    "RegionCallCFGCertificate",
    "certify_region_call_cfg",
]
