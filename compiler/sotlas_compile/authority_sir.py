"""Bridge canonical Authority Domains into the current SIR without inventing call IDs.

The prototype SIR still carries only the legacy boolean ``is_system`` marker and
``CallInst`` does not yet store source-stable ``call@line:column`` identities.
This bridge therefore keeps authority as a checked sidecar certificate.  It
proves that every source-level system call represented by ``AuthorityDomainPlan``
has the same caller/callee multiplicity in SIR while preserving named
capabilities and legacy unrestricted authority.

Repeated calls are certified as groups rather than being paired by list order.
That avoids claiming per-call identity the SIR does not yet possess.
"""
from __future__ import annotations

from dataclasses import dataclass

from .authority import AuthorityDomainPlan, AuthorityDomainError
from .canonical_sir import load_canonical_sir
from .typed_ast import Phase1SemanticError


class AuthoritySIRError(Phase1SemanticError):
    """Raised when canonical authority facts diverge from represented SIR."""


@dataclass(frozen=True)
class AuthoritySIRFunctionFact:
    function: str
    capabilities: tuple[str, ...]
    legacy_unrestricted: bool
    sir_is_system: bool

    @property
    def is_system(self) -> bool:
        return self.legacy_unrestricted or bool(self.capabilities)


@dataclass(frozen=True)
class AuthoritySIRCallGroup:
    caller: str
    callee: str
    source_point_ids: tuple[str, ...]
    required_capabilities: tuple[str, ...]
    requires_legacy_unrestricted: bool
    sir_call_count: int


@dataclass(frozen=True)
class AuthoritySIRCertificate:
    functions: tuple[AuthoritySIRFunctionFact, ...]
    call_groups: tuple[AuthoritySIRCallGroup, ...]

    def function(self, name: str) -> AuthoritySIRFunctionFact:
        matches = tuple(item for item in self.functions if item.function == name)
        if len(matches) != 1:
            raise AuthoritySIRError(
                f"authority SIR certificate requires exactly one function {name!r}"
            )
        return matches[0]

    def calls_from(self, caller: str) -> tuple[AuthoritySIRCallGroup, ...]:
        self.function(caller)
        return tuple(item for item in self.call_groups if item.caller == caller)


def _unwrap_module(value: object):
    sir = load_canonical_sir()
    module = getattr(value, "module", value)
    if not isinstance(module, sir.SIRModule):
        raise AuthoritySIRError(
            "authority SIR certification requires canonical SIRModule"
        )
    return sir, module


def _sir_call_counts(sir, function) -> dict[str, int]:
    counts: dict[str, int] = {}
    for block in tuple(getattr(function, "blocks", ()) or ()):
        for instruction in tuple(getattr(block, "instructions", ()) or ()):
            if not isinstance(instruction, sir.CallInst):
                continue
            callee = getattr(instruction, "callee", None)
            if not isinstance(callee, str) or not callee:
                raise AuthoritySIRError(
                    f"authority SIR call in {function.name!r} lacks callee identity"
                )
            counts[callee] = counts.get(callee, 0) + 1
    return counts


def certify_authority_sir(
    authority: AuthorityDomainPlan,
    sir_module: object,
) -> AuthoritySIRCertificate:
    """Certify least-authority facts against the SIR representation currently available."""
    if not isinstance(authority, AuthorityDomainPlan):
        raise AuthoritySIRError(
            "authority SIR certification requires canonical AuthorityDomainPlan"
        )

    sir, module = _unwrap_module(sir_module)
    sir_functions: dict[str, object] = {}
    for function in tuple(getattr(module, "functions", ()) or ()):
        name = getattr(function, "name", None)
        if not isinstance(name, str) or not name:
            raise AuthoritySIRError("authority SIR function lacks canonical name")
        if name in sir_functions:
            raise AuthoritySIRError(
                f"authority SIR contains duplicate function {name!r}"
            )
        sir_functions[name] = function

    facts: list[AuthoritySIRFunctionFact] = []
    contract_by_name = {item.function: item for item in authority.contracts}
    if len(contract_by_name) != len(authority.contracts):
        raise AuthoritySIRError("authority plan contains duplicate function contracts")

    for contract in authority.contracts:
        function = sir_functions.get(contract.function)
        if function is None:
            raise AuthoritySIRError(
                f"authority SIR is missing function {contract.function!r}"
            )
        sir_is_system = bool(getattr(function, "is_system", False))
        if contract.legacy_unrestricted and not sir_is_system:
            raise AuthoritySIRError(
                f"legacy @system function {contract.function!r} lost its SIR system marker"
            )
        facts.append(
            AuthoritySIRFunctionFact(
                function=contract.function,
                capabilities=contract.capabilities,
                legacy_unrestricted=contract.legacy_unrestricted,
                sir_is_system=sir_is_system,
            )
        )

    source_groups: dict[tuple[str, str], list[object]] = {}
    for edge in authority.calls:
        source_groups.setdefault((edge.caller, edge.callee), []).append(edge)

    call_groups: list[AuthoritySIRCallGroup] = []
    for caller_contract in authority.contracts:
        caller_sir = sir_functions[caller_contract.function]
        sir_counts = _sir_call_counts(sir, caller_sir)

        # Only calls to source functions with authority requirements participate
        # in this certificate. External/intrinsic authority gets its own ABI
        # contract later rather than being guessed here.
        relevant_callees = {
            name
            for name, contract in contract_by_name.items()
            if contract.is_system and sir_counts.get(name, 0) > 0
        }
        relevant_callees.update(
            callee
            for (caller, callee) in source_groups
            if caller == caller_contract.function
        )

        for callee in sorted(relevant_callees):
            edges = tuple(
                source_groups.get((caller_contract.function, callee), ())
            )
            count = sir_counts.get(callee, 0)
            if count != len(edges):
                raise AuthoritySIRError(
                    f"authority SIR call group {caller_contract.function} -> {callee} "
                    f"requires {len(edges)} represented calls, got {count}"
                )
            if not edges:
                # A SIR call to a source @system function that has no certified
                # source authority edge is an untrusted lowering artifact.
                raise AuthoritySIRError(
                    f"authority SIR call {caller_contract.function} -> {callee} "
                    "has no certified source authority edge"
                )

            required = edges[0].required_capabilities
            if any(edge.required_capabilities != required for edge in edges):
                raise AuthoritySIRError(
                    f"authority source edges disagree for {caller_contract.function} -> {callee}"
                )
            target = contract_by_name[callee]
            call_groups.append(
                AuthoritySIRCallGroup(
                    caller=caller_contract.function,
                    callee=callee,
                    source_point_ids=tuple(edge.point_id for edge in edges),
                    required_capabilities=required,
                    requires_legacy_unrestricted=target.legacy_unrestricted,
                    sir_call_count=count,
                )
            )

    return AuthoritySIRCertificate(
        functions=tuple(facts),
        call_groups=tuple(call_groups),
    )


__all__ = [
    "AuthoritySIRError",
    "AuthoritySIRFunctionFact",
    "AuthoritySIRCallGroup",
    "AuthoritySIRCertificate",
    "certify_authority_sir",
]
