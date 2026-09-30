"""Backend-neutral source-local address facts for M16.4b2.

This module bridges one deliberately narrow checked source shape into the
existing canonical SIR without teaching a machine backend to rediscover source
semantics::

    let local: T = parameter;
    unsafe { return *&local; }

The local address itself is preserved as a typed SIR side fact, analogous to
source linkage facts. Generic Target IR lowering first sees an ordinary local
load; the bridge below then materializes the explicit ``address_of`` operation
and rewrites that one load to consume the proven pointer value. References to
locals never escape this contract.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .scalar_if_return_cfg_generator import make_scalar_if_return_cfg_generator


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


def _name(expression: Any) -> str | None:
    kind = type(expression).__name__
    if kind == "Name":
        value = getattr(expression, "value", None)
    elif kind == "IdentNode":
        value = getattr(expression, "name", None)
    else:
        return None
    return value if isinstance(value, str) and value else None


def _unary_operator(expression: Any) -> str | None:
    operator = getattr(expression, "op", None)
    if isinstance(operator, str):
        return operator
    token_name = getattr(operator, "name", None)
    return {"STAR": "*", "LAND": "&", "AMP": "&"}.get(token_name)


def _unary_operand(expression: Any) -> Any:
    operand = getattr(expression, "operand", None)
    return operand if operand is not None else getattr(expression, "value", None)


def make_local_addressing_generator(sir):
    """Extend the canonical scalar generator with one non-escaping ``&local`` shape."""
    base = make_scalar_if_return_cfg_generator(sir)

    class LocalAddressingSIRGenerator(base):
        def _try_lower_local_address_roundtrip(
            self,
            fn: Any,
            entry_block: Any,
            sir_params: list[Any],
            return_type: str,
        ) -> bool:
            if return_type not in _LOCAL_ADDRESS_TYPES:
                return False
            body = list(getattr(fn, "body", None) or ())
            if len(body) != 2 or type(body[0]).__name__ not in (
                "Let", "LocalVarDeclNode"
            ) or type(body[1]).__name__ not in ("Unsafe", "UnsafeBlockNode"):
                return False

            local = body[0]
            local_name = getattr(local, "name", None)
            if not isinstance(local_name, str) or not local_name:
                return False
            if local_name in {value.name for value in sir_params}:
                return False
            local_type = (
                getattr(local, "type", None)
                or getattr(local, "type_ann", None)
            )
            try:
                local_type_name = self._type_name(local_type, "any")
            except ValueError:
                return False
            if local_type_name != return_type:
                return False

            initializer = getattr(local, "value", None)
            initializer_name = _name(initializer)
            initializer_value = next(
                (value for value in sir_params if value.name == initializer_name),
                None,
            )
            if initializer_value is None or initializer_value.type_name != return_type:
                return False

            unsafe_body = list(getattr(body[1], "body", None) or ())
            if len(unsafe_body) != 1 or type(unsafe_body[0]).__name__ not in (
                "Return", "ReturnNode"
            ):
                return False
            return_statement = unsafe_body[0]
            dereference = getattr(return_statement, "value", None)
            if type(dereference).__name__ not in ("Unary", "UnaryExprNode"):
                return False
            if _unary_operator(dereference) != "*":
                return False
            address = _unary_operand(dereference)
            if type(address).__name__ not in ("Unary", "UnaryExprNode"):
                return False
            if _unary_operator(address) != "&" or bool(getattr(address, "mutable", False)):
                return False
            if _name(_unary_operand(address)) != local_name:
                return False

            slot = self._next_val(f"slot_{local_name}", return_type)
            pointer = self._next_val(f"addr_{local_name}", f"{return_type}*")
            loaded = self._next_val("local_deref", return_type)
            entry_block.add(sir.AllocStackInst(
                var_name=local_name,
                type_name=return_type,
                result=slot,
            ))
            entry_block.add(sir.StoreInst(
                destination=slot,
                source=initializer_value,
            ))
            # Generic SIR/Target-IR lowering already understands a local load.
            # The LocalAddressFact below proves that this exact load must be
            # rewritten through the local address before machine lowering.
            entry_block.add(sir.LoadInst(source=slot, result=loaded))
            entry_block.add(sir.ReturnInst(
                value=loaded,
                point_id=self._statement_point_id(return_statement, "return"),
            ))

            fact = LocalAddressFact(
                function=getattr(fn, "name", ""),
                source_name=local_name,
                slot_value=slot.name,
                pointer_value=pointer.name,
                load_result=loaded.name,
                pointee_type=return_type,
                source_point_id=self._statement_point_id(address, "address_of"),
            )
            function_facts = tuple(getattr(entry_block, "local_address_facts", ()) or ())
            entry_block.local_address_facts = function_facts + (fact,)
            module_facts = tuple(getattr(self.sir_mod, "local_address_facts", ()) or ())
            self.sir_mod.local_address_facts = module_facts + (fact,)
            return True

        def _try_lower_direct_call_subset(
            self,
            fn: Any,
            entry_block: Any,
            sir_params: list[Any],
            return_type: str,
        ) -> bool:
            if self._try_lower_local_address_roundtrip(
                fn, entry_block, sir_params, return_type
            ):
                return True
            return super()._try_lower_direct_call_subset(
                fn, entry_block, sir_params, return_type
            )

    LocalAddressingSIRGenerator.__name__ = "LocalAddressingSIRGenerator"
    return LocalAddressingSIRGenerator


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
