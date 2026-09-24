"""Stable loader for the canonical ``compiler/sotlas/sir`` package.

The test/tooling process may already have imported the historical ``tools/sotlas``
package under the public name ``sotlas``.  Importing ``sotlas.sir`` after that
would silently bind production semantic facts to legacy SIR classes.

Load only the canonical SIR package under a private, stable namespace instead.
This is a composition helper, not a second lowering: the code executed is the
same ``compiler/sotlas/sir`` implementation shipped by the production tree.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
import sys

_CANONICAL_SIR_PACKAGE = "_sotlas_compiler_canonical_sir"


def load_canonical_sir():
    existing = sys.modules.get(_CANONICAL_SIR_PACKAGE)
    if existing is not None:
        return existing

    package_dir = Path(__file__).resolve().parents[1] / "sotlas" / "sir"
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
    """Rebuild and place ownership SIR from the canonical semantic snapshot."""
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
    checked = SimpleNamespace(parsed_module=parsed_module, ownership_sir=plan)
    return sir.generate_checked_ownership_sir(checked), plan


__all__ = ["load_canonical_sir", "build_canonical_checked_ownership_sir"]
