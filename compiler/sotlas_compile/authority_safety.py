"""Least-authority safety enforcement over the current canonical SIR.

Authority Domains are carried as a sidecar certificate because the prototype
SIR still exposes only the historical boolean ``is_system``.  Keeping this
pass in ``sotlas_compile`` avoids an import cycle from the generic SIR package
back into the compiler semantic layer.

Calls to source functions covered by ``AuthoritySIRCertificate`` are checked
with named least-authority semantics.  System calls outside that certificate
(intrinsics/external ABI) deliberately retain the legacy boolean rule and are
therefore fail-closed for named-only callers until explicit ABI authority
contracts exist.
"""
from __future__ import annotations

from dataclasses import dataclass

from .authority_sir import AuthoritySIRCertificate
from .canonical_sir import load_canonical_sir
from .typed_ast import Phase1SemanticError


class AuthoritySIRSafetyError(Phase1SemanticError):
    """Raised when certified authority is unsafe for the represented SIR."""


@dataclass(frozen=True)
class AuthoritySIRSafetyResult:
    success: bool
    errors: tuple[str, ...] = ()

    def require_success(self) -> None:
        if not self.success:
            raise AuthoritySIRSafetyError("; ".join(self.errors))


class AuthoritySIRSafetyPass:
    """Validate named Authority Domains against a certified SIR sidecar."""

    def __init__(self, certificate: AuthoritySIRCertificate):
        if not isinstance(certificate, AuthoritySIRCertificate):
            raise AuthoritySIRSafetyError(
                "authority SIR safety requires canonical AuthoritySIRCertificate"
            )
        self.certificate = certificate

    @staticmethod
    def _function_maps(certificate: AuthoritySIRCertificate):
        facts = {}
        errors: list[str] = []
        for fact in certificate.functions:
            if fact.function in facts:
                errors.append(
                    f"authority SIR safety has duplicate function fact {fact.function!r}"
                )
                continue
            if fact.legacy_unrestricted and fact.capabilities:
                errors.append(
                    f"authority function {fact.function!r} mixes legacy and named authority"
                )
                continue
            if len(set(fact.capabilities)) != len(fact.capabilities):
                errors.append(
                    f"authority function {fact.function!r} repeats a capability"
                )
                continue
            facts[fact.function] = fact
        return facts, errors

    @staticmethod
    def _group_maps(certificate: AuthoritySIRCertificate, facts):
        groups = {}
        errors: list[str] = []
        for group in certificate.call_groups:
            key = (group.caller, group.callee)
            if key in groups:
                errors.append(
                    f"authority SIR safety has duplicate call group {group.caller} -> {group.callee}"
                )
                continue
            caller = facts.get(group.caller)
            target = facts.get(group.callee)
            if caller is None or target is None:
                errors.append(
                    f"authority call group {group.caller} -> {group.callee} references a missing function fact"
                )
                continue
            if group.sir_call_count != len(group.source_point_ids):
                errors.append(
                    f"authority call group {group.caller} -> {group.callee} count diverges from source identities"
                )
                continue
            if len(set(group.source_point_ids)) != len(group.source_point_ids):
                errors.append(
                    f"authority call group {group.caller} -> {group.callee} repeats a source identity"
                )
                continue
            if not target.is_system:
                errors.append(
                    f"authority call group {group.caller} -> {group.callee} targets a non-system function"
                )
                continue
            if group.requires_legacy_unrestricted != target.legacy_unrestricted:
                errors.append(
                    f"authority call group {group.caller} -> {group.callee} disagrees on legacy authority"
                )
                continue

            if target.legacy_unrestricted:
                if group.required_capabilities:
                    errors.append(
                        f"legacy authority call {group.caller} -> {group.callee} must not claim named capabilities"
                    )
                    continue
                if not caller.legacy_unrestricted:
                    errors.append(
                        f"authority call {group.caller} -> {group.callee} requires legacy unrestricted @system authority"
                    )
                    continue
            else:
                if group.required_capabilities != target.capabilities:
                    errors.append(
                        f"authority call {group.caller} -> {group.callee} required capabilities diverge from target contract"
                    )
                    continue
                if not caller.legacy_unrestricted:
                    missing = tuple(
                        capability
                        for capability in target.capabilities
                        if capability not in caller.capabilities
                    )
                    if missing:
                        errors.append(
                            f"authority call {group.caller} -> {group.callee} is missing capabilities: {', '.join(missing)}"
                        )
                        continue
            groups[key] = group
        return groups, errors

    def run(self, sir_module: object) -> AuthoritySIRSafetyResult:
        sir = load_canonical_sir()
        module = getattr(sir_module, "module", sir_module)
        if not isinstance(module, sir.SIRModule):
            return AuthoritySIRSafetyResult(
                False,
                ("authority SIR safety requires canonical SIRModule",),
            )

        facts, errors = self._function_maps(self.certificate)
        groups, group_errors = self._group_maps(self.certificate, facts)
        errors.extend(group_errors)

        functions = {}
        for function in tuple(getattr(module, "functions", ()) or ()):
            name = getattr(function, "name", None)
            if not isinstance(name, str) or not name:
                errors.append("authority SIR safety found function without canonical name")
                continue
            if name in functions:
                errors.append(
                    f"authority SIR safety found duplicate SIR function {name!r}"
                )
                continue
            functions[name] = function

        for name, fact in facts.items():
            function = functions.get(name)
            if function is None:
                errors.append(
                    f"authority certificate function {name!r} is missing from SIR"
                )
                continue
            if bool(getattr(function, "is_system", False)) != fact.sir_is_system:
                errors.append(
                    f"authority function {name!r} changed its legacy SIR system marker after certification"
                )

        actual: dict[tuple[str, str], int] = {}
        for function in functions.values():
            caller_fact = facts.get(function.name)
            for block in tuple(getattr(function, "blocks", ()) or ()):
                for instruction in tuple(getattr(block, "instructions", ()) or ()):
                    if not isinstance(instruction, sir.CallInst):
                        continue
                    callee = getattr(instruction, "callee", None)
                    target_fact = facts.get(callee)
                    if target_fact is not None and target_fact.is_system:
                        key = (function.name, callee)
                        actual[key] = actual.get(key, 0) + 1
                        if caller_fact is None:
                            errors.append(
                                f"authority caller {function.name!r} has no certified fact for system call {callee!r}"
                            )
                        continue

                    # External/intrinsic authority is deliberately not guessed.
                    # Preserve the old rule until a named ABI contract exists.
                    if bool(getattr(instruction, "is_system", False)) and not bool(
                        getattr(function, "is_system", False)
                    ):
                        errors.append(
                            f"sir safety error: chamada para função @system '{callee}' "
                            f"em função não-privilegiada '{function.name}'"
                        )

        for key, group in groups.items():
            represented = actual.get(key, 0)
            if represented != group.sir_call_count:
                errors.append(
                    f"authority certified call group {key[0]} -> {key[1]} expects "
                    f"{group.sir_call_count} calls, got {represented}"
                )

        for key, represented in actual.items():
            if key not in groups:
                errors.append(
                    f"authority system call group {key[0]} -> {key[1]} has "
                    f"{represented} SIR call(s) but no certified source authority edge"
                )

        return AuthoritySIRSafetyResult(
            success=not errors,
            errors=tuple(errors),
        )


def enforce_authority_sir_safety(
    certificate: AuthoritySIRCertificate,
    sir_module: object,
) -> AuthoritySIRSafetyResult:
    """Run the canonical Authority-Domain safety pass over SIR."""
    return AuthoritySIRSafetyPass(certificate).run(sir_module)


__all__ = [
    "AuthoritySIRSafetyError",
    "AuthoritySIRSafetyResult",
    "AuthoritySIRSafetyPass",
    "enforce_authority_sir_safety",
]
