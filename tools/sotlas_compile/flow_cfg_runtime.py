"""Scheduler execution for certified serial Flow executable CFGs.

This module consumes the actual ``CallInst`` sequence emitted by ``flow_cfg``.
It does not reconstruct execution from source Flow declarations. The call CFG is
revalidated first, then each referenced stage body is checked against the same
pure unsigned/bool interpreter subset used by ``execute_interpreted_sir_flow``.

The initial executable CFG is intentionally serial and copy-safe. Ownership,
cleanup-bearing values and true parallel call CFGs remain fail-closed until their
SIR contracts are implemented.
"""
from __future__ import annotations

from threading import Event

from .canonical_sir import load_canonical_sir
from .flow_cfg import FlowCFGError, FlowExecutableCFG, validate_serial_flow_cfg
from .flow_graph import FlowDependency, FlowNode, certify_flow_graph
from .flow_runtime import FlowExecutionResult, execute_flow


class FlowCFGExecutionError(FlowCFGError):
    """Raised when a certified Flow call CFG cannot be safely executed."""


def execute_serial_flow_cfg(
    sir_module,
    cfg: FlowExecutableCFG,
    *,
    cancel_event: Event | None = None,
) -> FlowExecutionResult:
    """Execute one certified serial Flow call CFG through the local scheduler.

    Execution is derived from the generated ``CallInst`` arguments/results and
    the external call-point certificate after full reconciliation. Stage bodies
    are interpreted from canonical SIR; host bindings are not accepted.
    """
    cfg = validate_serial_flow_cfg(sir_module, cfg)
    sir = load_canonical_sir()
    module = getattr(sir_module, "module", sir_module)

    inference = sir.EffectInferencePass().run(module)
    if not inference.success:
        raise FlowCFGExecutionError(
            "SIR effect inference failed before Flow CFG execution: "
            + "; ".join(inference.errors)
        )

    from .flow_interpreter import (
        _INTEGER_WIDTHS,
        _interpret_function,
        _validate_function_shape,
    )

    functions = {function.name: function for function in module.functions}
    block = cfg.function.blocks[0]
    call_instructions = tuple(block.instructions[:-1])
    if len(call_instructions) != len(cfg.calls):
        raise FlowCFGExecutionError(
            f"Flow CFG {cfg.plan_name!r} changed after validation"
        )

    # Derive dependencies from the actual generated SSA arguments. The external
    # certificate is then required to agree with those call edges.
    result_stage: dict[str, str] = {}
    runtime_calls = []
    for point, instruction in zip(cfg.calls, call_instructions):
        if not isinstance(instruction, sir.CallInst):
            raise FlowCFGExecutionError(
                f"Flow stage {point.stage_name!r} executable instruction is not a call"
            )
        function = functions.get(instruction.callee)
        if function is None:
            raise FlowCFGExecutionError(
                f"Flow stage {point.stage_name!r} lost function {instruction.callee!r}"
            )
        summary = module.effect_summaries.get(instruction.callee)
        if (
            summary is None
            or tuple(getattr(summary, "transitive_effects", ()))
            or tuple(getattr(summary, "unresolved_calls", ()))
        ):
            raise FlowCFGExecutionError(
                f"Flow CFG execution requires pure stage function {instruction.callee!r}"
            )
        if getattr(function, "is_system", False):
            raise FlowCFGExecutionError(
                f"Flow CFG execution does not execute @system function {instruction.callee!r}"
            )
        if function.return_type not in (*_INTEGER_WIDTHS, "bool") or any(
            getattr(parameter, "type_name", None) not in _INTEGER_WIDTHS
            for parameter in function.parameters
        ):
            raise FlowCFGExecutionError(
                "Flow CFG interpreter supports unsigned scalar stage signatures only: "
                f"{instruction.callee!r}"
            )
        try:
            _validate_function_shape(function)
        except (TypeError, ValueError) as error:
            raise FlowCFGExecutionError(str(error)) from error

        argument_stages = []
        for argument in instruction.arguments:
            producer = result_stage.get(argument.name)
            if producer is None:
                raise FlowCFGExecutionError(
                    f"Flow stage {point.stage_name!r} reads non-dominating CFG value "
                    f"{argument.name!r}"
                )
            argument_stages.append(producer)
        argument_stages = tuple(argument_stages)
        if argument_stages != point.argument_stages:
            raise FlowCFGExecutionError(
                f"Flow stage {point.stage_name!r} CFG arguments diverge from provenance"
            )
        result_stage[instruction.result.name] = point.stage_name
        runtime_calls.append((point.stage_name, function, argument_stages))

    graph = certify_flow_graph(
        tuple(FlowNode(stage_name) for stage_name, _, _ in runtime_calls),
        tuple(
            FlowDependency(producer, stage_name)
            for stage_name, _, producers in runtime_calls
            for producer in producers
        ),
    )
    expected_layers = tuple((point.stage_name,) for point in cfg.calls)
    if graph.parallel_stages != expected_layers:
        raise FlowCFGExecutionError(
            f"Flow CFG {cfg.plan_name!r} no longer has the certified serial schedule"
        )

    actions = {}
    for stage_name, function, argument_stages in runtime_calls:
        def invoke(values, *, function=function, argument_stages=argument_stages):
            arguments = tuple(values[producer] for producer in argument_stages)
            return _interpret_function(function, arguments)

        actions[stage_name] = invoke

    return execute_flow(
        graph,
        actions,
        max_workers=1,
        cancel_event=cancel_event,
    )


__all__ = [
    "FlowCFGExecutionError",
    "execute_serial_flow_cfg",
]
