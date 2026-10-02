"""Backend-neutral source-local address facts and Target IR bridge.

M16.4b2 preserves a non-escaping source-local address as a typed SIR side fact,
analogous to source linkage facts. This module deliberately does not eagerly
import source generators or Target IR implementations so reduced compatibility
package views can load it without pulling unrelated compiler layers.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


_LOCAL_ADDRESS_TYPES = frozenset({"u8", "u16", "u32", "u64", "usize"})


class LocalAddressingError(ValueError):
    """Raised when source/SIR/Target-IR local-address facts disagree."""


@dataclass(frozen=True)
class LocalAddressFact:
    function: str
    source_name: str
    slot_value: str
    pointer_value: str
    load_result: str
    pointee_type: str
    source_point_id: str


def make_local_addressing_generator(sir):
    """Load source aggregate generators only when canonical SIR needs them."""
    from .dynamic_fixed_array_generator import extend_dynamic_fixed_array_generator
    from .enum_source_generator import extend_nullary_enum_generator
    from .local_addressing_generator import make_local_addressing_generator as factory
    from .slice_source_generator import extend_slice_source_generator
    from .struct_layout import (
        complete_sir_struct_layout_closure,
        nominal_struct_layout_scope,
    )

    generated = extend_dynamic_fixed_array_generator(factory(sir), sir)
    generated = extend_nullary_enum_generator(generated, sir)
    generated = extend_slice_source_generator(generated, sir)

    class NominalStructClosureGenerator(generated):
        """Scope nominal declarations and close layouts used by source lowering."""

        def generate_from_ast(self, ast: Any):
            definitions = {
                struct.name: struct
                for struct in tuple(getattr(ast, "structs", ()) or ())
                if isinstance(getattr(struct, "name", None), str)
                and getattr(struct, "name", None)
            }
            with nominal_struct_layout_scope(definitions):
                module = super().generate_from_ast(ast)

            complete_sir_struct_layout_closure(
                module,
                definitions,
                lambda item: self._type_name(item, "any"),
            )
            return module

    NominalStructClosureGenerator.__name__ = "NominalStructClosureGenerator"
    return NominalStructClosureGenerator


def attach_target_ir_local_addresses(
    target_ir: dict[str, Any],
    sir_module: Any,
) -> dict[str, Any]:
    """Materialize SIR-proven local addresses as Target IR ``address_of`` ops."""
    if not isinstance(target_ir, dict) or target_ir.get("schema") != "sotlas.target-ir.v1":
        raise LocalAddressingError("local address bridge requires Target IR v1")

    facts = tuple(getattr(sir_module, "local_address_facts", ()) or ())
    if not facts:
        return target_ir

    functions = {
        function.get("name"): function
        for function in target_ir.get("functions", ())
        if isinstance(function, dict)
    }
    seen: set[tuple[str, str]] = set()
    for fact in facts:
        if not isinstance(fact, LocalAddressFact):
            raise LocalAddressingError("canonical SIR contains malformed local address fact")
        if fact.pointee_type not in _LOCAL_ADDRESS_TYPES:
            raise LocalAddressingError(
                f"function {fact.function!r}: unsupported local address pointee {fact.pointee_type!r}"
            )
        function = functions.get(fact.function)
        if function is None:
            raise LocalAddressingError(
                f"local address fact references missing function {fact.function!r}"
            )

        definitions = {
            parameter.get("name")
            for parameter in function.get("parameters", ())
            if isinstance(parameter, dict)
        }
        slot_instruction = None
        load_location = None
        for block in function.get("blocks", ()):
            instructions = block.get("instructions", ())
            for index, instruction in enumerate(instructions):
                result = instruction.get("result")
                if isinstance(result, str) and result:
                    definitions.add(result)
                if (
                    instruction.get("op") == "alloc_stack"
                    and result == fact.slot_value
                ):
                    if slot_instruction is not None:
                        raise LocalAddressingError(
                            f"function {fact.function!r}: duplicate local address slot"
                        )
                    slot_instruction = instruction
                if (
                    instruction.get("op") == "load"
                    and result == fact.load_result
                ):
                    if load_location is not None:
                        raise LocalAddressingError(
                            f"function {fact.function!r}: duplicate local address load"
                        )
                    load_location = (block, index, instruction)

        if fact.pointer_value in definitions:
            raise LocalAddressingError(
                f"function {fact.function!r}: local address pointer name collides with SSA value"
            )
        if (
            slot_instruction is None
            or slot_instruction.get("type") != fact.pointee_type
            or slot_instruction.get("attributes", {}).get("source_name") != fact.source_name
        ):
            raise LocalAddressingError(
                f"function {fact.function!r}: local address fact has no matching stack slot"
            )
        if load_location is None:
            raise LocalAddressingError(
                f"function {fact.function!r}: local address fact has no matching load"
            )
        block, index, load = load_location
        if (
            load.get("type") != fact.pointee_type
            or load.get("operands") != [fact.slot_value]
        ):
            raise LocalAddressingError(
                f"function {fact.function!r}: local address load conflicts with SIR fact"
            )

        address_instruction = {
            "op": "address_of",
            "result": fact.pointer_value,
            "type": f"{fact.pointee_type}*",
            "operands": [fact.slot_value],
            "attributes": {
                "offset_bytes": 0,
                "source_name": fact.source_name,
                "source_point_id": fact.source_point_id,
            },
        }
        block["instructions"].insert(index, address_instruction)
        load["operands"] = [fact.pointer_value]
        seen.add((fact.function, fact.pointer_value))

    if len(seen) != len(facts):
        raise LocalAddressingError("not all canonical SIR local address facts reached Target IR")
    return target_ir


__all__ = [
    "LocalAddressFact",
    "LocalAddressingError",
    "attach_target_ir_local_addresses",
    "make_local_addressing_generator",
]
