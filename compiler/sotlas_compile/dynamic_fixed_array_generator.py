"""Narrow source/SIR bridge for runtime-bounded fixed-array indexing."""
from __future__ import annotations

import importlib
from typing import Any


_DYNAMIC_ARRAY_TYPES = frozenset({"u8", "u16", "u32", "u64", "usize"})


def _name(expression: Any) -> str | None:
    kind = type(expression).__name__
    if kind == "Name":
        value = getattr(expression, "value", None)
    elif kind == "IdentNode":
        value = getattr(expression, "name", None)
    else:
        return None
    return value if isinstance(value, str) and value else None


def extend_dynamic_fixed_array_generator(base, sir):
    """Add only ``unsafe { return ptr[index]; }`` with a ``usize`` SSA index."""
    fixed_array_sir = importlib.import_module(f"{sir.__name__}.fixed_arrays")

    class DynamicFixedArraySIRGenerator(base):
        def _try_lower_fixed_array_pointer_index_return(
            self,
            fn: Any,
            entry_block: Any,
            sir_params: list[Any],
            return_type: str,
        ) -> bool:
            if super()._try_lower_fixed_array_pointer_index_return(
                fn, entry_block, sir_params, return_type
            ):
                return True
            if return_type not in _DYNAMIC_ARRAY_TYPES:
                return False

            body = list(getattr(fn, "body", None) or ())
            if len(body) != 1 or type(body[0]).__name__ not in (
                "Unsafe", "UnsafeBlockNode"
            ):
                return False
            unsafe_body = list(getattr(body[0], "body", None) or ())
            if len(unsafe_body) != 1 or type(unsafe_body[0]).__name__ not in (
                "Return", "ReturnNode"
            ):
                return False
            return_statement = unsafe_body[0]
            indexed = getattr(return_statement, "value", None)
            if type(indexed).__name__ not in ("Index", "IndexExprNode"):
                return False

            target = getattr(indexed, "target", None)
            if target is None:
                target = getattr(indexed, "base", None)
            base_name = _name(target)
            index_name = _name(getattr(indexed, "index", None))
            if base_name is None or index_name is None or base_name == index_name:
                return False

            base_value = next(
                (value for value in sir_params if value.name == base_name),
                None,
            )
            index_value = next(
                (value for value in sir_params if value.name == index_name),
                None,
            )
            if (
                base_value is None
                or index_value is None
                or getattr(index_value, "type_name", None) != "usize"
            ):
                return False

            source_type = None
            for parameter in tuple(getattr(fn, "params", ()) or ()):
                if isinstance(parameter, tuple) and len(parameter) == 2:
                    parameter_name, parameter_type = parameter
                else:
                    parameter_name = getattr(parameter, "name", None)
                    parameter_type = (
                        getattr(parameter, "type_ann", None)
                        or getattr(parameter, "type", None)
                    )
                if parameter_name == base_name:
                    source_type = parameter_type
                    break
            if (
                source_type is None
                or not bool(getattr(source_type, "is_array", False))
                or not bool(getattr(source_type, "pointer", False))
                or bool(getattr(source_type, "is_reference", False))
            ):
                return False

            length = getattr(source_type, "array_size", None)
            element = getattr(source_type, "elem_type", None)
            if (
                not isinstance(length, int)
                or isinstance(length, bool)
                or length < 1
                or element is None
                or bool(getattr(element, "pointer", False))
                or bool(getattr(element, "is_array", False))
                or bool(getattr(element, "is_reference", False))
            ):
                return False
            try:
                element_type = self._type_name(element, "any")
            except ValueError:
                return False
            if (
                element_type != return_type
                or element_type not in _DYNAMIC_ARRAY_TYPES
            ):
                return False

            flattened_pointer = f"{element_type}*"
            fixed_array_pointer = f"[{element_type};{length}]*"
            if base_value.type_name not in (flattened_pointer, fixed_array_pointer):
                return False
            parameter_slots = [
                instruction
                for instruction in entry_block.instructions
                if type(instruction).__name__ == "AllocStackInst"
                and getattr(instruction, "var_name", None) == base_name
            ]
            if len(parameter_slots) != 1:
                return False
            parameter_slot = parameter_slots[0]
            slot_result = getattr(parameter_slot, "result", None)
            if (
                getattr(parameter_slot, "type_name", None)
                not in (flattened_pointer, fixed_array_pointer)
                or getattr(slot_result, "type_name", None)
                not in (flattened_pointer, fixed_array_pointer)
            ):
                return False

            base_value.type_name = fixed_array_pointer
            parameter_slot.type_name = fixed_array_pointer
            slot_result.type_name = fixed_array_pointer

            element_pointer = self._next_val(
                f"array_index_{index_name}_addr", f"{element_type}*"
            )
            loaded = self._next_val(
                f"array_index_{index_name}", element_type
            )
            entry_block.add(fixed_array_sir.DynamicFixedArrayElementAddressInst(
                base=base_value,
                index=index_value,
                result=element_pointer,
                element_type=element_type,
                length=length,
                bounds_policy="trap",
                point_id=self._statement_point_id(
                    indexed, "array_address_dynamic"
                ),
            ))
            entry_block.add(sir.LoadInst(source=element_pointer, result=loaded))
            entry_block.add(sir.ReturnInst(
                value=loaded,
                point_id=self._statement_point_id(return_statement, "return"),
            ))
            return True

    DynamicFixedArraySIRGenerator.__name__ = "DynamicFixedArraySIRGenerator"
    return DynamicFixedArraySIRGenerator


__all__ = ["extend_dynamic_fixed_array_generator"]
