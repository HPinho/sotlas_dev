"""Fail-closed interpreter for the straight-line integer Flow SIR subset."""
from __future__ import annotations

from threading import Event
from typing import Mapping

from .flow_graph import FlowDependency, FlowNode, certify_flow_graph
from .flow_runtime import FlowExecutionResult, execute_flow


_INTEGER_WIDTHS = {
    "u8": 8, "u16": 16, "u32": 32, "u64": 64, "usize": 64,
}
_BINARY_OPERATIONS = {"add": lambda left, right: left + right,
                      "sub": lambda left, right: left - right,
                      "mul": lambda left, right: left * right}


def _checked_unsigned(value, type_name: str, context: str) -> int:
    width = _INTEGER_WIDTHS.get(type_name)
    if width is None:
        raise ValueError(
            f"SIR Flow interpreter supports unsigned integer values, got {type_name!r}"
        )
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{context} must be an integer value")
    maximum = (1 << width) - 1
    if not 0 <= value <= maximum:
        raise ValueError(f"{context} is outside the range of {type_name}")
    return value


def _interpret_function(function, arguments: tuple[object, ...]) -> object:
    parameters = tuple(getattr(function, "parameters", ()) or ())
    blocks = tuple(getattr(function, "blocks", ()) or ())
    result_type = getattr(function, "return_type", None)
    if len(arguments) != len(parameters):
        raise ValueError(
            f"SIR function {function.name!r} received the wrong argument count"
        )
    if len(blocks) != 1:
        raise ValueError(
            f"SIR Flow interpreter requires one straight-line block in {function.name!r}"
        )

    values: dict[str, int] = {}
    for parameter, argument in zip(parameters, arguments):
        name = getattr(parameter, "name", None)
        type_name = getattr(parameter, "type_name", None)
        if not isinstance(name, str) or not name or name in values:
            raise ValueError(f"SIR function {function.name!r} has invalid parameters")
        values[name] = _checked_unsigned(
            argument, type_name, f"argument {name!r} to {function.name!r}"
        )

    def read(value, context: str) -> int:
        name = getattr(value, "name", None)
        type_name = getattr(value, "type_name", None)
        if not isinstance(name, str) or name not in values:
            raise ValueError(
                f"SIR function {function.name!r} reads undefined value {name!r}"
            )
        if type_name not in _INTEGER_WIDTHS:
            raise ValueError(f"{context} uses unsupported type {type_name!r}")
        return _checked_unsigned(values[name], type_name, context)

    instructions = tuple(getattr(blocks[0], "instructions", ()) or ())
    returned = False
    result = None
    for index, instruction in enumerate(instructions):
        kind = type(instruction).__name__
        if kind in {"AllocStackInst", "StoreInst"}:
            # The current frontend materializes scalar parameters in local
            # slots even when the expression uses their SSA parameter values.
            # Accept only the inert allocation + matching initialization pair.
            continue
        elif kind == "ConstantIntInst":
            target = getattr(instruction, "result", None)
            name = getattr(target, "name", None)
            type_name = getattr(target, "type_name", None)
            if not isinstance(name, str) or not name or name in values:
                raise ValueError(
                    f"SIR function {function.name!r} has an invalid SSA result"
                )
            values[name] = _checked_unsigned(
                instruction.value, type_name,
                f"constant in SIR function {function.name!r}",
            )
        elif kind == "BinaryOpInst":
            target = getattr(instruction, "result", None)
            target_name = getattr(target, "name", None)
            type_name = getattr(target, "type_name", None)
            operation = getattr(instruction, "operation", None)
            calculate = _BINARY_OPERATIONS.get(operation)
            left_value = getattr(instruction, "left", None)
            right_value = getattr(instruction, "right", None)
            if calculate is None:
                raise ValueError(
                    f"SIR Flow interpreter does not support operation {operation!r}"
                )
            if (
                not isinstance(target_name, str)
                or not target_name
                or target_name in values
                or getattr(left_value, "type_name", None) != type_name
                or getattr(right_value, "type_name", None) != type_name
            ):
                raise ValueError(
                    f"SIR function {function.name!r} has inconsistent arithmetic types"
                )
            left = read(left_value, f"left operand in {function.name!r}")
            right = read(right_value, f"right operand in {function.name!r}")
            width = _INTEGER_WIDTHS.get(type_name)
            if width is None:
                raise ValueError(f"SIR arithmetic uses unsupported type {type_name!r}")
            values[target_name] = calculate(left, right) & ((1 << width) - 1)
        elif kind == "ReturnInst":
            if returned or index != len(instructions) - 1:
                raise ValueError(
                    f"SIR function {function.name!r} has a non-terminal return"
                )
            value = getattr(instruction, "value", None)
            if value is None or getattr(value, "type_name", None) != result_type:
                raise ValueError(
                    f"SIR function {function.name!r} has an unsupported return"
                )
            result = read(value, f"return value from {function.name!r}")
            returned = True
        else:
            raise ValueError(
                f"SIR Flow interpreter does not support {kind} in {function.name!r}"
            )
    if not returned:
        raise ValueError(f"SIR function {function.name!r} has no supported return")
    return result


def execute_interpreted_sir_flow(
    sir_module,
    flow_name: str,
    *,
    max_workers: int | None = None,
    cancel_event: Event | None = None,
) -> FlowExecutionResult:
    """Interpret pure unsigned-integer stage bodies from one verified SIR Flow.

    This intentionally supports a much smaller subset than a native backend:
    stage functions must consist of one block with integer constants, unsigned
    ``add``/``sub``/``mul`` and a direct return. Calls, effects and control flow
    fail before the scheduler starts any stage.
    """
    from .flow_sir import FlowSIRError, validate_sir_flow_plans
    from .canonical_sir import load_canonical_sir

    EffectInferencePass = load_canonical_sir().EffectInferencePass
    plans = validate_sir_flow_plans(sir_module)
    matches = tuple(plan for plan in plans if plan.name == flow_name)
    if len(matches) != 1:
        raise FlowSIRError(
            f"SIR interpreter requires exactly one plan named {flow_name!r}"
        )
    inference = EffectInferencePass().run(sir_module)
    if not inference.success:
        raise FlowSIRError(
            "SIR effect inference failed before interpretation: "
            + "; ".join(inference.errors)
        )
    plan = matches[0]
    functions = {function.name: function for function in sir_module.functions}
    stages = {stage.name: stage for stage in plan.stages}
    stage_functions = {stage.function for stage in plan.stages}
    for stage in plan.stages:
        summary = sir_module.effect_summaries.get(stage.function)
        if summary is None or summary.transitive_effects or summary.unresolved_calls:
            raise FlowSIRError(
                f"SIR interpreter requires a pure stage function: {stage.function!r}"
            )
        function = functions[stage.function]
        if getattr(function, "is_system", False):
            raise FlowSIRError(
                f"SIR interpreter does not execute @system function {stage.function!r}"
            )
        if function.return_type not in _INTEGER_WIDTHS or any(
            getattr(parameter, "type_name", None) not in _INTEGER_WIDTHS
            for parameter in function.parameters
        ):
            raise FlowSIRError(
                f"SIR interpreter supports unsigned scalar stage signatures only: "
                f"{stage.function!r}"
            )
        for argument in stage.arguments:
            if argument.value.producer_function not in stage_functions:
                raise FlowSIRError(
                    f"Flow stage {stage.name!r} references a function outside its plan"
                )
        # Static shape and opcode validation runs before the scheduler starts.
        _validate_function_shape(function)

    graph = certify_flow_graph(
        tuple(FlowNode(stage.name) for stage in plan.stages),
        tuple(
            FlowDependency(argument.value.producer_stage, stage.name)
            for stage in plan.stages
            for argument in stage.arguments
        ),
    )
    if graph.parallel_stages != tuple(plan.parallel_stages):
        raise FlowSIRError("SIR Flow schedule changed before interpretation")

    actions = {}
    for stage in plan.stages:
        function = functions[stage.function]
        arguments = tuple(stage.arguments)

        def invoke(values, *, function=function, arguments=arguments):
            inputs = tuple(
                values[item.value.producer_stage] for item in arguments
            )
            return _interpret_function(function, inputs)

        actions[stage.name] = invoke
    return execute_flow(
        graph,
        actions,
        max_workers=max_workers,
        cancel_event=cancel_event,
    )


def _validate_function_shape(function) -> None:
    blocks = tuple(getattr(function, "blocks", ()) or ())
    if len(blocks) != 1:
        raise ValueError(
            f"SIR Flow interpreter requires one straight-line block in {function.name!r}"
        )
    instructions = tuple(getattr(blocks[0], "instructions", ()) or ())
    definitions = {parameter.name for parameter in function.parameters}
    parameter_types = {parameter.name: parameter.type_name for parameter in function.parameters}
    slots: dict[str, tuple[str, str]] = {}
    initialized_slots: set[str] = set()
    returned = False
    for index, instruction in enumerate(instructions):
        kind = type(instruction).__name__
        if kind == "AllocStackInst":
            result = getattr(instruction, "result", None)
            slot_name = getattr(result, "name", None)
            variable = getattr(instruction, "var_name", None)
            type_name = getattr(instruction, "type_name", None)
            if (
                not isinstance(slot_name, str)
                or slot_name in definitions
                or variable not in parameter_types
                or parameter_types[variable] != type_name
                or getattr(result, "type_name", None) != type_name
                or type_name not in _INTEGER_WIDTHS
            ):
                raise ValueError(f"SIR function {function.name!r} has an unsupported stack allocation")
            slots[slot_name] = (variable, type_name)
            definitions.add(slot_name)
        elif kind == "StoreInst":
            destination = getattr(instruction, "destination", None)
            source = getattr(instruction, "source", None)
            slot_name = getattr(destination, "name", None)
            slot = slots.get(slot_name)
            source_name = getattr(source, "name", None)
            if (
                slot is None
                or slot_name in initialized_slots
                or source_name != slot[0]
                or getattr(source, "type_name", None) != slot[1]
                or getattr(destination, "type_name", None) != slot[1]
            ):
                raise ValueError(f"SIR function {function.name!r} has an unsupported parameter store")
            initialized_slots.add(slot_name)
        elif kind == "ConstantIntInst":
            target = getattr(instruction, "result", None)
            name = getattr(target, "name", None)
            type_name = getattr(target, "type_name", None)
            if not isinstance(name, str) or name in definitions:
                raise ValueError(f"SIR function {function.name!r} repeats an SSA name")
            if type_name not in _INTEGER_WIDTHS:
                raise ValueError(f"SIR constant has unsupported type {type_name!r}")
            _checked_unsigned(instruction.value, type_name, "SIR constant")
            definitions.add(name)
        elif kind == "BinaryOpInst":
            target = getattr(instruction, "result", None)
            name = getattr(target, "name", None)
            type_name = getattr(target, "type_name", None)
            if getattr(instruction, "operation", None) not in _BINARY_OPERATIONS:
                raise ValueError(
                    f"SIR Flow interpreter does not support operation "
                    f"{getattr(instruction, 'operation', None)!r}"
                )
            if (
                not isinstance(name, str)
                or name in definitions
                or type_name not in _INTEGER_WIDTHS
                or getattr(instruction.left, "type_name", None) != type_name
                or getattr(instruction.right, "type_name", None) != type_name
                or instruction.left.name not in definitions
                or instruction.right.name not in definitions
            ):
                raise ValueError(
                    f"SIR function {function.name!r} has invalid arithmetic SSA facts"
                )
            definitions.add(name)
        elif kind == "ReturnInst":
            value = getattr(instruction, "value", None)
            if (
                returned
                or index != len(instructions) - 1
                or value is None
                or value.name not in definitions
                or value.type_name != function.return_type
            ):
                raise ValueError(
                    f"SIR function {function.name!r} has invalid return facts"
                )
            returned = True
        else:
            raise ValueError(
                f"SIR Flow interpreter does not support {kind} in {function.name!r}"
            )
    if initialized_slots != set(slots):
        raise ValueError(f"SIR function {function.name!r} has an uninitialized parameter slot")
    if not returned:
        raise ValueError(f"SIR function {function.name!r} has no direct return")


__all__ = ["execute_interpreted_sir_flow"]
