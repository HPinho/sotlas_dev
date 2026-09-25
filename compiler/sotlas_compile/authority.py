"""Backend-neutral Authority Domains for named ``@system`` capabilities.

Phase 3 replaces the old all-or-nothing hardware authority model with explicit
least-authority contracts without breaking the normative Sotlas systems-layer
boundary. Bare ``@system`` remains a legacy unrestricted implementation context;
named forms such as ``@system(pci.config)`` restrict which privileged ABI
boundaries the function body may cross.

A call to a source ``@system`` function is an encapsulated abstraction boundary:
the caller does not inherit or need the callee's internal hardware authority.
Direct privileged ABI/intrinsic calls are different: they are checked against
the caller's named Authority Domain. This keeps safe wrappers usable while
least authority is enforced exactly where code reaches hardware/ABI.
"""
from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
import re
from typing import Any, Iterator

from . import bootstrap
from .authority_abi import AuthorityABIContract, authority_abi_contract
from .typed_ast import Phase1SemanticError


class AuthorityDomainError(Phase1SemanticError):
    """Raised when an authority contract or authority call is invalid."""


_CAPABILITY_RE = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*$"
)
_SYSTEM_ATTR_RE = re.compile(r"^@system(?:\((.*)\))?$")
_LEGACY_PRIVILEGED_CONTEXT_ATTRS = frozenset({"@naked", "@interrupt"})


@dataclass(frozen=True)
class AuthorityContract:
    function: str
    capabilities: tuple[str, ...] = ()
    legacy_unrestricted: bool = False

    @property
    def is_system(self) -> bool:
        return self.legacy_unrestricted or bool(self.capabilities)

    def grants(self, capability: str) -> bool:
        return self.legacy_unrestricted or capability in self.capabilities


@dataclass(frozen=True)
class AuthorityCallEdge:
    caller: str
    callee: str
    point_id: str
    required_capabilities: tuple[str, ...]
    target_kind: str = "source"


@dataclass(frozen=True)
class AuthorityDomainPlan:
    contracts: tuple[AuthorityContract, ...]
    calls: tuple[AuthorityCallEdge, ...]

    def contract(self, function: str) -> AuthorityContract:
        matches = tuple(item for item in self.contracts if item.function == function)
        if len(matches) != 1:
            raise AuthorityDomainError(
                f"authority plan requires exactly one function {function!r}"
            )
        return matches[0]

    def calls_from(self, function: str) -> tuple[AuthorityCallEdge, ...]:
        self.contract(function)
        return tuple(item for item in self.calls if item.caller == function)


def _parse_capability_attribute(function: object) -> AuthorityContract:
    name = getattr(function, "name", None)
    if not isinstance(name, str) or not name:
        raise AuthorityDomainError("authority contract requires a function name")

    attributes = tuple(getattr(function, "attributes", ()) or ())
    system_attrs = tuple(
        item
        for item in attributes
        if isinstance(item, str)
        and (item == "@system" or item.startswith("@system("))
    )
    if not system_attrs:
        legacy_context = any(
            item in _LEGACY_PRIVILEGED_CONTEXT_ATTRS
            for item in attributes
            if isinstance(item, str)
        )
        return AuthorityContract(
            function=name,
            legacy_unrestricted=legacy_context,
        )
    if len(system_attrs) != 1:
        raise AuthorityDomainError(
            f"function {name!r} requires exactly one @system authority contract"
        )

    attribute = system_attrs[0]
    match = _SYSTEM_ATTR_RE.fullmatch(attribute)
    if match is None:
        raise AuthorityDomainError(
            f"function {name!r} has malformed authority attribute {attribute!r}"
        )
    payload = match.group(1)
    if payload is None:
        # Compatibility contract for the pre-Phase-3 all-or-nothing @system.
        return AuthorityContract(function=name, legacy_unrestricted=True)

    raw_items = tuple(part.strip() for part in payload.split(","))
    if not raw_items or any(not item for item in raw_items):
        raise AuthorityDomainError(
            f"function {name!r} requires at least one named @system capability"
        )
    for capability in raw_items:
        if _CAPABILITY_RE.fullmatch(capability) is None:
            raise AuthorityDomainError(
                f"function {name!r} has invalid authority capability {capability!r}"
            )
    if len(set(raw_items)) != len(raw_items):
        raise AuthorityDomainError(
            f"function {name!r} repeats an authority capability"
        )
    return AuthorityContract(function=name, capabilities=raw_items)


def _walk_direct_calls(value: Any) -> Iterator[object]:
    """Yield direct Call nodes recursively without reconstructing source order."""
    if isinstance(value, bootstrap.Call):
        yield value
    if value is None or isinstance(value, (str, bytes, int, float, bool)):
        return
    if isinstance(value, dict):
        for item in value.values():
            yield from _walk_direct_calls(item)
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            yield from _walk_direct_calls(item)
        return
    if is_dataclass(value):
        for item in fields(value):
            yield from _walk_direct_calls(getattr(value, item.name))


def _call_point_id(call: object) -> str:
    token = getattr(call, "token", None)
    line = getattr(token, "line", None)
    column = getattr(token, "column", None)
    if not isinstance(line, int) or not isinstance(column, int):
        raise AuthorityDomainError("authority call requires source-stable location")
    return f"call@{line}:{column}"


def _validate_call(
    caller: AuthorityContract,
    callee: AuthorityContract,
    *,
    point_id: str,
) -> AuthorityCallEdge | None:
    """Record a source-system abstraction boundary without capability leakage.

    The callee's authority describes what its own body may do. Calling that
    source abstraction does not grant the caller that authority and does not
    require the caller to already possess it.
    """
    if not callee.is_system:
        return None
    required = () if callee.legacy_unrestricted else callee.capabilities
    return AuthorityCallEdge(
        caller=caller.function,
        callee=callee.function,
        point_id=point_id,
        required_capabilities=required,
        target_kind="source",
    )


def _privileged_builtin(name: str):
    function = getattr(bootstrap, "BUILTIN_FUNCTIONS", {}).get(name)
    if function is None:
        return None
    attributes = tuple(getattr(function, "attributes", ()) or ())
    return function if "@system" in attributes else None


def _validate_abi_call(
    caller: AuthorityContract,
    abi: AuthorityABIContract,
    *,
    point_id: str,
) -> AuthorityCallEdge:
    missing = tuple(
        capability for capability in abi.capabilities
        if not caller.grants(capability)
    )
    if missing:
        raise AuthorityDomainError(
            f"authority intrinsic call {caller.function} -> {abi.symbol} at {point_id} "
            f"is missing capabilities: {', '.join(missing)}"
        )
    return AuthorityCallEdge(
        caller=caller.function,
        callee=abi.symbol,
        point_id=point_id,
        required_capabilities=abi.capabilities,
        target_kind=abi.kind,
    )


def _validate_legacy_intrinsic_call(
    caller: AuthorityContract,
    symbol: str,
    *,
    point_id: str,
) -> AuthorityCallEdge:
    if not caller.legacy_unrestricted:
        raise AuthorityDomainError(
            f"authority intrinsic call {caller.function} -> {symbol} at {point_id} "
            "requires legacy unrestricted @system authority because no named "
            "ABI contract exists"
        )
    return AuthorityCallEdge(
        caller=caller.function,
        callee=symbol,
        point_id=point_id,
        required_capabilities=(),
        target_kind="legacy_intrinsic",
    )


def plan_authority_domains(module: object) -> AuthorityDomainPlan:
    """Build and certify source boundaries and direct privileged ABI authority."""
    if not isinstance(module, bootstrap.Module):
        raise AuthorityDomainError("authority planning requires parsed Sotlas Module")

    functions = tuple(module.functions)
    contracts = tuple(_parse_capability_attribute(function) for function in functions)
    by_name: dict[str, AuthorityContract] = {}
    for contract in contracts:
        if contract.function in by_name:
            raise AuthorityDomainError(
                f"duplicate authority function {contract.function!r}"
            )
        by_name[contract.function] = contract

    calls: list[AuthorityCallEdge] = []
    seen_points: set[tuple[str, str]] = set()
    for function in functions:
        caller = by_name[function.name]
        for call in _walk_direct_calls(function.body):
            callee_name = getattr(call, "callee", None)
            if not isinstance(callee_name, str):
                continue
            point_id = _call_point_id(call)
            point_key = (caller.function, point_id)
            if point_key in seen_points:
                raise AuthorityDomainError(
                    f"duplicate authority call point {caller.function}::{point_id}"
                )
            seen_points.add(point_key)

            # Source declarations take precedence over builtin names so a
            # source function can never silently acquire an ABI authority
            # contract merely by sharing a symbol spelling.
            callee = by_name.get(callee_name)
            if callee is not None:
                edge = _validate_call(caller, callee, point_id=point_id)
                if edge is not None:
                    calls.append(edge)
                continue

            builtin = _privileged_builtin(callee_name)
            if builtin is None:
                # Ordinary unknown/external calls remain outside this intrinsic
                # slice. FFI gets a separate authority contract.
                continue
            abi = authority_abi_contract(callee_name)
            if abi is not None:
                calls.append(_validate_abi_call(caller, abi, point_id=point_id))
            else:
                calls.append(
                    _validate_legacy_intrinsic_call(
                        caller, callee_name, point_id=point_id
                    )
                )

    return AuthorityDomainPlan(contracts=contracts, calls=tuple(calls))


__all__ = [
    "AuthorityDomainError",
    "AuthorityContract",
    "AuthorityCallEdge",
    "AuthorityDomainPlan",
    "plan_authority_domains",
]
