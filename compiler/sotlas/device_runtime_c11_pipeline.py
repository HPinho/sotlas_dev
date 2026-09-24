"""Isolated reference C11 backend pipeline for proven DEVICE runtime plans.

This is a backend entrypoint, not a source-language feature.  It accepts only an
already-proven ``DeviceRuntimeLoweringPlan`` plus explicit host C identifiers,
then runs the complete reference chain:

logical ABI -> physical C11 ABI -> declarations -> operand materialization ->
validated call emission.

The result is a C11 fragment artifact.  It does not provide a runtime library,
link a device driver, submit hardware work or make DEVICE globally supported in
CodegenC.  A future frontend integration can consume this entrypoint without
reconstructing any ABI/lifecycle detail.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .device_runtime_c11 import (
    plan_reference_c11_device_runtime,
    reference_c11_device_runtime_contract,
)
from .device_runtime_c11_embed import (
    render_reference_c11_device_runtime_declarations,
)
from .device_runtime_c11_emit import (
    C11DeviceRuntimeEmissionPlan,
    emit_reference_c11_device_runtime_calls,
)
from .device_runtime_c11_materialize import (
    C11DeviceOwnerResult,
    C11DeviceOwnerSource,
    materialize_reference_c11_device_runtime,
)
from .sir.device_runtime_lowering import DeviceRuntimeLoweringPlan
from .sir.device_runtime_physical_abi import bind_device_runtime_physical_abi


class DeviceRuntimeC11PipelineError(ValueError):
    """Raised when the isolated DEVICE C11 backend entrypoint is misused."""


@dataclass(frozen=True)
class C11DeviceRuntimeBackendArtifact:
    abi_name: str
    abi_version: int
    function: str
    queue: str
    declaration_source: str
    body_source: str
    host_results: tuple[C11DeviceOwnerResult, ...]
    emission: C11DeviceRuntimeEmissionPlan


def lower_device_runtime_plan_to_reference_c11(
    logical_plan: DeviceRuntimeLoweringPlan,
    *,
    queue_identifier: str,
    host_owners: Iterable[C11DeviceOwnerSource],
    include_standard_headers: bool = False,
) -> C11DeviceRuntimeBackendArtifact:
    """Lower one proven DEVICE lifecycle to an isolated reference C11 fragment."""
    if not isinstance(logical_plan, DeviceRuntimeLoweringPlan):
        raise DeviceRuntimeC11PipelineError(
            "DEVICE C11 backend requires a proven logical lowering plan"
        )

    bound = bind_device_runtime_physical_abi(
        logical_plan,
        reference_c11_device_runtime_contract(),
    )
    declarations = plan_reference_c11_device_runtime(bound)
    materialized = materialize_reference_c11_device_runtime(
        declarations,
        bound,
        queue_identifier=queue_identifier,
        host_owners=host_owners,
    )
    emission = emit_reference_c11_device_runtime_calls(
        declarations,
        materialized,
    )
    declaration_source = render_reference_c11_device_runtime_declarations(
        declarations,
        include_standard_headers=include_standard_headers,
    )

    if emission.abi_name != logical_plan.abi_name:
        raise DeviceRuntimeC11PipelineError(
            "DEVICE C11 backend artifact changed ABI identity"
        )
    if emission.abi_version != logical_plan.abi_version:
        raise DeviceRuntimeC11PipelineError(
            "DEVICE C11 backend artifact changed ABI version"
        )
    if emission.function != logical_plan.function or emission.queue != logical_plan.queue:
        raise DeviceRuntimeC11PipelineError(
            "DEVICE C11 backend artifact changed function/queue identity"
        )
    if emission.host_results and len(emission.host_results) != sum(
        1 for call in logical_plan.calls if call.operation == "submit"
    ):
        raise DeviceRuntimeC11PipelineError(
            "DEVICE C11 backend artifact lost reacquired owners"
        )

    return C11DeviceRuntimeBackendArtifact(
        abi_name=emission.abi_name,
        abi_version=emission.abi_version,
        function=emission.function,
        queue=emission.queue,
        declaration_source=declaration_source,
        body_source=emission.render_body(),
        host_results=emission.host_results,
        emission=emission,
    )
