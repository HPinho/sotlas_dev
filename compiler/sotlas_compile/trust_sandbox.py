"""Certification boundary for ``@trust(isolated)`` foreign calls.

Source analysis intentionally leaves isolated boundaries unverified.  This
module defines the additional evidence a concrete sandbox provider must supply
before tooling/backend code may set ``isolation_verified=True``.  It does not
pretend that a sandbox exists merely because a provider object was registered.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Protocol, runtime_checkable

from .trust_domains import ForeignTrustBoundary


class TrustSandboxError(ValueError):
    """Raised when an isolation claim lacks complete sandbox evidence."""


REQUIRED_SANDBOX_CAPABILITIES = frozenset({
    "address_space_isolation",
    "syscall_filtering",
    "resource_limits",
    "explicit_teardown",
})


@dataclass(frozen=True)
class SandboxPolicy:
    policy_id: str
    allowed_effects: frozenset[str]
    memory_limit_bytes: int
    timeout_ms: int


@dataclass(frozen=True)
class SandboxAttestation:
    symbol: str
    provider: str
    target: str
    policy_id: str
    capabilities: frozenset[str]
    isolation_established: bool


@dataclass(frozen=True)
class CertifiedIsolatedBoundary:
    boundary: ForeignTrustBoundary
    attestation: SandboxAttestation

    @property
    def isolation_verified(self) -> bool:
        return self.boundary.isolation_verified


@runtime_checkable
class SandboxProvider(Protocol):
    name: str

    def attest(
        self, boundary: ForeignTrustBoundary, policy: SandboxPolicy
    ) -> SandboxAttestation: ...


def _text(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TrustSandboxError(f"{label} requires a non-empty identity")
    return value


def _validate_policy(policy: SandboxPolicy) -> SandboxPolicy:
    if not isinstance(policy, SandboxPolicy):
        raise TrustSandboxError("sandbox certification requires an explicit policy")
    _text(policy.policy_id, label="sandbox policy")
    if not isinstance(policy.allowed_effects, frozenset) or any(
        not isinstance(effect, str) or not effect
        for effect in policy.allowed_effects
    ):
        raise TrustSandboxError("sandbox allowed effects must be a frozenset of names")
    for value, label in (
        (policy.memory_limit_bytes, "sandbox memory limit"),
        (policy.timeout_ms, "sandbox timeout"),
    ):
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise TrustSandboxError(f"{label} must be a positive integer")
    return policy


def certify_isolated_boundary(
    boundary: ForeignTrustBoundary,
    provider: SandboxProvider,
    policy: SandboxPolicy,
) -> CertifiedIsolatedBoundary:
    """Promote one source-declared isolated boundary only with provider proof."""

    if not isinstance(boundary, ForeignTrustBoundary):
        raise TrustSandboxError("sandbox certification requires a foreign trust boundary")
    if boundary.trust_domain != "isolated":
        raise TrustSandboxError("sandbox certification is only valid for @trust(isolated)")
    if boundary.isolation_verified:
        raise TrustSandboxError("isolated boundary is already marked verified")
    symbol = _text(boundary.symbol, label="isolated foreign symbol")
    policy = _validate_policy(policy)
    if not set(boundary.effects).issubset(policy.allowed_effects):
        denied = sorted(set(boundary.effects) - set(policy.allowed_effects))
        raise TrustSandboxError(
            "sandbox policy does not permit boundary effects: " + ", ".join(denied)
        )
    if not isinstance(provider, SandboxProvider):
        raise TrustSandboxError("sandbox provider does not implement attestation")
    provider_name = _text(provider.name, label="sandbox provider")

    try:
        attestation = provider.attest(boundary, policy)
    except Exception as exc:
        raise TrustSandboxError(
            f"sandbox provider {provider_name!r} failed to attest {symbol!r}: {exc}"
        ) from exc
    if not isinstance(attestation, SandboxAttestation):
        raise TrustSandboxError("sandbox provider returned an invalid attestation")
    if attestation.symbol != symbol:
        raise TrustSandboxError("sandbox attestation symbol diverges from boundary")
    if attestation.provider != provider_name:
        raise TrustSandboxError("sandbox attestation provider identity diverges")
    _text(attestation.target, label="sandbox target")
    if attestation.policy_id != policy.policy_id:
        raise TrustSandboxError("sandbox attestation policy identity diverges")
    if not attestation.isolation_established:
        raise TrustSandboxError("sandbox provider did not establish isolation")
    if not isinstance(attestation.capabilities, frozenset):
        raise TrustSandboxError("sandbox attestation capabilities must be immutable")
    missing = REQUIRED_SANDBOX_CAPABILITIES - attestation.capabilities
    if missing:
        raise TrustSandboxError(
            "sandbox attestation lacks required capabilities: "
            + ", ".join(sorted(missing))
        )

    verified = replace(boundary, isolation_verified=True)
    return CertifiedIsolatedBoundary(verified, attestation)
