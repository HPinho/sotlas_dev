"""Backend-neutral deterministic cleanup planning for exclusive ownership.

The C11 backend already knows how to clean up a bounded set of direct ``sole``
fields and fixed arrays.  This module extracts that *ordering proof* from any
one backend.  It does not emit C, LLVM, calls, loops or frees; it describes the
only cleanup schedule a backend may lower for the certified shape.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class OwnershipCleanupError(ValueError):
    """Raised when deterministic cleanup cannot be proven for a value shape."""


class OwnedStorage(str, Enum):
    DIRECT = "direct"
    FIXED_ARRAY = "fixed_array"


@dataclass(frozen=True)
class OwnedFieldShape:
    name: str
    value: "ExclusiveValueShape"
    storage: OwnedStorage = OwnedStorage.DIRECT
    dimensions: tuple[int, ...] = ()


@dataclass(frozen=True)
class ExclusiveValueShape:
    type_name: str
    deinit_symbol: str | None = None
    deinit_uses_self: bool = False
    owned_fields: tuple[OwnedFieldShape, ...] = ()


@dataclass(frozen=True)
class CleanupChildPlan:
    field_name: str
    storage: OwnedStorage
    dimensions: tuple[int, ...]
    value: "ExclusiveCleanupPlan"


@dataclass(frozen=True)
class ExclusiveCleanupPlan:
    type_name: str
    deinit_symbol: str | None
    children: tuple[CleanupChildPlan, ...]

    @property
    def has_owned_descendants(self) -> bool:
        return bool(self.children)


@dataclass(frozen=True)
class CleanupEvent:
    """One observable cleanup event used by audits and backend tests.

    Fixed-array indices are included only when a bounded plan is expanded by
    ``expand_cleanup_events``; ordinary backends may lower the recursive plan
    without materializing every element in memory.
    """

    action: str
    type_name: str
    path: tuple[str | int, ...]
    symbol: str | None = None


def _required_name(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise OwnershipCleanupError(f"{label} requires a non-empty identity")
    return value


def _validated_dimensions(dimensions: Iterable[int]) -> tuple[int, ...]:
    result = tuple(dimensions)
    if not result:
        raise OwnershipCleanupError("fixed owned array requires dimensions")
    for size in result:
        if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
            raise OwnershipCleanupError(
                "fixed owned array dimensions must be positive integers"
            )
    return result


def build_exclusive_cleanup_plan(shape: ExclusiveValueShape) -> ExclusiveCleanupPlan:
    """Build the canonical recursive cleanup plan for one exclusive value.

    Children are stored in *cleanup order*, not declaration order.  Therefore
    they are reversed here exactly once and every backend can consume the same
    schedule without reconstructing language semantics.
    """

    if not isinstance(shape, ExclusiveValueShape):
        raise OwnershipCleanupError("exclusive cleanup requires a typed value shape")

    active: set[int] = set()

    def build(current: ExclusiveValueShape) -> ExclusiveCleanupPlan:
        identity = id(current)
        if identity in active:
            raise OwnershipCleanupError(
                "exclusive cleanup shape contains a recursive owned-value cycle"
            )
        active.add(identity)
        try:
            type_name = _required_name(current.type_name, label="cleanup type")
            deinit = current.deinit_symbol
            if deinit is not None:
                deinit = _required_name(deinit, label=f"deinit for {type_name}")
            if not isinstance(current.deinit_uses_self, bool):
                raise OwnershipCleanupError("deinit_uses_self must be boolean")

            declaration_children = tuple(current.owned_fields)
            names: set[str] = set()
            planned: list[CleanupChildPlan] = []
            for field in reversed(declaration_children):
                if not isinstance(field, OwnedFieldShape):
                    raise OwnershipCleanupError(
                        f"owned fields of {type_name} must be typed field shapes"
                    )
                name = _required_name(field.name, label=f"owned field of {type_name}")
                if name in names:
                    raise OwnershipCleanupError(
                        f"owned field {name!r} is declared more than once in {type_name}"
                    )
                names.add(name)
                if not isinstance(field.storage, OwnedStorage):
                    raise OwnershipCleanupError(
                        f"owned field {type_name}.{name} has unsupported storage"
                    )
                if field.storage is OwnedStorage.DIRECT:
                    if field.dimensions:
                        raise OwnershipCleanupError(
                            f"direct owned field {type_name}.{name} cannot have dimensions"
                        )
                    dimensions: tuple[int, ...] = ()
                else:
                    dimensions = _validated_dimensions(field.dimensions)
                planned.append(
                    CleanupChildPlan(
                        field_name=name,
                        storage=field.storage,
                        dimensions=dimensions,
                        value=build(field.value),
                    )
                )

            if current.deinit_uses_self and planned:
                raise OwnershipCleanupError(
                    f"deinit for {type_name} accesses self while owned descendants "
                    "require recursive cleanup"
                )
            return ExclusiveCleanupPlan(
                type_name=type_name,
                deinit_symbol=deinit,
                children=tuple(planned),
            )
        finally:
            active.remove(identity)

    return build(shape)


def _reverse_indices(dimensions: tuple[int, ...]):
    if not dimensions:
        yield ()
        return

    indices = [size - 1 for size in dimensions]
    while True:
        yield tuple(indices)
        cursor = len(indices) - 1
        while cursor >= 0:
            if indices[cursor] > 0:
                indices[cursor] -= 1
                for reset in range(cursor + 1, len(indices)):
                    indices[reset] = dimensions[reset] - 1
                break
            cursor -= 1
        if cursor < 0:
            return


def expand_cleanup_events(
    plan: ExclusiveCleanupPlan,
    *,
    max_array_elements: int = 4096,
) -> tuple[CleanupEvent, ...]:
    """Expand a plan into observable events for audits/tests.

    Expansion is deliberately bounded so an enormous fixed array cannot cause
    tooling to allocate an unbounded event list.  Backends are expected to
    lower arrays as reverse loops when appropriate.
    """

    if not isinstance(plan, ExclusiveCleanupPlan):
        raise OwnershipCleanupError("cleanup expansion requires a canonical plan")
    if (
        not isinstance(max_array_elements, int)
        or isinstance(max_array_elements, bool)
        or max_array_elements < 1
    ):
        raise OwnershipCleanupError("cleanup expansion bound must be positive")

    events: list[CleanupEvent] = []

    def emit(current: ExclusiveCleanupPlan, path: tuple[str | int, ...]) -> None:
        if current.deinit_symbol is not None:
            events.append(
                CleanupEvent(
                    action="invoke_deinit",
                    type_name=current.type_name,
                    path=path,
                    symbol=current.deinit_symbol,
                )
            )
        for child in current.children:
            field_path = (*path, child.field_name)
            if child.storage is OwnedStorage.DIRECT:
                emit(child.value, field_path)
                events.append(
                    CleanupEvent(
                        action="end_owned_lifetime",
                        type_name=child.value.type_name,
                        path=field_path,
                    )
                )
                continue

            count = 1
            for size in child.dimensions:
                count *= size
                if count > max_array_elements:
                    raise OwnershipCleanupError(
                        f"cleanup expansion for {child.field_name!r} exceeds bound"
                    )
            for indices in _reverse_indices(child.dimensions):
                element_path = (*field_path, *indices)
                emit(child.value, element_path)
                events.append(
                    CleanupEvent(
                        action="end_owned_lifetime",
                        type_name=child.value.type_name,
                        path=element_path,
                    )
                )

    emit(plan, ())
    events.append(
        CleanupEvent(
            action="end_owned_lifetime",
            type_name=plan.type_name,
            path=(),
        )
    )
    return tuple(events)
