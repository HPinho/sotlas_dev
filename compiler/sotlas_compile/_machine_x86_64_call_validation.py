"""Validation contracts for Sotlas-owned x86-64 direct calls."""
from __future__ import annotations

from typing import Any

from . import _machine_x86_64_core as _core


MachineBackendError = _core.MachineBackendError


def module_signatures(target_ir: dict[str, Any]) -> dict[str, dict[str, Any]]:
    signatures: dict[str, dict[str, Any]] = {}
    for function in target_ir.get("functions", ()):
        name = function.get("name")
        if not isinstance(name, str) or _core._SYMBOL_RE.fullmatch(name) is None:
            raise MachineBackendError(f"invalid x86-64 symbol name {name!r}")
        if name in signatures:
            raise MachineBackendError(f"duplicate machine function symbol {name!r}")
        signatures[name] = {
            "parameters": tuple(
                parameter.get("type") for parameter in function.get("parameters", ())
            ),
            "return_type": function.get("return_type"),
        }
    return signatures


def validate_direct_calls(target_ir: dict[str, Any]) -> None:
    if not isinstance(target_ir, dict) or target_ir.get("schema") != "sotlas.target-ir.v1":
        raise MachineBackendError("x86-64 machine backend requires Target IR v1")

    signatures = module_signatures(target_ir)
    call_graph: dict[str, set[str]] = {name: set() for name in signatures}
    for function in target_ir.get("functions", ()):
        caller = function["name"]
        value_types = _core._type_map(function)
        for block in function.get("blocks", ()):
            for instruction in block.get("instructions", ()):
                if instruction.get("op") != "call":
                    continue
                if instruction.get("semantic_only"):
                    raise MachineBackendError(
                        f"function {caller!r}: semantic call cannot reach machine ABI lowering"
                    )
                attributes = instruction.get("attributes", {})
                callee = attributes.get("callee")
                if not isinstance(callee, str) or _core._SYMBOL_RE.fullmatch(callee) is None:
                    raise MachineBackendError(
                        f"function {caller!r}: direct call has an invalid callee symbol"
                    )
                if attributes.get("system"):
                    raise MachineBackendError(
                        f"function {caller!r}: system/foreign call {callee!r} is outside M16.3a"
                    )
                signature = signatures.get(callee)
                if signature is None:
                    raise MachineBackendError(
                        f"function {caller!r}: direct call target {callee!r} is not a module function"
                    )
                call_graph[caller].add(callee)

                operands = tuple(instruction.get("operands", ()))
                parameters = signature["parameters"]
                if len(operands) != len(parameters):
                    raise MachineBackendError(
                        f"function {caller!r}: call to {callee!r} has the wrong argument count"
                    )
                for index, (operand, parameter_type) in enumerate(
                    zip(operands, parameters, strict=True)
                ):
                    operand_type = value_types.get(operand)
                    if operand_type != parameter_type:
                        raise MachineBackendError(
                            f"function {caller!r}: call argument {index + 1} to {callee!r} "
                            f"has type {operand_type!r}, expected {parameter_type!r}"
                        )
                    _core._require_machine_scalar(
                        parameter_type,
                        context=f"function {caller!r} call argument {index + 1}",
                    )

                result = instruction.get("result")
                result_type = instruction.get("type")
                return_type = signature["return_type"]
                if return_type == "void":
                    if result is not None or result_type not in (None, "void"):
                        raise MachineBackendError(
                            f"function {caller!r}: void call to {callee!r} cannot produce a value"
                        )
                else:
                    _core._require_machine_scalar(
                        return_type,
                        context=f"function {caller!r} call return from {callee!r}",
                    )
                    if not isinstance(result, str) or not result:
                        raise MachineBackendError(
                            f"function {caller!r}: non-void call to {callee!r} requires a result"
                        )
                    if result_type != return_type or value_types.get(result) != return_type:
                        raise MachineBackendError(
                            f"function {caller!r}: call result type for {callee!r} must be {return_type!r}"
                        )

    state = {name: 0 for name in call_graph}

    def visit(name: str) -> None:
        if state[name] == 1:
            raise MachineBackendError(
                "recursive direct calls remain outside the M16.3a machine contract"
            )
        if state[name] == 2:
            return
        state[name] = 1
        for callee in sorted(call_graph[name]):
            visit(callee)
        state[name] = 2

    for name in sorted(call_graph):
        if state[name] == 0:
            visit(name)


def validate_abi_function_shape(function: dict[str, Any]) -> None:
    """Preserve core CFG proof rules while allowing SysV stack parameters."""
    name = function.get("name")
    if not isinstance(name, str) or _core._SYMBOL_RE.fullmatch(name) is None:
        raise MachineBackendError(f"invalid x86-64 symbol name {name!r}")
    for parameter in function.get("parameters", ()):
        _core._require_machine_scalar(
            parameter.get("type"),
            context=f"function {name!r} parameter {parameter.get('name')!r}",
        )
    return_type = function.get("return_type")
    if return_type != "void":
        _core._require_machine_scalar(return_type, context=f"function {name!r} return")

    blocks = function.get("blocks", ())
    if not blocks:
        raise MachineBackendError(f"function {name!r}: machine CFG has no blocks")
    labels = _core._block_label_map(function)
    value_types = _core._type_map(function)
    successors: dict[str, tuple[str, ...]] = {}
    for block in blocks:
        label = block["label"]
        instructions = block.get("instructions", ())
        if not instructions:
            raise MachineBackendError(f"function {name!r}: block {label!r} is empty")
        terminators = [
            index for index, instruction in enumerate(instructions)
            if instruction.get("op") in _core._TERMINATORS
        ]
        if terminators != [len(instructions) - 1]:
            raise MachineBackendError(
                f"function {name!r}: block {label!r} must end in exactly one terminator"
            )
        if any(instruction.get("op") == "phi" for instruction in instructions):
            raise MachineBackendError(
                f"function {name!r}: phi lowering waits for the edge-copy milestone"
            )
        terminator = instructions[-1]
        op = terminator.get("op")
        if op == "branch":
            targets = terminator.get("targets", ())
            if len(targets) != 1 or targets[0] not in labels:
                raise MachineBackendError(f"function {name!r}: branch has an invalid target")
            successors[label] = (targets[0],)
        elif op == "cond_branch":
            operands = terminator.get("operands", ())
            targets = terminator.get("targets", ())
            if len(operands) != 1:
                raise MachineBackendError(
                    f"function {name!r}: cond_branch requires one condition"
                )
            if value_types.get(operands[0]) != "bool":
                raise MachineBackendError(
                    f"function {name!r}: cond_branch condition must have type 'bool'"
                )
            if len(targets) != 2 or any(target not in labels for target in targets):
                raise MachineBackendError(
                    f"function {name!r}: cond_branch has invalid targets"
                )
            successors[label] = tuple(targets)
        else:
            successors[label] = ()

    allowed_backedges = _core._prove_bounded_loop_backedges(
        function, successors=successors, value_types=value_types
    )
    visit_state = {label: 0 for label in labels}

    def visit(label: str) -> None:
        if visit_state[label] == 2:
            return
        if visit_state[label] == 1:
            raise MachineBackendError(
                f"function {name!r}: CFG backedge lacks a bounded-loop proof"
            )
        visit_state[label] = 1
        for target in successors.get(label, ()):
            if visit_state[target] == 1:
                if (label, target) not in allowed_backedges:
                    raise MachineBackendError(
                        f"function {name!r}: CFG backedge lacks a bounded-loop proof"
                    )
                continue
            visit(target)
        visit_state[label] = 2

    for label in labels:
        if visit_state[label] == 0:
            visit(label)


__all__ = [
    "MachineBackendError",
    "module_signatures",
    "validate_direct_calls",
    "validate_abi_function_shape",
]
