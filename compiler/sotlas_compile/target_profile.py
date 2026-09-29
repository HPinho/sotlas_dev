"""Canonical Sotlas target-profile frontend contract.

This extension gives the production bootstrap frontend an explicit execution
profile without creating a second parser.  It recognizes the grammar-level
``target <profile>;`` declaration plus the transitional ``barecore;`` spelling,
attaches one immutable profile plan to the parsed module, and keeps unsupported
backend/profile combinations fail-closed.
"""
from __future__ import annotations

from dataclasses import dataclass


SUPPORTED_TARGET_PROFILES = frozenset({"barecore", "native", "web"})


@dataclass(frozen=True)
class TargetProfilePlan:
    """Canonical source-level execution-profile fact."""

    profile: str
    explicit: bool
    spelling: str | None = None
    line: int = 1
    column: int = 1

    @property
    def is_barecore(self) -> bool:
        return self.profile == "barecore"

    @property
    def is_native(self) -> bool:
        return self.profile == "native"

    @property
    def is_web(self) -> bool:
        return self.profile == "web"

    @property
    def is_freestanding(self) -> bool:
        return self.is_barecore


def _token_offset(source: str, token) -> int:
    lines = source.splitlines(keepends=True)
    line_index = max(0, int(token.line) - 1)
    if line_index >= len(lines):
        return len(source)
    return min(
        len(source),
        sum(len(line) for line in lines[:line_index])
        + max(0, int(token.column) - 1),
    )


def _masked_prefix(source: str, end_offset: int) -> str:
    prefix = source[:end_offset]
    return "".join("\n" if ch == "\n" else " " for ch in prefix) + source[end_offset:]


def _raise(bootstrap, message: str, token, filename: str | None, source: str):
    raise bootstrap.SotlasBootstrapError(
        message,
        token.line,
        token.column,
        filename,
        source,
    )


def _read_profile_prefix(bootstrap, source: str, filename: str | None):
    tokens = bootstrap.lex(source, filename)
    first = tokens[0]
    first_text = getattr(first, "text", "")

    if first_text not in ("target", "barecore"):
        return TargetProfilePlan("native", False), source

    if first_text == "barecore":
        semicolon = tokens[1]
        if semicolon.kind != ";":
            _raise(
                bootstrap,
                "esperado ';' após barecore target profile",
                semicolon,
                filename,
                source,
            )
        plan = TargetProfilePlan(
            "barecore", True, "barecore;", first.line, first.column
        )
        next_index = 2
        end_offset = _token_offset(source, semicolon) + len(semicolon.text)
    else:
        profile_token = tokens[1]
        if profile_token.kind in (";", "EOF"):
            _raise(
                bootstrap,
                "target profile ausente após 'target'",
                profile_token,
                filename,
                source,
            )
        profile = profile_token.text
        if profile not in SUPPORTED_TARGET_PROFILES:
            _raise(
                bootstrap,
                f"target profile não suportado: {profile}",
                profile_token,
                filename,
                source,
            )
        semicolon = tokens[2]
        if semicolon.kind != ";":
            _raise(
                bootstrap,
                "esperado ';' após target profile",
                semicolon,
                filename,
                source,
            )
        plan = TargetProfilePlan(
            profile,
            True,
            f"target {profile};",
            first.line,
            first.column,
        )
        next_index = 3
        end_offset = _token_offset(source, semicolon) + len(semicolon.text)

    if next_index < len(tokens):
        next_token = tokens[next_index]
        if getattr(next_token, "text", "") in ("target", "barecore"):
            _raise(
                bootstrap,
                "target profile duplicado",
                next_token,
                filename,
                source,
            )

    return plan, _masked_prefix(source, end_offset)


def plan_target_profile(module) -> TargetProfilePlan:
    plan = getattr(module, "target_profile_plan", None)
    if isinstance(plan, TargetProfilePlan):
        return plan
    profile = getattr(module, "target_profile", "native")
    return TargetProfilePlan(
        profile,
        bool(getattr(module, "target_profile_explicit", False)),
    )


def require_backend_profile(module, backend: str, bootstrap=None) -> TargetProfilePlan:
    """Fail closed until a backend has an explicit profile contract."""

    plan = plan_target_profile(module)
    if backend == "c11" and plan.profile == "native":
        return plan

    if bootstrap is None:
        raise ValueError(
            f"{backend} backend does not lower target {plan.profile} yet"
        )
    raise bootstrap.SotlasBootstrapError(
        f"{backend} backend does not lower target {plan.profile} yet",
        plan.line,
        plan.column,
        getattr(module, "filename", None),
        getattr(module, "source", None),
    )


def install(bootstrap) -> None:
    """Install target-profile parsing into the one canonical bootstrap route."""

    if getattr(bootstrap, "_TARGET_PROFILE_FRONTEND_INSTALLED", False):
        return

    original_parse = bootstrap.parse
    original_emit_c = bootstrap.emit_c

    def parse_with_target_profile(source: str, filename: str | None = None):
        plan, parser_source = _read_profile_prefix(
            bootstrap, source, filename
        )
        module = original_parse(parser_source, filename=filename)
        # Parser offsets remain correct because the directive is masked without
        # changing source length or line breaks.  Restore the original source so
        # diagnostics quote what the programmer actually wrote.
        module.source = source
        module.target_profile_plan = plan
        module.target_profile = plan.profile
        module.target_profile_explicit = plan.explicit
        module.is_barecore = plan.is_barecore
        return module

    def emit_c_with_target_profile(module, *args, **kwargs):
        require_backend_profile(module, "c11", bootstrap=bootstrap)
        return original_emit_c(module, *args, **kwargs)

    bootstrap.parse = parse_with_target_profile
    bootstrap.emit_c = emit_c_with_target_profile
    bootstrap.TargetProfilePlan = TargetProfilePlan
    bootstrap.SUPPORTED_TARGET_PROFILES = SUPPORTED_TARGET_PROFILES
    bootstrap.plan_target_profile = plan_target_profile
    bootstrap.require_backend_profile = require_backend_profile
    bootstrap._TARGET_PROFILE_FRONTEND_INSTALLED = True
