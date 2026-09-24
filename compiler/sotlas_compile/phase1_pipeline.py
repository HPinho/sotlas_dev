"""Opt-in canonical Phase-1 semantic pipeline.

This module composes the production bootstrap parser/checker with the isolated
Phase-1 Typed AST and ownership passes. It is explicit by design: importing the
package does not change bootstrap.check and callers must opt in to this API.
"""
from __future__ import annotations

from dataclasses import dataclass

from . import bootstrap
from .typed_ast import (
    Phase1ModuleSnapshot,
    build_phase1_semantic_snapshot,
)


@dataclass(frozen=True)
class Phase1CheckedModule:
    parsed_module: object
    semantic: Phase1ModuleSnapshot
    ownership_sir: object


def analyze_module_phase1(parsed_module) -> Phase1CheckedModule:
    """Run the canonical checker, semantic snapshot, and ownership SIR bridge."""
    try:
        bootstrap.check(parsed_module)
    except bootstrap.SotlasBootstrapError as error:
        # The production checker now runs the shared whisper escape validator.
        # Keep Phase-1 callers' semantic error type stable while preserving the
        # production diagnostic for the CLI and direct bootstrap API.
        if "whisper" in error.message:
            from .typed_ast import Phase1SemanticError
            raise Phase1SemanticError(error.message) from error
        raise
    semantic = build_phase1_semantic_snapshot(parsed_module)

    # Keep the Typed AST package independent from SIR imports. The public
    # pipeline is the composition boundary between canonical semantic facts
    # and the backend-neutral intermediate representation.
    from sotlas.sir import lower_ownership_module_semantics

    ownership_sir = lower_ownership_module_semantics(
        semantic.ownership,
        semantic.ownership_domains,
    )
    return Phase1CheckedModule(
        parsed_module=parsed_module,
        semantic=semantic,
        ownership_sir=ownership_sir,
    )


def analyze_source_phase1(
    source: str, filename: str | None = None
) -> Phase1CheckedModule:
    """Parse source through the canonical frontend and run opt-in Phase 1."""
    parsed_module = bootstrap.parse(source, filename=filename)
    return analyze_module_phase1(parsed_module)


__all__ = [
    "Phase1CheckedModule",
    "analyze_module_phase1",
    "analyze_source_phase1",
]
