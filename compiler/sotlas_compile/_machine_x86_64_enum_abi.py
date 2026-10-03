"""M16.4h2e2a explicit x86-64 SysV ABI classification for nominal payload enums.

This layer consumes the h2e1 physical planner but deliberately does not alter the
central aggregate classifier or transport planner yet.
"""
from __future__ import annotations

from typing import Any

from . import _machine_x86_64_core as _core
from ._machine_x86_64_enum_layout import plan_x86_64_sysv_nominal_enum_layouts


_INTEGER_CLASS = "INTEGER"
_MEMORY_CLASS = "MEMORY"
_TARGET = "x86_64-unknown-linux-gnu"
_ABI = "sysv"

_INTEGER_SCALARS = frozenset({
    "bool",
    "u8",
    "i8",
    "u16",
    "i16",
    "u32",
    "i32",
    "u64",
    "i64",
    "usize",
    "isize",
})


def _integer_only_classes(size_bytes: int) -> list[str]:
    if (
        not isinstance(size_bytes, int)
        or isinstance(size_bytes, bool)
        or size_bytes < 1
    ):
        raise _core.MachineBackendError(
            "x86-64 nominal enum ABI classification requires positive byte size"
        )
    if size_bytes <= 8:
        return [_INTEGER_CLASS]
    if size_bytes <= 16:
        return [_INTEGER_CLASS, _INTEGER_CLASS]
    return [_MEMORY_CLASS]


def _require_integer_only_payload_subset(
    enum_name: str,
    layout: dict[str, Any],
) -> None:
    variants = layout.get("ordered_variants")
    if not isinstance(variants, list) or not variants:
        raise _core.MachineBackendError(
            f"enum {enum_name!r}: nominal enum ABI classification requires variants"
        )

    for variant in variants:
        if not isinstance(variant, dict):
            raise _core.MachineBackendError(
                f"enum {enum_name!r}: malformed h2e1 variant layout"
            )
        payload_type = variant.get("payload_type")
        representation = variant.get("payload_representation")
        if payload_type is None:
            if representation is not None:
                raise _core.MachineBackendError(
                    f"enum {enum_name!r}: payload representation without payload"
                )
            continue

        if representation == "nominal_struct":
            # h1c3 struct layout is currently integer-only, so a nominal struct
            # proven by that planner is safe for this restricted classifier.
            continue
        if representation == "scalar" and payload_type in _INTEGER_SCALARS:
            continue

        raise _core.MachineBackendError(
            f"enum {enum_name!r}: h2e2a ABI classification only supports "
            "INTEGER-class payloads; SSE/other payload classes wait for a later slice"
        )


def classify_x86_64_sysv_nominal_enums(
    target_ir: dict[str, Any],
) -> dict[str, Any]:
    """Classify h2e1 nominal tagged unions without assigning transport locations."""
    if (
        not isinstance(target_ir, dict)
        or target_ir.get("schema") != "sotlas.target-ir.v1"
    ):
        raise _core.MachineBackendError(
            "x86-64 nominal enum ABI classification requires Target IR v1"
        )

    layouts = plan_x86_64_sysv_nominal_enum_layouts(target_ir)
    classified: list[dict[str, Any]] = []
    for enum_name in sorted(layouts):
        layout = layouts[enum_name]
        _require_integer_only_payload_subset(enum_name, layout)

        classified.append({
            "kind": "enum",
            "name": enum_name,
            "storage": "tagged_union",
            "size_bytes": layout["size_bytes"],
            "alignment_bytes": layout["alignment_bytes"],
            "classes": _integer_only_classes(layout["size_bytes"]),
            "tag_offset_bytes": layout["tag_offset_bytes"],
            "payload_offset_bytes": layout["payload_offset_bytes"],
            "payload_size_bytes": layout["payload_size_bytes"],
            "payload_alignment_bytes": layout["payload_alignment_bytes"],
        })

    return {
        "schema": "sotlas.nominal-enum-abi.x86_64-sysv.v1",
        "target": _TARGET,
        "abi": _ABI,
        "aggregates": classified,
        "limitations": [
            "h2e2a classifies nominal payload enums but does not assign argument or return locations.",
            "Only INTEGER-class nominal/scalar payloads are supported in this slice.",
            "SSE/other payload classes remain fail-closed.",
            "Machine enum construction and payload extraction remain deferred.",
        ],
    }


__all__ = ["classify_x86_64_sysv_nominal_enums"]
