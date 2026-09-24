"""Isolated reference C11 call emission for the validated DEVICE runtime ABI.

This is the first layer that renders runtime invocation statements.  It remains
isolated from the general CodegenC pipeline and therefore does not claim global
DEVICE backend support.  Every statement must come from a declaration plan and
operand materialization plan that agree on ABI identity and source-stable
lifecycle points.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

from .device_runtime_c11 import C11DeviceRuntimeDeclarationPlan
from .device_runtime_c11_materialize import (
    C11DeviceOwnerResult,
    C11DeviceRuntimeMaterializationPlan,
)


class DeviceRuntimeC11EmissionError(ValueError):
    """Raised when a materialized DEVICE call stream cannot be emitted safely."""


_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SAFE_ARGUMENT = re.compile(
    r"^(?:[A-Za-z_][A-Za-z0-9_]*|&[A-Za-z_][A-Za-z0-9_]*|\(size_t\)[0-9]+)$"
)
_SAFE_STORAGE = re.compile(
    r"^(?:uintptr_t|size_t|sotlas_device_submission_t|sotlas_device_completion_t|"
    r"sotlas_device_fence_t) [A-Za-z_][A-Za-z0-9_]*;$"
)
_SAFE_COMPLETION_PRELUDE = re.compile(
    r"^sotlas_device_completion_t [A-Za-z_][A-Za-z0-9_]*\[[1-9][0-9]*\] = \{ "
    r"[A-Za-z_][A-Za-z0-9_]*(?:, [A-Za-z_][A-Za-z0-9_]*)* \};$"
)


@dataclass(frozen=True)
class C11DeviceRuntimeEmissionPlan:
    abi_name: str
    abi_version: int
    function: str
    queue: str
    point_ids: tuple[str, ...]
    declaration_source: str
    storage_declarations: tuple[str, ...]
    call_statements: tuple[str, ...]
    host_results: tuple[C11DeviceOwnerResult, ...]

    def render_body(self, *, indent: str = "    ") -> str:
        lines = [*(indent + line for line in self.storage_declarations)]
        if lines and self.call_statements:
            lines.append("")
        lines.extend(indent + line for line in self.call_statements)
        return "\n".join(lines) + ("\n" if lines else "")


def emit_reference_c11_device_runtime_calls(
    declarations: C11DeviceRuntimeDeclarationPlan,
    materialized: C11DeviceRuntimeMaterializationPlan,
) -> C11DeviceRuntimeEmissionPlan:
    """Render only the already-materialized reference C11 DEVICE call stream."""
    if not isinstance(declarations, C11DeviceRuntimeDeclarationPlan):
        raise DeviceRuntimeC11EmissionError(
            "DEVICE C11 emission requires a declaration plan"
        )
    if not isinstance(materialized, C11DeviceRuntimeMaterializationPlan):
        raise DeviceRuntimeC11EmissionError(
            "DEVICE C11 emission requires a materialization plan"
        )
    if (
        declarations.abi_name != materialized.abi_name
        or declarations.abi_version != materialized.abi_version
        or declarations.function != materialized.function
        or declarations.queue != materialized.queue
    ):
        raise DeviceRuntimeC11EmissionError(
            "DEVICE C11 declaration and materialization identities diverge"
        )
    if declarations.point_ids != materialized.point_ids:
        raise DeviceRuntimeC11EmissionError(
            "DEVICE C11 declaration and materialization point order diverges"
        )
    if len(declarations.calls) != len(materialized.calls):
        raise DeviceRuntimeC11EmissionError(
            "DEVICE C11 declaration and materialization call counts diverge"
        )

    for storage in materialized.storage_declarations:
        if not isinstance(storage, str) or not _SAFE_STORAGE.fullmatch(storage):
            raise DeviceRuntimeC11EmissionError(
                "DEVICE C11 materialized storage is not in the reference subset"
            )

    prototype_by_operation = {
        prototype.operation: prototype for prototype in declarations.prototypes
    }
    statements: list[str] = []

    for declaration_call, materialized_call in zip(
        declarations.calls, materialized.calls, strict=True
    ):
        if (
            declaration_call.operation != materialized_call.operation
            or declaration_call.point_id != materialized_call.point_id
            or declaration_call.symbol != materialized_call.symbol
        ):
            raise DeviceRuntimeC11EmissionError(
                "DEVICE C11 materialized call diverges from declaration plan"
            )
        prototype = prototype_by_operation.get(materialized_call.operation)
        if prototype is None or prototype.symbol != materialized_call.symbol:
            raise DeviceRuntimeC11EmissionError(
                "DEVICE C11 call has no canonical prototype"
            )
        if len(materialized_call.arguments) != len(prototype.parameters):
            raise DeviceRuntimeC11EmissionError(
                "DEVICE C11 call argument count diverges from prototype"
            )
        for argument in materialized_call.arguments:
            if not isinstance(argument, str) or not _SAFE_ARGUMENT.fullmatch(argument):
                raise DeviceRuntimeC11EmissionError(
                    "DEVICE C11 materialized argument is outside the safe subset"
                )

        if materialized_call.operation == "synchronize":
            if (
                len(materialized_call.prelude) != 1
                or not _SAFE_COMPLETION_PRELUDE.fullmatch(materialized_call.prelude[0])
            ):
                raise DeviceRuntimeC11EmissionError(
                    "DEVICE C11 synchronization requires one canonical completion array"
                )
        elif materialized_call.prelude:
            raise DeviceRuntimeC11EmissionError(
                "DEVICE C11 non-synchronization call cannot inject prelude statements"
            )
        statements.extend(materialized_call.prelude)

        direct = materialized_call.direct_result_target
        has_direct_return = prototype.return_type != "void"
        if has_direct_return:
            if not isinstance(direct, str) or not _SAFE_IDENTIFIER.fullmatch(direct):
                raise DeviceRuntimeC11EmissionError(
                    "DEVICE C11 direct runtime result requires safe storage"
                )
        elif direct is not None:
            raise DeviceRuntimeC11EmissionError(
                "DEVICE C11 void runtime call cannot have a direct result target"
            )

        arguments = ", ".join(materialized_call.arguments)
        invocation = f"{materialized_call.symbol}({arguments});"
        if has_direct_return:
            invocation = f"{direct} = {invocation}"
        statements.append(invocation)

    for result in materialized.host_results:
        if (
            not _SAFE_IDENTIFIER.fullmatch(result.address_identifier)
            or not _SAFE_IDENTIFIER.fullmatch(result.extent_identifier)
        ):
            raise DeviceRuntimeC11EmissionError(
                "DEVICE C11 host result identifiers are outside the safe subset"
            )

    point_ids = tuple(call.point_id for call in materialized.calls)
    if point_ids != declarations.point_ids:
        raise DeviceRuntimeC11EmissionError(
            "DEVICE C11 emission lost source-stable lifecycle point identities"
        )

    return C11DeviceRuntimeEmissionPlan(
        abi_name=materialized.abi_name,
        abi_version=materialized.abi_version,
        function=materialized.function,
        queue=materialized.queue,
        point_ids=point_ids,
        declaration_source=declarations.render_declarations(),
        storage_declarations=materialized.storage_declarations,
        call_statements=tuple(statements),
        host_results=materialized.host_results,
    )
