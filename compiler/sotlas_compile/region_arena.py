"""Backend-neutral symbolic arena/lifetime identity graph for REGION owners.

REGION bindings are reusable ownership slots, not permanent arena identities: a
binding can be consumed and later re-armed by ``handover``. Therefore this layer
never assigns one arena identity to ``function::binding`` for its whole lifetime.
It freezes three distinct concepts instead:

* static owner slots, derived from the certified REGION lifetime plan;
* canonical declaration origins and source-stable ownership epochs;
* identity-preserving constraints at transfer/call/return boundaries.

Only declaration origins whose producer truly introduces identity (parameters
and fresh values in the current frontend) become ``origin`` epochs. A local
created from a call/move does not receive a fake root; its identity must arrive
through another ownership constraint. The graph chooses no physical allocator,
allocates no storage and does not collapse path-dependent alternatives.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .region_boundary_link import RegionBoundaryLinkPlan
from .region_interprocedural import RegionInterproceduralLifetimePlan
from .region_return_link import RegionReturnLinkPlan
from .typed_ast import Phase1SemanticError


class RegionArenaLifetimeError(Phase1SemanticError):
    """Raised when symbolic REGION arena/lifetime identities cannot be certified."""


@dataclass(frozen=True)
class RegionArenaSlot:
    function: str
    binding: str
    type: Any

    @property
    def identity(self) -> tuple[str, str]:
        return (self.function, self.binding)


@dataclass(frozen=True)
class RegionArenaEpoch:
    epoch_id: str
    function: str
    binding: str
    phase: str
    point_id: str
    type: Any
    activation_id: str | None = None

    @property
    def slot_identity(self) -> tuple[str, str]:
        return (self.function, self.binding)


@dataclass(frozen=True)
class RegionArenaConstraint:
    source_epoch_id: str
    target_epoch_id: str
    via: str
    point_id: str
    preserves_identity: bool = True

    @property
    def identity(self) -> tuple[str, str, str, str]:
        return (
            self.source_epoch_id,
            self.target_epoch_id,
            self.via,
            self.point_id,
        )


@dataclass(frozen=True)
class RegionArenaLifetimeGraph:
    slots: tuple[RegionArenaSlot, ...]
    epochs: tuple[RegionArenaEpoch, ...]
    constraints: tuple[RegionArenaConstraint, ...]

    def slot(self, function: str, binding: str) -> RegionArenaSlot:
        matches = tuple(
            item
            for item in self.slots
            if item.function == function and item.binding == binding
        )
        if len(matches) != 1:
            raise RegionArenaLifetimeError(
                f"REGION arena graph requires exactly one slot {function}::{binding}"
            )
        return matches[0]

    def epoch(self, epoch_id: str) -> RegionArenaEpoch:
        matches = tuple(item for item in self.epochs if item.epoch_id == epoch_id)
        if len(matches) != 1:
            raise RegionArenaLifetimeError(
                f"REGION arena graph requires exactly one epoch {epoch_id!r}"
            )
        return matches[0]

    def epochs_for(self, function: str, binding: str) -> tuple[RegionArenaEpoch, ...]:
        self.slot(function, binding)
        return tuple(
            item
            for item in self.epochs
            if item.function == function and item.binding == binding
        )

    def origin_epochs(self) -> tuple[RegionArenaEpoch, ...]:
        return tuple(item for item in self.epochs if item.phase == "origin")

    def constraints_at(self, point_id: str) -> tuple[RegionArenaConstraint, ...]:
        return tuple(item for item in self.constraints if item.point_id == point_id)


def _required_text(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RegionArenaLifetimeError(f"{label} requires a non-empty identity")
    return value


def _epoch_id(
    *,
    phase: str,
    function: str,
    binding: str,
    point_id: str,
    activation_id: str | None = None,
) -> str:
    activation = f"[{activation_id}]" if activation_id is not None else ""
    return f"{phase}@{function}::{point_id}{activation}::{binding}"


def build_region_arena_lifetime_graph(
    lifetime: RegionInterproceduralLifetimePlan,
    boundaries: RegionBoundaryLinkPlan,
    return_links: RegionReturnLinkPlan,
) -> RegionArenaLifetimeGraph:
    """Freeze symbolic ownership epochs and identity-preserving REGION constraints."""
    if not isinstance(lifetime, RegionInterproceduralLifetimePlan):
        raise RegionArenaLifetimeError(
            "REGION arena graph requires certified interprocedural lifetime facts"
        )
    if not isinstance(boundaries, RegionBoundaryLinkPlan):
        raise RegionArenaLifetimeError(
            "REGION arena graph requires certified caller/callee boundaries"
        )
    if not isinstance(return_links, RegionReturnLinkPlan):
        raise RegionArenaLifetimeError(
            "REGION arena graph requires certified return links"
        )

    slots: list[RegionArenaSlot] = []
    by_slot: dict[tuple[str, str], RegionArenaSlot] = {}
    for function_plan in lifetime.functions:
        for owner in function_plan.local.owners:
            slot = RegionArenaSlot(
                function=_required_text(owner.function, label="REGION arena function"),
                binding=_required_text(owner.binding, label="REGION arena binding"),
                type=owner.type,
            )
            if slot.identity in by_slot:
                raise RegionArenaLifetimeError(
                    f"duplicate REGION arena slot {slot.function}::{slot.binding}"
                )
            by_slot[slot.identity] = slot
            slots.append(slot)

    epochs: list[RegionArenaEpoch] = []
    by_epoch: dict[str, RegionArenaEpoch] = {}
    constraints: list[RegionArenaConstraint] = []
    seen_constraints: set[tuple[str, str, str, str]] = set()

    def require_slot(function: str, binding: str) -> RegionArenaSlot:
        key = (function, binding)
        slot = by_slot.get(key)
        if slot is None:
            raise RegionArenaLifetimeError(
                f"REGION arena edge references unknown slot {function}::{binding}"
            )
        return slot

    def add_epoch(
        *,
        function: str,
        binding: str,
        phase: str,
        point_id: str,
        activation_id: str | None = None,
    ) -> RegionArenaEpoch:
        slot = require_slot(function, binding)
        stable_point = _required_text(point_id, label="REGION arena point")
        identifier = _epoch_id(
            phase=phase,
            function=function,
            binding=binding,
            point_id=stable_point,
            activation_id=activation_id,
        )
        existing = by_epoch.get(identifier)
        if existing is not None:
            if (
                existing.function != function
                or existing.binding != binding
                or existing.phase != phase
                or existing.point_id != stable_point
                or existing.type != slot.type
                or existing.activation_id != activation_id
            ):
                raise RegionArenaLifetimeError(
                    f"REGION arena epoch identity collision {identifier!r}"
                )
            return existing
        epoch = RegionArenaEpoch(
            epoch_id=identifier,
            function=function,
            binding=binding,
            phase=phase,
            point_id=stable_point,
            type=slot.type,
            activation_id=activation_id,
        )
        by_epoch[identifier] = epoch
        epochs.append(epoch)
        return epoch

    def add_constraint(
        source: RegionArenaEpoch,
        target: RegionArenaEpoch,
        *,
        via: str,
        point_id: str,
    ) -> None:
        if source.type != target.type:
            raise RegionArenaLifetimeError(
                f"REGION arena continuity type mismatch at {point_id!r}"
            )
        item = RegionArenaConstraint(
            source_epoch_id=source.epoch_id,
            target_epoch_id=target.epoch_id,
            via=_required_text(via, label="REGION arena continuity operation"),
            point_id=_required_text(point_id, label="REGION arena continuity point"),
        )
        if item.identity in seen_constraints:
            raise RegionArenaLifetimeError(
                f"duplicate REGION arena continuity constraint {item.identity!r}"
            )
        seen_constraints.add(item.identity)
        constraints.append(item)

    # Canonical owner origins are mandatory in the interprocedural plan. Only
    # producers that introduce a new identity become graph roots. Call/move
    # declarations wait for their actual incoming ownership constraint.
    for function_plan in lifetime.functions:
        if set(function_plan.origins.bindings) != set(function_plan.local.bindings):
            raise RegionArenaLifetimeError(
                f"REGION arena origins diverged for function {function_plan.function!r}"
            )
        for origin in function_plan.origins.origins:
            slot = require_slot(origin.function, origin.binding)
            if slot.type != origin.type:
                raise RegionArenaLifetimeError(
                    f"REGION arena origin type mismatch for {origin.function}::{origin.binding}"
                )
            if origin.produces_identity:
                add_epoch(
                    function=origin.function,
                    binding=origin.binding,
                    phase="origin",
                    point_id=origin.point_id,
                )

    # Local same-domain destinations create a new ownership epoch for the reused
    # destination slot. The source side is a pre-event epoch, so a later
    # dataflow pass can resolve which previous epoch reaches this point.
    for function_plan in lifetime.functions:
        function = function_plan.function
        for transfer in function_plan.local.transfers:
            if transfer.destination is None:
                continue
            point_id = _required_text(
                transfer.point_id,
                label="REGION arena local transfer point",
            )
            source = add_epoch(
                function=function,
                binding=transfer.source,
                phase="pre",
                point_id=point_id,
            )
            target = add_epoch(
                function=function,
                binding=transfer.destination,
                phase="post",
                point_id=point_id,
            )
            add_constraint(
                source,
                target,
                via=f"local:{transfer.via}",
                point_id=point_id,
            )

    # A callee parameter activation is call-site scoped. This is essential for
    # recursion and for one callee reached from multiple callers.
    for link in boundaries.links:
        source = add_epoch(
            function=link.caller,
            binding=link.source_binding,
            phase="pre",
            point_id=link.point_id,
        )
        activation_id = f"{link.caller}:{link.point_id}:arg{link.argument_index}"
        target = add_epoch(
            function=link.callee,
            binding=link.parameter,
            phase="call_entry",
            point_id=link.point_id,
            activation_id=activation_id,
        )
        add_constraint(source, target, via="call", point_id=link.point_id)

    # Return sources are also activation scoped. Multiple path-dependent return
    # bindings remain separate constraints instead of being collapsed into a
    # single static arena equality.
    for link in return_links.links:
        destination = add_epoch(
            function=link.caller,
            binding=link.destination,
            phase="post",
            point_id=link.point_id,
        )
        for binding in link.callee_return_bindings:
            activation_id = f"{link.caller}:{link.point_id}:return"
            source = add_epoch(
                function=link.callee,
                binding=binding,
                phase="call_return",
                point_id=link.point_id,
                activation_id=activation_id,
            )
            add_constraint(source, destination, via="return", point_id=link.point_id)

    return RegionArenaLifetimeGraph(
        slots=tuple(slots),
        epochs=tuple(epochs),
        constraints=tuple(constraints),
    )


__all__ = [
    "RegionArenaLifetimeError",
    "RegionArenaSlot",
    "RegionArenaEpoch",
    "RegionArenaConstraint",
    "RegionArenaLifetimeGraph",
    "build_region_arena_lifetime_graph",
]
