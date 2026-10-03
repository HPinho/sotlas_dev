"""Validation contracts for Sotlas-owned x86-64 direct calls."""
from __future__ import annotations

from typing import Any

from . import _machine_x86_64_core as _core
from ._machine_x86_64_types import require_abi_scalar


MachineBackendError = _core.MachineBackendError


def function_linkage(function: dict[str, Any]) -> str:
    """Validate one Target IR function's symbol-linkage contract.

    Target IR created before M16.3d may omit linkage metadata; that historical
    form remains externally linked until its producer migrates explicitly.
    """
    name = function.get("name")
    linkage = function.get("linkage", "external")
    if linkage not in {"internal", "external"}:
        raise MachineBackendError(
            f"function {name!r}: invalid symbol linkage {linkage!r}"
        )

    visibility = function.get("source_visibility")
    if visibility is not None and visibility not in {"private", "public"}:
        raise MachineBackendError(
            f"function {name!r}: invalid source visibility {visibility!r}"
        )
    abi_export = function.get("abi_export")
    if abi_export is not None and not isinstance(abi_export, bool):
        raise MachineBackendError(
            f"function {name!r}: abi_export must be boolean"
        )

    if visibility == "public" and linkage != "external":
        raise MachineBackendError(
            f"function {name!r}: public source visibility requires external linkage"
        )
    if abi_export is True and linkage != "external":
        raise MachineBackendError(
            f"function {name!r}: @export requires external linkage"
        )
    return linkage


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
    """Validate the scalar module-local SysV direct-call contract.

    M16.3e deliberately treats recursive edges exactly like any other validated
    direct edge. Self-recursive and mutually recursive call graphs therefore use
    ordinary ABI stack frames; this layer neither proves nor promises a maximum
    recursion depth. Deterministic/realtime/freestanding profiles that require a
    depth bound must enforce that policy before machine ABI lowering. M16.4a
    extends scalar ABI transport to canonical pointer values without admitting
    pointer arithmetic or aggregate ABI lowering.
    """
    if not isinstance(target_ir, dict) or target_ir.get("schema") != "sotlas.target-ir.v1":
        raise MachineBackendError("x86-64 machine backend requires Target IR v1")

    signatures = module_signatures(target_ir)
    for function in target_ir.get("functions", ()):
        caller = function["name"]
        value_types = _core._type_map(function)
        seen_system_points: set[str] = set()
        for block in function.get("blocks", ()):
            for instruction in block.get("instructions", ()):
                if instruction.get("op") == "system_op":
                    attributes = instruction.get("attributes", {})
                    symbol = attributes.get("symbol")
                    point_id = attributes.get("point_id")
                    required = {
                        "__cli": ["cpu.interrupts"],
                        "__sti": ["cpu.interrupts"],
                    }.get(symbol)
                    if required is None or attributes.get("capabilities") != required:
                        raise MachineBackendError(
                            f"function {caller!r}: unsupported or unauthorized machine intrinsic {symbol!r}"
                        )
                    if (
                        instruction.get("operands")
                        or instruction.get("result") is not None
                        or not isinstance(point_id, str)
                        or not point_id.startswith("call@")
                        or point_id in seen_system_points
                    ):
                        raise MachineBackendError(
                            f"function {caller!r}: malformed or duplicate machine intrinsic source point"
                        )
                    seen_system_points.add(point_id)
                    continue
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
                    require_abi_scalar(
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
                    require_abi_scalar(
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


def validate_abi_function_shape(function: dict[str, Any]) -> None:
    """Preserve core CFG proof rules while allowing SysV stack parameters."""
    name = function.get("name")
    if not isinstance(name, str) or _core._SYMBOL_RE.fullmatch(name) is None:
        raise MachineBackendError(f"invalid x86-64 symbol name {name!r}")
    function_linkage(function)
    for parameter in function.get("parameters", ()):
        require_abi_scalar(
            parameter.get("type"),
            context=f"function {name!r} parameter {parameter.get('name')!r}",
        )
    return_type = function.get("return_type")
    if return_type != "void":
        require_abi_scalar(return_type, context=f"function {name!r} return")

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
    "function_linkage",
    "module_signatures",
    "validate_direct_calls",
    "validate_abi_function_shape",
]
