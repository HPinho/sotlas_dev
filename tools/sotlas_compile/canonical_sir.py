"""Stable loader and composition bridge for the canonical compiler SIR.

Tests and tooling may already have imported the historical ``tools/sotlas``
package under the public name ``sotlas``. Importing ``sotlas.sir`` after that
would silently bind production semantic facts to legacy SIR classes.

This module always loads ``compiler/sotlas/sir`` under a private namespace and
uses narrow REGION-aware generator extensions only for source shapes that the
prototype base generator does not yet represent. Ownership placement remains the
canonical validator: no marker bypasses graph/type/source-point verification.
"""
from __future__ import annotations

from dataclasses import dataclass
import importlib.util
from pathlib import Path
import sys

from .authority_call_generator import make_authority_call_generator
from .region_return_cfg_generator import make_region_return_cfg_generator

_CANONICAL_SIR_PACKAGE = "_sotlas_compiler_canonical_sir"


def _repository_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        candidate = parent / "compiler" / "sotlas" / "sir" / "__init__.py"
        if candidate.is_file():
            return parent
    raise RuntimeError("cannot locate repository root for canonical compiler SIR")


def _attach_source_effect_summaries(checked_module: object, sir_module) -> None:
    """Carry checked source effect facts onto matching canonical SIR functions."""
    parsed_module = getattr(checked_module, "parsed_module", None)
    summaries = getattr(checked_module, "source_effects", None)
    if summaries is None and parsed_module is not None:
        summaries = getattr(parsed_module, "source_effect_summaries", None)
    if not summaries:
        return
    for function in sir_module.functions:
        summary = summaries.get(function.name)
        if summary is None:
            continue
        function.source_effect_summary = summary
        function.declared_effects = summary.declared_effects


def load_canonical_sir():
    existing = sys.modules.get(_CANONICAL_SIR_PACKAGE)
    if existing is not None:
        return existing

    package_dir = _repository_root() / "compiler" / "sotlas" / "sir"
    spec = importlib.util.spec_from_file_location(
        _CANONICAL_SIR_PACKAGE,
        package_dir / "__init__.py",
        submodule_search_locations=[str(package_dir)],
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load canonical compiler SIR package")
    module = importlib.util.module_from_spec(spec)
    sys.modules[_CANONICAL_SIR_PACKAGE] = module
    spec.loader.exec_module(module)
    return module


def build_canonical_checked_ownership_sir(checked_module: object):
    """Generate and place canonical ownership SIR from one semantic snapshot."""
    parsed_module = getattr(checked_module, "parsed_module", None)
    semantic = getattr(checked_module, "semantic", None)
    if parsed_module is None or semantic is None:
        raise ValueError(
            "canonical checked SIR generation requires parsed_module and semantic snapshot"
        )
    ownership = getattr(semantic, "ownership", None)
    domains = getattr(semantic, "ownership_domains", None)
    if ownership is None or domains is None:
        raise ValueError("canonical checked SIR generation lacks ownership semantics")

    sir = load_canonical_sir()
    plan = sir.lower_ownership_module_semantics(ownership, domains)

    generator_type = make_region_return_cfg_generator(sir)
    generator = generator_type(
        module_name=getattr(parsed_module, "name", "main")
    )
    module = generator.generate_from_ast(parsed_module)
    _attach_source_effect_summaries(checked_module, module)
    placement = sir.apply_ownership_module_plan(module, plan)
    return sir.CheckedOwnershipSIR(module, placement), plan


@dataclass(frozen=True)
class CheckedAuthoritySIR:
    """Strict Phase-3 SIR result with ownership and Authority proof attached."""

    ownership: object
    ownership_plan: object
    authority_certificate: object
    authority_safety: object

    @property
    def module(self):
        return self.ownership.module

    @property
    def placement(self):
        return self.ownership.placement


def build_canonical_checked_authority_sir(
    checked_module: object,
) -> CheckedAuthoritySIR:
    """Generate canonical SIR and require ownership plus Authority safety.

    Named ABI calls are represented as source-stable ``AuthorityABIInst`` facts.
    Those facts carry privilege semantics only; the C11 reference backend still
    owns the physical intrinsic lowering. Legacy-uncontracted intrinsics remain
    fail-closed in this strict Phase-3 entry point.
    """
    parsed_module = getattr(checked_module, "parsed_module", None)
    semantic = getattr(checked_module, "semantic", None)
    authority = getattr(checked_module, "authority", None)
    if parsed_module is None or semantic is None or authority is None:
        raise ValueError(
            "canonical authority SIR generation requires parsed_module, "
            "semantic snapshot, and authority plan"
        )
    ownership = getattr(semantic, "ownership", None)
    domains = getattr(semantic, "ownership_domains", None)
    if ownership is None or domains is None:
        raise ValueError("canonical authority SIR generation lacks ownership semantics")

    sir = load_canonical_sir()
    ownership_plan = sir.lower_ownership_module_semantics(ownership, domains)
    generator_type = make_authority_call_generator(sir, authority)
    generator = generator_type(
        module_name=getattr(parsed_module, "name", "main")
    )
    module = generator.generate_from_ast(parsed_module)
    _attach_source_effect_summaries(checked_module, module)

    # Import locally to keep authority_sir -> canonical_sir loading acyclic.
    from .authority_sir import certify_authority_sir, place_authority_abi_facts
    from .authority_safety import enforce_authority_sir_safety

    place_authority_abi_facts(authority, module)
    placement = sir.apply_ownership_module_plan(module, ownership_plan)
    checked_ownership = sir.CheckedOwnershipSIR(module, placement)

    authority_certificate = certify_authority_sir(authority, checked_ownership)
    authority_safety = enforce_authority_sir_safety(
        authority_certificate,
        checked_ownership,
    )
    authority_safety.require_success()
    return CheckedAuthoritySIR(
        ownership=checked_ownership,
        ownership_plan=ownership_plan,
        authority_certificate=authority_certificate,
        authority_safety=authority_safety,
    )


__all__ = [
    "CheckedAuthoritySIR",
    "load_canonical_sir",
    "build_canonical_checked_ownership_sir",
    "build_canonical_checked_authority_sir",
]
