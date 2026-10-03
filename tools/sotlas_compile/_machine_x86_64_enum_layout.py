"""M16.4h2e1 x86-64 SysV physical planning for nominal tagged unions.

This planner consumes the already-certified logical Target IR sidecars and derives
machine byte layout without mutating Target IR or selecting call/return ABI.
"""
from __future__ import annotations

from typing import Any

from . import _machine_x86_64_core as _core
from ._machine_x86_64_struct_layout import plan_x86_64_sysv_struct_layouts
from .enum_nominal_payloads import validate_target_ir_nominal_enum_payloads


_SCALAR_LAYOUT = {
    "bool": (1, 1),
    "u8": (1, 1),
    "i8": (1, 1),
    "u16": (2, 2),
    "i16": (2, 2),
    "u32": (4, 4),
    "i32": (4, 4),
    "f32": (4, 4),
    "u64": (8, 8),
    "i64": (8, 8),
    "usize": (8, 8),
    "isize": (8, 8),
    "f64": (8, 8),
}


def _align(value: int, alignment: int) -> int:
    return (value + alignment - 1) & -alignment


def plan_x86_64_sysv_nominal_enum_layouts(
    target_ir: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Derive physical tagged-union layout from logical nominal payload facts.

    h2e1 is deliberately a planner only. It does not write byte layout into
    Target IR, classify aggregate ABI transport, emit constructors, or attach
    cleanup/move/drop behavior.
    """
    if (
        not isinstance(target_ir, dict)
        or target_ir.get("schema") != "sotlas.target-ir.v1"
    ):
        raise _core.MachineBackendError(
            "x86-64 nominal enum layout requires Target IR v1"
        )

    try:
        validate_target_ir_nominal_enum_payloads(target_ir)
    except ValueError as exc:
        raise _core.MachineBackendError(
            f"x86-64 nominal enum layout rejected logical payload facts: {exc}"
        ) from exc

    declarations = target_ir.get("nominal_enum_payloads", {})
    if not declarations:
        return {}

    struct_layouts = plan_x86_64_sysv_struct_layouts(target_ir)
    planned: dict[str, dict[str, Any]] = {}

    for enum_name, declaration in declarations.items():
        if (
            not isinstance(enum_name, str)
            or not enum_name
            or not isinstance(declaration, dict)
            or declaration.get("tag_type") != "u32"
            or declaration.get("storage") != "tagged_union"
        ):
            raise _core.MachineBackendError(
                "x86-64 nominal enum layout contains a malformed declaration"
            )

        variants = declaration.get("variants")
        if not isinstance(variants, list) or not variants:
            raise _core.MachineBackendError(
                f"enum {enum_name!r}: x86-64 tagged-union layout requires variants"
            )

        seen_names: set[str] = set()
        seen_discriminants: set[int] = set()
        variant_inputs: list[dict[str, Any]] = []
        max_payload_size = 0
        max_payload_alignment = 1
        saw_payload = False
        saw_nominal = False

        for variant in variants:
            if not isinstance(variant, dict):
                raise _core.MachineBackendError(
                    f"enum {enum_name!r}: malformed tagged-union variant"
                )
            name = variant.get("name")
            discriminant = variant.get("discriminant")
            if (
                not isinstance(name, str)
                or not name
                or name in seen_names
                or not isinstance(discriminant, int)
                or isinstance(discriminant, bool)
                or discriminant < 0
                or discriminant > 0xFFFFFFFF
                or discriminant in seen_discriminants
            ):
                raise _core.MachineBackendError(
                    f"enum {enum_name!r}: malformed tagged-union variant identity"
                )
            seen_names.add(name)
            seen_discriminants.add(discriminant)

            payload_type = variant.get("payload_type")
            representation = variant.get("payload_representation")
            item: dict[str, Any] = {
                "name": name,
                "discriminant": discriminant,
            }

            if payload_type is None:
                if representation is not None:
                    raise _core.MachineBackendError(
                        f"enum {enum_name!r} variant {name!r}: payload representation without payload"
                    )
                variant_inputs.append(item)
                continue

            if not isinstance(payload_type, str) or not payload_type:
                raise _core.MachineBackendError(
                    f"enum {enum_name!r} variant {name!r}: malformed payload type"
                )

            if representation == "scalar":
                scalar = _SCALAR_LAYOUT.get(payload_type)
                if scalar is None:
                    raise _core.MachineBackendError(
                        f"enum {enum_name!r} variant {name!r}: unsupported scalar payload {payload_type!r}"
                    )
                payload_size, payload_alignment = scalar
            elif representation == "nominal_struct":
                nested = struct_layouts.get(payload_type)
                if nested is None:
                    raise _core.MachineBackendError(
                        f"enum {enum_name!r} variant {name!r}: nominal payload "
                        f"{payload_type!r} has no physical struct layout"
                    )
                payload_size = nested["size_bytes"]
                payload_alignment = nested["alignment_bytes"]
                saw_nominal = True
            else:
                raise _core.MachineBackendError(
                    f"enum {enum_name!r} variant {name!r}: unsupported payload representation {representation!r}"
                )

            saw_payload = True
            max_payload_size = max(max_payload_size, payload_size)
            max_payload_alignment = max(max_payload_alignment, payload_alignment)
            item.update({
                "payload_type": payload_type,
                "payload_representation": representation,
                "payload_size_bytes": payload_size,
                "payload_alignment_bytes": payload_alignment,
            })
            variant_inputs.append(item)

        if not saw_payload or not saw_nominal:
            raise _core.MachineBackendError(
                f"enum {enum_name!r}: h2e1 requires at least one nominal tagged-union payload"
            )

        tag_size = 4
        tag_alignment = 4
        payload_offset = _align(tag_size, max_payload_alignment)
        aggregate_alignment = max(tag_alignment, max_payload_alignment)
        aggregate_size = _align(
            payload_offset + max_payload_size,
            aggregate_alignment,
        )

        ordered_variants: list[dict[str, Any]] = []
        variant_map: dict[str, dict[str, Any]] = {}
        for item in variant_inputs:
            lowered = dict(item)
            if "payload_type" in lowered:
                lowered["payload_offset_bytes"] = payload_offset
            ordered_variants.append(lowered)
            variant_map[lowered["name"]] = lowered

        planned[enum_name] = {
            "name": enum_name,
            "tag_type": "u32",
            "storage": "tagged_union",
            "size_bytes": aggregate_size,
            "alignment_bytes": aggregate_alignment,
            "tag_offset_bytes": 0,
            "tag_size_bytes": tag_size,
            "tag_alignment_bytes": tag_alignment,
            "payload_offset_bytes": payload_offset,
            "payload_size_bytes": max_payload_size,
            "payload_alignment_bytes": max_payload_alignment,
            "variants": variant_map,
            "ordered_variants": ordered_variants,
        }

    return planned


__all__ = ["plan_x86_64_sysv_nominal_enum_layouts"]
