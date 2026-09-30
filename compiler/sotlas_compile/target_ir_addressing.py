"""Backend-neutral address calculation contract for Target IR v1.

M16.4b1 deliberately starts with the one address primitive required by later
aggregate lowering: taking the exact address of a local ``alloc_stack`` slot.
No byte offset, field projection, array indexing, pointer arithmetic, cast, or
pointer-to-pointer calculation is admitted by this contract.
"""
from __future__ import annotations

from typing import Any


class TargetIRAddressingError(ValueError):
    """Raised when Target IR addressing facts violate the M16.4b1 contract."""


def validate_target_ir_addressing(target_ir: dict[str, Any]) -> None:
    """Validate exact local-slot ``address_of`` operations in Target IR v1."""
    if not isinstance(target_ir, dict) or target_ir.get("schema") != "sotlas.target-ir.v1":
        raise TargetIRAddressingError("address calculation requires Target IR v1")

    for function in target_ir.get("functions", ()):
        name = function.get("name")
        slots: dict[str, str] = {}
        for block in function.get("blocks", ()):
            for instruction in block.get("instructions", ()):
                if instruction.get("op") != "alloc_stack":
                    continue
                result = instruction.get("result")
                type_name = instruction.get("type")
                if not isinstance(result, str) or not result or result in slots:
                    raise TargetIRAddressingError(
                        f"function {name!r}: invalid or duplicate alloc_stack result"
                    )
                if not isinstance(type_name, str) or not type_name:
                    raise TargetIRAddressingError(
                        f"function {name!r}: alloc_stack has an invalid type"
                    )
                slots[result] = type_name

        for block in function.get("blocks", ()):
            for instruction in block.get("instructions", ()):
                if instruction.get("op") != "address_of":
                    continue
                result = instruction.get("result")
                operands = instruction.get("operands", ())
                pointer_type = instruction.get("type")
                if not isinstance(result, str) or not result:
                    raise TargetIRAddressingError(
                        f"function {name!r}: address_of requires a result"
                    )
                if len(operands) != 1:
                    raise TargetIRAddressingError(
                        f"function {name!r}: address_of requires one local stack slot"
                    )
                source = operands[0]
                slot_type = slots.get(source)
                if slot_type is None:
                    raise TargetIRAddressingError(
                        f"function {name!r}: address_of source is not a local stack slot"
                    )
                if "*" in slot_type:
                    raise TargetIRAddressingError(
                        f"function {name!r}: pointer-to-pointer address calculation is not supported"
                    )
                if pointer_type != f"{slot_type}*":
                    raise TargetIRAddressingError(
                        f"function {name!r}: address_of result type must be {slot_type + '*'!r}"
                    )
                offset = instruction.get("attributes", {}).get("offset_bytes", 0)
                if offset != 0:
                    raise TargetIRAddressingError(
                        f"function {name!r}: address_of byte offsets wait for aggregate layout"
                    )


__all__ = ["TargetIRAddressingError", "validate_target_ir_addressing"]
