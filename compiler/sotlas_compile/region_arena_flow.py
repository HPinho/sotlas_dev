"""Path-sensitive reaching-epoch certification for REGION symbolic arenas.

``region_arena`` freezes symbolic owner slots, epochs and identity-preserving
constraints, but intentionally leaves ``pre`` epochs disconnected from the
producer that reaches them. This layer resolves that missing local dataflow from
canonical SIR CFG order.

Acyclic points use ordinary reachability. Callee slots preserve activation
sensitivity explicitly: when no local ``post`` supersedes function entry, a
``pre`` is fed by the certified set of activation-scoped ``call_entry`` epochs
rather than by a fake generic origin. Cyclic points reuse the canonical iteration
identity: exactly the naming backedge is cut before within-iteration reachability
is computed. Parameter-origin + one later ``post`` becomes an explicit
loop-carried recurrence.

The pass is backend-neutral: it does not allocate an arena or assign addresses.
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
    function: str
    binding: str
    pre_epoch_id: str
    initial_epoch_id: str
    carried_epoch_id: str
    iteration_id: str


@dataclass(frozen=True)
class RegionArenaFlowActivation:
    """Activation-scoped entry alternatives that may feed one callee ``pre``."""

    function: str
    binding: str
    pre_epoch_id: str
    input_epoch_ids: tuple[str, ...]


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
    activations: tuple[RegionArenaFlowActivation, ...] = ()

    @property
    def complete(self) -> bool:
        return not self.unresolved

    def resolution_for(self, pre_epoch_id: str) -> RegionArenaFlowResolution:
        matches = tuple(item for item in self.resolutions if item.pre_epoch_id == pre_epoch_id)
        if len(matches) != 1:
            raise RegionArenaFlowError(
                f"REGION arena flow requires exactly one resolution for {pre_epoch_id!r}"
            )
        return matches[0]

    def recurrence_for(self, pre_epoch_id: str) -> RegionArenaFlowRecurrence:
        matches = tuple(item for item in self.recurrences if item.pre_epoch_id == pre_epoch_id)
        if len(matches) != 1:
            raise RegionArenaFlowError(
                f"REGION arena flow requires exactly one recurrence for {pre_epoch_id!r}"
            )
        return matches[0]

    def activation_for(self, pre_epoch_id: str) -> RegionArenaFlowActivation:
        matches = tuple(item for item in self.activations if item.pre_epoch_id == pre_epoch_id)
        if len(matches) != 1:
            raise RegionArenaFlowError(
                f"REGION arena flow requires exactly one activation set for {pre_epoch_id!r}"
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


def _point_location(lifetime, *, function: str, point_id: str) -> _PointLocation:
    function_plan = lifetime.function(function)
    call_matches = tuple(
        item for item in lifetime.call_cfg.points
        if item.function == function and item.point_id == point_id
    )
    local_matches = tuple(
        item for item in function_plan.lifetime_cfg.locations if item.point_id == point_id
    )
    if len(call_matches) + len(local_matches) != 1:
        raise RegionArenaFlowError(
            f"REGION arena point {function}::{point_id} requires exactly one CFG location"
        )
    item = call_matches[0] if call_matches else local_matches[0]
    return _PointLocation(
        block=_required_text(item.block, label="REGION arena CFG block"),
        instruction_index=item.instruction_index,
        iteration_id=item.iteration_id,
    )


def _location_before(first, second, successors):
    if first.block == second.block:
        return first.instruction_index < second.instruction_index
    forward = _reachable(successors, first.block, second.block)
    reverse = _reachable(successors, second.block, first.block)
    if forward and reverse:
        return None
    return forward


def _strictly_before(first, second_location, successors):
    if first.location is None:
        return True
    return _location_before(first.location, second_location, successors)


def _producer_before_producer(first, second, successors):
    if first.location is None:
        return second.location is not None
    if second.location is None:
        return False
    return _location_before(first.location, second.location, successors)


def _maximal_reaching(producers, target, successors):
    reaching = []
    ambiguous_reachability = False
    for producer in producers:
        relation = _strictly_before(producer, target, successors)
        if relation is None:
            ambiguous_reachability = True
            continue
        if relation:
            reaching.append(producer)
    maximal = []
    for candidate in reaching:
        shadowed = False
        for other in reaching:
            if other is candidate:
                continue
            if _producer_before_producer(candidate, other, successors) is True:
                if _strictly_before(other, target, successors) is True:
                    shadowed = True
                    break
        if not shadowed:
            maximal.append(candidate)
    return tuple(maximal), ambiguous_reachability


def _append_resolution(resolutions, pre, producer):
    if producer.type != pre.type:
        raise RegionArenaFlowError(f"REGION arena flow type mismatch at {pre.epoch_id!r}")
    resolutions.append(
        RegionArenaFlowResolution(pre.function, pre.binding, pre.epoch_id, producer.epoch_id)
    )


def _append_unresolved(unresolved, pre, reason):
    unresolved.append(RegionArenaFlowUnresolved(pre.function, pre.binding, pre.epoch_id, reason))


def _parameter_origin(producers):
    return tuple(
        item for item in producers
        if item.location is None
        and item.epoch.phase == "origin"
        and item.epoch.point_id.startswith("param_origin@")
    )


def _certify_cyclic_pre(
    *, function, successors, producers, pre, pre_location,
    resolutions, recurrences, unresolved,
):
    iteration_id = pre_location.iteration_id
    if iteration_id is None:
        raise RegionArenaFlowError("cyclic REGION arena point lacks iteration identity")
    cut = _cut_iteration_backedge(function, successors, iteration_id)
    iteration_posts = tuple(
        item for item in producers
        if item.location is not None and item.location.iteration_id == iteration_id
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
        item for item in iteration_posts
        if item.location is not None and _location_before(pre_location, item.location, cut) is True
    )
    if later_posts:
        origins = _parameter_origin(producers)
        if len(later_posts) == 1 and len(origins) == 1:
            initial, carried = origins[0].epoch, later_posts[0].epoch
            if initial.type != pre.type or carried.type != pre.type:
                raise RegionArenaFlowError(f"REGION arena recurrence type mismatch at {pre.epoch_id!r}")
            recurrences.append(
                RegionArenaFlowRecurrence(
                    pre.function, pre.binding, pre.epoch_id,
                    initial.epoch_id, carried.epoch_id, iteration_id,
                )
            )
            return
        _append_unresolved(
            unresolved,
            pre,
            "ambiguous_loop_carry" if len(later_posts) != 1 else "loop_carry_without_parameter_origin",
        )
        return
    _append_unresolved(unresolved, pre, "cyclic_no_local_producer")


def _certify_activation_pre(
    *, activation_epochs, local_posts, pre, pre_location, successors,
    resolutions, activations, unresolved,
):
    # A local post proven before the pre supersedes activation entry identity.
    maximal, ambiguous = _maximal_reaching(local_posts, pre_location, successors)
    if len(maximal) == 1:
        _append_resolution(resolutions, pre, maximal[0].epoch)
        return
    if len(maximal) > 1:
        _append_unresolved(unresolved, pre, "ambiguous_merge")
        return
    if ambiguous:
        _append_unresolved(unresolved, pre, "activation_local_reachability")
        return
    if pre_location.iteration_id is not None:
        _append_unresolved(unresolved, pre, "activation_cyclic")
        return

    inputs = tuple(dict.fromkeys(item.epoch_id for item in activation_epochs))
    if not inputs:
        _append_unresolved(unresolved, pre, "activation_missing_entry")
        return
    if any(item.type != pre.type or not item.activation_id for item in activation_epochs):
        raise RegionArenaFlowError(
            f"REGION arena activation type/identity mismatch at {pre.epoch_id!r}"
        )
    activations.append(
        RegionArenaFlowActivation(pre.function, pre.binding, pre.epoch_id, inputs)
    )


def certify_region_arena_flow(
    lifetime: RegionInterproceduralLifetimePlan,
    arena: RegionArenaLifetimeGraph,
    sir_module: object,
) -> RegionArenaFlowCertificate:
    if not isinstance(lifetime, RegionInterproceduralLifetimePlan):
        raise RegionArenaFlowError("REGION arena flow requires certified interprocedural lifetime facts")
    if not isinstance(arena, RegionArenaLifetimeGraph):
        raise RegionArenaFlowError("REGION arena flow requires a RegionArenaLifetimeGraph")

    module = _unwrap_module(sir_module)
    functions = {
        _required_text(getattr(item, "name", None), label="REGION arena SIR function"): item
        for item in tuple(getattr(module, "functions", ()) or ())
    }
    if len(functions) != len(tuple(getattr(module, "functions", ()) or ())):
        raise RegionArenaFlowError("REGION arena flow contains duplicate SIR functions")

    resolutions = []
    recurrences = []
    activations = []
    unresolved = []

    for slot in arena.slots:
        function = functions.get(slot.function)
        if function is None:
            raise RegionArenaFlowError(f"REGION arena flow requires SIR function {slot.function!r}")
        successors = _successors(function)
        epochs = arena.epochs_for(slot.function, slot.binding)
        pre_epochs = tuple(item for item in epochs if item.phase == "pre")
        if not pre_epochs:
            continue
        activation_epochs = tuple(item for item in epochs if item.phase == "call_entry")
        producers = []
        for epoch in epochs:
            if epoch.phase == "origin":
                producers.append(_Producer(epoch, None))
            elif epoch.phase == "post":
                producers.append(
                    _Producer(
                        epoch,
                        _point_location(lifetime, function=epoch.function, point_id=epoch.point_id),
                    )
                )
        local_posts = tuple(item for item in producers if item.location is not None)

        for pre in pre_epochs:
            pre_location = _point_location(lifetime, function=pre.function, point_id=pre.point_id)
            if activation_epochs:
                _certify_activation_pre(
                    activation_epochs=activation_epochs,
                    local_posts=local_posts,
                    pre=pre,
                    pre_location=pre_location,
                    successors=successors,
                    resolutions=resolutions,
                    activations=activations,
                    unresolved=unresolved,
                )
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
            maximal, ambiguous = _maximal_reaching(producers, pre_location, successors)
            if len(maximal) == 1:
                _append_resolution(resolutions, pre, maximal[0].epoch)
            elif len(maximal) > 1:
                _append_unresolved(unresolved, pre, "ambiguous_merge")
            elif ambiguous:
                _append_unresolved(unresolved, pre, "cyclic_reachability")
            else:
                _append_unresolved(unresolved, pre, "no_reaching_producer")

    classified = [
        {item.pre_epoch_id for item in resolutions},
        {item.pre_epoch_id for item in recurrences},
        {item.pre_epoch_id for item in activations},
        {item.pre_epoch_id for item in unresolved},
    ]
    for index, first in enumerate(classified):
        for second in classified[index + 1:]:
            if first & second:
                raise RegionArenaFlowError("REGION arena flow classified the same pre epoch more than once")
    all_pre_ids = {epoch.epoch_id for epoch in arena.epochs if epoch.phase == "pre"}
    if set().union(*classified) != all_pre_ids:
        raise RegionArenaFlowError("REGION arena flow failed to classify every pre epoch")

    return RegionArenaFlowCertificate(
        resolutions=tuple(resolutions),
        unresolved=tuple(unresolved),
        recurrences=tuple(recurrences),
        activations=tuple(activations),
    )


__all__ = [
    "RegionArenaFlowError",
    "RegionArenaFlowResolution",
    "RegionArenaFlowRecurrence",
    "RegionArenaFlowActivation",
    "RegionArenaFlowUnresolved",
    "RegionArenaFlowCertificate",
    "certify_region_arena_flow",
]
