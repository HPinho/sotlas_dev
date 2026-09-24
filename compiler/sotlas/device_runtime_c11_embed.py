"""Embedding helpers for reference C11 DEVICE runtime declarations.

The standalone declaration plan includes standard headers by default.  The
production C11 backend already owns its prelude: hosted mode includes stdint and
stddef, while barecore defines the required freestanding integer/size types.
This helper renders only the DEVICE-specific typedefs/prototypes when embedding
inside either existing prelude, avoiding duplicate or forbidden includes.
"""
from __future__ import annotations

from .device_runtime_c11 import C11DeviceRuntimeDeclarationPlan


class DeviceRuntimeC11EmbeddingError(ValueError):
    """Raised when a DEVICE declaration plan cannot be embedded safely."""


def render_reference_c11_device_runtime_declarations(
    plan: C11DeviceRuntimeDeclarationPlan,
    *,
    include_standard_headers: bool,
) -> str:
    """Render reference declarations for standalone or existing-prelude use."""
    if not isinstance(plan, C11DeviceRuntimeDeclarationPlan):
        raise DeviceRuntimeC11EmbeddingError(
            "DEVICE C11 embedding requires a declaration plan"
        )
    if not plan.typedefs or not plan.prototypes:
        raise DeviceRuntimeC11EmbeddingError(
            "DEVICE C11 embedding requires typedefs and prototypes"
        )

    lines: list[str] = []
    if include_standard_headers:
        if plan.includes != ("#include <stddef.h>", "#include <stdint.h>"):
            raise DeviceRuntimeC11EmbeddingError(
                "DEVICE C11 standard header set diverges from reference ABI"
            )
        lines.extend(plan.includes)
        lines.append("")

    lines.extend(plan.typedefs)
    lines.append("")
    lines.extend(prototype.declaration for prototype in plan.prototypes)
    return "\n".join(lines).rstrip() + "\n"
