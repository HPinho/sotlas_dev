"""Executable SIR CFG lowering for the serial Sotlas Flow subset.

The declarative ``FlowSIRPlan`` remains the canonical orchestration contract.
This module materializes that contract as an ordinary ``SIRFunction`` only when
the plan is strictly serial: every canonical parallel layer contains exactly one
stage. Parallel plans stay fail-closed until SIR has an execution contract that
can preserve concurrency instead of silently serializing it.

The first executable subset is also deliberately restricted to primitive scalar
values. Nominal, pointer/reference and typestate values can carry ownership or
lifetime obligations that Flow does not yet integrate into its executable CFG;
they therefore fail closed instead of being copied as ordinary SSA values.

Stage identity/provenance is kept in an external certificate rather than being
smuggled into unrelated ``CallInst`` fields. The generated CFG is revalidated
against the canonical Flow plan before it is returned.
"""
from __future__ import annotations

from dataclasses import dataclass

from .canonical_sir import load_canonical_sir
from .flow_sir import FlowSIRError, validate_sir_flow_plans


class FlowCFGError(FlowSIRError):
    """Raised when a Flow plan cannot be represented by the executable CFG subset."""


_COPY_SAFE_SCALAR_TYPES = frozenset({
    "bool",
    "u8", "u16", "u32", "u64", "usize",
    "i8", "i16", "i32", "i64", "isize",
    "f32", "f64",
})


@dataclass(frozen=True)
class FlowCFGCallPoint:
    plan_name: str
    stage_name: str
    stage_function: str
    block_label: str
    instruction_index: int
    result_name: str
    result_type: str
    argument_stages: tuple[str, ...]


@dataclass(frozen=True)
class FlowExecutableCFG:
    plan_name: str
    function_name: str
    function: object
    calls: tuple[FlowCFGCallPoint, ...]
    final_stage: str
    result_type: str


def _unwrap_module(value):
    sir = load_canonical_sir()
    module = getattr(value, "module", value)
    if not isinstance(module, sir.SIRModule):
        raise FlowCFGError("Flow executable CFG requires a canonical SIRModule")
    return sir, module


def _select_plan(module, flow_name: str):
    plans = validate_sir_flow_plans(module)
    matches = tuple(plan for plan in plans if plan.name == flow_name)
    if len(matches) != 1:
        raise FlowCFGError(
            f"Flow executable CFG requires exactly one plan named {flow_name!r}"
        )
    return matches[0]


def _serial_stage_order(plan) -> tuple[str, ...]:
    layers = tuple(plan.parallel_stages)
    if not layers or not tuple(plan.stages):
        raise FlowCFGError(f"Flow plan {plan.name!r} has no executable stages")
    if any(len(layer) != 1 for layer in layers):
        raise FlowCFGError(
            f"Flow plan {plan.name!r} is not strictly serial; executable CFG "
            "currently rejects parallel stages"
        )
    order = tuple(layer[0] for layer in layers)
    declared = tuple(stage.name for stage in plan.stages)
    if len(order) != len(declared) or set(order) != set(declared):
        raise FlowCFGError(
            f"Flow plan {plan.name!r} serial schedule does not cover its stages"
        )
    return order


def _require_copy_safe_types(plan) -> None:
    """Reject values whose ownership/lifetime semantics are not integrated yet."""
    for stage in plan.stages:
        if stage.result_type not in _COPY_SAFE_SCALAR_TYPES:
            raise FlowCFGError(
                f"Flow stage {stage.name!r} executable CFG does not yet integrate "
                f"ownership/lifetime semantics for type {stage.result_type!r}"
            )
        for argument in stage.arguments:
            if (
                argument.type_name not in _COPY_SAFE_SCALAR_TYPES
                or argument.value.type_name not in _COPY_SAFE_SCALAR_TYPES
            ):
                raise FlowCFGError(
                    f"Flow stage {stage.name!r} executable CFG does not yet integrate "
                    f"ownership/lifetime semantics for type {argument.type_name!r}"
                )


def _generated_function_name(flow_name: str) -> str:
    return f"__sotlas_flow_{flow_name}"


def lower_serial_flow_to_cfg(sir_module, flow_name: str) -> FlowExecutableCFG:
    """Lower one strictly serial Flow plan to a revalidated SIR call CFG.

    The generated function has no parameters because root Flow stages are
    already required to have no dependencies/parameters. Every stage result is
    an SSA value and consumer calls receive only the producer results certified
    by ``FlowSIRArgument`` provenance. The final stage result becomes the
    function return value.

    Until Flow is integrated with Ownership, only primitive scalar values may
    cross stage boundaries in this executable representation.
    """
    sir, module = _unwrap_module(sir_module)
    plan = _select_plan(module, flow_name)
    order = _serial_stage_order(plan)
    _require_copy_safe_types(plan)
    stages = {stage.name: stage for stage in plan.stages}
    functions = {function.name: function for function in module.functions}

    function_name = _generated_function_name(plan.name)
    if function_name in functions:
        raise FlowCFGError(
            f"Flow executable CFG function {function_name!r} already exists"
        )

    final_stage = stages[order[-1]]
    generated = sir.SIRFunction(function_name, [], final_stage.result_type)
    block = generated.add_block("entry")
    outputs = {}
    points: list[FlowCFGCallPoint] = []

    for stage_name in order:
        stage = stages[stage_name]
        callee = functions.get(stage.function)
        if callee is None:
            raise FlowCFGError(
                f"Flow stage {stage.name!r} has no canonical SIR function"
            )
        arguments = []
        argument_stages = []
        for argument in stage.arguments:
            producer_name = argument.value.producer_stage
            producer_value = outputs.get(producer_name)
            if producer_value is None:
                raise FlowCFGError(
                    f"Flow stage {stage.name!r} depends on {producer_name!r} "
                    "before that producer dominates the serial CFG"
                )
            if producer_value.type_name != argument.type_name:
                raise FlowCFGError(
                    f"Flow stage {stage.name!r} dependency type changed before CFG lowering"
                )
            arguments.append(producer_value)
            argument_stages.append(producer_name)

        result = sir.SIRValue(
            f"flow_{plan.name}_{stage.name}_result",
            stage.result_type,
        )
        instruction_index = len(block.instructions)
        block.add(sir.CallInst(
            stage.function,
            list(arguments),
            result,
            is_system=bool(getattr(callee, "is_system", False)),
        ))
        outputs[stage.name] = result
        points.append(FlowCFGCallPoint(
            plan.name,
            stage.name,
            stage.function,
            block.label,
            instruction_index,
            result.name,
            result.type_name,
            tuple(argument_stages),
        ))

    block.add(sir.ReturnInst(outputs[order[-1]]))
    certificate = FlowExecutableCFG(
        plan.name,
        function_name,
        generated,
        tuple(points),
        order[-1],
        final_stage.result_type,
    )
    validate_serial_flow_cfg(module, certificate)
    return certificate


def validate_serial_flow_cfg(sir_module, cfg: FlowExecutableCFG) -> FlowExecutableCFG:
    """Reconcile one generated serial Flow CFG with the canonical SIR plan."""
    sir, module = _unwrap_module(sir_module)
    if not isinstance(cfg, FlowExecutableCFG):
        raise FlowCFGError("Flow CFG validation requires a FlowExecutableCFG")
    plan = _select_plan(module, cfg.plan_name)
    order = _serial_stage_order(plan)
    _require_copy_safe_types(plan)
    stages = {stage.name: stage for stage in plan.stages}
    functions = {function.name: function for function in module.functions}

    expected_name = _generated_function_name(plan.name)
    function = cfg.function
    if (
        not isinstance(function, sir.SIRFunction)
        or cfg.function_name != expected_name
        or function.name != expected_name
        or tuple(function.parameters)
    ):
        raise FlowCFGError(f"Flow plan {plan.name!r} has an invalid executable function")
    final_stage = stages[order[-1]]
    if cfg.final_stage != order[-1] or cfg.result_type != final_stage.result_type:
        raise FlowCFGError(f"Flow plan {plan.name!r} final result facts changed")
    if function.return_type != cfg.result_type:
        raise FlowCFGError(f"Flow plan {plan.name!r} executable return type changed")

    blocks = tuple(function.blocks)
    if len(blocks) != 1 or blocks[0].label != "entry":
        raise FlowCFGError(
            f"Flow plan {plan.name!r} executable CFG requires one entry block"
        )
    instructions = tuple(blocks[0].instructions)
    if len(instructions) != len(order) + 1:
        raise FlowCFGError(
            f"Flow plan {plan.name!r} executable CFG instruction count changed"
        )
    if len(cfg.calls) != len(order):
        raise FlowCFGError(f"Flow plan {plan.name!r} call certificate is incomplete")

    outputs = {}
    seen_results = set()
    for index, (stage_name, point) in enumerate(zip(order, cfg.calls)):
        stage = stages[stage_name]
        instruction = instructions[index]
        callee = functions.get(stage.function)
        if callee is None:
            raise FlowCFGError(
                f"Flow stage {stage.name!r} lost its canonical SIR function"
            )
        if not isinstance(instruction, sir.CallInst):
            raise FlowCFGError(
                f"Flow stage {stage.name!r} executable instruction is not a call"
            )
        if (
            point.plan_name != plan.name
            or point.stage_name != stage.name
            or point.stage_function != stage.function
            or point.block_label != "entry"
            or point.instruction_index != index
        ):
            raise FlowCFGError(
                f"Flow stage {stage.name!r} call identity diverges from its plan"
            )
        if (
            instruction.callee != stage.function
            or instruction.is_system != bool(getattr(callee, "is_system", False))
            or instruction.defer_point_id is not None
        ):
            raise FlowCFGError(
                f"Flow stage {stage.name!r} executable callee facts changed"
            )
        result = instruction.result
        if (
            result is None
            or result.name != point.result_name
            or result.type_name != point.result_type
            or result.type_name != stage.result_type
            or result.name in seen_results
        ):
            raise FlowCFGError(
                f"Flow stage {stage.name!r} executable result facts changed"
            )
        seen_results.add(result.name)

        if len(instruction.arguments) != len(stage.arguments):
            raise FlowCFGError(
                f"Flow stage {stage.name!r} executable argument count changed"
            )
        expected_argument_stages = tuple(
            argument.value.producer_stage for argument in stage.arguments
        )
        if point.argument_stages != expected_argument_stages:
            raise FlowCFGError(
                f"Flow stage {stage.name!r} call provenance changed"
            )
        for actual, argument in zip(instruction.arguments, stage.arguments):
            producer = outputs.get(argument.value.producer_stage)
            if producer is None:
                raise FlowCFGError(
                    f"Flow stage {stage.name!r} reads a non-dominating producer"
                )
            if (
                actual.name != producer.name
                or actual.type_name != producer.type_name
                or actual.type_name != argument.type_name
            ):
                raise FlowCFGError(
                    f"Flow stage {stage.name!r} executable argument provenance changed"
                )
        outputs[stage.name] = result

    terminator = instructions[-1]
    final_value = outputs[order[-1]]
    if (
        not isinstance(terminator, sir.ReturnInst)
        or terminator.point_id is not None
        or terminator.value is None
        or terminator.value.name != final_value.name
        or terminator.value.type_name != final_value.type_name
    ):
        raise FlowCFGError(
            f"Flow plan {plan.name!r} executable return no longer matches final stage"
        )
    return cfg


__all__ = [
    "FlowCFGError",
    "FlowCFGCallPoint",
    "FlowExecutableCFG",
    "lower_serial_flow_to_cfg",
    "validate_serial_flow_cfg",
]
