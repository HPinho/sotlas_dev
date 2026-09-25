"""Canonical declaration-origin identities for tracked ownership bindings.

This certificate is ownership-domain neutral.  It derives owner declaration
origins from the already parsed module and validates them against the canonical
``OwnershipDomainGraph``; it does not re-typecheck source or create new owners.

Parameters use a semantic identity (``param_origin@function::binding``) because
the bootstrap AST stores parameters as name/type pairs without source tokens.
Local declarations retain their exact ``let`` token as ``local_origin@line:col``.
The producer classification distinguishes declarations that introduce a fresh
lifetime identity from declarations whose identity must arrive from another
ownership event (call result, move, name forwarding, and similar forms).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .typed_ast import OwnershipDomain, Phase1SemanticError


class OwnershipOriginError(Phase1SemanticError):
    """Raised when a tracked owner lacks one canonical declaration origin."""


@dataclass(frozen=True)
class OwnershipOrigin:
    function: str
    binding: str
    type: Any
    domain: OwnershipDomain
    point_id: str
    declaration_kind: str
    producer: str
    produces_identity: bool
    source_binding: str | None = None
    callee: str | None = None

    @property
    def identity(self) -> tuple[str, str]:
        return (self.function, self.binding)


@dataclass(frozen=True)
class OwnershipOriginPlan:
    function: str
    origins: tuple[OwnershipOrigin, ...]

    @property
    def bindings(self) -> tuple[str, ...]:
        return tuple(item.binding for item in self.origins)

    def origin(self, binding: str) -> OwnershipOrigin:
        matches = tuple(item for item in self.origins if item.binding == binding)
        if len(matches) != 1:
            raise OwnershipOriginError(
                f"ownership origin plan requires exactly one origin {self.function}::{binding}"
            )
        return matches[0]


def _required_text(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise OwnershipOriginError(f"{label} requires a non-empty identity")
    return value


def _parsed_function(parsed_module: object, function: str):
    candidates = list(tuple(getattr(parsed_module, "functions", ()) or ()))
    for class_decl in tuple(getattr(parsed_module, "classes", ()) or ()):
        candidates.extend(tuple(getattr(class_decl, "methods", ()) or ()))
    matches = tuple(
        item for item in candidates if getattr(item, "name", None) == function
    )
    if len(matches) != 1:
        raise OwnershipOriginError(
            f"ownership origin planning requires exactly one parsed function {function!r}"
        )
    return matches[0]


def _parameter_name(parameter: object) -> str | None:
    if isinstance(parameter, tuple) and len(parameter) == 2:
        name = parameter[0]
    else:
        name = getattr(parameter, "name", None)
    return name if isinstance(name, str) and name else None


def _source_name(expr: object) -> str | None:
    if type(expr).__name__ == "Name":
        value = getattr(expr, "value", None)
        return value if isinstance(value, str) and value else None
    return None


def _local_point(statement: object) -> str:
    token = getattr(statement, "token", None)
    line = getattr(token, "line", None)
    column = getattr(token, "column", None)
    if (
        not isinstance(line, int)
        or line <= 0
        or not isinstance(column, int)
        or column <= 0
    ):
        raise OwnershipOriginError(
            "tracked local ownership declaration lacks source-stable token"
        )
    return f"local_origin@{line}:{column}"


def _producer(value: object) -> tuple[str, bool, str | None, str | None]:
    kind = type(value).__name__
    if kind == "StructLit":
        return ("fresh", True, None, None)
    if kind == "Call":
        callee = getattr(value, "callee", None)
        return (
            "call",
            False,
            None,
            callee if isinstance(callee, str) and callee else None,
        )
    if kind == "MoveExpr":
        source = _source_name(getattr(value, "value", None))
        return ("move", False, source, None)
    if kind == "ShareExpr":
        source = _source_name(getattr(value, "value", None))
        return ("share", False, source, None)
    if kind == "Name":
        return ("name", False, _source_name(value), None)
    if kind == "ArrayLit":
        return ("fresh", True, None, None)
    return (kind.lower() if kind else "unknown", False, None, None)


def plan_checked_ownership_origins(
    checked_module: object,
    *,
    function: str,
    domain: OwnershipDomain | None = None,
) -> OwnershipOriginPlan:
    """Freeze declaration origins for canonical ownership nodes in one function."""
    parsed_module = getattr(checked_module, "parsed_module", None)
    semantic = getattr(checked_module, "semantic", None)
    if parsed_module is None or semantic is None:
        raise OwnershipOriginError(
            "ownership origin planning requires a Phase1CheckedModule snapshot"
        )
    graph = getattr(semantic, "ownership_domains", None)
    if graph is None:
        raise OwnershipOriginError(
            "ownership origin planning requires the canonical ownership graph"
        )

    function_id = _required_text(function, label="ownership origin function")
    parsed_function = _parsed_function(parsed_module, function_id)
    parameter_names = {
        name
        for item in tuple(getattr(parsed_function, "params", ()) or ())
        if (name := _parameter_name(item)) is not None
    }
    local_by_name: dict[str, object] = {}
    for statement in tuple(getattr(parsed_function, "body", ()) or ()):
        if type(statement).__name__ != "Let":
            continue
        name = getattr(statement, "name", None)
        if not isinstance(name, str) or not name:
            continue
        if name in local_by_name:
            raise OwnershipOriginError(
                f"duplicate ownership declaration source for {function_id}::{name}"
            )
        local_by_name[name] = statement

    nodes = tuple(
        item
        for item in tuple(getattr(graph, "nodes", ()) or ())
        if getattr(item, "function", None) == function_id
        and (domain is None or getattr(item, "domain", None) is domain)
    )
    origins: list[OwnershipOrigin] = []
    seen: set[tuple[str, str]] = set()
    seen_points: set[str] = set()

    for node in nodes:
        binding = _required_text(
            getattr(node, "binding", None), label="ownership origin binding"
        )
        identity = (function_id, binding)
        if identity in seen:
            raise OwnershipOriginError(
                f"duplicate ownership origin node {function_id}::{binding}"
            )
        seen.add(identity)

        if binding in parameter_names:
            point_id = f"param_origin@{function_id}::{binding}"
            declaration_kind = "parameter"
            producer = "parameter"
            produces_identity = True
            source_binding = None
            callee = None
        else:
            statement = local_by_name.get(binding)
            if statement is None:
                raise OwnershipOriginError(
                    f"tracked owner {function_id}::{binding} lacks canonical declaration origin"
                )
            point_id = _local_point(statement)
            declaration_kind = "local"
            producer, produces_identity, source_binding, callee = _producer(
                getattr(statement, "value", None)
            )

        if point_id in seen_points:
            raise OwnershipOriginError(
                f"duplicate ownership origin point identity {point_id!r}"
            )
        seen_points.add(point_id)
        origins.append(
            OwnershipOrigin(
                function=function_id,
                binding=binding,
                type=getattr(node, "type", None),
                domain=getattr(node, "domain", None),
                point_id=point_id,
                declaration_kind=declaration_kind,
                producer=producer,
                produces_identity=produces_identity,
                source_binding=source_binding,
                callee=callee,
            )
        )

    return OwnershipOriginPlan(function=function_id, origins=tuple(origins))


__all__ = [
    "OwnershipOriginError",
    "OwnershipOrigin",
    "OwnershipOriginPlan",
    "plan_checked_ownership_origins",
]
