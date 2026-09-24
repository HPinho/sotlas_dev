"""Structural bridge from graph-derived DEVICE frontend semantics to SIR.

The frontend/runtime package owns canonical ownership graph semantics while SIR
must remain independent from that package.  This module therefore consumes the
frontend plan structurally and requires an explicit semantic-binding -> SIR
value map before lowering completion/fence/reacquisition facts.

No runtime symbol is bound and no backend execution is enabled here.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Protocol

from .device_runtime import (
    DeviceRuntimeSIRBridgePlan,
    validate_device_runtime_sir_plan,
)
from .device_sync import DeviceSyncSIRPlan, lower_device_sync_batch
from .instructions import SIRValue


class DeviceFrontendRuntimeSIRError(ValueError):
    """Raised when frontend DEVICE identities cannot be preserved in SIR."""


class _LifecycleLike(Protocol):
    function: str
    queue: str
    completed_tokens: tuple[Any, ...]
    reacquisition: Any
    bindings: tuple[str, ...]
    point_ids: tuple[str, ...]


class _RuntimeLike(Protocol):
    function: str
    queue: str
    requirements: tuple[Any, ...]
    point_ids: tuple[str, ...]


class _FrontendRuntimeLike(Protocol):
    lifecycle: _LifecycleLike
    runtime: _RuntimeLike


@dataclass(frozen=True)
class DeviceRuntimeSIRValueBinding:
    """Explicit correspondence between one semantic owner and SIR values."""

    binding: str
    source: SIRValue
    destination: SIRValue


@dataclass(frozen=True)
class DeviceFrontendRuntimeSIRPlan:
    """Validated frontend/runtime/SIR correspondence for one DEVICE lifecycle."""

    function: str
    queue: str
    bindings: tuple[str, ...]
    values: tuple[DeviceRuntimeSIRValueBinding, ...]
    sir: DeviceSyncSIRPlan
    bridge: DeviceRuntimeSIRBridgePlan

    @property
    def point_ids(self) -> tuple[str, ...]:
        return self.bridge.runtime_point_ids


def _required_text(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DeviceFrontendRuntimeSIRError(f"{label} requires a non-empty identity")
    return value


def _materialize(
    values: Iterable[DeviceRuntimeSIRValueBinding],
) -> tuple[DeviceRuntimeSIRValueBinding, ...]:
    result = tuple(values)
    if not result:
        raise DeviceFrontendRuntimeSIRError(
            "DEVICE frontend/SIR bridge requires at least one owner mapping"
        )
    return result


def lower_device_frontend_runtime_to_sir(
    frontend_plan: _FrontendRuntimeLike,
    values: Iterable[DeviceRuntimeSIRValueBinding],
) -> DeviceFrontendRuntimeSIRPlan:
    """Lower graph-derived DEVICE lifecycle facts into SIR without losing identity."""
    lifecycle = getattr(frontend_plan, "lifecycle", None)
    runtime = getattr(frontend_plan, "runtime", None)
    if lifecycle is None or runtime is None:
        raise DeviceFrontendRuntimeSIRError(
            "DEVICE frontend/SIR bridge requires lifecycle and runtime plans"
        )

    function = _required_text(
        getattr(lifecycle, "function", None), label="DEVICE lifecycle function"
    )
    queue = _required_text(
        getattr(lifecycle, "queue", None), label="DEVICE lifecycle queue"
    )
    if getattr(runtime, "function", None) != function:
        raise DeviceFrontendRuntimeSIRError(
            "DEVICE runtime plan changed frontend function identity"
        )
    if getattr(runtime, "queue", None) != queue:
        raise DeviceFrontendRuntimeSIRError(
            "DEVICE runtime plan changed frontend queue identity"
        )

    semantic_bindings = tuple(getattr(lifecycle, "bindings", ()) or ())
    if not semantic_bindings:
        raise DeviceFrontendRuntimeSIRError(
            "DEVICE lifecycle contains no canonical owner bindings"
        )
    semantic_bindings = tuple(
        _required_text(binding, label="DEVICE semantic binding")
        for binding in semantic_bindings
    )
    if len(set(semantic_bindings)) != len(semantic_bindings):
        raise DeviceFrontendRuntimeSIRError(
            "DEVICE semantic owner bindings must be unique"
        )

    mappings = _materialize(values)
    if len(mappings) != len(semantic_bindings):
        raise DeviceFrontendRuntimeSIRError(
            "DEVICE frontend/SIR bridge requires one value mapping per owner"
        )
    mapping_bindings: list[str] = []
    for mapping in mappings:
        if not isinstance(mapping, DeviceRuntimeSIRValueBinding):
            raise DeviceFrontendRuntimeSIRError(
                "DEVICE frontend/SIR bridge contains an invalid value mapping"
            )
        binding = _required_text(mapping.binding, label="DEVICE SIR mapping binding")
        mapping_bindings.append(binding)
        if not isinstance(mapping.source, SIRValue) or not isinstance(
            mapping.destination, SIRValue
        ):
            raise DeviceFrontendRuntimeSIRError(
                "DEVICE SIR mapping requires source and destination SIRValue objects"
            )
        _required_text(mapping.source.name, label="DEVICE SIR source value")
        _required_text(mapping.destination.name, label="DEVICE SIR destination value")
        if mapping.source.name == mapping.destination.name:
            raise DeviceFrontendRuntimeSIRError(
                "DEVICE SIR source and destination must be distinct values"
            )
    if tuple(mapping_bindings) != semantic_bindings:
        raise DeviceFrontendRuntimeSIRError(
            "DEVICE SIR value mapping order diverges from canonical bindings"
        )

    sources = tuple(mapping.source for mapping in mappings)
    destinations = tuple(mapping.destination for mapping in mappings)
    if len({value.name for value in sources}) != len(sources):
        raise DeviceFrontendRuntimeSIRError(
            "DEVICE SIR source values must be unique per owner"
        )
    if len({value.name for value in destinations}) != len(destinations):
        raise DeviceFrontendRuntimeSIRError(
            "DEVICE SIR destination values must be unique per owner"
        )

    completed_tokens = tuple(
        getattr(lifecycle, "completed_tokens", ()) or ()
    )
    if len(completed_tokens) != len(semantic_bindings):
        raise DeviceFrontendRuntimeSIRError(
            "DEVICE lifecycle lost one completed token per owner"
        )
    batch = getattr(lifecycle, "reacquisition", None)
    if batch is None:
        raise DeviceFrontendRuntimeSIRError(
            "DEVICE lifecycle is missing synchronized reacquisition proof"
        )

    runtime_points = tuple(getattr(runtime, "point_ids", ()) or ())
    lifecycle_points = tuple(getattr(lifecycle, "point_ids", ()) or ())
    if runtime_points != lifecycle_points:
        raise DeviceFrontendRuntimeSIRError(
            "DEVICE runtime point order diverges from graph-derived lifecycle"
        )

    sir_plan = lower_device_sync_batch(
        batch,
        completed_tokens,
        sources,
        destinations,
    )
    bridge = validate_device_runtime_sir_plan(sir_plan, runtime)
    if bridge.runtime_point_ids != lifecycle_points:
        raise DeviceFrontendRuntimeSIRError(
            "DEVICE SIR/runtime bridge changed graph-derived lifecycle identity"
        )
    if bridge.submission_point_ids != tuple(
        token.submission_point_id for token in completed_tokens
    ):
        raise DeviceFrontendRuntimeSIRError(
            "DEVICE SIR/runtime bridge lost canonical submission identities"
        )
    if bridge.completion_point_ids != tuple(
        token.completion_point_id for token in completed_tokens
    ):
        raise DeviceFrontendRuntimeSIRError(
            "DEVICE SIR/runtime bridge lost canonical completion identities"
        )

    return DeviceFrontendRuntimeSIRPlan(
        function=function,
        queue=queue,
        bindings=semantic_bindings,
        values=mappings,
        sir=sir_plan,
        bridge=bridge,
    )
