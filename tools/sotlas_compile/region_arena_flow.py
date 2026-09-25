"""Path-sensitive reaching-epoch certification for REGION symbolic arenas.

``region_arena`` freezes symbolic owner slots, epochs and identity-preserving
constraints, but intentionally leaves ``pre`` epochs disconnected from the
producer that reaches them. This layer resolves that missing local dataflow from
canonical SIR CFG order.

Acyclic points use ordinary reachability. Cyclic points reuse the canonical
iteration identity already certified for REGION ownership operations: exactly
the naming backedge is cut before within-iteration reachability is computed.
Only a previous ``post`` proven to occur earlier in that same iteration may feed
a cyclic ``pre`` directly. When a parameter-origin feeds the first iteration and
exactly one later ``post`` feeds subsequent iterations, the pass records an
explicit loop-carried recurrence rather than leaving the relation unresolved.

The pass is deliberately backend-neutral: it does not allocate an arena and it
does not assign physical addresses.
"""
from __future__ import annotations

from dataclasses import dataclass

from .canonical_sir import load_canonical_sir
from .region_arena import RegionArenaEpoch, RegionArenaLifetimeGraph
from .region_cfg import _reachable, _successors
from .region_interprocedural import RegionInterproceduralLifetimePlan
from .region_iteration_order import _cut_iteration_backedge
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
class RegionArenaFlowRecurrence:
    """Certified loop-carried arena identity for one cyclic ``pre`` epoch."""

    function: str
    binding: str
    pre_epoch_id: str
    initial_epoch_id: str
    carried_epoch_id: str
    iteration_id: str


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
    recurrences: tuple[RegionArenaFlowRecurrence, ...] = ()

    @property
    def complete(self) -> bool:
        # Recurrences are certified flow, not unresolved holes.
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

    def recurrence_for(self, pre_epoch_id: str) -> RegionArenaFlowRecurrence:
        matches = tuple(
            item for item in self.recurrences if item.pre_epoch_id == pre_epoch_id
        )
        if len(matches) != 1:
            raise RegionArenaFlowError(
                f"REGION arena flow requires exactly one recurrence for {pre_epoch_id!r}"
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


def _location_before(
    first: _PointLocation,
    second: _PointLocation,
    successors: dict[str, tuple[str, ...]],
) -> bool | None:
    if first.block == second.block:
        return first.instruction_index < second.instruction_index
    forward = _reachable(successors, first.block, second.block)
    reverse = _reachable(successors, second.block, first.block)
    if forward and reverse:
        return None
    return forward


def _strictly_before(
    first: _Producer,
    second_location: _PointLocation,
    successors: dict[str, tuple[str, ...]],
) -> bool | None:
    if first.location is None:
        return True
    return _location_before(first.location, second_location, successors)


def _producer_before_producer(
    first: _Producer,
    second: _Producer,
    successors: dict[str, tuple[str, ...]],
) -> bool | None:
    if first.location is None:
        return second.location is not None
    if second.location is None:
        return False
    return _location_before(first.location, second.location, successors)


def _maximal_reaching(
    producers: tuple[_Producer, ...] | list[_Producer],
    target: _PointLocation,
    successors: dict[str, tuple[str, ...]],
) -> tuple[tuple[_Producer, ...], bool]:
    reaching: list[_Producer] = []
    ambiguous_reachability = False
    for producer in producers:
        relation = _strictly_before(producer, target, successors)
        if relation is None:
            ambiguous_reachability = True
            continue
        if relation:
            reaching.append(producer)

    maximal: list[_Producer] = []
    for candidate in reaching:
        shadowed = False
        for other in reaching:
            if other is candidate:
                continue
            relation = _producer_before_producer(candidate, other, successors)
            if relation is True:
                other_reaches_target = _strictly_before(other, target, successors)
                if other_reaches_target is True:
                    shadowed = True
                    break
        if not shadowed:
            maximal.append(candidate)
    return tuple(maximal), ambiguous_reachability


def _append_resolution(
    resolutions: list[RegionArenaFlowResolution],
    pre: RegionArenaEpoch,
    producer: RegionArenaEpoch,
) -> None:
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


def _append_unresolved(
    unresolved: list[RegionArenaFlowUnresolved],
    pre: RegionArenaEpoch,
    reason: str,
) -> None:
    unresolved.append(
        RegionArenaFlowUnresolved(
            function=pre.function,
            binding=pre.binding,
            pre_epoch_id=pre.epoch_id,
            reason=reason,
        )
    )


def _parameter_origin(producers: list[_Producer]) -> tuple[_Producer, ...]:
    return tuple(
        item
        for item in producers
        if item.location is None
        and item.epoch.phase == "origin"
        and item.epoch.point_id.startswith("param_origin@")
    )


def _certify_cyclic_pre(
    *,
    function: object,
    successors: dict[str, tuple[str, ...]],
    producers: list[_Producer],
    pre: RegionArenaEpoch,
    pre_location: _PointLocation,
    resolutions: list[RegionArenaFlowResolution],
    recurrences: list[RegionArenaFlowRecurrence],
    unresolved: list[RegionArenaFlowUnresolved],
) -> None:
    iteration_id = pre_location.iteration_id
    if iteration_id is None:
        raise RegionArenaFlowError("cyclic REGION arena point lacks iteration identity")

    cut = _cut_iteration_backedge(function, successors, iteration_id)
    iteration_posts = tuple(
        item
        for item in producers
        if item.location is not None
        and item.location.iteration_id == iteration_id
    )
    maximal, ambiguous = _maximal_reaching(iteration_posts, pre_location, cut)
    if len(maximal) == 1:
        _append_resolution(resolutions, pre, maximal[0].epoch)
        return
    if len(maximal) > 1:
        _append_unresolved(unresolved, pre, "ambiguous_merge")
        return
    if ambiguous:
        _append_unresolved(unresolved, pre, "cyclic_reachability")
        return

    later_posts = tuple(
        item
        for item in iteration_posts
        if item.location is not None
        and _location_before(pre_location, item.location, cut) is True
    )
    if later_posts:
        origins = _parameter_origin(producers)
        if len(later_posts) == 1 and len(origins) == 1:
            initial = origins[0].epoch
            carried = later_posts[0].epoch
            if initial.type != pre.type or carried.type != pre.type:
                raise RegionArenaFlowError(
                    f"REGION arena recurrence type mismatch at {pre.epoch_id!r}"
                )
            recurrences.append(
                RegionArenaFlowRecurrence(
                    function=pre.function,
                    binding=pre.binding,
                    pre_epoch_id=pre.epoch_id,
                    initial_epoch_id=initial.epoch_id,
                    carried_epoch_id=carried.epoch_id,
                    iteration_id=iteration_id,
                )
            )
            return
        reason = (
            "ambiguous_loop_carry"
            if len(later_posts) != 1
            else "loop_carry_without_parameter_origin"
        )
        _append_unresolved(unresolved, pre, reason)
        return

    _append_unresolved(unresolved, pre, "cyclic_no_local_producer")


def certify_region_arena_flow(
    lifetime: RegionInterproceduralLifetimePlan,
    arena: RegionArenaLifetimeGraph,
    sir_module: object,
) -> RegionArenaFlowCertificate:
    """Resolve/certify function-local producers for symbolic REGION ``pre`` epochs."""
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
    recurrences: list[RegionArenaFlowRecurrence] = []
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

        activation_epochs = tuple(item for item in epochs if item.phase == "call_entry")
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
            if activation_epochs:
                _append_unresolved(unresolved, pre, "activation_sensitive")
                continue
            if pre_location.iteration_id is not None:
                _certify_cyclic_pre(
                    function=function,
                    successors=successors,
                    producers=producers,
                    pre=pre,
                    pre_location=pre_location,
                    resolutions=resolutions,
                    recurrences=recurrences,
                    unresolved=unresolved,
                )
                continue

            maximal, ambiguous_reachability = _maximal_reaching(
                producers,
                pre_location,
                successors,
            )
            if len(maximal) == 1:
                _append_resolution(resolutions, pre, maximal[0].epoch)
                continue
            if len(maximal) > 1:
                _append_unresolved(unresolved, pre, "ambiguous_merge")
                continue
            if ambiguous_reachability:
                _append_unresolved(unresolved, pre, "cyclic_reachability")
                continue
            _append_unresolved(unresolved, pre, "no_reaching_producer")

    resolved_ids = {item.pre_epoch_id for item in resolutions}
    recurrence_ids = {item.pre_epoch_id for item in recurrences}
    unresolved_ids = {item.pre_epoch_id for item in unresolved}
    if resolved_ids & recurrence_ids or resolved_ids & unresolved_ids or recurrence_ids & unresolved_ids:
        raise RegionArenaFlowError(
            "REGION arena flow classified the same pre epoch more than once"
        )
    all_pre_ids = {epoch.epoch_id for epoch in arena.epochs if epoch.phase == "pre"}
    if resolved_ids | recurrence_ids | unresolved_ids != all_pre_ids:
        raise RegionArenaFlowError(
            "REGION arena flow failed to classify every pre epoch"
        )

    return RegionArenaFlowCertificate(
        resolutions=tuple(resolutions),
        unresolved=tuple(unresolved),
        recurrences=tuple(recurrences),
    )


__all__ = [
    "RegionArenaFlowError",
    "RegionArenaFlowResolution",
    "RegionArenaFlowRecurrence",
    "RegionArenaFlowUnresolved",
    "RegionArenaFlowCertificate",
    "certify_region_arena_flow",
]
