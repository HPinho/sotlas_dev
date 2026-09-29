"""Canonical target-profile contract for the production Sotlas frontend.

Target profiles are contextual at the file header so adding the contract does not
reserve ordinary identifiers such as ``native`` or ``web`` elsewhere in source.
The parser records one immutable semantic fact on each module; backend layers
consume that fact instead of re-reading source text.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TargetProfile:
    name: str
    freestanding: bool
    hosted: bool
    web: bool


TARGET_NATIVE = TargetProfile("native", freestanding=False, hosted=True, web=False)
TARGET_BARECORE = TargetProfile(
    "barecore", freestanding=True, hosted=False, web=False
)
TARGET_WEB = TargetProfile("web", freestanding=False, hosted=False, web=True)

_TARGETS = {
    profile.name: profile
    for profile in (TARGET_NATIVE, TARGET_BARECORE, TARGET_WEB)
}

_BARECORE_TYPE_DEFS = r"""/* Sotlas barecore ABI: no hosted C headers. */
#ifndef SOTLAS_BARECORE_ABI_TYPES
#define SOTLAS_BARECORE_ABI_TYPES 1
typedef __INT8_TYPE__ int8_t;
typedef __UINT8_TYPE__ uint8_t;
typedef __INT16_TYPE__ int16_t;
typedef __UINT16_TYPE__ uint16_t;
typedef __INT32_TYPE__ int32_t;
typedef __UINT32_TYPE__ uint32_t;
typedef __INT64_TYPE__ int64_t;
typedef __UINT64_TYPE__ uint64_t;
typedef __INTPTR_TYPE__ intptr_t;
typedef __UINTPTR_TYPE__ uintptr_t;
typedef __SIZE_TYPE__ size_t;
typedef _Bool bool;
#ifndef true
#define true 1
#endif
#ifndef false
#define false 0
#endif
#ifndef NULL
#define NULL ((void *)0)
#endif
#ifndef UINT64_C
#define UINT64_C(value) value##ULL
#endif
#endif
"""

_HOSTED_INCLUDE_LINES = frozenset(
    {
        "#include <stdint.h>",
        "#include <stddef.h>",
        "#include <stdbool.h>",
        "#include <stdlib.h>",
        "#include <stdio.h>",
        "#include <string.h>",
        "#include <pthread.h>",
    }
)


def target_profile_of(module) -> TargetProfile:
    """Return the canonical target profile for a parsed module."""
    name = getattr(module, "target_profile", "native")
    try:
        return _TARGETS[name]
    except KeyError as error:
        raise ValueError(f"unknown Sotlas target profile: {name!r}") from error


def _assign_profile(module, profile: TargetProfile, *, explicit: bool) -> None:
    module.target_profile = profile.name
    module.target_profile_facts = profile
    module.target_profile_explicit = explicit
    module.is_barecore = profile.freestanding


def _propagate_project_target(bootstrap, entry, modules):
    if not modules:
        return modules
    try:
        entry_path = entry.resolve()
    except AttributeError:
        entry_path = entry
    root = None
    for module in modules:
        filename = getattr(module, "filename", None)
        if not filename:
            continue
        try:
            candidate = Path(filename).resolve()
        except (OSError, RuntimeError):
            continue
        if candidate == entry_path:
            root = module
            break
    if root is None:
        root = modules[-1]

    root_profile = target_profile_of(root)
    for module in modules:
        if module is root:
            continue
        profile = target_profile_of(module)
        if getattr(module, "target_profile_explicit", False):
            if profile.name != root_profile.name:
                raise bootstrap.SotlasBootstrapError(
                    f"target profile mismatch: project {root_profile.name!r} "
                    f"cannot import explicit {profile.name!r} module {module.name!r}",
                    1,
                    1,
                    module.filename,
                    module.source,
                )
            continue
        _assign_profile(module, root_profile, explicit=False)
    return modules


def install(bootstrap) -> None:
    """Install target-header parsing into the one canonical frontend."""
    if getattr(bootstrap, "_TARGET_PROFILE_FRONTEND_INSTALLED", False):
        return

    base_parser = bootstrap.Parser

    class TargetProfileParser(base_parser):
        """Parse an optional target header before the mandatory module header."""

        def _accept_contextual_word(self, word: str):
            token = self.current
            if token.text == word:
                self.at += 1
                return token
            return None

        def _parse_target_profile(self):
            explicit = False
            profile = TARGET_NATIVE

            target_token = self._accept_contextual_word("target")
            if target_token is not None:
                explicit = True
                profile_token = self.current
                if profile_token.kind in (";", "EOF"):
                    raise bootstrap.SotlasBootstrapError(
                        "target profile name expected after 'target'",
                        profile_token.line,
                        profile_token.column,
                        self.filename,
                        self.source,
                    )
                self.at += 1
                profile = _TARGETS.get(profile_token.text)
                if profile is None:
                    raise bootstrap.SotlasBootstrapError(
                        f"unsupported target profile {profile_token.text!r}",
                        profile_token.line,
                        profile_token.column,
                        self.filename,
                        self.source,
                    )
                self.expect(";")
            else:
                barecore_token = self._accept_contextual_word("barecore")
                if barecore_token is not None:
                    explicit = True
                    profile = TARGET_BARECORE
                    self.expect(";")

            if self.current.text in ("target", "barecore"):
                duplicate = self.current
                raise bootstrap.SotlasBootstrapError(
                    "target profile may be declared only once before module",
                    duplicate.line,
                    duplicate.column,
                    self.filename,
                    self.source,
                )
            return profile, explicit

        def parse(self):
            profile, explicit = self._parse_target_profile()
            module = super().parse()
            _assign_profile(module, profile, explicit=explicit)
            return module

    bootstrap.Parser = TargetProfileParser
    bootstrap.TargetProfile = TargetProfile
    bootstrap.TARGET_NATIVE = TARGET_NATIVE
    bootstrap.TARGET_BARECORE = TARGET_BARECORE
    bootstrap.TARGET_WEB = TARGET_WEB
    original_compile_project = bootstrap.compile_project

    def target_compile_project(entry):
        modules = original_compile_project(entry)
        return _propagate_project_target(bootstrap, entry, modules)

    bootstrap.compile_project = target_compile_project
    bootstrap.target_profile_of = target_profile_of
    bootstrap._TARGET_PROFILE_FRONTEND_INSTALLED = True


def _walk_values(value):
    """Yield nested dataclass/list/tuple values without following token metadata."""
    if value is None:
        return
    yield value
    if isinstance(value, (tuple, list)):
        for item in value:
            yield from _walk_values(item)
        return
    fields = getattr(value, "__dataclass_fields__", None)
    if not fields:
        return
    for field_name in fields:
        if field_name in {"token", "target_profile_facts"}:
            continue
        yield from _walk_values(getattr(value, field_name, None))


def _barecore_uses_share(bootstrap, module) -> bool:
    return any(
        isinstance(value, bootstrap.ShareExpr)
        for value in _walk_values(module)
    )


def _barecore_has_heap_owned_enum_payload(module) -> bool:
    sole_types = {
        item.name for item in module.structs
        if item.is_sole and not item.is_register
    }
    return any(
        variant.payload_type is not None
        and variant.payload_type.name in sole_types
        and not variant.payload_type.pointer
        and not variant.payload_type.is_reference
        for enum_obj in module.enums
        for variant in enum_obj.variants
    )


def _strip_hosted_includes(code: str) -> str:
    lines = [
        line
        for line in code.splitlines()
        if line.strip() not in _HOSTED_INCLUDE_LINES
    ]
    suffix = "\n" if code.endswith("\n") else ""
    return "\n".join(lines) + suffix


def _freestanding_preamble(bootstrap) -> str:
    return (
        _BARECORE_TYPE_DEFS.rstrip()
        + "\n\n"
        + _strip_hosted_includes(bootstrap.PREAMBLE).lstrip()
    )


def _requested_include_preamble(args, kwargs) -> bool:
    if "include_preamble" in kwargs:
        return bool(kwargs["include_preamble"])
    # emit_c(module, mangle=False, include_preamble=True, ...)
    return bool(args[1]) if len(args) >= 2 else True


def _without_preamble(args, kwargs):
    args = list(args)
    kwargs = dict(kwargs)
    if len(args) >= 2:
        args[1] = False
        kwargs.pop("include_preamble", None)
    else:
        kwargs["include_preamble"] = False
    return tuple(args), kwargs


def _reject_barecore_hosted_lowering(bootstrap, module) -> None:
    if _barecore_uses_share(bootstrap, module):
        raise bootstrap.SotlasBootstrapError(
            "target barecore forbids implicit shared/ARC heap lowering; "
            "use explicit freestanding ownership until a Sotlas allocator is bound",
            1,
            1,
            module.filename,
            module.source,
        )
    if _barecore_has_heap_owned_enum_payload(module):
        raise bootstrap.SotlasBootstrapError(
            "target barecore does not implicitly heap-allocate sole enum payloads",
            1,
            1,
            module.filename,
            module.source,
        )


def _assert_freestanding_output(bootstrap, module, code: str) -> None:
    for line in code.splitlines():
        if line.strip() in _HOSTED_INCLUDE_LINES:
            raise bootstrap.SotlasBootstrapError(
                f"target barecore emitted hosted dependency {line.strip()!r}",
                1,
                1,
                module.filename,
                module.source,
            )


def install_c11_backend(bootstrap) -> None:
    """Make C11 honor target facts at the final canonical backend boundary."""
    if getattr(bootstrap, "_TARGET_PROFILE_C11_INSTALLED", False):
        return

    original_emit_c = bootstrap.emit_c
    original_emit_header = bootstrap.emit_header
    original_emit_c_project = bootstrap.emit_c_project

    def target_emit_c(module, *args, **kwargs):
        profile = target_profile_of(module)
        if profile.web:
            raise bootstrap.SotlasBootstrapError(
                "target web cannot be lowered by the C11 backend",
                1,
                1,
                module.filename,
                module.source,
            )
        if not profile.freestanding:
            return original_emit_c(module, *args, **kwargs)

        _reject_barecore_hosted_lowering(bootstrap, module)
        include_preamble = _requested_include_preamble(args, kwargs)
        inner_args, inner_kwargs = _without_preamble(args, kwargs)
        code = original_emit_c(module, *inner_args, **inner_kwargs)

        # Source contracts must not silently pull libc into the kernel.
        code = code.replace("abort();", "__builtin_trap();")
        code = _strip_hosted_includes(code)
        _assert_freestanding_output(bootstrap, module, code)

        if include_preamble:
            return _freestanding_preamble(bootstrap).rstrip() + "\n\n" + code.lstrip()
        return code

    def target_emit_header(module):
        profile = target_profile_of(module)
        if profile.web:
            raise bootstrap.SotlasBootstrapError(
                "target web cannot emit a C11 header",
                1,
                1,
                module.filename,
                module.source,
            )
        header = original_emit_header(module)
        if not profile.freestanding:
            return header
        _reject_barecore_hosted_lowering(bootstrap, module)
        header = _strip_hosted_includes(header)
        header = header.replace("abort();", "__builtin_trap();")
        _assert_freestanding_output(bootstrap, module, header)
        return _BARECORE_TYPE_DEFS.rstrip() + "\n\n" + header.lstrip()

    def target_emit_c_project(entry, output):
        modules = bootstrap.compile_project(entry)
        if not modules:
            return original_emit_c_project(entry, output)
        root = modules[-1]
        profile = target_profile_of(root)
        if profile.web:
            raise bootstrap.SotlasBootstrapError(
                "target web cannot be lowered by the C11 backend",
                1,
                1,
                root.filename,
                root.source,
            )
        if not profile.freestanding:
            return original_emit_c_project(entry, output)

        fragments = [_freestanding_preamble(bootstrap)]
        for module in modules:
            fragments.append(
                bootstrap.emit_c(
                    module, mangle=False, include_preamble=False
                )
            )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("\n".join(fragments), encoding="utf-8")

    bootstrap.emit_c = target_emit_c
    bootstrap.emit_header = target_emit_header
    bootstrap.emit_c_project = target_emit_c_project
    bootstrap._TARGET_PROFILE_C11_INSTALLED = True
