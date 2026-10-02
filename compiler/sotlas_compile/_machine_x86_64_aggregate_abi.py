"""x86-64 SysV aggregate ABI classification for the M16.4g1a slice."""
from __future__ import annotations
from typing import Any
from . import _machine_x86_64_core as _core
from ._machine_x86_64_struct_layout import plan_x86_64_sysv_struct_layouts
from .target_ir_slices import TargetIRSliceError, validate_target_ir_slice_views

_INTEGER_CLASS = "INTEGER"
_MEMORY_CLASS = "MEMORY"
_TARGET = "x86_64-unknown-linux-gnu"
_ABI = "sysv"


def _integer_only_classes(size_bytes: int) -> list[str]:
    if (not isinstance(size_bytes, int) or isinstance(size_bytes, bool) or size_bytes < 1):
        raise _core.MachineBackendError("x86-64 aggregate ABI classification requires positive byte size")
    if size_bytes <= 8:
        return [_INTEGER_CLASS]
    if size_bytes <= 16:
        return [_INTEGER_CLASS, _INTEGER_CLASS]
    return [_MEMORY_CLASS]


def _slice_classifications(target_ir: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        validate_target_ir_slice_views(target_ir)
    except TargetIRSliceError as error:
        raise _core.MachineBackendError(str(error)) from error
    classified = []
    for view in sorted(target_ir.get("slice_views", ()) or (), key=lambda item: (item["function"], item["name"])):
        classified.append({
            "kind": "slice",
            "function": view["function"],
            "name": view["name"],
            "logical_type": view["logical_type"],
            "size_bytes": 16,
            "alignment_bytes": 8,
            "classes": [_INTEGER_CLASS, _INTEGER_CLASS],
            "eightbytes": [
                {"index": 0, "class": _INTEGER_CLASS, "source": "data", "value": view["data"]},
                {"index": 1, "class": _INTEGER_CLASS, "source": "length", "value": view["length"]},
            ],
        })
    return classified


def _struct_classifications(target_ir: dict[str, Any]) -> list[dict[str, Any]]:
    layouts = plan_x86_64_sysv_struct_layouts(target_ir)
    classified = []
    for name in sorted(layouts):
        layout = layouts[name]
        classified.append({
            "kind": "struct",
            "name": name,
            "size_bytes": layout["size_bytes"],
            "alignment_bytes": layout["alignment_bytes"],
            "classes": _integer_only_classes(layout["size_bytes"]),
            "field_offsets": [
                {"name": field["name"], "type": field["type"], "offset_bytes": field["offset_bytes"]}
                for field in layout["ordered_fields"]
            ],
        })
    return classified


def _tag_only_enum_classifications(target_ir: dict[str, Any]) -> list[dict[str, Any]]:
    classified = []
    for declaration in target_ir.get("enum_declarations", ()) or ():
        if not isinstance(declaration, dict):
            raise _core.MachineBackendError("x86-64 aggregate ABI classification found malformed enum declaration")
        name = declaration.get("name")
        storage = declaration.get("storage")
        tag_type = declaration.get("tag_type")
        if not isinstance(name, str) or not name:
            raise _core.MachineBackendError("x86-64 aggregate ABI classification requires named enums")
        if storage == "tagged_union":
            raise _core.MachineBackendError(
                f"enum {name!r}: payload enum ABI classification requires certified tagged-union byte layout"
            )
        if storage != "tag_only" or tag_type != "u32":
            raise _core.MachineBackendError(f"enum {name!r}: unsupported enum ABI representation")
        classified.append({
            "kind": "enum",
            "name": name,
            "storage": "tag_only",
            "size_bytes": 4,
            "alignment_bytes": 4,
            "classes": [_INTEGER_CLASS],
        })
    return sorted(classified, key=lambda item: item["name"])


def classify_x86_64_sysv_aggregates(target_ir: dict[str, Any]) -> dict[str, Any]:
    """Classify proven aggregate layouts without assigning physical registers."""
    if not isinstance(target_ir, dict) or target_ir.get("schema") != "sotlas.target-ir.v1":
        raise _core.MachineBackendError("x86-64 aggregate ABI classification requires Target IR v1")
    return {
        "schema": "sotlas.aggregate-abi.x86_64-sysv.v1",
        "target": _TARGET,
        "abi": _ABI,
        "aggregates": [
            *_struct_classifications(target_ir),
            *_slice_classifications(target_ir),
            *_tag_only_enum_classifications(target_ir),
        ],
    }


__all__ = ["classify_x86_64_sysv_aggregates"]
