"""Path-sensitive reaching-epoch certification for REGION symbolic arenas.

``region_arena`` freezes symbolic owner slots, epochs and identity-preserving
constraints, but intentionally leaves ``pre`` epochs disconnected from the
producer that reaches them.  This layer resolves that missing local dataflow
for CFG points that can be proven without crossing a loop backedge or an
activation-specific callee entry.

The pass is deliberately backend-neutral: it does not allocate an arena and it
does not assign physical addresses.  It proves which declaration-origin or
previous ``post`` epoch feeds a ``pre`` epoch.  Ambiguous branch joins, cyclic
points and activation-sensitive callee slots are reported explicitly instead of
being guessed.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .canonical_sir import load_canonical_sir
from .region_arena import RegionArenaEpoch, RegionArenaLifetimeGraph
from .region_cfg import _reachable, _successors
from .region_interprocedural import RegionInterproceduralLifetimePlan
from .typed_ast import Phase1SemanticError


class RegionArenaFlowError(Phase1SemanticError):
    """Raised when REGION arena reaching-epoch facts are structurally invalid."""


@dataclass(frozen=True)
class RegionArenaFlowResolution:
    function: str
    binding: str
    pre_epoch_id: str
    producer_epoch_id: str


@dataclass(frozen=True)
class RegionArenaFlowUnresolved:
    function: str
    binding: str
    pre_epoch_id: str
    reason: str


@dataclass(frozen=True)
class RegionArenaFlowCertificate:
    resolutions: tuple[RegionArenaFlowResolution, ...]
    unresolved: tuple[RegionArenaFlowUnresolved, ...]

    @property
    def complete(self) -> bool:
        return not self.unresolved

    def resolution_for(self, pre_epoch_id: str) -> RegionArenaFlowResolution:
        matches = tuple(
            item for item in self.resolutions if item.pre_epoch_id == pre_epoch_id
        )
        if len(matches) != 1:
            raise RegionArenaFlowError(
                f"REGION arena flow requires exactly one resolution for {pre_epoch_id!r}"
            )
        return matches[0]


@dataclass(frozen=True)
class _PointLocation:
    block: str
    instruction_index: int
    iteration_id: str | None


@dataclass(frozen=True)
class _Producer:
    epoch: RegionArenaEpoch
    location: _PointLocation | None


def _required_text(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RegionArenaFlowError(f"{label} requires a non-empty identity")
    return value


def _unwrap_module(value: object):
    sir = load_canonical_sir()
    module = getattr(value, "module", value)
    if not isinstance(module, sir.SIRModule):
        raise RegionArenaFlowError(
            "REGION arena flow requires canonical SIRModule or CheckedOwnershipSIR"
        )
    return module


def _point_location(
    lifetime: RegionInterproceduralLifetimePlan,
    *,
    function: str,
    point_id: str,
) -> _PointLocation:
    function_plan = lifetime.function(function)
    call_matches = tuple(
        item
        for item in lifetime.call_cfg.points
        if item.function == function and item.point_id == point_id
    )
    local_matches = tuple(
        item
        for item in function_plan.lifetime_cfg.locations
        if item.point_id == point_id
    )
    matches = len(call_matches) + len(local_matches)
    if matches != 1:
        raise RegionArenaFlowError(
            f"REGION arena point {function}::{point_id} requires exactly one CFG location"
        )
    if call_matches:
        item = call_matches[0]
        return _PointLocation(
            block=_required_text(item.block, label="REGION arena call block"),
            instruction_index=item.instruction_index,
            iteration_id=item.iteration_id,
        )
    item = local_matches[0]
    return _PointLocation(
        block=_required_text(item.block, label="REGION arena lifetime block"),
        instruction_index=item.instruction_index,
        iteration_id=item.iteration_id,
    )


def _strictly_before(
    first: _Producer,
    second_location: _PointLocation,
    successors: dict[str, tuple[str, ...]],
) -> bool | None:
    # Declaration origins dominate the function-local static flow.  Callee
    # activations are filtered before this relation is used.
    if first.location is None:
        return True
    first_location = first.location
    if first_location.block == second_location.block:
        # ``post`` occurs after the ownership-taking instruction.  A ``pre`` at
        # the same instruction therefore cannot be fed by that post.
        return first_location.instruction_index < second_location.instruction_index
    forward = _reachable(successors, first_location.block, second_location.block)
    reverse = _reachable(successors, second_location.block, first_location.block)
    if forward and reverse:
        return None
    return forward


def _producer_before_producer(
    first: _Producer,
    second: _Producer,
    successors: dict[str, tuple[str, ...]],
) -> bool | None:
    if first.location is None:
        return second.location is not None
    if second.location is None:
        return False
    if first.location.block == second.location.block:
        return first.location.instruction_index < second.location.instruction_index
    forward = _reachable(successors, first.location.block, second.location.block)
    reverse = _reachable(successors, second.location.block, first.location.block)
    if forward and reverse:
        return None
    return forward


def certify_region_arena_flow(
    lifetime: RegionInterproceduralLifetimePlan,
    arena: RegionArenaLifetimeGraph,
    sir_module: object,
) -> RegionArenaFlowCertificate:
    """Resolve unambiguous function-local producers for symbolic REGION ``pre`` epochs."""
    if not isinstance(lifetime, RegionInterproceduralLifetimePlan):
        raise RegionArenaFlowError(
            "REGION arena flow requires certified interprocedural lifetime facts"
        )
    if not isinstance(arena, RegionArenaLifetimeGraph):
        raise RegionArenaFlowError(
            "REGION arena flow requires a RegionArenaLifetimeGraph"
        )

    module = _unwrap_module(sir_module)
    functions = {
        _required_text(getattr(item, "name", None), label="REGION arena SIR function"): item
        for item in tuple(getattr(module, "functions", ()) or ())
    }
    if len(functions) != len(tuple(getattr(module, "functions", ()) or ())):
        raise RegionArenaFlowError("REGION arena flow contains duplicate SIR functions")

    resolutions: list[RegionArenaFlowResolution] = []
    unresolved: list[RegionArenaFlowUnresolved] = []

    for slot in arena.slots:
        function = functions.get(slot.function)
        if function is None:
            raise RegionArenaFlowError(
                f"REGION arena flow requires SIR function {slot.function!r}"
            )
        successors = _successors(function)
        epochs = arena.epochs_for(slot.function, slot.binding)
        pre_epochs = tuple(item for item in epochs if item.phase == "pre")
        if not pre_epochs:
            continue

        activation_epochs = tuple(
            item for item in epochs if item.phase == "call_entry"
        )
        producers: list[_Producer] = []
        for epoch in epochs:
            if epoch.phase == "origin":
                producers.append(_Producer(epoch=epoch, location=None))
            elif epoch.phase == "post":
                producers.append(
                    _Producer(
                        epoch=epoch,
                        location=_point_location(
                            lifetime,
                            function=epoch.function,
                            point_id=epoch.point_id,
                        ),
                    )
                )

        for pre in pre_epochs:
            pre_location = _point_location(
                lifetime,
                function=pre.function,
                point_id=pre.point_id,
            )
            if pre_location.iteration_id is not None:
                unresolved.append(
                    RegionArenaFlowUnresolved(
                        function=pre.function,
                        binding=pre.binding,
                        pre_epoch_id=pre.epoch_id,
                        reason="cyclic",
                    )
                )
                continue
            if activation_epochs:
                unresolved.append(
                    RegionArenaFlowUnresolved(
                        function=pre.function,
                        binding=pre.binding,
                        pre_epoch_id=pre.epoch_id,
                        reason="activation_sensitive",
                    )
                )
                continue

            reaching: list[_Producer] = []
            ambiguous_reachability = False
            for producer in producers:
                relation = _strictly_before(producer, pre_location, successors)
                if relation is None:
                    ambiguous_reachability = True
                    continue
                if relation:
                    reaching.append(producer)

            if ambiguous_reachability and not reaching:
                unresolved.append(
                    RegionArenaFlowUnresolved(
                        function=pre.function,
                        binding=pre.binding,
                        pre_epoch_id=pre.epoch_id,
                        reason="cyclic_reachability",
                    )
                )
                continue

            maximal: list[_Producer] = []
            for candidate in reaching:
                shadowed = False
                for other in reaching:
                    if other is candidate:
                        continue
                    relation = _producer_before_producer(
                        candidate,
                        other,
                        successors,
                    )
                    if relation is True:
                        other_reaches_pre = _strictly_before(
                            other,
                            pre_location,
                            successors,
                        )
                        if other_reaches_pre is True:
                            shadowed = True
                            break
                if not shadowed:
                    maximal.append(candidate)

            if len(maximal) == 1:
                producer = maximal[0].epoch
                if producer.type != pre.type:
                    raise RegionArenaFlowError(
                        f"REGION arena flow type mismatch at {pre.epoch_id!r}"
                    )
                resolutions.append(
                    RegionArenaFlowResolution(
                        function=pre.function,
                        binding=pre.binding,
                        pre_epoch_id=pre.epoch_id,
                        producer_epoch_id=producer.epoch_id,
                    )
                )
                continue

            reason = "no_reaching_producer" if not maximal else "ambiguous_merge"
            unresolved.append(
                RegionArenaFlowUnresolved(
                    function=pre.function,
                    binding=pre.binding,
                    pre_epoch_id=pre.epoch_id,
                    reason=reason,
                )
            )

    resolved_ids = {item.pre_epoch_id for item in resolutions}
    unresolved_ids = {item.pre_epoch_id for item in unresolved}
    if resolved_ids & unresolved_ids:
        raise RegionArenaFlowError(
            "REGION arena flow resolved and unresolved the same pre epoch"
        )
    all_pre_ids = {
        epoch.epoch_id for epoch in arena.epochs if epoch.phase == "pre"
    }
    if resolved_ids | unresolved_ids != all_pre_ids:
        raise RegionArenaFlowError(
            "REGION arena flow failed to classify every pre epoch"
        )

    return RegionArenaFlowCertificate(
        resolutions=tuple(resolutions),
        unresolved=tuple(unresolved),
    )


__all__ = [
    "RegionArenaFlowError",
    "RegionArenaFlowResolution",
    "RegionArenaFlowUnresolved",
    "RegionArenaFlowCertificate",
    "certify_region_arena_flow",
]
