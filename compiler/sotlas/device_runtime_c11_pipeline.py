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

import importlib
import sys
from dataclasses import dataclass
from pathlib import Path
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
class DeviceSourceRuntimeC11Artifact:
    """C11 reference artifact composed from one canonical checked source module."""

    checked_runtime: object
    backend: "C11DeviceRuntimeBackendArtifact"

    @property
    def point_ids(self) -> tuple[str, ...]:
        return self.backend.point_ids

    @property
    def declaration_source(self) -> str:
        return self.backend.declaration_source

    @property
    def body_source(self) -> str:
        return self.backend.body_source

    @property
    def host_results(self) -> tuple[C11DeviceOwnerResult, ...]:
        return self.backend.host_results


@dataclass(frozen=True)
class C11DeviceRuntimeBackendArtifact:
    abi_name: str
    abi_version: int
    function: str
    queue: str
    point_ids: tuple[str, ...]
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
    if emission.point_ids != logical_plan.point_ids:
        raise DeviceRuntimeC11PipelineError(
            "DEVICE C11 backend artifact changed source-stable lifecycle identities"
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
        point_ids=emission.point_ids,
        declaration_source=declaration_source,
        body_source=emission.render_body(),
        host_results=emission.host_results,
        emission=emission,
    )


def lower_checked_device_source_to_reference_c11(
    checked_module: object,
    *,
    function: str,
    queue: str,
    completion_point_ids: Iterable[str],
    synchronization_point_id: str,
    reacquisition_point_ids: Iterable[str],
    host_owners: Iterable[C11DeviceOwnerSource],
    queue_identifier: str = "__sotlas_device_queue",
    sir_values: dict[str, tuple[object, object]] | None = None,
    include_standard_headers: bool = False,
) -> DeviceSourceRuntimeC11Artifact:
    """Compose checked source ownership, SIR, ABI and reference C11 lowering.

    SIR values must be supplied explicitly when their compiler-specific value
    type is needed. When omitted, deterministic bindings are derived from the
    canonical source owner names and their checked nominal types.
    """
    package_name = checked_module.__class__.__module__.rsplit(".", 1)[0]
    try:
        phase1_module = importlib.import_module(f"{package_name}.phase1_pipeline")
        package_path = phase1_module.__file__
        compiler_root = Path(package_path).parent.parent
        if str(compiler_root) not in sys.path:
            sys.path.insert(0, str(compiler_root))
        elif sys.path[0] != str(compiler_root):
            sys.path.remove(str(compiler_root))
            sys.path.insert(0, str(compiler_root))
        frontend_module = importlib.import_module(f"{package_name}.device_frontend")
        lifecycle_module = importlib.import_module(f"{package_name}.device_lifecycle")
        abi_module = importlib.import_module(f"{package_name}.device_runtime_abi")
        typed_module = importlib.import_module(f"{package_name}.typed_ast")
    except (ImportError, AttributeError) as error:
        raise DeviceRuntimeC11PipelineError(
            "DEVICE source-to-C11 composition cannot load its checked compiler package"
        ) from error

    plan_checked_device_runtime = frontend_module.plan_checked_device_runtime
    DeviceLifecycleSourcePoints = lifecycle_module.DeviceLifecycleSourcePoints
    DeviceRuntimeABIContract = abi_module.DeviceRuntimeABIContract
    DeviceRuntimeABISymbol = abi_module.DeviceRuntimeABISymbol
    DeviceRuntimeOperation = abi_module.DeviceRuntimeOperation
    bind_device_runtime_abi = abi_module.bind_device_runtime_abi
    # The SIR bridge may load a second mirror of the compiler package. Bind the
    # structural graph check to the class that produced this checked module.
    frontend_module.OwnershipDomainGraph = typed_module.OwnershipDomainGraph
    from .device_runtime_c11 import (
        CANONICAL_C11_DEVICE_SYMBOLS,
        REFERENCE_C11_DEVICE_ABI_NAME,
        REFERENCE_C11_DEVICE_ABI_VERSION,
    )
    try:
        sir_package = f"{__package__}.sir"
        SIRValue = importlib.import_module(
            f"{sir_package}.instructions"
        ).SIRValue
        sir_frontend_runtime = importlib.import_module(
            f"{sir_package}.device_frontend_runtime"
        )
        DeviceRuntimeSIRValueBinding = sir_frontend_runtime.DeviceRuntimeSIRValueBinding
        lower_device_frontend_runtime_to_sir = (
            sir_frontend_runtime.lower_device_frontend_runtime_to_sir
        )
        plan_bound_device_runtime_calls = importlib.import_module(
            f"{sir_package}.device_runtime_calls"
        ).plan_bound_device_runtime_calls
        plan_device_runtime_lowering = importlib.import_module(
            f"{sir_package}.device_runtime_lowering"
        ).plan_device_runtime_lowering
    except ImportError as error:
        raise DeviceRuntimeC11PipelineError(
            "DEVICE source-to-C11 composition requires the canonical SIR runtime bridges"
        ) from error

    points = DeviceLifecycleSourcePoints(
        completion_point_ids=tuple(completion_point_ids),
        synchronization_point_id=synchronization_point_id,
        reacquisition_point_ids=tuple(reacquisition_point_ids),
    )
    try:
        checked_runtime = plan_checked_device_runtime(
            checked_module,
            function=function,
            queue=queue,
            points=points,
        )
    except (TypeError, ValueError) as error:
        raise DeviceRuntimeC11PipelineError(
            f"DEVICE source ownership could not be certified: {error}"
        ) from error

    if sir_values is None:
        source_types = {
            node.binding: getattr(node.type, "name", node.type)
            for node in checked_runtime.graph.nodes
            if node.function == function
        }
        sir_value_bindings = tuple(
            (
                binding,
                SIRValue(f"__sotlas_device_{binding}", source_types[binding]),
                SIRValue(f"__sotlas_host_{binding}", source_types[binding]),
            )
            for binding in checked_runtime.bindings
        )
    else:
        if set(sir_values) != set(checked_runtime.bindings):
            raise DeviceRuntimeC11PipelineError(
                "DEVICE explicit SIR value bindings must match checked owner bindings exactly"
            )
        try:
            sir_value_bindings = tuple(
                (binding, *sir_values[binding])
                for binding in checked_runtime.bindings
            )
        except (TypeError, ValueError) as error:
            raise DeviceRuntimeC11PipelineError(
                "DEVICE explicit SIR value bindings are malformed"
            ) from error

    try:
        sir_plan = lower_device_frontend_runtime_to_sir(
            checked_runtime.runtime,
            tuple(
                DeviceRuntimeSIRValueBinding(*binding)
                for binding in sir_value_bindings
            ),
        )
        logical_contract = DeviceRuntimeABIContract(
            name=REFERENCE_C11_DEVICE_ABI_NAME,
            version=REFERENCE_C11_DEVICE_ABI_VERSION,
            symbols=tuple(
                DeviceRuntimeABISymbol(DeviceRuntimeOperation(operation), symbol)
                for operation, symbol in CANONICAL_C11_DEVICE_SYMBOLS.items()
            ),
        )
        bound_logical = bind_device_runtime_abi(
            checked_runtime.runtime.runtime,
            logical_contract,
        )
        calls = plan_bound_device_runtime_calls(sir_plan.bridge, bound_logical)
        logical = plan_device_runtime_lowering(calls)
        backend = lower_device_runtime_plan_to_reference_c11(
            logical,
            queue_identifier=queue_identifier,
            host_owners=host_owners,
            include_standard_headers=include_standard_headers,
        )
    except (TypeError, ValueError, KeyError) as error:
        raise DeviceRuntimeC11PipelineError(
            f"DEVICE source-to-C11 lowering failed closed: {error}"
        ) from error

    if backend.point_ids != checked_runtime.point_ids:
        raise DeviceRuntimeC11PipelineError(
            "DEVICE source-to-C11 composition changed checked lifecycle identities"
        )
    return DeviceSourceRuntimeC11Artifact(checked_runtime, backend)
