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
    ReturnInst,
    BranchInst,
    ShareInst,
    RetainInst,
    ReleaseInst,
    DestroyInst,
    DeferUseInst,
)


@dataclass(frozen=True)
class SharedOwnershipSIRSegment:
    via: str
    instructions: Tuple[SIRInstruction, ...]
    point_id: str | None = None


@dataclass(frozen=True)
class SharedOwnershipSIRPlan:
    semantic: Tuple[SIRInstruction, ...]
    cleanup_segments: Tuple[SharedOwnershipSIRSegment, ...]


@dataclass(frozen=True)
class SharedOwnershipSIRPlacement:
    plan: SharedOwnershipSIRPlan
    inserted_return_instructions: int
    inserted_loop_control_instructions: int = 0
    inserted_backedge_instructions: int = 0


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


def lower_shared_ownership_trace(trace: Any) -> SharedOwnershipSIRPlan:
    """Lower canonical shared ownership facts without claiming CFG placement."""
    types = _share_types(trace, _type_map(trace))
    semantic: list[SIRInstruction] = []

    for event in getattr(trace, "events", ()) or ():
        kind = getattr(event, "kind", None)
        via = str(getattr(event, "via", ""))
        if kind == "domain_transition" and via.startswith("share:"):
            source = getattr(event, "name")
            alias = via.split(":", 1)[1]
            source_value = _value(source, types)
            semantic.append(ShareInst(source_value))
            if alias and alias not in types:
                types[alias] = source_value.type_name
            continue
        if kind == "retain" and via.startswith("share:"):
            owner = getattr(event, "name")
            account = via.split(":", 1)[1]
            if owner not in types and account in types:
                types[owner] = types[account]
            semantic.append(RetainInst(_value(owner, types)))

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

    control_plan = getattr(trace, "shared_loop_control_exit", None)
    actions = tuple(getattr(control_plan, "actions", ()) or ())
    if actions:
        grouped_actions: dict[tuple[str, str | None], list[SIRInstruction]] = {}
        for action in actions:
            kind = getattr(action, "kind")
            owner = getattr(action, "owner", None)
            via = str(getattr(action, "via", "loop_control"))
            if owner is None:
                raise ValueError(
                    f"shared ownership SIR {kind} action lacks owner"
                )
            if kind == "defer":
                defer_point_id = getattr(action, "defer_point_id", None)
                if defer_point_id is None:
                    raise ValueError(
                        "shared loop-control defer lacks source identity"
                    )
                if not str(defer_point_id).startswith("defer@"):
                    raise ValueError(
                        f"shared loop-control defer has invalid source identity "
                        f"{defer_point_id!r}"
                    )
                payload_kind = via.split(":", 1)[1] if ":" in via else ""
                if payload_kind != "expression":
                    raise ValueError(
                        "shared loop-control defer payload lowering is not "
                        f"implemented in SIR for {payload_kind or 'unknown'} "
                        f"payload at {defer_point_id}"
                    )
                inst = DeferUseInst(_value(owner, types), str(defer_point_id))
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

    return SharedOwnershipSIRPlan(tuple(semantic), tuple(segments))


def place_shared_return_cleanup(
    function: SIRFunction,
    plan: SharedOwnershipSIRPlan,
) -> int:
    """Insert ARC cleanup immediately before source-identified return points.

    Only segments with point IDs starting with return@ are placed here.
    Other control-flow cleanup remains untouched for dedicated placement passes.
    The function fails closed if a return segment cannot be matched exactly once.
    """
    return_segments = {
        segment.point_id: segment
        for segment in plan.cleanup_segments
        if segment.point_id is not None
        and segment.point_id.startswith("return@")
    }
    if not return_segments:
        return 0

    seen: dict[str, int] = {point_id: 0 for point_id in return_segments}
    inserted = 0

    for block in function.blocks:
        rewritten: list[SIRInstruction] = []
        for instruction in block.instructions:
            if isinstance(instruction, ReturnInst):
                point_id = instruction.point_id
                if point_id in return_segments:
                    seen[point_id] += 1
                    if seen[point_id] > 1:
                        raise ValueError(
                            f"shared ARC return cleanup point {point_id!r} "
                            "matches multiple ReturnInst nodes"
                        )
                    segment = return_segments[point_id]
                    rewritten.extend(segment.instructions)
                    inserted += len(segment.instructions)
            rewritten.append(instruction)
        block.instructions = rewritten

    missing = [point_id for point_id, count in seen.items() if count == 0]
    if missing:
        raise ValueError(
            "shared ARC return cleanup point(s) missing from SIR CFG: "
            + ", ".join(sorted(missing))
        )

    return inserted


def place_shared_loop_control_cleanup(
    function: SIRFunction,
    plan: SharedOwnershipSIRPlan,
) -> int:
    """Insert ARC cleanup before source-identified break/continue branches."""
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

    if not segments:
        return 0

    seen = {key: 0 for key in segments}
    inserted = 0
    for block in function.blocks:
        rewritten: list[SIRInstruction] = []
        for instruction in block.instructions:
            if isinstance(instruction, BranchInst):
                control = instruction.control_kind
                point_id = instruction.point_id
                key = (control, point_id)
                if control in ("break", "continue") and key in segments:
                    seen[key] += 1
                    if seen[key] > 1:
                        raise ValueError(
                            f"shared ARC {control} cleanup point {point_id!r} "
                            "matches multiple BranchInst nodes"
                        )
                    segment = segments[key]
                    rewritten.extend(segment.instructions)
                    inserted += len(segment.instructions)
            rewritten.append(instruction)
        block.instructions = rewritten

    missing = [point_id for (control, point_id), count in seen.items() if count == 0]
    if missing:
        raise ValueError(
            "shared ARC loop-control cleanup point(s) missing from SIR CFG: "
            + ", ".join(sorted(missing))
        )
    return inserted


def place_shared_loop_backedge_cleanup(
    function: SIRFunction,
    plan: SharedOwnershipSIRPlan,
) -> int:
    """Insert ARC cleanup before source-identified normal loop backedges."""
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

    if not segments:
        return 0

    seen = {point_id: 0 for point_id in segments}
    inserted = 0
    for block in function.blocks:
        rewritten: list[SIRInstruction] = []
        for instruction in block.instructions:
            if (
                isinstance(instruction, BranchInst)
                and instruction.control_kind == "backedge"
                and instruction.point_id in segments
            ):
                point_id = instruction.point_id
                seen[point_id] += 1
                if seen[point_id] > 1:
                    raise ValueError(
                        f"shared ARC backedge cleanup point {point_id!r} "
                        "matches multiple BranchInst nodes"
                    )
                segment = segments[point_id]
                rewritten.extend(segment.instructions)
                inserted += len(segment.instructions)
            rewritten.append(instruction)
        block.instructions = rewritten

    missing = [point_id for point_id, count in seen.items() if count == 0]
    if missing:
        raise ValueError(
            "shared ARC backedge cleanup point(s) missing from SIR CFG: "
            + ", ".join(sorted(missing))
        )
    return inserted


def apply_shared_ownership_trace(
    function: SIRFunction,
    trace: Any,
) -> SharedOwnershipSIRPlacement:
    """Lower one canonical ownership trace and place supported CFG cleanups.

    Return cleanup is currently the only placement stage. The complete plan is
    still returned so callers can inspect unplaced loop/backedge/control segments.
    """
    plan = lower_shared_ownership_trace(trace)
    inserted_return = place_shared_return_cleanup(function, plan)
    inserted_control = place_shared_loop_control_cleanup(function, plan)
    inserted_backedge = place_shared_loop_backedge_cleanup(function, plan)
    return SharedOwnershipSIRPlacement(
        plan,
        inserted_return,
        inserted_control,
        inserted_backedge,
    )

__all__ = [
    "SharedOwnershipSIRSegment",
    "SharedOwnershipSIRPlan",
    "SharedOwnershipSIRPlacement",
    "lower_shared_ownership_trace",
    "place_shared_return_cleanup",
    "place_shared_loop_control_cleanup",
    "place_shared_loop_backedge_cleanup",
    "apply_shared_ownership_trace",
]
