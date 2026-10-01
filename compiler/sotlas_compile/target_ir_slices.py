"""Target IR bridge for backend-neutral logical slice views (M16.4f1)."""
from __future__ import annotations

from typing import Any

from .target_ir import TargetIRLoweringError


_SLICE_ELEMENT_TYPES = frozenset({"u8", "u16", "u32", "u64", "usize"})
_REQUIRED_KEYS = frozenset({
    "function",
    "name",
    "logical_type",
    "element_type",
    "mutable",
    "data",
    "length",
    "representation",
    "source_point_id",
})
_FORBIDDEN_LAYOUT_KEYS = frozenset({
    "size_bytes",
    "alignment_bytes",
    "data_offset_bytes",
    "length_offset_bytes",
    "abi_class",
    "register_class",
})


class TargetIRSliceError(TargetIRLoweringError):
    """Raised when logical slice representation facts are inconsistent."""


def _value_types(function: dict[str, Any]) -> dict[str, str]:
    values: dict[str, str] = {}
    for parameter in function.get("parameters", ()):
        if not isinstance(parameter, dict):
            continue
        name = parameter.get("name")
        type_name = parameter.get("type")
        if isinstance(name, str) and name and isinstance(type_name, str) and type_name:
            values[name] = type_name
    for block in function.get("blocks", ()):
        if not isinstance(block, dict):
            continue
        for instruction in block.get("instructions", ()):
            if not isinstance(instruction, dict):
                continue
            result = instruction.get("result")
            type_name = instruction.get("type")
            if isinstance(result, str) and result and isinstance(type_name, str) and type_name:
                values[result] = type_name
    return values


def validate_target_ir_slice_views(target_ir: dict[str, Any]) -> None:
    """Validate f1 slice metadata without accepting any target byte-layout claim."""
    if not isinstance(target_ir, dict) or target_ir.get("schema") != "sotlas.target-ir.v1":
        raise TargetIRSliceError("slice view bridge requires Target IR v1")

    views = target_ir.get("slice_views", ())
    if views in (None, ()):
        return
    if not isinstance(views, list):
        raise TargetIRSliceError("slice_views must be a list")

    functions = {
        function.get("name"): function
        for function in target_ir.get("functions", ())
        if isinstance(function, dict) and isinstance(function.get("name"), str)
    }
    seen: set[tuple[str, str]] = set()

    for view in views:
        if not isinstance(view, dict):
            raise TargetIRSliceError("slice view must be an object")
        forbidden = _FORBIDDEN_LAYOUT_KEYS.intersection(view)
        if forbidden:
            raise TargetIRSliceError(
                "slice view cannot carry target byte layout or ABI classification"
            )
        if set(view) != set(_REQUIRED_KEYS):
            raise TargetIRSliceError(
                "slice view contains missing or unsupported logical fields"
            )

        function_name = view["function"]
        name = view["name"]
        element_type = view["element_type"]
        mutable = view["mutable"]
        data = view["data"]
        length = view["length"]
        representation = view["representation"]
        source_point_id = view["source_point_id"]
        logical_type = view["logical_type"]

        if (
            not isinstance(function_name, str)
            or not function_name
            or not isinstance(name, str)
            or not name
            or element_type not in _SLICE_ELEMENT_TYPES
            or not isinstance(mutable, bool)
            or not isinstance(data, str)
            or not data
            or not isinstance(length, str)
            or not length
            or representation != "pointer_length"
            or not isinstance(source_point_id, str)
            or not source_point_id.startswith("slice_view@")
        ):
            raise TargetIRSliceError("slice view contains malformed logical facts")

        expected_logical_type = (
            f"&mut [{element_type}]" if mutable else f"&[{element_type}]"
        )
        if logical_type != expected_logical_type:
            raise TargetIRSliceError(
                f"slice view {name!r} has inconsistent logical type"
            )

        key = (function_name, name)
        if key in seen:
            raise TargetIRSliceError(
                f"duplicate slice view {name!r} in function {function_name!r}"
            )
        seen.add(key)

        function = functions.get(function_name)
        if function is None:
            raise TargetIRSliceError(
                f"slice view references missing function {function_name!r}"
            )
        values = _value_types(function)
        if values.get(data) != f"{element_type}*":
            raise TargetIRSliceError(
                f"slice view {name!r} data must be {element_type}*"
            )
        if values.get(length) != "usize":
            raise TargetIRSliceError(
                f"slice view {name!r} length must be usize"
            )


def attach_target_ir_slice_views(
    target_ir: dict[str, Any],
    sir_module: Any,
) -> dict[str, Any]:
    """Attach canonical SIR slice facts as logical Target IR metadata."""
    if not isinstance(target_ir, dict) or target_ir.get("schema") != "sotlas.target-ir.v1":
        raise TargetIRSliceError("slice view bridge requires Target IR v1")

    facts = tuple(getattr(sir_module, "slice_view_facts", ()) or ())
    if not facts:
        validate_target_ir_slice_views(target_ir)
        return target_ir

    views = target_ir.setdefault("slice_views", [])
    if not isinstance(views, list):
        raise TargetIRSliceError("slice_views must be a list")

    for fact in facts:
        if type(fact).__name__ != "SliceViewFact":
            raise TargetIRSliceError("canonical SIR contains malformed slice view fact")

        function = getattr(fact, "function", None)
        name = getattr(fact, "name", None)
        element_type = getattr(fact, "element_type", None)
        mutable = getattr(fact, "mutable", None)
        data = getattr(fact, "data", None)
        length = getattr(fact, "length", None)
        point_id = getattr(fact, "point_id", None)
        data_name = getattr(data, "name", None)
        data_type = getattr(data, "type_name", None)
        length_name = getattr(length, "name", None)
        length_type = getattr(length, "type_name", None)

        if (
            not isinstance(function, str)
            or not function
            or not isinstance(name, str)
            or not name
            or element_type not in _SLICE_ELEMENT_TYPES
            or not isinstance(mutable, bool)
            or data_type != f"{element_type}*"
            or length_type != "usize"
            or not isinstance(data_name, str)
            or not data_name
            or not isinstance(length_name, str)
            or not length_name
            or not isinstance(point_id, str)
            or not point_id.startswith("slice_view@")
        ):
            raise TargetIRSliceError("canonical SIR contains malformed slice view fact")

        logical_type = (
            f"&mut [{element_type}]" if mutable else f"&[{element_type}]"
        )
        views.append({
            "function": function,
            "name": name,
            "logical_type": logical_type,
            "element_type": element_type,
            "mutable": mutable,
            "data": data_name,
            "length": length_name,
            "representation": "pointer_length",
            "source_point_id": point_id,
        })

    validate_target_ir_slice_views(target_ir)
    return target_ir


__all__ = [
    "TargetIRSliceError",
    "attach_target_ir_slice_views",
    "validate_target_ir_slice_views",
]
