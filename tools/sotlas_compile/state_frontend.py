"""Production-frontend bridge for Sotlas Phase 4 State Spaces.

This module installs the *public syntax* for ``space`` declarations and the
minimal Sotlas-1.0 typestate spelling ``Space<State>`` on the canonical
``sotlas_compile.bootstrap`` frontend.

The bridge certifies source State Spaces and their declared typestate.  The
production C backend erases state qualifiers to nominal C types; state-changing
operations remain an explicit unsafe assertion validated against the graph.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

from .state_space import (
    StateSpacePayload,
    StateSpacePlan,
    StateSpaceState,
    StateSpaceTransition,
    certify_state_space,
)
from .state_typestate import StateQualifiedType, certify_typestate
from .typed_ast import Phase1SemanticError


class StateSpaceFrontendError(Phase1SemanticError):
    """Raised when public State Space syntax violates the Phase-4 contract."""


@dataclass(frozen=True)
class ParsedStatePayload:
    type_name: str
    name: str | None = None


@dataclass(frozen=True)
class ParsedState:
    name: str
    payload: tuple[ParsedStatePayload, ...] = ()


@dataclass(frozen=True)
class ParsedStateTransition:
    source: str
    target: str


@dataclass(frozen=True)
class ParsedStateSpaceDecl:
    name: str
    states: tuple[ParsedState, ...]
    transitions: tuple[ParsedStateTransition, ...]
    initial_state: str | None = None
    public: bool = False
    line: int = 1
    column: int = 1


@dataclass(frozen=True)
class StateSpaceFrontendPlan:
    """Canonical source-to-semantics bridge for one parsed module."""

    declarations: tuple[ParsedStateSpaceDecl, ...]
    spaces: tuple[StateSpacePlan, ...]
    qualified_types: tuple[StateQualifiedType, ...]

    def space(self, name: str) -> StateSpacePlan:
        matches = tuple(item for item in self.spaces if item.name == name)
        if len(matches) != 1:
            raise StateSpaceFrontendError(
                f"State Space {name!r} is not uniquely defined in this module"
            )
        return matches[0]


_TYPESTATE_NAME_RE = re.compile(
    r"^(?P<space>[A-Za-z_][A-Za-z0-9_]*)<"
    r"(?P<state>[A-Za-z_][A-Za-z0-9_]*)>$"
)


def _error(bootstrap, message: str, token, filename, source):
    raise bootstrap.SotlasBootstrapError(
        message,
        getattr(token, "line", 1),
        getattr(token, "column", 1),
        filename,
        source,
    )


def _expect_kind(tokens, index, kind, bootstrap, filename, source):
    if index >= len(tokens) or tokens[index].kind != kind:
        token = tokens[index] if index < len(tokens) else tokens[-1]
        _error(bootstrap, f"esperado {kind} em declaração space", token, filename, source)
    return tokens[index], index + 1


def _expect_ident(tokens, index, bootstrap, filename, source):
    if index >= len(tokens) or tokens[index].kind != "IDENT":
        token = tokens[index] if index < len(tokens) else tokens[-1]
        _error(bootstrap, "identificador esperado em declaração space", token, filename, source)
    return tokens[index], index + 1


def _tokens_text(items: Iterable[object]) -> str:
    """Render a compact, deterministic type spelling from source tokens."""
    parts = [getattr(item, "text", "") for item in items]
    if not parts:
        return ""
    return "".join(parts).strip()


def _split_payload_items(tokens, bootstrap, filename, source):
    """Split the token slice inside ``state name(...)`` at top-level commas."""
    items = []
    current = []
    angle = bracket = paren = 0
    for token in tokens:
        kind = token.kind
        if kind == "<":
            angle += 1
        elif kind == ">":
            angle = max(0, angle - 1)
        elif kind == "[":
            bracket += 1
        elif kind == "]":
            bracket = max(0, bracket - 1)
        elif kind == "(":
            paren += 1
        elif kind == ")":
            paren = max(0, paren - 1)
        if kind == "," and angle == bracket == paren == 0:
            if not current:
                _error(bootstrap, "payload vazio em state", token, filename, source)
            items.append(tuple(current))
            current = []
        else:
            current.append(token)
    if current:
        items.append(tuple(current))
    return tuple(items)


def _payload_from_tokens(tokens, bootstrap, filename, source) -> ParsedStatePayload:
    depth_angle = depth_bracket = depth_paren = 0
    colon_index = None
    for index, token in enumerate(tokens):
        if token.kind == "<":
            depth_angle += 1
        elif token.kind == ">":
            depth_angle = max(0, depth_angle - 1)
        elif token.kind == "[":
            depth_bracket += 1
        elif token.kind == "]":
            depth_bracket = max(0, depth_bracket - 1)
        elif token.kind == "(":
            depth_paren += 1
        elif token.kind == ")":
            depth_paren = max(0, depth_paren - 1)
        elif token.kind == ":" and depth_angle == depth_bracket == depth_paren == 0:
            colon_index = index
            break

    if colon_index is None:
        type_name = _tokens_text(tokens)
        if not type_name:
            token = tokens[0] if tokens else None
            _error(bootstrap, "payload de state exige tipo", token, filename, source)
        return ParsedStatePayload(type_name=type_name)

    left = tokens[:colon_index]
    right = tokens[colon_index + 1 :]
    if len(left) != 1 or left[0].kind != "IDENT":
        token = left[0] if left else tokens[colon_index]
        _error(
            bootstrap,
            "payload nomeado de state exige identificador simples antes de ':'",
            token,
            filename,
            source,
        )
    type_name = _tokens_text(right)
    if not type_name:
        _error(
            bootstrap,
            "payload nomeado de state exige tipo após ':'",
            tokens[colon_index],
            filename,
            source,
        )
    return ParsedStatePayload(type_name=type_name, name=left[0].text)


def _parse_state_decl(tokens, index, bootstrap, filename, source):
    state_kw = tokens[index]
    index += 1
    name_tok, index = _expect_ident(tokens, index, bootstrap, filename, source)
    payload = []
    if index < len(tokens) and tokens[index].kind == "(":
        index += 1
        payload_tokens = []
        depth = 1
        while index < len(tokens) and depth > 0:
            token = tokens[index]
            if token.kind == "(":
                depth += 1
                payload_tokens.append(token)
            elif token.kind == ")":
                depth -= 1
                if depth > 0:
                    payload_tokens.append(token)
            else:
                payload_tokens.append(token)
            index += 1
        if depth != 0:
            _error(
                bootstrap,
                f"state {name_tok.text!r} possui payload sem ')'",
                state_kw,
                filename,
                source,
            )
        if payload_tokens:
            for item in _split_payload_items(
                tuple(payload_tokens), bootstrap, filename, source
            ):
                payload.append(
                    _payload_from_tokens(item, bootstrap, filename, source)
                )
    if index < len(tokens) and tokens[index].kind in (";", ","):
        index += 1
    return ParsedState(name_tok.text, tuple(payload)), index


def _parse_space_at(tokens, index, bootstrap, filename, source):
    public = False
    anchor = tokens[index]
    if tokens[index].kind == "pub":
        public = True
        index += 1
    if index >= len(tokens) or tokens[index].kind != "space":
        _error(bootstrap, "declaração space esperada", anchor, filename, source)
    index += 1
    name_tok, index = _expect_ident(tokens, index, bootstrap, filename, source)
    _, index = _expect_kind(tokens, index, "{", bootstrap, filename, source)

    states = []
    transitions = []
    initial_state = None
    while index < len(tokens) and tokens[index].kind != "}":
        token = tokens[index]
        if token.kind == "IDENT" and token.text == "initial":
            if initial_state is not None:
                _error(
                    bootstrap,
                    f"space {name_tok.text!r} declares more than one initial state",
                    token,
                    filename,
                    source,
                )
            state_kw, index = _expect_ident(
                tokens, index + 1, bootstrap, filename, source
            )
            if state_kw.text != "state":
                _error(
                    bootstrap,
                    "initial must be followed by state",
                    state_kw,
                    filename,
                    source,
                )
            state, index = _parse_state_decl(
                tokens, index - 1, bootstrap, filename, source
            )
            initial_state = state.name
            states.append(state)
            continue
        if token.kind == "IDENT" and token.text == "state":
            state, index = _parse_state_decl(
                tokens, index, bootstrap, filename, source
            )
            states.append(state)
            continue

        source_tok, index = _expect_ident(
            tokens, index, bootstrap, filename, source
        )
        _, index = _expect_kind(tokens, index, "->", bootstrap, filename, source)
        target_tok, index = _expect_ident(
            tokens, index, bootstrap, filename, source
        )
        if index < len(tokens) and tokens[index].kind in (";", ","):
            index += 1
        transitions.append(
            ParsedStateTransition(source_tok.text, target_tok.text)
        )

    if index >= len(tokens) or tokens[index].kind != "}":
        _error(
            bootstrap,
            f"space {name_tok.text!r} sem '}}'",
            name_tok,
            filename,
            source,
        )
    index += 1
    return (
        ParsedStateSpaceDecl(
            name=name_tok.text,
            states=tuple(states),
            transitions=tuple(transitions),
            initial_state=initial_state,
            public=public,
            line=anchor.line,
            column=anchor.column,
        ),
        index,
    )


def _extract_state_spaces(tokens, bootstrap, filename, source):
    """Remove top-level ``space`` blocks before the existing parser consumes tokens."""
    output = []
    declarations = []
    index = 0
    brace_depth = 0
    while index < len(tokens):
        token = tokens[index]
        at_top = brace_depth == 0
        is_space = at_top and token.kind == "space"
        is_pub_space = (
            at_top
            and token.kind == "pub"
            and index + 1 < len(tokens)
            and tokens[index + 1].kind == "space"
        )
        if is_space or is_pub_space:
            decl, index = _parse_space_at(
                tokens, index, bootstrap, filename, source
            )
            declarations.append(decl)
            continue

        output.append(token)
        if token.kind == "{":
            brace_depth += 1
        elif token.kind == "}":
            brace_depth = max(0, brace_depth - 1)
        index += 1

    return output, tuple(declarations)


def _canonical_space(decl: ParsedStateSpaceDecl) -> StateSpacePlan:
    try:
        return certify_state_space(
            decl.name,
            tuple(
                StateSpaceState(
                    state.name,
                    tuple(
                        StateSpacePayload(type_name=item.type_name, name=item.name)
                        for item in state.payload
                    ),
                )
                for state in decl.states
            ),
            tuple(
                StateSpaceTransition(item.source, item.target)
                for item in decl.transitions
            ),
            initial_state=decl.initial_state,
        )
    except Phase1SemanticError as error:
        raise StateSpaceFrontendError(str(error)) from error


def _iter_statement_types(items, bootstrap):
    for item in items:
        if isinstance(item, bootstrap.Let):
            if item.type is not None:
                yield item.type
        elif isinstance(item, bootstrap.If):
            yield from _iter_statement_types(item.then_body, bootstrap)
            yield from _iter_statement_types(item.else_body, bootstrap)
        elif isinstance(item, (bootstrap.While, bootstrap.Loop, bootstrap.Unsafe)):
            yield from _iter_statement_types(item.body, bootstrap)
        elif isinstance(item, bootstrap.For):
            yield from _iter_statement_types(item.body, bootstrap)
        elif isinstance(item, bootstrap.Defer) and item.body is not None:
            yield from _iter_statement_types(item.body, bootstrap)


def _iter_declared_types(module, bootstrap):
    for struct in getattr(module, "structs", ()):
        for field in getattr(struct, "fields", ()):
            yield field.type
    for class_decl in getattr(module, "classes", ()):
        for field in getattr(class_decl, "fields", ()):
            yield field.type
    for enum in getattr(module, "enums", ()):
        for variant in getattr(enum, "variants", ()):
            if getattr(variant, "payload_type", None) is not None:
                yield variant.payload_type
    for glob in getattr(module, "globals", ()):
        yield glob.type
    for function in getattr(module, "functions", ()):
        for _, type_obj in getattr(function, "params", ()):
            yield type_obj
        result = getattr(function, "result", None)
        if result is not None:
            yield result
        yield from _iter_statement_types(getattr(function, "body", ()), bootstrap)


def _walk_type(type_obj):
    if type_obj is None:
        return
    yield type_obj
    elem = getattr(type_obj, "elem_type", None)
    if elem is not None:
        yield from _walk_type(elem)
    for param in getattr(type_obj, "fn_params", ()):
        yield from _walk_type(param)
    result = getattr(type_obj, "fn_ret", None)
    if result is not None:
        yield from _walk_type(result)


def _qualified_type_fact(type_obj, by_space):
    state_space = getattr(type_obj, "state_space", None)
    state_name = getattr(type_obj, "state_name", None)
    if state_space is not None or state_name is not None:
        if not isinstance(state_space, str) or not isinstance(state_name, str):
            raise StateSpaceFrontendError(
                "typed State Space name must include both space and state"
            )
        space = by_space.get(state_space)
        if space is None:
            return None
        if (
            getattr(type_obj, "pointer", False)
            or getattr(type_obj, "is_reference", False)
            or getattr(type_obj, "is_array", False)
            or getattr(type_obj, "is_fn_ptr", False)
            or getattr(type_obj, "ownership_domain", None) is not None
        ):
            raise StateSpaceFrontendError(
                f"typestate {type_obj.display()} currently requires a direct by-value type"
            )
        try:
            return certify_typestate(space, type_obj.name, state_name)
        except Phase1SemanticError as error:
            raise StateSpaceFrontendError(str(error)) from error
    name = getattr(type_obj, "name", "")
    match = _TYPESTATE_NAME_RE.fullmatch(name or "")
    if match is None:
        return None
    space_name = match.group("space")
    if space_name not in by_space:
        return None
    if (
        getattr(type_obj, "pointer", False)
        or getattr(type_obj, "is_reference", False)
        or getattr(type_obj, "is_array", False)
        or getattr(type_obj, "is_fn_ptr", False)
        or getattr(type_obj, "ownership_domain", None) is not None
    ):
        raise StateSpaceFrontendError(
            f"typestate {name} currently requires a direct by-value type"
        )
    try:
        return certify_typestate(
            by_space[space_name],
            space_name,
            match.group("state"),
        )
    except Phase1SemanticError as error:
        raise StateSpaceFrontendError(str(error)) from error


def plan_state_space_frontend(module, bootstrap=None) -> StateSpaceFrontendPlan:
    """Certify source ``space`` declarations and direct declared typestates."""
    declarations = tuple(getattr(module, "state_spaces", ()))
    seen = set()
    spaces = []
    for decl in declarations:
        if not isinstance(decl, ParsedStateSpaceDecl):
            raise StateSpaceFrontendError(
                "production module contains an invalid State Space declaration"
            )
        if decl.name in seen:
            raise StateSpaceFrontendError(
                f"State Space {decl.name!r} is declared more than once"
            )
        seen.add(decl.name)
        spaces.append(_canonical_space(decl))

    by_space = {item.name: item for item in spaces}
    qualified = []
    if bootstrap is not None and by_space:
        for root in _iter_declared_types(module, bootstrap):
            for type_obj in _walk_type(root):
                fact = _qualified_type_fact(type_obj, by_space)
                if fact is not None:
                    qualified.append(fact)

    return StateSpaceFrontendPlan(
        declarations=declarations,
        spaces=tuple(spaces),
        qualified_types=tuple(qualified),
    )


def _preview_error(bootstrap, module, plan: StateSpaceFrontendPlan):
    decl = plan.declarations[0]
    raise bootstrap.SotlasBootstrapError(
        "State Spaces estão em PREVIEW no frontend: a semântica source/typestate "
        "foi certificada, mas o lowering SIR/backend do Sotlas 1.0 ainda não; "
        "o pipeline de produção rejeita este módulo fail-closed",
        decl.line,
        decl.column,
        getattr(module, "filename", None),
        getattr(module, "source", None),
    )


def _frontend_error_as_bootstrap(bootstrap, module, error):
    decls = tuple(getattr(module, "state_spaces", ()))
    line = decls[0].line if decls else 1
    column = decls[0].column if decls else 1
    raise bootstrap.SotlasBootstrapError(
        str(error),
        line,
        column,
        getattr(module, "filename", None),
        getattr(module, "source", None),
    ) from error


def _validate_state_local_initializers(module, plan, bootstrap):
    """Keep local typestate annotations from manufacturing arbitrary states.

    A fresh nominal struct value may acquire a typestate only when that space
    explicitly names the state as its initial state. Other typed locals must
    come from an already-qualified binding or a function with the exact return
    contract. The core checker validates calls and assignments after this pass.
    """
    functions = {item.name: item for item in getattr(module, "functions", ())}

    def fail(item, message):
        raise bootstrap.SotlasBootstrapError(
            message,
            item.token.line,
            item.token.column,
            getattr(module, "filename", None),
            getattr(module, "source", None),
        )

    def value_type(value, scope):
        if isinstance(value, bootstrap.Name):
            return scope.get(value.value)
        if isinstance(value, bootstrap.MoveExpr):
            return value_type(value.value, scope)
        if isinstance(value, bootstrap.Call):
            target = functions.get(value.callee)
            return getattr(target, "result", None) if target is not None else None
        return None

    def visit(items, inherited_scope):
        scope = dict(inherited_scope)
        for item in items:
            if isinstance(item, bootstrap.Let):
                expected = item.type
                if (
                    expected is not None
                    and getattr(expected, "state_space", None) is not None
                    and getattr(expected, "state_name", None) is not None
                ):
                    space = plan.space(expected.state_space)
                    value = item.value
                    if isinstance(value, bootstrap.StructLit):
                        if value.struct_name != expected.name:
                            fail(
                                item,
                                "typestate initializer nominal type does not match "
                                f"{expected.display()}",
                            )
                        if space.initial_state is None:
                            fail(
                                item,
                                f"state space {space.name!r} has no declared initial state",
                            )
                        if expected.state_name != space.initial_state:
                            fail(
                                item,
                                f"fresh {expected.name} value can only begin in "
                                f"initial state {space.initial_state}",
                            )
                    else:
                        actual = value_type(value, scope)
                        if actual is None or not bootstrap.same_type(
                            actual, expected
                        ):
                            fail(
                                item,
                                f"cannot establish {expected.display()} from this "
                                "initializer; use a value with the exact typestate contract",
                            )
                if item.type is not None:
                    scope[item.name] = item.type
                elif isinstance(item.value, bootstrap.StructLit):
                    scope[item.name] = bootstrap.Type(item.value.struct_name)
                else:
                    inferred = value_type(item.value, scope)
                    if inferred is not None:
                        scope[item.name] = inferred
            elif isinstance(item, bootstrap.If):
                visit(item.then_body, scope)
                visit(item.else_body, scope)
            elif isinstance(
                item, (bootstrap.While, bootstrap.Loop, bootstrap.Unsafe)
            ):
                visit(item.body, scope)
            elif isinstance(item, bootstrap.For):
                visit(item.body, scope)
            elif isinstance(item, bootstrap.Defer) and item.body is not None:
                visit(item.body, scope)

    for function in getattr(module, "functions", ()):
        visit(function.body, dict(function.params))


def install(bootstrap) -> None:
    """Install State Space syntax on the final canonical production frontend."""
    if getattr(bootstrap, "_STATE_SPACE_FRONTEND_INSTALLED", False):
        return

    bootstrap.KEYWORDS.add("space")
    base_parser = bootstrap.Parser

    class StateSpaceParser(base_parser):
        def __init__(self, tokens, filename=None, source=None):
            filtered, declarations = _extract_state_spaces(
                tokens, bootstrap, filename, source
            )
            self._sotlas_state_spaces = declarations
            self._sotlas_state_space_names = frozenset(
                item.name for item in declarations
            )
            super().__init__(filtered, filename=filename, source=source)

        def parse(self):
            module = super().parse()
            module.state_spaces = self._sotlas_state_spaces
            return module

        def type(self):
            if (
                self.current.kind == "IDENT"
                and self.current.text in self._sotlas_state_space_names
                and self.at + 1 < len(self.tokens)
                and self.tokens[self.at + 1].kind == "<"
            ):
                base = self.current
                self.at += 1
                self.expect("<")
                state = self.expect("IDENT")
                self.expect(">")
                return bootstrap.Type(
                    base.text,
                    state_space=base.text,
                    state_name=state.text,
                )
            return super().type()

    bootstrap.Parser = StateSpaceParser

    bootstrap.ParsedStatePayload = ParsedStatePayload
    bootstrap.ParsedState = ParsedState
    bootstrap.ParsedStateTransition = ParsedStateTransition
    bootstrap.ParsedStateSpaceDecl = ParsedStateSpaceDecl
    bootstrap.StateSpaceFrontendPlan = StateSpaceFrontendPlan

    def public_plan(module):
        return plan_state_space_frontend(module, bootstrap=bootstrap)

    bootstrap.plan_state_space_frontend = public_plan

    original_check = bootstrap.check

    def state_space_check(module, imported_fns=None, imported_types=None,
                          imported_enums=None, imported_globals=None):
        try:
            plan = public_plan(module)
        except StateSpaceFrontendError as error:
            _frontend_error_as_bootstrap(bootstrap, module, error)
        module.state_space_frontend_plan = plan
        phase1_internal = getattr(module, "_state_phase1_internal", False)
        if plan.declarations and not phase1_internal:
            _preview_error(bootstrap, module, plan)
        if plan.declarations:
            _validate_state_local_initializers(module, plan, bootstrap)
        module.state_transition_facts = ()
        result = original_check(
            module,
            imported_fns,
            imported_types,
            imported_enums,
            imported_globals,
        )
        if phase1_internal:
            module.state_transition_facts = tuple(
                getattr(module, "state_transition_facts", ())
            )
        return result

    bootstrap.check = state_space_check

    original_emit_c = bootstrap.emit_c

    def state_space_emit_c(module, *args, **kwargs):
        try:
            plan = public_plan(module)
        except StateSpaceFrontendError as error:
            _frontend_error_as_bootstrap(bootstrap, module, error)
        module.state_space_frontend_plan = plan
        if plan.declarations and not getattr(
            module, "_state_phase1_internal", False
        ):
            _preview_error(bootstrap, module, plan)
        return original_emit_c(module, *args, **kwargs)

    bootstrap.emit_c = state_space_emit_c

    original_emit_header = bootstrap.emit_header

    def state_space_emit_header(module, *args, **kwargs):
        try:
            plan = public_plan(module)
        except StateSpaceFrontendError as error:
            _frontend_error_as_bootstrap(bootstrap, module, error)
        module.state_space_frontend_plan = plan
        if plan.declarations and not getattr(
            module, "_state_phase1_internal", False
        ):
            _preview_error(bootstrap, module, plan)
        return original_emit_header(module, *args, **kwargs)

    bootstrap.emit_header = state_space_emit_header
    bootstrap._STATE_SPACE_FRONTEND_INSTALLED = True

__all__ = [
    "StateSpaceFrontendError",
    "ParsedStatePayload",
    "ParsedState",
    "ParsedStateTransition",
    "ParsedStateSpaceDecl",
    "StateSpaceFrontendPlan",
    "plan_state_space_frontend",
    "install",
]
