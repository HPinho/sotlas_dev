"""Canonical Sotlas-owned x86-64 SysV backend orchestration.

The public layer performs M16.2c SSA destruction first: leading scalar phi nodes
become private stack-backed edge copies. The machine core then proves the
M16.2d bounded-loop subset, while the M16.3 ABI layer handles validated
module-local direct calls with SysV register/stack arguments, RAX returns,
aligned call sites and explicit preservation of caller-saved value registers.

M16.3b preserves typed SIR call results across the Target IR boundary, M16.3d
preserves source linkage, and M16.3e admits self/mutual recursion through the
same ordinary direct-call ABI. Indirect/foreign calls and aggregate ABI lowering
remain fail-closed.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from . import _machine_x86_64_calls as _calls
from . import _machine_x86_64_core as _core
from .target_ir_calls import lower_sir_to_typed_target_ir


MachineBackendError = _core.MachineBackendError


def _value_types(function: dict[str, Any]) -> dict[str, str]:
    types: dict[str, str] = {}
    for parameter in function.get("parameters", ()):
        name = parameter.get("name")
        type_name = parameter.get("type")
        if isinstance(name, str) and isinstance(type_name, str):
            types[name] = type_name
    for block in function.get("blocks", ()):
        for instruction in block.get("instructions", ()):
            if instruction.get("op") == "alloc_stack":
                continue
            result = instruction.get("result")
            type_name = instruction.get("type")
            if isinstance(result, str) and isinstance(type_name, str):
                types[result] = type_name
    return types


def _all_value_names(function: dict[str, Any]) -> set[str]:
    names = {
        parameter.get("name")
        for parameter in function.get("parameters", ())
        if isinstance(parameter.get("name"), str)
    }
    for block in function.get("blocks", ()):
        for instruction in block.get("instructions", ()):
            result = instruction.get("result")
            if isinstance(result, str):
                names.add(result)
    return names


def _fresh_phi_slot(
    used_names: set[str], *, block_index: int, phi_index: int
) -> str:
    base = f"__sotlas_phi_slot_{block_index}_{phi_index}"
    candidate = base
    suffix = 0
    while candidate in used_names:
        suffix += 1
        candidate = f"{base}_{suffix}"
    used_names.add(candidate)
    return candidate


def _lower_function_phis(function: dict[str, Any]) -> bool:
    blocks = function.get("blocks", ())
    if not isinstance(blocks, list) or not blocks:
        return False

    has_phi = any(
        instruction.get("op") == "phi"
        for block in blocks
        for instruction in block.get("instructions", ())
        if isinstance(instruction, dict)
    )
    if not has_phi:
        return False

    name = function.get("name")
    labels: list[str] = []
    block_by_label: dict[str, dict[str, Any]] = {}
    for block in blocks:
        label = block.get("label")
        if not isinstance(label, str) or not label or label in block_by_label:
            raise MachineBackendError(
                f"function {name!r}: phi lowering requires unique CFG block labels"
            )
        labels.append(label)
        block_by_label[label] = block

    predecessors = {label: set() for label in labels}
    for block in blocks:
        instructions = block.get("instructions", ())
        if not instructions:
            raise MachineBackendError(
                f"function {name!r}: phi lowering encountered an empty block"
            )
        terminator = instructions[-1]
        for target in terminator.get("targets", ()):
            if target in predecessors:
                predecessors[target].add(block["label"])

    entry_label = labels[0]
    dominators = {
        label: ({label} if label == entry_label else set(labels))
        for label in labels
    }
    changed = True
    while changed:
        changed = False
        for label in labels[1:]:
            incoming_blocks = predecessors[label]
            common = (
                set.intersection(*(dominators[item] for item in incoming_blocks))
                if incoming_blocks else set()
            )
            updated = {label} | common
            if updated != dominators[label]:
                dominators[label] = updated
                changed = True

    definitions: dict[str, tuple[str, int] | None] = {}
    for parameter in function.get("parameters", ()):
        parameter_name = parameter.get("name")
        if isinstance(parameter_name, str):
            definitions[parameter_name] = None
    for block in blocks:
        for instruction_index, instruction in enumerate(block.get("instructions", ())):
            result = instruction.get("result")
            if isinstance(result, str):
                definitions[result] = (block["label"], instruction_index)

    value_types = _value_types(function)
    used_names = _all_value_names(function)
    phi_allocations: list[dict[str, Any]] = []
    edge_stores: dict[str, list[dict[str, Any]]] = {
        label: [] for label in labels
    }
    replacements: dict[str, list[dict[str, Any]]] = {}

    for block_index, block in enumerate(blocks):
        label = block["label"]
        instructions = list(block.get("instructions", ()))
        lowered_prefix: list[dict[str, Any]] = []
        seen_non_phi = False
        phi_index = 0
        for instruction in instructions:
            if instruction.get("op") != "phi":
                seen_non_phi = True
                lowered_prefix.append(instruction)
                continue
            if seen_non_phi:
                raise MachineBackendError(
                    f"function {name!r}: phi in block {label!r} must precede non-phi instructions"
                )

            result = instruction.get("result")
            type_name = instruction.get("type")
            incoming = instruction.get("incoming")
            if not isinstance(result, str) or not result:
                raise MachineBackendError(
                    f"function {name!r}: phi in block {label!r} has an invalid result"
                )
            _core._require_machine_scalar(
                type_name,
                context=f"function {name!r} phi {result!r}",
            )
            if not isinstance(incoming, list) or not incoming:
                raise MachineBackendError(
                    f"function {name!r}: phi {result!r} has no incoming values"
                )

            incoming_by_block: dict[str, str] = {}
            for item in incoming:
                if not isinstance(item, dict):
                    raise MachineBackendError(
                        f"function {name!r}: phi {result!r} has a malformed incoming edge"
                    )
                predecessor = item.get("block")
                source = item.get("value")
                if (
                    not isinstance(predecessor, str)
                    or predecessor not in block_by_label
                    or not isinstance(source, str)
                    or not source
                ):
                    raise MachineBackendError(
                        f"function {name!r}: phi {result!r} has a malformed incoming edge"
                    )
                if predecessor in incoming_by_block:
                    raise MachineBackendError(
                        f"function {name!r}: phi {result!r} has duplicate predecessor inputs"
                    )
                incoming_by_block[predecessor] = source

            if set(incoming_by_block) != predecessors[label]:
                raise MachineBackendError(
                    f"function {name!r}: phi {result!r} inputs do not match CFG predecessors"
                )
            for predecessor, source in incoming_by_block.items():
                if value_types.get(source) != type_name:
                    raise MachineBackendError(
                        f"function {name!r}: phi {result!r} input from {predecessor!r} "
                        f"does not match type {type_name!r}"
                    )
                definition = definitions.get(source)
                if source not in definitions:
                    raise MachineBackendError(
                        f"function {name!r}: phi {result!r} uses undefined value {source!r}"
                    )
                if definition is not None:
                    definition_block, definition_index = definition
                    predecessor_instructions = block_by_label[predecessor].get(
                        "instructions", ()
                    )
                    if definition_block == predecessor:
                        if definition_index >= len(predecessor_instructions) - 1:
                            raise MachineBackendError(
                                f"function {name!r}: phi {result!r} input {source!r} "
                                "is not available on its predecessor edge"
                            )
                    elif definition_block not in dominators[predecessor]:
                        raise MachineBackendError(
                            f"function {name!r}: phi {result!r} input {source!r} "
                            "does not dominate its predecessor edge"
                        )

            slot = _fresh_phi_slot(
                used_names, block_index=block_index, phi_index=phi_index
            )
            phi_index += 1
            phi_allocations.append(
                {
                    "op": "alloc_stack",
                    "result": slot,
                    "type": type_name,
                    "attributes": {
                        "source_name": None,
                        "machine_lowering": "phi_edge_copy",
                    },
                }
            )
            for predecessor, source in incoming_by_block.items():
                edge_stores[predecessor].append(
                    {
                        "op": "store",
                        "operands": [source, slot],
                        "attributes": {
                            "machine_lowering": "phi_edge_copy",
                            "phi_target": label,
                            "phi_result": result,
                        },
                    }
                )
            lowered_prefix.append(
                {
                    "op": "load",
                    "result": result,
                    "operands": [slot],
                    "type": type_name,
                    "attributes": {"machine_lowering": "phi_edge_copy"},
                }
            )
        replacements[label] = lowered_prefix

    entry = blocks[0]
    replacements[entry["label"]] = (
        phi_allocations + replacements[entry["label"]]
    )

    for block in blocks:
        label = block["label"]
        instructions = replacements[label]
        stores = edge_stores[label]
        if stores:
            instructions = instructions[:-1] + stores + instructions[-1:]
        block["instructions"] = instructions
    return True


def lower_phi_edge_copies(target_ir: dict[str, Any]) -> dict[str, Any]:
    """Destroy scalar SSA phi nodes into backend-private edge copies."""
    if not isinstance(target_ir, dict) or target_ir.get("schema") != "sotlas.target-ir.v1":
        return target_ir
    if not any(
        instruction.get("op") == "phi"
        for function in target_ir.get("functions", ())
        for block in function.get("blocks", ())
        for instruction in block.get("instructions", ())
        if isinstance(instruction, dict)
    ):
        return target_ir

    lowered = deepcopy(target_ir)
    changed = False
    for function in lowered.get("functions", ()):
        changed = _lower_function_phis(function) or changed
    if changed:
        limitations = list(lowered.get("limitations", ()))
        limitations.append(
            "Scalar phi nodes are destroyed into private stack-backed edge copies before x86-64 instruction selection."
        )
        lowered["limitations"] = limitations
    return lowered


def plan_x86_64_sysv_allocation(
    target_ir: dict[str, Any], *, register_count: int = 2
) -> dict[str, Any]:
    return _calls.plan_x86_64_sysv_allocation(
        lower_phi_edge_copies(target_ir), register_count=register_count
    )


def emit_x86_64_sysv_assembly(
    target_ir: dict[str, Any], *, register_count: int = 2
) -> str:
    return _calls.emit_x86_64_sysv_assembly(
        lower_phi_edge_copies(target_ir), register_count=register_count
    )


def compile_source_to_x86_64_sysv_assembly(
    source: str,
    filename: str = "<stdin>",
    *,
    register_count: int = 2,
) -> str:
    from .canonical_sir import build_canonical_checked_ownership_sir
    from .phase1_pipeline import analyze_source_phase1

    checked = analyze_source_phase1(source, filename=filename)
    checked_sir, _ = build_canonical_checked_ownership_sir(checked)
    module = checked_sir.module
    unlowered = tuple(getattr(module, "unlowered_functions", ()) or ())
    if unlowered:
        raise MachineBackendError(
            "x86-64 machine backend cannot lower source bodies for: "
            + ", ".join(sorted(unlowered))
        )
    target_ir = lower_sir_to_typed_target_ir(module)
    return emit_x86_64_sysv_assembly(
        target_ir, register_count=register_count
    )


__all__ = [
    "MachineBackendError",
    "lower_phi_edge_copies",
    "plan_x86_64_sysv_allocation",
    "emit_x86_64_sysv_assembly",
    "compile_source_to_x86_64_sysv_assembly",
]
