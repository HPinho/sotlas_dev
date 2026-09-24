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

import importlib.util
from pathlib import Path
import sys

from .region_return_cfg_generator import make_region_return_cfg_generator

_CANONICAL_SIR_PACKAGE = "_sotlas_compiler_canonical_sir"


def _repository_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        candidate = parent / "compiler" / "sotlas" / "sir" / "__init__.py"
        if candidate.is_file():
            return parent
    raise RuntimeError("cannot locate repository root for canonical compiler SIR")


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
    placement = sir.apply_ownership_module_plan(module, plan)
    return sir.CheckedOwnershipSIR(module, placement), plan


__all__ = ["load_canonical_sir", "build_canonical_checked_ownership_sir"]
