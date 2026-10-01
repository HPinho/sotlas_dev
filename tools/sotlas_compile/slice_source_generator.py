"""Narrow source/SIR bridge for explicit slice parameter views (M16.4f2b)."""
from __future__ import annotations

import importlib
from typing import Any


_SLICE_ELEMENT_TYPES = frozenset({"u8", "u16", "u32", "u64", "usize"})


def _slice_parameter(parameter: Any):
    if not isinstance(parameter, tuple) or len(parameter) != 2:
        return None
    name, type_info = parameter
    if (
        not isinstance(name, str)
        or not name
        or type(type_info).__name__ != "SliceType"
        or not bool(getattr(type_info, "is_slice", False))
        or not bool(getattr(type_info, "pointer", False))
        or not bool(getattr(type_info, "is_reference", False))
        or bool(getattr(type_info, "is_array", False))
    ):
        return None

    element = getattr(type_info, "elem_type", None)
    element_type = getattr(element, "name", None)
    if (
        element_type not in _SLICE_ELEMENT_TYPES
        or bool(getattr(element, "pointer", False))
        or bool(getattr(element, "is_reference", False))
        or bool(getattr(element, "is_array", False))
        or bool(getattr(element, "is_fn_ptr", False))
        or getattr(element, "ownership_domain", None) is not None
    ):
        return None

    return name, type_info, element_type


def extend_slice_source_generator(base, sir):
    """Preserve one checked source slice parameter as logical data+length SIR.

    The function body deliberately remains in ``unlowered_functions``.  f2b
    proves source identity and pointer+length representation only; it does not
    claim executable body lowering, call ABI, or machine register assignment.

    The base generator may already accept a trivial ``return;`` body as a
    generic void subset.  A slice signature still requires aggregate ABI work,
    so this wrapper reclassifies that otherwise-lowered function as unlowered
    after preserving the logical pointer+length representation.
    """

    slice_sir = importlib.import_module(f"{sir.__name__}.slices")

    class SliceSourceSIRGenerator(base):
        def generate_from_ast(self, ast: Any):
            module = super().generate_from_ast(ast)
            facts = list(getattr(module, "slice_view_facts", ()) or ())
            if facts:
                raise RuntimeError(
                    "base SIR generator already contains slice view facts"
                )

            functions_by_name = {
                function.name: function
                for function in tuple(getattr(module, "functions", ()) or ())
            }
            unlowered = set(
                tuple(getattr(module, "unlowered_functions", ()) or ())
            )

            for fn in tuple(getattr(ast, "functions", ()) or ()):
                fn_name = getattr(fn, "name", None)
                if not isinstance(fn_name, str) or not fn_name:
                    continue

                params = tuple(getattr(fn, "params", ()) or ())
                if len(params) != 1:
                    continue
                slice_parameter = _slice_parameter(params[0])
                if slice_parameter is None:
                    continue
                source_name, source_type, element_type = slice_parameter

                return_type = (
                    getattr(fn, "ret", None)
                    or getattr(fn, "result", None)
                    or getattr(fn, "return_type", None)
                )
                if self._type_name(return_type, "void") != "void":
                    continue
                if bool(getattr(fn, "public", False)) or "@extern(C)" in tuple(
                    getattr(fn, "attributes", ()) or ()
                ):
                    continue

                body = tuple(getattr(fn, "body", ()) or ())
                if (
                    len(body) != 1
                    or type(body[0]).__name__ not in ("Return", "ReturnNode")
                    or getattr(body[0], "value", None) is not None
                ):
                    continue

                sir_fn = functions_by_name.get(fn_name)
                if sir_fn is None:
                    continue
                parameters = tuple(getattr(sir_fn, "parameters", ()) or ())
                blocks = tuple(getattr(sir_fn, "blocks", ()) or ())
                if len(parameters) != 1 or len(blocks) != 1:
                    continue
                original_parameter = parameters[0]
                if (
                    getattr(original_parameter, "name", None) != source_name
                    or getattr(original_parameter, "type_name", None)
                    != f"{element_type}*"
                ):
                    continue

                block = blocks[0]
                existing = list(getattr(block, "instructions", ()) or ())
                if (
                    len(existing) != 3
                    or type(existing[0]).__name__ != "AllocStackInst"
                    or type(existing[1]).__name__ != "StoreInst"
                    or type(existing[2]).__name__ != "ReturnInst"
                ):
                    continue
                old_alloc, old_store, terminal_return = existing
                old_slot = getattr(old_alloc, "result", None)
                if (
                    getattr(old_alloc, "var_name", None) != source_name
                    or getattr(old_alloc, "type_name", None)
                    != f"{element_type}*"
                    or getattr(getattr(old_store, "destination", None), "name", None)
                    != getattr(old_slot, "name", None)
                    or getattr(getattr(old_store, "destination", None), "type_name", None)
                    != getattr(old_slot, "type_name", None)
                    or getattr(getattr(old_store, "source", None), "name", None)
                    != source_name
                    or getattr(getattr(old_store, "source", None), "type_name", None)
                    != f"{element_type}*"
                    or getattr(terminal_return, "value", None) is not None
                ):
                    continue

                data = sir.SIRValue(
                    name=f"{source_name}__data",
                    type_name=f"{element_type}*",
                )
                length = sir.SIRValue(
                    name=f"{source_name}__len",
                    type_name="usize",
                )
                data_slot = self._next_val(
                    f"slot_{source_name}_data", data.type_name
                )
                length_slot = self._next_val(
                    f"slot_{source_name}_len", length.type_name
                )

                sir_fn.parameters = [data, length]
                block.instructions = [
                    sir.AllocStackInst(
                        var_name=f"{source_name}.data",
                        type_name=data.type_name,
                        result=data_slot,
                    ),
                    sir.StoreInst(destination=data_slot, source=data),
                    sir.AllocStackInst(
                        var_name=f"{source_name}.len",
                        type_name=length.type_name,
                        result=length_slot,
                    ),
                    sir.StoreInst(destination=length_slot, source=length),
                    terminal_return,
                ]
                facts.append(
                    slice_sir.SliceViewFact(
                        function=fn_name,
                        name=source_name,
                        element_type=element_type,
                        mutable=bool(getattr(source_type, "mutable", False)),
                        data=data,
                        length=length,
                        point_id=self._statement_point_id(
                            body[0], "slice_view"
                        ),
                    )
                )

                if fn_name not in unlowered:
                    module.unlowered_functions.append(fn_name)
                    unlowered.add(fn_name)

            module.slice_view_facts = tuple(facts)
            return module

    SliceSourceSIRGenerator.__name__ = "SliceSourceSIRGenerator"
    return SliceSourceSIRGenerator


__all__ = ["extend_slice_source_generator"]
