"""Canonical SIR source bridge for the M16.4b2 non-escaping local address slice."""
from __future__ import annotations

from typing import Any

from .local_addressing import LocalAddressFact
from .scalar_if_return_cfg_generator import make_scalar_if_return_cfg_generator


_LOCAL_ADDRESS_TYPES = frozenset({"u8", "u16", "u32", "u64", "usize"})


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
    """Extend the scalar generator with ``let local = param; *&local`` only."""
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
            if (
                len(body) != 2
                or type(body[0]).__name__ not in ("Let", "LocalVarDeclNode")
                or type(body[1]).__name__ not in ("Unsafe", "UnsafeBlockNode")
            ):
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

            initializer_name = _name(getattr(local, "value", None))
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
            # This ordinary local load keeps generic SIR valid. The explicit
            # LocalAddressFact proves that the typed Target IR bridge must
            # materialize address_of immediately before this exact load.
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
            sir_function = next(
                (
                    function
                    for function in self.sir_mod.functions
                    if function.name == fact.function
                ),
                None,
            )
            if sir_function is None:
                raise ValueError(
                    f"local address lowering lost SIR function {fact.function!r}"
                )
            function_facts = tuple(
                getattr(sir_function, "local_address_facts", ()) or ()
            )
            sir_function.local_address_facts = function_facts + (fact,)
            module_facts = tuple(
                getattr(self.sir_mod, "local_address_facts", ()) or ()
            )
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


__all__ = ["make_local_addressing_generator"]
