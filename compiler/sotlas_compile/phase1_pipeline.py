"""Opt-in canonical Phase-1 semantic pipeline.

This module composes the production bootstrap parser/checker with the isolated
Phase-1 Typed AST and ownership passes. It is explicit by design: importing the
package does not change bootstrap.check and callers must opt in to this API.
"""
from __future__ import annotations

from dataclasses import dataclass

from . import bootstrap
from .typed_ast import Phase1ModuleSnapshot, build_phase1_semantic_snapshot


@dataclass(frozen=True)
class Phase1CheckedModule:
    parsed_module: object
    semantic: Phase1ModuleSnapshot


def analyze_module_phase1(parsed_module) -> Phase1CheckedModule:
    """Run the canonical checker, then the explicit Phase-1 semantic snapshot."""
    bootstrap.check(parsed_module)
    return Phase1CheckedModule(
        parsed_module=parsed_module,
        semantic=build_phase1_semantic_snapshot(parsed_module),
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
