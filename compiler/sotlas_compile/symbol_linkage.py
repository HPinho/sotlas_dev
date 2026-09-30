"""Backend-neutral source visibility and symbol linkage facts.

This module preserves language-level ``pub`` visibility and explicit ``@export``
ABI exposure independently from any machine backend. Generated helper
functions without a source declaration are module-internal by default.

The module deliberately has no dependency on Target IR. Historical compatibility
loaders import ``canonical_sir`` from reduced ``tools/sotlas_compile`` package
views where Target IR is not installed; source-linkage facts must remain usable
there.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class SymbolLinkageError(ValueError):
    """Raised when canonical symbol-linkage facts are malformed or inconsistent."""


@dataclass(frozen=True)
class SourceSymbolLinkage:
    symbol: str
    linkage: str
    source_visibility: str
    abi_export: bool


def _source_function_facts(parsed_module: Any) -> dict[str, SourceSymbolLinkage]:
    facts: dict[str, SourceSymbolLinkage] = {}
    for function in tuple(getattr(parsed_module, "functions", ()) or ()):
        name = getattr(function, "name", None)
        if not isinstance(name, str) or not name:
            raise ValueError("checked source module has an invalid function symbol")
        if name in facts:
            raise ValueError(f"checked source module has duplicate function symbol {name!r}")
        public = bool(getattr(function, "public", False))
        attributes = tuple(getattr(function, "attributes", ()) or ())
        abi_export = "@export" in attributes
        facts[name] = SourceSymbolLinkage(
            symbol=name,
            linkage="external" if public or abi_export else "internal",
            source_visibility="public" if public else "private",
            abi_export=abi_export,
        )
    return facts


def attach_checked_source_symbol_linkage(
    checked_module: Any,
    sir_module: Any,
) -> tuple[SourceSymbolLinkage, ...]:
    """Attach deterministic source visibility/linkage facts to canonical SIR."""
    parsed_module = getattr(checked_module, "parsed_module", None)
    if parsed_module is None:
        raise ValueError("symbol linkage lowering requires the checked source module")

    source_facts = _source_function_facts(parsed_module)
    facts: list[SourceSymbolLinkage] = []
    seen: set[str] = set()
    for function in tuple(getattr(sir_module, "functions", ()) or ()):
        name = getattr(function, "name", None)
        if not isinstance(name, str) or not name or name in seen:
            raise ValueError("canonical SIR has an invalid or duplicate function symbol")
        seen.add(name)
        fact = source_facts.get(name)
        if fact is None:
            fact = SourceSymbolLinkage(
                symbol=name,
                linkage="internal",
                source_visibility="private",
                abi_export=False,
            )
        function.linkage = fact.linkage
        function.source_visibility = fact.source_visibility
        function.abi_export = fact.abi_export
        facts.append(fact)

    result = tuple(facts)
    existing = tuple(getattr(sir_module, "symbol_linkage", ()) or ())
    if existing and existing != result:
        raise ValueError("generated SIR already contains conflicting symbol linkage")
    sir_module.symbol_linkage = result
    return result


def attach_target_ir_symbol_linkage(
    target_ir: dict[str, Any],
    sir_module: Any,
) -> dict[str, Any]:
    """Copy SIR-proven linkage into Target IR without machine-side guessing.

    Historical/synthetic SIR without ``symbol_linkage`` remains untouched so
    existing Target IR producers can migrate explicitly. The machine backend
    treats absent metadata as its legacy external-linkage contract.
    """
    if not isinstance(target_ir, dict) or target_ir.get("schema") != "sotlas.target-ir.v1":
        raise SymbolLinkageError("symbol linkage bridge requires Target IR v1")

    facts = tuple(getattr(sir_module, "symbol_linkage", ()) or ())
    if not facts:
        return target_ir

    by_symbol: dict[str, SourceSymbolLinkage] = {}
    for fact in facts:
        symbol = getattr(fact, "symbol", None)
        linkage = getattr(fact, "linkage", None)
        visibility = getattr(fact, "source_visibility", None)
        abi_export = getattr(fact, "abi_export", None)
        if (
            not isinstance(symbol, str)
            or not symbol
            or linkage not in {"internal", "external"}
            or visibility not in {"private", "public"}
            or not isinstance(abi_export, bool)
        ):
            raise SymbolLinkageError("canonical SIR contains malformed symbol linkage")
        if symbol in by_symbol:
            raise SymbolLinkageError(
                f"canonical SIR contains duplicate symbol linkage for {symbol!r}"
            )
        by_symbol[symbol] = fact

    seen: set[str] = set()
    for function in target_ir.get("functions", ()):
        name = function.get("name")
        if not isinstance(name, str) or not name:
            raise SymbolLinkageError("Target IR contains an invalid function name")
        fact = by_symbol.get(name)
        if fact is None:
            raise SymbolLinkageError(
                f"Target IR function {name!r} has no canonical SIR linkage fact"
            )
        function["linkage"] = fact.linkage
        function["source_visibility"] = fact.source_visibility
        function["abi_export"] = fact.abi_export
        seen.add(name)

    missing = sorted(set(by_symbol) - seen)
    if missing:
        raise SymbolLinkageError(
            "canonical SIR linkage facts were not preserved in Target IR: "
            + ", ".join(missing)
        )
    return target_ir


__all__ = [
    "SymbolLinkageError",
    "SourceSymbolLinkage",
    "attach_checked_source_symbol_linkage",
    "attach_target_ir_symbol_linkage",
]
