"""Materialize reference C11 DEVICE operand storage without emitting calls.

This layer consumes the declaration-only C11 plan plus the validated physical
plan and assigns deterministic C identifiers to every runtime operand/result.
It still does not render or execute a runtime invocation.  A later emitter must
consume the returned call layouts exactly and may not reconstruct lifecycle
state independently.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Iterable

from .device_runtime_c11 import (
    C11DeviceRuntimeDeclarationPlan,
    DeviceRuntimeC11ABIError,
)
from .sir.device_runtime_physical_abi import BoundDeviceRuntimePhysicalABIPlan


class DeviceRuntimeC11MaterializationError(ValueError):
    """Raised when safe C11 operand materialization cannot be proven."""


_C_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_C11_KEYWORDS = {
    "auto", "break", "case", "char", "const", "continue", "default", "do",
    "double", "else", "enum", "extern", "float", "for", "goto", "if", "inline",
    "int", "long", "register", "restrict", "return", "short", "signed", "sizeof",
    "static", "struct", "switch", "typedef", "union", "unsigned", "void", "volatile",
    "while", "_Alignas", "_Alignof", "_Atomic", "_Bool", "_Complex", "_Generic",
    "_Imaginary", "_Noreturn", "_Static_assert", "_Thread_local",
}


@dataclass(frozen=True)
class C11DeviceOwnerSource:
    """Existing host-side owner components supplied by the enclosing C11 lowering."""

    binding: str
    address_identifier: str
    extent_identifier: str


@dataclass(frozen=True)
class C11DeviceOwnerResult:
    """Host-side owner components produced after validated reacquisition."""

    binding: str
    address_identifier: str
    extent_identifier: str


@dataclass(frozen=True)
class C11DeviceRuntimeMaterializedCall:
    """One future call's concrete operands, but not the call expression itself."""

    operation: str
    point_id: str
    symbol: str
    prelude: tuple[str, ...]
    arguments: tuple[str, ...]
    direct_result_target: str | None


@dataclass(frozen=True)
class C11DeviceRuntimeMaterializationPlan:
    abi_name: str
    abi_version: int
    function: str
    queue: str
    queue_identifier: str
    storage_declarations: tuple[str, ...]
    calls: tuple[C11DeviceRuntimeMaterializedCall, ...]
    host_results: tuple[C11DeviceOwnerResult, ...]

    @property
    def point_ids(self) -> tuple[str, ...]:
        return tuple(call.point_id for call in self.calls)


def _required_text(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DeviceRuntimeC11MaterializationError(
            f"{label} requires a non-empty identity"
        )
    return value


def _c_identifier(value: Any, *, label: str) -> str:
    identifier = _required_text(value, label=label)
    if not _C_IDENTIFIER.fullmatch(identifier) or identifier in _C11_KEYWORDS:
        raise DeviceRuntimeC11MaterializationError(
            f"{label} must be a safe C11 identifier"
        )
    return identifier


def _materialize(values: Iterable[Any], *, label: str) -> tuple[Any, ...]:
    result = tuple(values)
    if not result:
        raise DeviceRuntimeC11MaterializationError(f"{label} requires at least one item")
    return result


def _binding_map(
    sources: tuple[C11DeviceOwnerSource, ...],
) -> dict[str, C11DeviceOwnerSource]:
    result: dict[str, C11DeviceOwnerSource] = {}
    used_identifiers: set[str] = set()
    for source in sources:
        if not isinstance(source, C11DeviceOwnerSource):
            raise DeviceRuntimeC11MaterializationError(
                "DEVICE C11 owner sources contain an invalid entry"
            )
        binding = _required_text(source.binding, label="DEVICE C11 source binding")
        if binding in result:
            raise DeviceRuntimeC11MaterializationError(
                "DEVICE C11 owner sources contain a duplicate binding"
            )
        address = _c_identifier(
            source.address_identifier,
            label=f"DEVICE C11 {binding} address identifier",
        )
        extent = _c_identifier(
            source.extent_identifier,
            label=f"DEVICE C11 {binding} extent identifier",
        )
        if address == extent or address in used_identifiers or extent in used_identifiers:
            raise DeviceRuntimeC11MaterializationError(
                "DEVICE C11 owner source identifiers must be globally unique"
            )
        used_identifiers.update((address, extent))
        result[binding] = source
    return result


def materialize_reference_c11_device_runtime(
    declarations: C11DeviceRuntimeDeclarationPlan,
    bound_plan: BoundDeviceRuntimePhysicalABIPlan,
    *,
    queue_identifier: str,
    host_owners: Iterable[C11DeviceOwnerSource],
) -> C11DeviceRuntimeMaterializationPlan:
    """Assign safe C11 storage/operand identities without rendering calls."""
    if not isinstance(declarations, C11DeviceRuntimeDeclarationPlan):
        raise DeviceRuntimeC11MaterializationError(
            "DEVICE C11 materialization requires a declaration plan"
        )
    if not isinstance(bound_plan, BoundDeviceRuntimePhysicalABIPlan):
        raise DeviceRuntimeC11MaterializationError(
            "DEVICE C11 materialization requires a validated physical plan"
        )
    if (
        declarations.abi_name != bound_plan.abi_name
        or declarations.abi_version != bound_plan.abi_version
        or declarations.function != bound_plan.function
        or declarations.queue != bound_plan.queue
    ):
        raise DeviceRuntimeC11MaterializationError(
            "DEVICE C11 declaration and physical plans do not share one identity"
        )
    if declarations.point_ids != bound_plan.point_ids:
        raise DeviceRuntimeC11MaterializationError(
            "DEVICE C11 declaration and physical lifecycle points diverge"
        )
    if len(declarations.calls) != len(bound_plan.calls):
        raise DeviceRuntimeC11MaterializationError(
            "DEVICE C11 declaration and physical call counts diverge"
        )

    queue_name = _c_identifier(queue_identifier, label="DEVICE C11 queue identifier")
    sources = _materialize(tuple(host_owners), label="DEVICE C11 host owners")
    source_by_binding = _binding_map(sources)

    logical_calls = tuple(bound.logical for bound in bound_plan.calls)
    for declaration_call, logical in zip(
        declarations.calls, logical_calls, strict=True
    ):
        if (
            declaration_call.operation != logical.operation
            or declaration_call.point_id != logical.point_id
            or declaration_call.symbol != logical.symbol
        ):
            raise DeviceRuntimeC11MaterializationError(
                "DEVICE C11 declaration call diverges from physical lifecycle proof"
            )

    operations = tuple(call.operation for call in declarations.calls)
    owner_count = operations.count("submit")
    expected_operations = (
        ("submit",) * owner_count
        + ("complete",) * owner_count
        + ("synchronize",)
        + ("reacquire",) * owner_count
    )
    if owner_count == 0 or operations != expected_operations:
        raise DeviceRuntimeC11MaterializationError(
            "DEVICE C11 materialization received a non-canonical lifecycle"
        )

    submit_bindings = tuple(
        _required_text(logical_calls[index].binding, label="DEVICE C11 submit binding")
        for index in range(owner_count)
    )
    if len(set(submit_bindings)) != owner_count:
        raise DeviceRuntimeC11MaterializationError(
            "DEVICE C11 materialization requires unique submitted bindings"
        )
    if set(source_by_binding) != set(submit_bindings):
        raise DeviceRuntimeC11MaterializationError(
            "DEVICE C11 host owner sources must exactly cover submitted bindings"
        )

    storage: list[str] = []
    generated: set[str] = {queue_name}
    source_identifiers = {
        identifier
        for source in sources
        for identifier in (source.address_identifier, source.extent_identifier)
    }
    generated.update(source_identifiers)

    device_address: list[str] = []
    device_extent: list[str] = []
    submissions: list[str] = []
    completions: list[str] = []
    host_address: list[str] = []
    host_extent: list[str] = []

    def reserve(name: str, declaration: str) -> str:
        if name in generated:
            raise DeviceRuntimeC11MaterializationError(
                f"DEVICE C11 generated identifier collision for {name}"
            )
        generated.add(name)
        storage.append(declaration)
        return name

    for index in range(owner_count):
        device_address.append(
            reserve(
                f"__sotlas_device_owner_{index}_address",
                f"uintptr_t __sotlas_device_owner_{index}_address;",
            )
        )
        device_extent.append(
            reserve(
                f"__sotlas_device_owner_{index}_extent",
                f"size_t __sotlas_device_owner_{index}_extent;",
            )
        )
        submissions.append(
            reserve(
                f"__sotlas_device_submission_{index}",
                f"sotlas_device_submission_t __sotlas_device_submission_{index};",
            )
        )
        completions.append(
            reserve(
                f"__sotlas_device_completion_{index}",
                f"sotlas_device_completion_t __sotlas_device_completion_{index};",
            )
        )
        host_address.append(
            reserve(
                f"__sotlas_host_owner_{index}_address",
                f"uintptr_t __sotlas_host_owner_{index}_address;",
            )
        )
        host_extent.append(
            reserve(
                f"__sotlas_host_owner_{index}_extent",
                f"size_t __sotlas_host_owner_{index}_extent;",
            )
        )

    fence = reserve(
        "__sotlas_device_sync_fence",
        "sotlas_device_fence_t __sotlas_device_sync_fence;",
    )
    completion_array = "__sotlas_device_completions"
    if completion_array in generated:
        raise DeviceRuntimeC11MaterializationError(
            "DEVICE C11 completion array identifier collides with existing storage"
        )
    generated.add(completion_array)

    materialized_calls: list[C11DeviceRuntimeMaterializedCall] = []
    sync_index = owner_count * 2
    for index, declaration_call in enumerate(declarations.calls):
        operation = declaration_call.operation
        prelude: tuple[str, ...] = ()
        direct_target: str | None = None

        if operation == "submit":
            owner_index = index
            source = source_by_binding[submit_bindings[owner_index]]
            arguments = (
                queue_name,
                source.address_identifier,
                source.extent_identifier,
                f"&{device_address[owner_index]}",
                f"&{device_extent[owner_index]}",
            )
            direct_target = submissions[owner_index]
        elif operation == "complete":
            owner_index = index - owner_count
            arguments = (queue_name, submissions[owner_index])
            direct_target = completions[owner_index]
        elif operation == "synchronize":
            completion_values = ", ".join(completions)
            prelude = (
                "sotlas_device_completion_t "
                f"{completion_array}[{owner_count}] = {{ {completion_values} }};",
            )
            arguments = (
                queue_name,
                completion_array,
                f"(size_t){owner_count}",
            )
            direct_target = fence
        else:
            owner_index = index - (sync_index + 1)
            arguments = (
                queue_name,
                device_address[owner_index],
                device_extent[owner_index],
                fence,
                f"&{host_address[owner_index]}",
                f"&{host_extent[owner_index]}",
            )

        prototype = next(
            prototype
            for prototype in declarations.prototypes
            if prototype.operation == operation
        )
        if len(arguments) != len(prototype.parameters):
            raise DeviceRuntimeC11MaterializationError(
                f"DEVICE C11 {operation} materialized operand count diverges from prototype"
            )
        if (declaration_call.direct_result is None) != (direct_target is None):
            raise DeviceRuntimeC11MaterializationError(
                f"DEVICE C11 {operation} return storage diverges from declaration"
            )

        materialized_calls.append(
            C11DeviceRuntimeMaterializedCall(
                operation=operation,
                point_id=declaration_call.point_id,
                symbol=declaration_call.symbol,
                prelude=prelude,
                arguments=arguments,
                direct_result_target=direct_target,
            )
        )

    host_results = tuple(
        C11DeviceOwnerResult(
            binding=binding,
            address_identifier=host_address[index],
            extent_identifier=host_extent[index],
        )
        for index, binding in enumerate(submit_bindings)
    )
    result = C11DeviceRuntimeMaterializationPlan(
        abi_name=declarations.abi_name,
        abi_version=declarations.abi_version,
        function=declarations.function,
        queue=declarations.queue,
        queue_identifier=queue_name,
        storage_declarations=tuple(storage),
        calls=tuple(materialized_calls),
        host_results=host_results,
    )
    if result.point_ids != declarations.point_ids:
        raise DeviceRuntimeC11MaterializationError(
            "DEVICE C11 materialization changed lifecycle point order"
        )
    return result
