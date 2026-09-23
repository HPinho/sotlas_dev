"""Backend-neutral lowering and verified CFG placement for shared ownership.

Ownership facts are first lowered into explicit SIR operations. Cleanup segments
with source-stable return point identities can then be inserted into matching
ReturnInst nodes. Other control-flow kinds remain staged until their terminators
and backedges have equally precise CFG identities.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Tuple

from .instructions import (
    SIRInstruction,
    SIRValue,
    SIRFunction,
    SIRModule,
    ReturnInst,
    BranchInst,
    OwnershipDomainPointInst,
    OwnershipDomainTransferInst,
    WhisperBorrowInst,
    DirectAccessInst,
    SharedOwnershipPointInst,
    ShareInst,
    RetainInst,
    ReleaseInst,
    DestroyInst,
    DeferUseInst,
    CallInst,
)


@dataclass(frozen=True)
class OwnershipDomainSIRPlan:
    instructions: Tuple[SIRInstruction, ...]


@dataclass(frozen=True)
class OwnershipFunctionSIRPlan:
    function: str
    domain: OwnershipDomainSIRPlan
    shared: "SharedOwnershipSIRPlan"


@dataclass(frozen=True)
class OwnershipModuleSIRPlan:
    functions: Tuple[OwnershipFunctionSIRPlan, ...]


@dataclass(frozen=True)
class OwnershipDomainSIRPlacement:
    plan: OwnershipDomainSIRPlan
    inserted_instructions: int


@dataclass(frozen=True)
class OwnershipModuleSIRPlacement:
    plan: OwnershipModuleSIRPlan
    inserted_domain_instructions: int


@dataclass(frozen=True)
class OwnershipModulePlacement:
    plan: OwnershipModuleSIRPlan
    inserted_domain_instructions: int
    inserted_shared_semantic_instructions: int
    inserted_function_exit_instructions: int
    inserted_return_cleanup_instructions: int
    inserted_loop_control_instructions: int
    inserted_backedge_instructions: int


@dataclass(frozen=True)
class CheckedOwnershipSIR:
    module: SIRModule
    placement: OwnershipModulePlacement


@dataclass(frozen=True)
class SharedOwnershipSIRSegment:
    via: str
    instructions: Tuple[SIRInstruction, ...]
    point_id: str | None = None


@dataclass(frozen=True)
class SharedOwnershipSIRSemanticPoint:
    point_id: str
    source: str
    alias: str
    instructions: Tuple[SIRInstruction, ...]


@dataclass(frozen=True)
class SharedOwnershipSIRPlan:
    semantic: Tuple[SIRInstruction, ...]
    cleanup_segments: Tuple[SharedOwnershipSIRSegment, ...]
    semantic_points: Tuple[SharedOwnershipSIRSemanticPoint, ...] = ()


@dataclass(frozen=True)
class SharedOwnershipSIRPlacement:
    plan: SharedOwnershipSIRPlan
    inserted_return_instructions: int
    inserted_loop_control_instructions: int = 0
    inserted_backedge_instructions: int = 0
    inserted_function_exit_instructions: int = 0


def _type_map(trace: Any) -> dict[str, str]:
    result: dict[str, str] = {}
    final_env = getattr(trace, "final_env", None)
    for binding in getattr(final_env, "bindings", ()) or ():
        type_info = getattr(binding, "type", None)
        type_name = getattr(type_info, "name", None)
        if type_name:
            result[getattr(binding, "name")] = type_name
    return result


def _share_types(trace: Any, result: dict[str, str]) -> dict[str, str]:
    for event in getattr(trace, "events", ()) or ():
        if getattr(event, "kind", None) != "domain_transition":
            continue
        if not str(getattr(event, "via", "")).startswith("share:"):
            continue
        source = getattr(event, "name", "")
        if source in result:
            continue
        event_type = getattr(event, "type", None)
        type_name = getattr(event_type, "name", None)
        if type_name:
            result[source] = type_name
    return result


def _value(name: str, types: dict[str, str]) -> SIRValue:
    type_name = types.get(name)
    if type_name is None:
        raise ValueError(
            f"shared ownership SIR lowering lacks type for binding {name!r}"
        )
    return SIRValue(name, type_name)


def _domain_name(domain: Any) -> str | None:
    if domain is None:
        return None
    return str(getattr(domain, "value", domain))


def lower_ownership_domain_graph(
    graph: Any,
    function_name: str,
) -> OwnershipDomainSIRPlan:
    """Lower canonical domain-graph transfers for one function into SIR."""
    nodes = {
        getattr(node, "binding"): node
        for node in getattr(graph, "nodes", ()) or ()
        if getattr(node, "function", None) == function_name
    }
    instructions: list[SIRInstruction] = []

    for transfer in getattr(graph, "transfers", ()) or ():
        if getattr(transfer, "function", None) != function_name:
            continue
        operation = str(getattr(transfer, "via", ""))
        if operation not in ("quarantine", "handover"):
            continue

        binding = getattr(transfer, "binding", "")
        node = nodes.get(binding)
        if node is None:
            raise ValueError(
                f"ownership domain graph lacks node for "
                f"{function_name}::{binding}"
            )
        type_info = getattr(node, "type", None)
        type_name = getattr(type_info, "name", None)
        if not type_name:
            raise ValueError(
                f"ownership domain graph lacks type for "
                f"{function_name}::{binding}"
            )

        source_domain = _domain_name(
            getattr(transfer, "source_domain", None)
        )
        target_domain = _domain_name(
            getattr(transfer, "target_domain", None)
        )
        if source_domain is None or target_domain is None:
            raise ValueError(
                f"ownership domain graph lacks complete domains for "
                f"{operation} {function_name}::{binding}"
            )

        destination_value = None
        destination = getattr(transfer, "destination", None)
        if operation == "quarantine":
            if source_domain != "exclusive" or target_domain != "island":
                raise ValueError(
                    f"invalid quarantine ownership transition "
                    f"{source_domain}->{target_domain} for "
                    f"{function_name}::{binding}"
                )
            if destination is not None:
                raise ValueError(
                    f"quarantine transfer for {function_name}::{binding} "
                    "cannot have destination"
                )
        else:
            if destination is None and source_domain in (
                "island", "region", "device", "external"
            ):
                raise ValueError(
                    f"island handover {function_name}::{binding} requires "
                    "explicit destination for SIR lowering"
                )
            if destination is not None:
                destination_domain = _domain_name(
                    getattr(transfer, "destination_domain", None)
                )
                if destination_domain != target_domain:
                    raise ValueError(
                        f"handover destination domain mismatch for "
                        f"{function_name}::{binding}"
                    )
                destination_node = nodes.get(destination)
                if destination_node is None:
                    raise ValueError(
                        f"ownership domain graph lacks destination node for "
                        f"{function_name}::{destination}"
                    )
                destination_type_info = getattr(destination_node, "type", None)
                destination_type = getattr(destination_type_info, "name", None)
                destination_node_domain = _domain_name(
                    getattr(destination_node, "domain", None)
                )
                if destination_node_domain != target_domain:
                    raise ValueError(
                        f"handover destination domain mismatch for "
                        f"{function_name}::{binding}"
                    )
                if destination_type != type_name or destination_type_info != type_info:
                    raise ValueError(
                        f"handover destination type mismatch for "
                        f"{function_name}::{binding}"
                    )
                destination_value = SIRValue(destination, type_name)

        point_id = getattr(transfer, "point_id", None)
        if point_id is not None and not str(point_id).startswith(
            f"{operation}@"
        ):
            raise ValueError(
                f"ownership domain graph has invalid source point "
                f"{point_id!r} for {function_name}::{binding}"
            )
        instructions.append(
            OwnershipDomainTransferInst(
                operation=operation,
                source=SIRValue(binding, type_name),
                source_domain=source_domain,
                target_domain=target_domain,
                destination=destination_value,
                point_id=point_id,
            )
        )

    for borrow in getattr(graph, "whisper_borrows", ()) or ():
        if getattr(borrow, "function", None) != function_name:
            continue
        source = getattr(borrow, "source", None)
        callee = getattr(borrow, "callee", None)
        parameter = getattr(borrow, "parameter", None)
        type_info = getattr(borrow, "type", None)
        source_domain = _domain_name(getattr(borrow, "source_domain", None))
        point_id = getattr(borrow, "point_id", None)
        if (
            not isinstance(source, str) or not source
            or not isinstance(callee, str) or not callee
            or not isinstance(parameter, str) or not parameter
            or not getattr(type_info, "name", None)
            or source_domain not in (
                "exclusive", "shared", "island", "whisper", "direct"
            )
            or not isinstance(point_id, str)
            or not point_id.startswith("whisper@")
        ):
            raise ValueError(
                f"invalid canonical whisper borrow for {function_name!r}"
            )
        instructions.append(
            WhisperBorrowInst(
                source=SIRValue(source, type_info.name),
                callee=callee,
                parameter=parameter,
                source_domain=source_domain,
                point_id=point_id,
            )
        )

    for access in getattr(graph, "direct_accesses", ()) or ():
        if getattr(access, "function", None) != function_name:
            continue
        source = getattr(access, "source", None)
        callee = getattr(access, "callee", None)
        parameter = getattr(access, "parameter", None)
        type_info = getattr(access, "type", None)
        source_domain = _domain_name(getattr(access, "source_domain", None))
        point_id = getattr(access, "point_id", None)
        source_node = nodes.get(source)
        source_node_domain = _domain_name(
            getattr(source_node, "domain", None)
        ) if source_node is not None else None
        source_node_type = getattr(source_node, "type", None)
        forwarded_direct = source_domain == "direct"
        if (
            not isinstance(source, str) or not source
            or not isinstance(callee, str) or not callee
            or not isinstance(parameter, str) or not parameter
            or not getattr(type_info, "name", None)
            or source_domain not in ("exclusive", "shared", "direct")
            or (
                forwarded_direct
                and source_node is not None
            )
            or (
                not forwarded_direct
                and (
                    source_node is None
                    or source_node_domain != source_domain
                    or getattr(source_node_type, "name", None)
                    != getattr(type_info, "name", None)
                )
            )
            or not isinstance(point_id, str)
            or not point_id.startswith("direct@")
        ):
            raise ValueError(
                f"invalid canonical direct access or owner node for "
                f"{function_name!r}"
            )
        instructions.append(
            DirectAccessInst(
                source=SIRValue(source, type_info.name),
                callee=callee,
                parameter=parameter,
                source_domain=source_domain,
                point_id=point_id,
            )
        )

    return OwnershipDomainSIRPlan(tuple(instructions))


def lower_ownership_domain_trace(trace: Any) -> OwnershipDomainSIRPlan:
    """Lower quarantine/handover domain facts into backend-neutral SIR.

    This stage records semantic ownership movement only. It does not select a
    runtime ABI, emit C, or claim target-specific synchronization behavior.
    """
    types = _type_map(trace)
    instructions: list[SIRInstruction] = []

    for event in getattr(trace, "events", ()) or ():
        kind = getattr(event, "kind", None)
        if kind == "borrow" and getattr(event, "domain", None) is not None:
            event_domain = _domain_name(event.domain)
            if event_domain not in ("whisper", "direct"):
                continue
            source = getattr(event, "source_binding", None)
            callee = getattr(event, "callee", None)
            parameter = getattr(event, "parameter", None)
            event_type = getattr(event, "type", None)
            source_domain = _domain_name(
                getattr(event, "source_domain", None)
            )
            point_id = getattr(event, "point_id", None)
            if (
                not isinstance(source, str) or not source
                or not isinstance(callee, str) or not callee
                or not isinstance(parameter, str) or not parameter
                or not getattr(event_type, "name", None)
                or source_domain not in (
                    "exclusive", "shared", "whisper", "direct"
                )
                or not isinstance(point_id, str)
                or not point_id.startswith(f"{event_domain}@")
            ):
                raise ValueError(
                    f"invalid {event_domain} access ownership trace event"
                )
            access_inst = (
                WhisperBorrowInst(
                    source=SIRValue(source, event_type.name),
                    callee=callee,
                    parameter=parameter,
                    source_domain=source_domain,
                    point_id=point_id,
                )
            )
            if event_domain == "direct":
                access_inst = DirectAccessInst(
                    source=SIRValue(source, event_type.name),
                    callee=callee,
                    parameter=parameter,
                    source_domain=source_domain,
                    point_id=point_id,
                )
            instructions.append(access_inst)
            continue
        if kind not in ("quarantine", "handover"):
            continue

        name = getattr(event, "name", "")
        event_type = getattr(event, "type", None)
        type_name = getattr(event_type, "name", None)
        if name and name not in types and type_name:
            types[name] = type_name

        source_domain = _domain_name(getattr(event, "source_domain", None))
        target_domain = _domain_name(getattr(event, "target_domain", None))
        if source_domain is None or target_domain is None:
            raise ValueError(
                f"ownership domain SIR lowering lacks complete domains for "
                f"{kind} {name!r}"
            )

        if kind == "quarantine":
            if source_domain != "exclusive" or target_domain != "island":
                raise ValueError(
                    f"invalid quarantine ownership transition "
                    f"{source_domain}->{target_domain} for {name!r}"
                )
            destination_value = None
        else:
            destination = getattr(event, "destination", None)
            destination_value = None
            if destination is not None:
                destination_domain = _domain_name(
                    getattr(event, "destination_domain", None)
                )
                if destination_domain != target_domain:
                    raise ValueError(
                        f"handover destination domain mismatch for {name!r}"
                    )
                if destination not in types:
                    source_type = types.get(name) or type_name
                    if source_type is None:
                        raise ValueError(
                            f"ownership domain SIR lowering lacks type for "
                            f"handover destination {destination!r}"
                        )
                    types[destination] = source_type
                destination_value = _value(destination, types)
            elif source_domain in ("island", "region", "device", "external"):
                raise ValueError(
                    f"island handover {name!r} requires explicit destination "
                    "for SIR lowering"
                )

        instructions.append(
            OwnershipDomainTransferInst(
                operation=kind,
                source=_value(name, types),
                source_domain=source_domain,
                target_domain=target_domain,
                destination=destination_value,
                point_id=getattr(event, "point_id", None),
            )
        )

    return OwnershipDomainSIRPlan(tuple(instructions))


def _ownership_domain_transfer_replacements(
    function: SIRFunction,
    plan: OwnershipDomainSIRPlan,
) -> dict[int, OwnershipDomainTransferInst]:
    """Preflight one function without mutating its CFG."""
    markers: list[OwnershipDomainPointInst] = []
    for block in function.blocks:
        for instruction in block.instructions:
            if isinstance(instruction, OwnershipDomainPointInst):
                markers.append(instruction)

    transfers = tuple(
        instruction for instruction in plan.instructions
        if isinstance(instruction, OwnershipDomainTransferInst)
    )
    if len(markers) != len(transfers):
        raise ValueError(
            f"ownership domain SIR point count mismatch for {function.name!r}: "
            f"{len(markers)} marker(s) vs {len(transfers)} transfer(s)"
        )

    marker_by_point: dict[str, OwnershipDomainPointInst] = {}
    for marker in markers:
        if marker.point_id in marker_by_point:
            raise ValueError(
                f"duplicate ownership domain SIR point {marker.point_id!r}"
            )
        if not marker.point_id.startswith(f"{marker.operation}@"):
            raise ValueError(
                f"invalid ownership domain point identity {marker.point_id!r}"
            )
        marker_by_point[marker.point_id] = marker

    exact = all(
        getattr(transfer, "point_id", None) is not None
        for transfer in transfers
    )
    pairs: list[
        tuple[OwnershipDomainPointInst, OwnershipDomainTransferInst]
    ] = []
    if exact:
        seen_transfer_points: set[str] = set()
        for transfer in transfers:
            point_id = str(transfer.point_id)
            if point_id in seen_transfer_points:
                raise ValueError(
                    f"duplicate ownership domain transfer point {point_id!r}"
                )
            seen_transfer_points.add(point_id)
            marker = marker_by_point.get(point_id)
            if marker is None:
                raise ValueError(
                    f"ownership domain transfer point {point_id!r} "
                    f"missing from SIR CFG for {function.name!r}"
                )
            pairs.append((marker, transfer))
    else:
        pairs = list(zip(markers, transfers))

    for marker, transfer in pairs:
        if marker.operation != transfer.operation:
            raise ValueError(
                f"ownership domain operation mismatch at {marker.point_id!r}"
            )
        if marker.source_name != transfer.source.name:
            raise ValueError(
                f"ownership domain source mismatch at {marker.point_id!r}"
            )
        transfer_destination = (
            transfer.destination.name
            if transfer.destination is not None else None
        )
        if marker.destination_name != transfer_destination:
            raise ValueError(
                f"ownership domain destination mismatch at {marker.point_id!r}"
            )

    direct_markers = [
        instruction
        for block in function.blocks
        for instruction in block.instructions
        if isinstance(instruction, DirectAccessInst)
    ]
    direct_facts = [
        instruction for instruction in plan.instructions
        if isinstance(instruction, DirectAccessInst)
    ]
    if len(direct_markers) != len(direct_facts):
        raise ValueError(
            f"direct access SIR point count mismatch for {function.name!r}: "
            f"{len(direct_markers)} marker(s) vs {len(direct_facts)} fact(s)"
        )
    direct_by_key = {}
    for marker in direct_markers:
        if not marker.point_id.startswith("direct@"):
            raise ValueError(
                f"invalid direct access SIR point {marker.point_id!r}"
            )
        key = (
            marker.point_id,
            marker.callee,
            marker.parameter,
            marker.source.name,
        )
        if key in direct_by_key:
            raise ValueError(
                f"duplicate direct access SIR fact at {marker.point_id!r}"
            )
        direct_by_key[key] = marker
    for fact in direct_facts:
        point_id = fact.point_id
        key = (point_id, fact.callee, fact.parameter, fact.source.name)
        marker = direct_by_key.pop(key, None)
        if marker is None:
            raise ValueError(
                f"direct access graph fact at {point_id!r} missing from SIR CFG "
                f"for {function.name!r}"
            )
        if (
            marker.source_domain != fact.source_domain
            or marker.source.type_name != fact.source.type_name
        ):
            raise ValueError(
                f"direct access fact mismatch at {point_id!r}"
            )
    if direct_by_key:
        point_id = next(iter(direct_by_key))[0]
        raise ValueError(
            f"unverified direct access SIR fact at {point_id!r}"
        )

    whisper_markers = [
        instruction
        for block in function.blocks
        for instruction in block.instructions
        if isinstance(instruction, WhisperBorrowInst)
    ]
    whisper_facts = [
        instruction for instruction in plan.instructions
        if isinstance(instruction, WhisperBorrowInst)
    ]
    if len(whisper_markers) != len(whisper_facts):
        raise ValueError(
            f"whisper borrow SIR point count mismatch for {function.name!r}: "
            f"{len(whisper_markers)} marker(s) vs {len(whisper_facts)} fact(s)"
        )
    whisper_by_key = {}
    for marker in whisper_markers:
        if not marker.point_id.startswith("whisper@"):
            raise ValueError(
                f"invalid whisper borrow SIR point {marker.point_id!r}"
            )
        key = (
            marker.point_id,
            marker.callee,
            marker.parameter,
            marker.source.name,
        )
        if key in whisper_by_key:
            raise ValueError(
                f"duplicate whisper borrow SIR fact at {marker.point_id!r}"
            )
        whisper_by_key[key] = marker
    for fact in whisper_facts:
        key = (fact.point_id, fact.callee, fact.parameter, fact.source.name)
        marker = whisper_by_key.pop(key, None)
        if marker is None or (
            marker.source_domain != fact.source_domain
            or marker.source.type_name != fact.source.type_name
        ):
            raise ValueError(
                f"whisper borrow fact mismatch at {fact.point_id!r}"
            )
    if whisper_by_key:
        point_id = next(iter(whisper_by_key))[0]
        raise ValueError(
            f"unverified whisper borrow SIR fact at {point_id!r}"
        )

    return {id(marker): transfer for marker, transfer in pairs}


def _commit_ownership_domain_replacements(
    function: SIRFunction,
    replacements: dict[int, OwnershipDomainTransferInst],
) -> int:
    inserted = 0
    for block in function.blocks:
        rewritten: list[SIRInstruction] = []
        for instruction in block.instructions:
            replacement = replacements.get(id(instruction))
            if replacement is not None:
                rewritten.append(replacement)
                inserted += 1
            else:
                rewritten.append(instruction)
        block.instructions = rewritten
    return inserted


def place_ownership_domain_transfers(
    function: SIRFunction,
    plan: OwnershipDomainSIRPlan,
) -> OwnershipDomainSIRPlacement:
    """Atomically replace source markers with validated domain-transfer SIR."""
    replacements = _ownership_domain_transfer_replacements(function, plan)
    inserted = _commit_ownership_domain_replacements(function, replacements)
    return OwnershipDomainSIRPlacement(plan, inserted)


def apply_ownership_module_domain_transfers(
    module: SIRModule,
    plan: OwnershipModuleSIRPlan,
) -> OwnershipModuleSIRPlacement:
    """Apply all per-function ownership-domain placements transactionally."""
    functions: dict[str, SIRFunction] = {}
    for function in module.functions:
        if function.name in functions:
            raise ValueError(
                f"duplicate SIR function {function.name!r} during ownership placement"
            )
        functions[function.name] = function

    preflight: list[
        tuple[SIRFunction, dict[int, OwnershipDomainTransferInst]]
    ] = []
    seen_plans: set[str] = set()
    for function_plan in plan.functions:
        name = function_plan.function
        if name in seen_plans:
            raise ValueError(
                f"duplicate ownership SIR plan for function {name!r}"
            )
        seen_plans.add(name)
        function = functions.get(name)
        if function is None:
            raise ValueError(
                f"ownership SIR plan references missing function {name!r}"
            )
        replacements = _ownership_domain_transfer_replacements(
            function, function_plan.domain
        )
        preflight.append((function, replacements))

    inserted = 0
    for function, replacements in preflight:
        inserted += _commit_ownership_domain_replacements(
            function, replacements
        )
    return OwnershipModuleSIRPlacement(plan, inserted)


def _cleanup_instructions(
    steps: Iterable[Any],
    types: dict[str, str],
) -> Tuple[SIRInstruction, ...]:
    instructions: list[SIRInstruction] = []
    for step in steps:
        owner = getattr(step, "owner")
        account = getattr(step, "account")
        instructions.append(ReleaseInst(_value(owner, types)))
        if getattr(step, "destroy_after", False):
            instructions.append(DestroyInst(_value(account, types)))
    return tuple(instructions)


def _defer_instruction(
    action: Any,
    types: dict[str, str],
    lowered_calls: dict[tuple[str, str | None, str], tuple[str, tuple[str, ...]]],
    context: str,
) -> SIRInstruction | None:
    owner = getattr(action, "owner", None)
    defer_point_id = getattr(action, "defer_point_id", None)
    if defer_point_id is None:
        raise ValueError(f"{context} defer lacks source identity")
    if not str(defer_point_id).startswith("defer@"):
        raise ValueError(
            f"{context} defer has invalid source identity {defer_point_id!r}"
        )

    via = str(getattr(action, "via", ""))
    payload_kind = via.rsplit(":", 1)[-1]
    call = getattr(action, "defer_call", None)
    if payload_kind in ("call", "method") or (
        payload_kind == "block" and call is not None
    ):
        if (not isinstance(call, tuple) or len(call) != 2
                or not isinstance(call[0], str) or not call[0]
                or not isinstance(call[1], tuple)
                or not all(
                    isinstance(arg, str)
                    and (
                        arg in types
                        or (
                            arg.startswith("&")
                            and arg[1:] in types
                            and not arg.startswith("&&")
                        )
                    )
                    for arg in call[1]
                )):
            raise ValueError(
                f"{context} defer {payload_kind} lacks typed direct arguments at "
                f"{defer_point_id}"
            )
        control = via.split(":", 1)[0]
        call_key = (
            control,
            getattr(action, "point_id", None),
            str(defer_point_id),
        )
        if call_key in lowered_calls:
            if lowered_calls[call_key] != call:
                raise ValueError(
                    f"conflicting shared defer call payload at {defer_point_id}"
                )
            return None
        lowered_calls[call_key] = call
        call_arguments = []
        for argument in call[1]:
            if argument.startswith("&"):
                source = argument[1:]
                call_arguments.append(
                    SIRValue(source, f"{types[source]}*")
                )
            else:
                call_arguments.append(_value(argument, types))
        return CallInst(
            call[0], call_arguments,
            defer_point_id=str(defer_point_id),
        )
    if payload_kind == "expression":
        if owner is None:
            raise ValueError(f"{context} defer expression lacks owner")
        return DeferUseInst(_value(owner, types), str(defer_point_id))
    raise ValueError(
        f"shared defer payload lowering is not implemented in SIR for "
        f"{payload_kind or 'unknown'} payload at {defer_point_id}"
    )


def lower_shared_ownership_trace(trace: Any) -> SharedOwnershipSIRPlan:
    """Lower canonical shared ownership facts without claiming CFG placement."""
    types = _share_types(trace, _type_map(trace))
    semantic: list[SIRInstruction] = []
    semantic_points: dict[str, dict[str, Any]] = {}

    for event in getattr(trace, "events", ()) or ():
        kind = getattr(event, "kind", None)
        via = str(getattr(event, "via", ""))
        if kind == "domain_transition" and via.startswith("share:"):
            source = getattr(event, "name")
            alias = via.split(":", 1)[1]
            source_value = _value(source, types)
            share_inst = ShareInst(source_value)
            semantic.append(share_inst)
            if alias and alias not in types:
                types[alias] = source_value.type_name
            point_id = getattr(event, "point_id", None)
            if point_id is not None:
                semantic_points.setdefault(
                    str(point_id),
                    {"source": source, "alias": alias, "instructions": []},
                )["instructions"].append(share_inst)
            continue
        if kind == "retain" and via.startswith("share:"):
            owner = getattr(event, "name")
            account = via.split(":", 1)[1]
            if owner not in types and account in types:
                types[owner] = types[account]
            retain_inst = RetainInst(_value(owner, types))
            semantic.append(retain_inst)
            point_id = getattr(event, "point_id", None)
            if point_id is not None:
                point = semantic_points.setdefault(
                    str(point_id),
                    {
                        "source": getattr(event, "source_binding", None) or account,
                        "alias": owner,
                        "instructions": [],
                    },
                )
                event_source = getattr(event, "source_binding", None) or account
                if point["source"] != event_source or point["alias"] != owner:
                    raise ValueError(
                        f"shared ownership SIR point {point_id!r} has "
                        "inconsistent source/alias facts"
                    )
                point["instructions"].append(retain_inst)

    points = tuple(
        SharedOwnershipSIRSemanticPoint(
            point_id=point_id,
            source=data["source"],
            alias=data["alias"],
            instructions=tuple(data["instructions"]),
        )
        for point_id, data in semantic_points.items()
    )
    for point in points:
        if not point.point_id.startswith("share@"):
            raise ValueError(
                f"shared ownership SIR point has invalid identity {point.point_id!r}"
            )
        instruction_kinds = tuple(type(inst) for inst in point.instructions)
        if instruction_kinds not in ((ShareInst, RetainInst), (RetainInst,)):
            raise ValueError(
                f"shared ownership SIR point {point.point_id!r} has "
                "unsupported share/retain operations"
            )

    segments: list[SharedOwnershipSIRSegment] = []
    cleanup_sources = (
        ("scope_exit", getattr(trace, "shared_cleanup", None)),
        ("path_exit", getattr(trace, "shared_path_cleanup", None)),
        ("loop_backedge", getattr(trace, "shared_loop_cleanup", None)),
    )
    for label, plan in cleanup_sources:
        steps = tuple(getattr(plan, "steps", ()) or ())
        if not steps:
            continue
        groups: dict[tuple[str, str | None], list[Any]] = {}
        for step in steps:
            via = str(getattr(step, "via", label))
            point_id = getattr(step, "point_id", None)
            groups.setdefault((via, point_id), []).append(step)
        for (via, point_id), grouped in groups.items():
            segments.append(
                SharedOwnershipSIRSegment(
                    via,
                    _cleanup_instructions(grouped, types),
                    point_id or ("function_exit" if via == "scope_exit" else None),
                )
            )

    exit_actions = tuple(
        getattr(getattr(trace, "shared_exit", None), "actions", ()) or ()
    )
    if exit_actions:
        exit_instructions: list[SIRInstruction] = []
        lowered_exit_calls: dict[
            tuple[str, str | None, str], tuple[str, tuple[str, ...]]
        ] = {}
        exit_arc_instructions: list[SIRInstruction] = []
        for action in exit_actions:
            kind = getattr(action, "kind", None)
            owner = getattr(action, "owner", None)
            if owner is None:
                raise ValueError(
                    f"shared function-exit SIR {kind} action lacks owner"
                )
            if kind == "defer":
                instruction = _defer_instruction(
                    action, types, lowered_exit_calls, "shared function-exit"
                )
                if instruction is not None:
                    exit_instructions.append(instruction)
            elif kind == "release":
                instruction = ReleaseInst(_value(owner, types))
                exit_arc_instructions.append(instruction)
                exit_instructions.append(instruction)
            elif kind == "destroy":
                instruction = DestroyInst(_value(owner, types))
                exit_arc_instructions.append(instruction)
                exit_instructions.append(instruction)
            else:
                raise ValueError(
                    f"unsupported shared function-exit action {kind!r}"
                )

        cleanup_index = next(
            (
                index for index, segment in enumerate(segments)
                if segment.via == "scope_exit"
                and segment.point_id == "function_exit"
            ),
            None,
        )
        if cleanup_index is not None:
            cleanup_segment = segments[cleanup_index]
            if tuple(exit_arc_instructions) != cleanup_segment.instructions:
                raise ValueError(
                    "shared function-exit actions do not match ARC cleanup segment"
                )
            segments[cleanup_index] = SharedOwnershipSIRSegment(
                "scope_exit", tuple(exit_instructions), "function_exit"
            )
        elif exit_instructions:
            if exit_arc_instructions:
                raise ValueError(
                    "shared function-exit actions lack a matching ARC cleanup segment"
                )
            segments.append(
                SharedOwnershipSIRSegment(
                    "scope_exit", tuple(exit_instructions), "function_exit"
                )
            )

    return_actions = tuple(
        getattr(getattr(trace, "shared_return_exit", None), "actions", ())
        or ()
    )
    if return_actions:
        grouped_return_actions: dict[str, list[Any]] = {}
        for action in return_actions:
            point_id = getattr(action, "point_id", None)
            if not isinstance(point_id, str) or not point_id.startswith("return@"):
                raise ValueError(
                    "shared return-exit action lacks a source-identified return"
                )
            grouped_return_actions.setdefault(point_id, []).append(action)

        lowered_return_calls: dict[
            tuple[str, str | None, str], tuple[str, tuple[str, ...]]
        ] = {}
        for point_id, grouped in grouped_return_actions.items():
            defer_instructions: list[SIRInstruction] = []
            return_arc_instructions: list[SIRInstruction] = []
            for action in grouped:
                kind = getattr(action, "kind", None)
                owner = getattr(action, "owner", None)
                if owner is None:
                    raise ValueError(
                        f"shared return-exit SIR {kind} action lacks owner"
                    )
                if kind == "defer":
                    instruction = _defer_instruction(
                        action,
                        types,
                        lowered_return_calls,
                        "shared return-exit",
                    )
                    if instruction is not None:
                        defer_instructions.append(instruction)
                elif kind == "release":
                    return_arc_instructions.append(
                        ReleaseInst(_value(owner, types))
                    )
                elif kind == "destroy":
                    return_arc_instructions.append(
                        DestroyInst(_value(owner, types))
                    )
                else:
                    raise ValueError(
                        f"unsupported shared return-exit action {kind!r}"
                    )

            cleanup_index = next(
                (
                    index for index, segment in enumerate(segments)
                    if segment.via == "early_return"
                    and segment.point_id == point_id
                ),
                None,
            )
            if cleanup_index is not None:
                cleanup_segment = segments[cleanup_index]
                if tuple(return_arc_instructions) != cleanup_segment.instructions:
                    raise ValueError(
                        "shared return-exit actions do not match ARC cleanup segment"
                    )
                segments[cleanup_index] = SharedOwnershipSIRSegment(
                    "early_return",
                    tuple(defer_instructions) + cleanup_segment.instructions,
                    point_id,
                )
            elif return_arc_instructions:
                raise ValueError(
                    "shared return-exit actions lack a matching ARC cleanup segment"
                )
            elif defer_instructions:
                segments.append(
                    SharedOwnershipSIRSegment(
                        "early_return", tuple(defer_instructions), point_id
                    )
                )

    control_plan = getattr(trace, "shared_loop_control_exit", None)
    actions = tuple(getattr(control_plan, "actions", ()) or ())
    if actions:
        grouped_actions: dict[tuple[str, str | None], list[SIRInstruction]] = {}
        lowered_calls: dict[
            tuple[str, str | None, str], tuple[str, tuple[str, ...]]
        ] = {}
        for action in actions:
            kind = getattr(action, "kind")
            owner = getattr(action, "owner", None)
            via = str(getattr(action, "via", "loop_control"))
            if owner is None:
                raise ValueError(
                    f"shared ownership SIR {kind} action lacks owner"
                )
            if kind == "defer":
                inst = _defer_instruction(
                    action, types, lowered_calls, "shared loop-control"
                )
                if inst is None:
                    continue
            elif kind == "release":
                inst = ReleaseInst(_value(owner, types))
            elif kind == "destroy":
                inst = DestroyInst(_value(owner, types))
            else:
                continue
            control = via.split(":", 1)[0]
            point_id = getattr(action, "point_id", None)
            grouped_actions.setdefault((control, point_id), []).append(inst)
        for (control, point_id), instructions in grouped_actions.items():
            segments.append(
                SharedOwnershipSIRSegment(
                    f"loop_control:{control}",
                    tuple(instructions),
                    point_id,
                )
            )

    return SharedOwnershipSIRPlan(
        tuple(semantic), tuple(segments), points
    )


def lower_shared_ownership_graph(
    graph: Any,
    function_name: str,
    trace: Any,
) -> SharedOwnershipSIRPlan:
    """Use canonical graph accounts for share/retain semantics and trace for cleanup."""
    trace_plan = lower_shared_ownership_trace(trace)

    accounts = tuple(
        account
        for account in getattr(graph, "shared_accounts", ()) or ()
        if getattr(account, "function", None) == function_name
    )
    transitions = tuple(
        transition
        for transition in getattr(graph, "planned_transitions", ()) or ()
        if getattr(transition, "function", None) == function_name
        and getattr(transition, "operation", None) == "share"
    )

    if not accounts and not transitions:
        if trace_plan.semantic:
            raise ValueError(
                f"canonical ownership graph lacks shared account(s) for "
                f"{function_name!r}"
            )
        return trace_plan

    transition_by_binding: dict[str, Any] = {}
    for transition in transitions:
        binding = getattr(transition, "binding", "")
        if binding in transition_by_binding:
            raise ValueError(
                f"duplicate canonical shared transition for "
                f"{function_name}::{binding}"
            )
        transition_by_binding[binding] = transition

    semantic: list[SIRInstruction] = []
    points: list[SharedOwnershipSIRSemanticPoint] = []
    seen_accounts: set[str] = set()

    for account in accounts:
        binding = getattr(account, "binding", "")
        if binding in seen_accounts:
            raise ValueError(
                f"duplicate canonical shared account for "
                f"{function_name}::{binding}"
            )
        seen_accounts.add(binding)

        transition = transition_by_binding.get(binding)
        if transition is None:
            raise ValueError(
                f"canonical shared account {function_name}::{binding} "
                "lacks EXCLUSIVE->SHARED transition"
            )

        source = _domain_name(getattr(transition, "source", None))
        target = _domain_name(getattr(transition, "target", None))
        if source != "exclusive" or target != "shared":
            raise ValueError(
                f"invalid canonical shared transition "
                f"{source}->{target} for {function_name}::{binding}"
            )

        point_id = getattr(account, "point_id", None)
        transition_point = getattr(transition, "point_id", None)
        if (
            point_id is None
            or not str(point_id).startswith("share@")
            or transition_point != point_id
        ):
            raise ValueError(
                f"canonical shared source point mismatch for "
                f"{function_name}::{binding}"
            )

        owners = tuple(getattr(account, "owners", ()) or ())
        strong_refs = getattr(account, "strong_refs", None)
        if (
            len(owners) < 2
            or owners[0] != binding
            or strong_refs != len(owners)
        ):
            raise ValueError(
                f"canonical shared account {function_name}::{binding} "
                "does not match its strong-owner accounting"
            )

        type_info = getattr(account, "type", None)
        transition_type = getattr(transition, "type", None)
        type_name = getattr(type_info, "name", None)
        transition_type_name = getattr(transition_type, "name", None)
        if not type_name or transition_type_name != type_name:
            raise ValueError(
                f"canonical shared type mismatch for "
                f"{function_name}::{binding}"
            )

        alias = owners[1]
        share_inst = ShareInst(SIRValue(binding, type_name))
        retain_inst = RetainInst(SIRValue(alias, type_name))
        semantic.extend((share_inst, retain_inst))
        points.append(
            SharedOwnershipSIRSemanticPoint(
                point_id=str(point_id),
                source=binding,
                alias=alias,
                instructions=(share_inst, retain_inst),
            )
        )

        alias_points = tuple(
            point for point in getattr(graph, "shared_alias_points", ()) or ()
            if getattr(point, "function", None) == function_name
            and getattr(point, "account", None) == binding
            and getattr(point, "operation", None) == "share_alias"
        )
        if len(alias_points) != len(owners) - 2:
            raise ValueError(
                f"canonical shared account {function_name}::{binding} "
                "lacks source-identified clone alias points"
            )
        seen_aliases = {binding, alias}
        for alias_point in alias_points:
            clone_source = getattr(alias_point, "source", None)
            clone_alias = getattr(alias_point, "alias", None)
            clone_point_id = getattr(alias_point, "point_id", None)
            if (
                clone_source not in seen_aliases
                or clone_alias in seen_aliases
                or clone_alias not in owners
                or not isinstance(clone_point_id, str)
                or not clone_point_id.startswith("share@")
            ):
                raise ValueError(
                    f"invalid canonical shared alias point for "
                    f"{function_name}::{binding}"
                )
            retain_clone = RetainInst(SIRValue(clone_alias, type_name))
            semantic.append(retain_clone)
            points.append(SharedOwnershipSIRSemanticPoint(
                point_id=clone_point_id,
                source=clone_source,
                alias=clone_alias,
                instructions=(retain_clone,),
            ))
            seen_aliases.add(clone_alias)

    extra_transitions = sorted(set(transition_by_binding) - seen_accounts)
    if extra_transitions:
        raise ValueError(
            f"canonical shared transition lacks account for "
            f"{function_name}::{extra_transitions[0]}"
        )

    if len(trace_plan.semantic_points) != len(points):
        raise ValueError(
            f"canonical shared graph/trace point count mismatch for "
            f"{function_name!r}"
        )
    trace_points = {
        point.point_id: (point.source, point.alias)
        for point in trace_plan.semantic_points
    }
    for point in points:
        if trace_points.get(point.point_id) != (point.source, point.alias):
            raise ValueError(
                f"canonical shared graph/trace identity mismatch at "
                f"{point.point_id!r}"
            )

    return SharedOwnershipSIRPlan(
        tuple(semantic),
        trace_plan.cleanup_segments,
        tuple(points),
    )


def lower_ownership_module_semantics(
    analysis: Any,
    domain_graph: Any,
) -> OwnershipModuleSIRPlan:
    """Compose canonical domain-graph lowering with trace-based shared ARC."""
    traces = tuple(getattr(analysis, "traces", ()) or ())
    graph_functions = {
        getattr(node, "function", None)
        for node in getattr(domain_graph, "nodes", ()) or ()
    }
    functions: list[OwnershipFunctionSIRPlan] = []
    seen: set[str] = set()

    for function_name, trace in traces:
        if function_name in seen:
            raise ValueError(
                f"duplicate ownership trace for function {function_name!r}"
            )
        seen.add(function_name)
        if graph_functions and function_name not in graph_functions:
            # Functions without tracked ownership legitimately have no graph node.
            has_domain_transfer = any(
                getattr(transfer, "function", None) == function_name
                and str(getattr(transfer, "via", "")) in ("quarantine", "handover")
                for transfer in getattr(domain_graph, "transfers", ()) or ()
            )
            if has_domain_transfer:
                raise ValueError(
                    f"ownership domain graph lacks function nodes for "
                    f"{function_name!r}"
                )
        functions.append(
            OwnershipFunctionSIRPlan(
                function=function_name,
                domain=lower_ownership_domain_graph(
                    domain_graph, function_name
                ),
                shared=lower_shared_ownership_graph(
                    domain_graph, function_name, trace
                ),
            )
        )
    return OwnershipModuleSIRPlan(tuple(functions))


def lower_ownership_module_analysis(
    analysis: Any,
) -> OwnershipModuleSIRPlan:
    """Lower every canonical ownership trace into one per-function SIR plan.

    This is the module-level bridge between OwnershipModuleAnalysis and SIR.
    It composes domain-transfer semantics with shared/ARC semantics without
    performing CFG placement or backend lowering.
    """
    functions: list[OwnershipFunctionSIRPlan] = []
    seen: set[str] = set()
    for function_name, trace in getattr(analysis, "traces", ()) or ():
        if function_name in seen:
            raise ValueError(
                f"duplicate ownership trace for function {function_name!r}"
            )
        seen.add(function_name)
        functions.append(
            OwnershipFunctionSIRPlan(
                function=function_name,
                domain=lower_ownership_domain_trace(trace),
                shared=lower_shared_ownership_trace(trace),
            )
        )
    return OwnershipModuleSIRPlan(tuple(functions))


def _shared_semantic_replacements(
    function: SIRFunction,
    plan: SharedOwnershipSIRPlan,
) -> dict[int, Tuple[SIRInstruction, ...]]:
    markers: list[SharedOwnershipPointInst] = []
    for block in function.blocks:
        for instruction in block.instructions:
            if isinstance(instruction, SharedOwnershipPointInst):
                markers.append(instruction)

    if plan.semantic and not plan.semantic_points:
        if markers:
            raise ValueError(
                f"shared ownership SIR plan for {function.name!r} lacks "
                "source-stable semantic points"
            )
        return {}

    marker_by_point: dict[str, SharedOwnershipPointInst] = {}
    for marker in markers:
        if marker.point_id in marker_by_point:
            raise ValueError(
                f"duplicate shared ownership SIR point {marker.point_id!r}"
            )
        if not marker.point_id.startswith("share@"):
            raise ValueError(
                f"invalid shared ownership point identity {marker.point_id!r}"
            )
        marker_by_point[marker.point_id] = marker

    point_by_id: dict[str, SharedOwnershipSIRSemanticPoint] = {}
    for point in plan.semantic_points:
        if point.point_id in point_by_id:
            raise ValueError(
                f"duplicate shared ownership semantic point {point.point_id!r}"
            )
        if not point.point_id.startswith("share@"):
            raise ValueError(
                f"invalid shared ownership semantic point {point.point_id!r}"
            )
        point_by_id[point.point_id] = point

    if len(marker_by_point) != len(point_by_id):
        raise ValueError(
            f"shared ownership SIR point count mismatch for {function.name!r}: "
            f"{len(marker_by_point)} marker(s) vs {len(point_by_id)} point(s)"
        )

    replacements: dict[int, Tuple[SIRInstruction, ...]] = {}
    for point_id, point in point_by_id.items():
        marker = marker_by_point.get(point_id)
        if marker is None:
            raise ValueError(
                f"shared ownership semantic point {point_id!r} "
                f"missing from SIR CFG for {function.name!r}"
            )
        if marker.source_name != point.source:
            raise ValueError(
                f"shared ownership source mismatch at {point_id!r}"
            )
        if marker.alias_name != point.alias:
            raise ValueError(
                f"shared ownership alias mismatch at {point_id!r}"
            )
        replacements[id(marker)] = point.instructions
    return replacements


def _commit_shared_semantic_replacements(
    function: SIRFunction,
    replacements: dict[int, Tuple[SIRInstruction, ...]],
) -> int:
    inserted = 0
    for block in function.blocks:
        rewritten: list[SIRInstruction] = []
        for instruction in block.instructions:
            replacement = replacements.get(id(instruction))
            if replacement is None:
                rewritten.append(instruction)
            else:
                rewritten.extend(replacement)
                inserted += len(replacement)
        block.instructions = rewritten
    return inserted


def _function_exit_cleanup_segment(
    plan: SharedOwnershipSIRPlan,
) -> SharedOwnershipSIRSegment | None:
    segments = [
        segment for segment in plan.cleanup_segments
        if segment.point_id == "function_exit"
    ]
    if len(segments) > 1:
        raise ValueError("duplicate shared ARC function_exit cleanup segment")
    if not segments:
        return None
    segment = segments[0]
    if segment.via != "scope_exit":
        raise ValueError(
            "shared ARC function_exit cleanup must use scope_exit"
        )
    return segment


def _validate_shared_function_exit_cleanup(
    function: SIRFunction,
    plan: SharedOwnershipSIRPlan,
) -> tuple[ReturnInst, SharedOwnershipSIRSegment] | None:
    segment = _function_exit_cleanup_segment(plan)
    if segment is None:
        return None

    unpointed_returns: list[ReturnInst] = []
    for block in function.blocks:
        for index, instruction in enumerate(block.instructions):
            if not isinstance(instruction, ReturnInst):
                continue
            if instruction.point_id is not None:
                continue
            if index != len(block.instructions) - 1:
                raise ValueError(
                    f"shared ARC function_exit return in {function.name!r} "
                    "is not terminal"
                )
            unpointed_returns.append(instruction)

    if not unpointed_returns and _return_cleanup_segments(plan):
        return None

    if len(unpointed_returns) != 1:
        raise ValueError(
            f"shared ARC function_exit for {function.name!r} requires exactly "
            f"one implicit fallthrough ReturnInst, got {len(unpointed_returns)}"
        )
    return unpointed_returns[0], segment


def _commit_shared_function_exit_cleanup(
    function: SIRFunction,
    placement: tuple[ReturnInst, SharedOwnershipSIRSegment] | None,
) -> int:
    if placement is None:
        return 0
    target, segment = placement
    inserted = 0
    for block in function.blocks:
        rewritten: list[SIRInstruction] = []
        for instruction in block.instructions:
            if instruction is target:
                rewritten.extend(segment.instructions)
                inserted += len(segment.instructions)
            rewritten.append(instruction)
        block.instructions = rewritten
    return inserted


def place_shared_function_exit_cleanup(
    function: SIRFunction,
    plan: SharedOwnershipSIRPlan,
) -> int:
    """Insert normal scope-exit ARC cleanup before one implicit fallthrough return."""
    placement = _validate_shared_function_exit_cleanup(function, plan)
    return _commit_shared_function_exit_cleanup(function, placement)


def _return_cleanup_segments(
    plan: SharedOwnershipSIRPlan,
) -> dict[str, SharedOwnershipSIRSegment]:
    segments: dict[str, SharedOwnershipSIRSegment] = {}
    for segment in plan.cleanup_segments:
        point_id = segment.point_id
        if point_id is None or not point_id.startswith("return@"):
            continue
        if point_id in segments:
            raise ValueError(
                f"duplicate shared ARC return cleanup segment for {point_id!r}"
            )
        segments[point_id] = segment
    return segments


def _loop_control_cleanup_segments(
    plan: SharedOwnershipSIRPlan,
) -> dict[tuple[str, str], SharedOwnershipSIRSegment]:
    segments: dict[tuple[str, str], SharedOwnershipSIRSegment] = {}
    for segment in plan.cleanup_segments:
        point_id = segment.point_id
        if point_id is None:
            continue
        if segment.via not in ("loop_control:break", "loop_control:continue"):
            continue
        control = segment.via.split(":", 1)[1]
        if not point_id.startswith(f"{control}@"):
            raise ValueError(
                f"shared ARC {control} segment has mismatched point {point_id!r}"
            )
        key = (control, point_id)
        if key in segments:
            raise ValueError(
                f"duplicate shared ARC {control} cleanup segment for {point_id!r}"
            )
        segments[key] = segment
    return segments


def _loop_backedge_cleanup_segments(
    plan: SharedOwnershipSIRPlan,
) -> dict[str, SharedOwnershipSIRSegment]:
    segments: dict[str, SharedOwnershipSIRSegment] = {}
    for segment in plan.cleanup_segments:
        point_id = segment.point_id
        if point_id is None or not point_id.startswith(
            ("while_backedge@", "for_backedge@", "loop_backedge@")
        ):
            continue
        if not segment.via.startswith("loop_backedge:"):
            continue
        if point_id in segments:
            raise ValueError(
                f"duplicate shared ARC backedge cleanup segment for {point_id!r}"
            )
        segments[point_id] = segment
    return segments


def _validate_shared_return_cleanup(
    function: SIRFunction,
    plan: SharedOwnershipSIRPlan,
) -> dict[str, SharedOwnershipSIRSegment]:
    segments = _return_cleanup_segments(plan)
    if not segments:
        return segments

    seen = {point_id: 0 for point_id in segments}
    for block in function.blocks:
        for instruction in block.instructions:
            if not isinstance(instruction, ReturnInst):
                continue
            point_id = instruction.point_id
            if point_id in segments:
                seen[point_id] += 1

    duplicates = [point_id for point_id, count in seen.items() if count > 1]
    if duplicates:
        point_id = sorted(duplicates)[0]
        raise ValueError(
            f"shared ARC return cleanup point {point_id!r} "
            "matches multiple ReturnInst nodes"
        )
    missing = [point_id for point_id, count in seen.items() if count == 0]
    if missing:
        raise ValueError(
            "shared ARC return cleanup point(s) missing from SIR CFG: "
            + ", ".join(sorted(missing))
        )
    return segments


def _validate_shared_loop_control_cleanup(
    function: SIRFunction,
    plan: SharedOwnershipSIRPlan,
) -> dict[tuple[str, str], SharedOwnershipSIRSegment]:
    segments = _loop_control_cleanup_segments(plan)
    if not segments:
        return segments

    seen = {key: 0 for key in segments}
    for block in function.blocks:
        for instruction in block.instructions:
            if not isinstance(instruction, BranchInst):
                continue
            control = instruction.control_kind
            point_id = instruction.point_id
            key = (control, point_id)
            if control in ("break", "continue") and key in segments:
                seen[key] += 1

    duplicates = [key for key, count in seen.items() if count > 1]
    if duplicates:
        control, point_id = sorted(duplicates)[0]
        raise ValueError(
            f"shared ARC {control} cleanup point {point_id!r} "
            "matches multiple BranchInst nodes"
        )
    missing = [
        point_id for (control, point_id), count in seen.items() if count == 0
    ]
    if missing:
        raise ValueError(
            "shared ARC loop-control cleanup point(s) missing from SIR CFG: "
            + ", ".join(sorted(missing))
        )
    return segments


def _validate_shared_loop_backedge_cleanup(
    function: SIRFunction,
    plan: SharedOwnershipSIRPlan,
) -> dict[str, SharedOwnershipSIRSegment]:
    segments = _loop_backedge_cleanup_segments(plan)
    if not segments:
        return segments

    seen = {point_id: 0 for point_id in segments}
    for block in function.blocks:
        for instruction in block.instructions:
            if (
                isinstance(instruction, BranchInst)
                and instruction.control_kind == "backedge"
                and instruction.point_id in segments
            ):
                seen[instruction.point_id] += 1

    duplicates = [point_id for point_id, count in seen.items() if count > 1]
    if duplicates:
        point_id = sorted(duplicates)[0]
        raise ValueError(
            f"shared ARC backedge cleanup point {point_id!r} "
            "matches multiple BranchInst nodes"
        )
    missing = [point_id for point_id, count in seen.items() if count == 0]
    if missing:
        raise ValueError(
            "shared ARC backedge cleanup point(s) missing from SIR CFG: "
            + ", ".join(sorted(missing))
        )
    return segments


def _commit_shared_return_cleanup(
    function: SIRFunction,
    segments: dict[str, SharedOwnershipSIRSegment],
) -> int:
    if not segments:
        return 0
    rewrites: list[tuple[Any, list[SIRInstruction]]] = []
    inserted = 0
    for block in function.blocks:
        rewritten: list[SIRInstruction] = []
        for instruction in block.instructions:
            if (
                isinstance(instruction, ReturnInst)
                and instruction.point_id in segments
            ):
                segment = segments[instruction.point_id]
                rewritten.extend(segment.instructions)
                inserted += len(segment.instructions)
            rewritten.append(instruction)
        rewrites.append((block, rewritten))
    for block, rewritten in rewrites:
        block.instructions = rewritten
    return inserted


def place_shared_return_cleanup(
    function: SIRFunction,
    plan: SharedOwnershipSIRPlan,
) -> int:
    """Atomically insert ARC cleanup before source-identified return points."""
    segments = _validate_shared_return_cleanup(function, plan)
    return _commit_shared_return_cleanup(function, segments)


def _commit_shared_loop_control_cleanup(
    function: SIRFunction,
    segments: dict[tuple[str, str], SharedOwnershipSIRSegment],
) -> int:
    if not segments:
        return 0
    rewrites: list[tuple[Any, list[SIRInstruction]]] = []
    inserted = 0
    for block in function.blocks:
        rewritten: list[SIRInstruction] = []
        for instruction in block.instructions:
            if isinstance(instruction, BranchInst):
                key = (instruction.control_kind, instruction.point_id)
                if key in segments:
                    segment = segments[key]
                    rewritten.extend(segment.instructions)
                    inserted += len(segment.instructions)
            rewritten.append(instruction)
        rewrites.append((block, rewritten))
    for block, rewritten in rewrites:
        block.instructions = rewritten
    return inserted


def place_shared_loop_control_cleanup(
    function: SIRFunction,
    plan: SharedOwnershipSIRPlan,
) -> int:
    """Atomically insert ARC cleanup before identified break/continue branches."""
    segments = _validate_shared_loop_control_cleanup(function, plan)
    return _commit_shared_loop_control_cleanup(function, segments)


def _commit_shared_loop_backedge_cleanup(
    function: SIRFunction,
    segments: dict[str, SharedOwnershipSIRSegment],
) -> int:
    if not segments:
        return 0
    rewrites: list[tuple[Any, list[SIRInstruction]]] = []
    inserted = 0
    for block in function.blocks:
        rewritten: list[SIRInstruction] = []
        for instruction in block.instructions:
            if (
                isinstance(instruction, BranchInst)
                and instruction.control_kind == "backedge"
                and instruction.point_id in segments
            ):
                segment = segments[instruction.point_id]
                rewritten.extend(segment.instructions)
                inserted += len(segment.instructions)
            rewritten.append(instruction)
        rewrites.append((block, rewritten))
    for block, rewritten in rewrites:
        block.instructions = rewritten
    return inserted


def place_shared_loop_backedge_cleanup(
    function: SIRFunction,
    plan: SharedOwnershipSIRPlan,
) -> int:
    """Atomically insert ARC cleanup before identified normal loop backedges."""
    segments = _validate_shared_loop_backedge_cleanup(function, plan)
    return _commit_shared_loop_backedge_cleanup(function, segments)

def apply_ownership_module_plan(
    module: SIRModule,
    plan: OwnershipModuleSIRPlan,
) -> OwnershipModulePlacement:
    """Apply all currently placeable ownership semantics atomically.

    Domain-transfer markers and all supported ARC cleanup points are preflighted
    across the entire module before the first CFG mutation. Shared semantic
    ShareInst/RetainInst operations remain in the plan until source-stable
    placement points exist for them.
    """
    functions: dict[str, SIRFunction] = {}
    for function in module.functions:
        if function.name in functions:
            raise ValueError(
                f"duplicate SIR function {function.name!r} during ownership placement"
            )
        functions[function.name] = function

    preflight: list[
        tuple[
            SIRFunction,
            dict[int, OwnershipDomainTransferInst],
            dict[int, Tuple[SIRInstruction, ...]],
            tuple[ReturnInst, SharedOwnershipSIRSegment] | None,
            dict[str, SharedOwnershipSIRSegment],
            dict[tuple[str, str], SharedOwnershipSIRSegment],
            dict[str, SharedOwnershipSIRSegment],
        ]
    ] = []
    seen_plans: set[str] = set()
    for function_plan in plan.functions:
        name = function_plan.function
        if name in seen_plans:
            raise ValueError(
                f"duplicate ownership SIR plan for function {name!r}"
            )
        seen_plans.add(name)
        function = functions.get(name)
        if function is None:
            raise ValueError(
                f"ownership SIR plan references missing function {name!r}"
            )

        replacements = _ownership_domain_transfer_replacements(
            function, function_plan.domain
        )
        shared_replacements = _shared_semantic_replacements(
            function, function_plan.shared
        )
        function_exit = _validate_shared_function_exit_cleanup(
            function, function_plan.shared
        )
        return_segments = _validate_shared_return_cleanup(
            function, function_plan.shared
        )
        control_segments = _validate_shared_loop_control_cleanup(
            function, function_plan.shared
        )
        backedge_segments = _validate_shared_loop_backedge_cleanup(
            function, function_plan.shared
        )
        preflight.append(
            (
                function,
                replacements,
                shared_replacements,
                function_exit,
                return_segments,
                control_segments,
                backedge_segments,
            )
        )

    inserted_domain = 0
    inserted_shared_semantic = 0
    inserted_function_exit = 0
    inserted_return = 0
    inserted_control = 0
    inserted_backedge = 0
    for (
        function,
        replacements,
        shared_replacements,
        function_exit,
        return_segments,
        control_segments,
        backedge_segments,
    ) in preflight:
        inserted_domain += _commit_ownership_domain_replacements(
            function, replacements
        )
        inserted_shared_semantic += _commit_shared_semantic_replacements(
            function, shared_replacements
        )
        inserted_function_exit += _commit_shared_function_exit_cleanup(
            function, function_exit
        )
        inserted_return += _commit_shared_return_cleanup(
            function, return_segments
        )
        inserted_control += _commit_shared_loop_control_cleanup(
            function, control_segments
        )
        inserted_backedge += _commit_shared_loop_backedge_cleanup(
            function, backedge_segments
        )

    return OwnershipModulePlacement(
        plan,
        inserted_domain,
        inserted_shared_semantic,
        inserted_function_exit,
        inserted_return,
        inserted_control,
        inserted_backedge,
    )


def generate_checked_ownership_sir(
    checked_module: Any,
) -> CheckedOwnershipSIR:
    """Generate SIR from one checked frontend module and apply ownership semantics.

    The frontend remains independent from SIR: this composition boundary lives
    entirely in the SIR package. The checked object must expose parsed_module
    and ownership_sir, matching the public checked-module contract.
    """
    parsed_module = getattr(checked_module, "parsed_module", None)
    ownership_plan = getattr(checked_module, "ownership_sir", None)
    if parsed_module is None:
        raise ValueError("checked ownership SIR generation lacks parsed_module")
    if ownership_plan is None:
        raise ValueError("checked ownership SIR generation lacks ownership_sir")

    from .generator import SIRGenerator

    generator = SIRGenerator(
        module_name=getattr(parsed_module, "name", "main")
    )
    module = generator.generate_from_ast(parsed_module)
    placement = apply_ownership_module_plan(module, ownership_plan)
    return CheckedOwnershipSIR(module, placement)


def apply_shared_ownership_trace(
    function: SIRFunction,
    trace: Any,
) -> SharedOwnershipSIRPlacement:
    """Lower one canonical ownership trace and place supported CFG cleanups.

    All currently supported placement kinds are preflighted before mutation.
    The complete plan is returned together with committed instruction counts.
    """
    plan = lower_shared_ownership_trace(trace)

    # Preflight every supported placement before the first CFG mutation so
    # a later control/backedge mismatch cannot leave earlier return cleanup
    # partially committed.
    function_exit = _validate_shared_function_exit_cleanup(function, plan)
    _validate_shared_return_cleanup(function, plan)
    _validate_shared_loop_control_cleanup(function, plan)
    _validate_shared_loop_backedge_cleanup(function, plan)

    inserted_function_exit = _commit_shared_function_exit_cleanup(
        function, function_exit
    )
    inserted_return = place_shared_return_cleanup(function, plan)
    inserted_control = place_shared_loop_control_cleanup(function, plan)
    inserted_backedge = place_shared_loop_backedge_cleanup(function, plan)
    return SharedOwnershipSIRPlacement(
        plan,
        inserted_return,
        inserted_control,
        inserted_backedge,
        inserted_function_exit,
    )

__all__ = [
    "OwnershipDomainSIRPlan",
    "lower_ownership_domain_graph",
    "lower_ownership_domain_trace",
    "OwnershipDomainSIRPlacement",
    "place_ownership_domain_transfers",
    "OwnershipModuleSIRPlacement",
    "apply_ownership_module_domain_transfers",
    "OwnershipModulePlacement",
    "apply_ownership_module_plan",
    "CheckedOwnershipSIR",
    "generate_checked_ownership_sir",
    "OwnershipFunctionSIRPlan",
    "OwnershipModuleSIRPlan",
    "lower_ownership_module_semantics",
    "lower_ownership_module_analysis",
    "SharedOwnershipSIRSegment",
    "SharedOwnershipSIRSemanticPoint",
    "SharedOwnershipSIRPlan",
    "SharedOwnershipSIRPlacement",
    "lower_shared_ownership_trace",
    "place_shared_function_exit_cleanup",
    "place_shared_return_cleanup",
    "place_shared_loop_control_cleanup",
    "place_shared_loop_backedge_cleanup",
    "apply_shared_ownership_trace",
]
