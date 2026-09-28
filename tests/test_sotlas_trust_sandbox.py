from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
COMPILER_DIR = ROOT / "compiler"
if str(COMPILER_DIR) not in sys.path:
    sys.path.insert(0, str(COMPILER_DIR))

from sotlas_compile.trust_domains import ForeignTrustBoundary
from sotlas_compile.trust_sandbox import (
    REQUIRED_SANDBOX_CAPABILITIES,
    SandboxAttestation,
    SandboxPolicy,
    TrustSandboxError,
    certify_isolated_boundary,
)


def _boundary(*, trust="isolated", effects=("ffi",)):
    return ForeignTrustBoundary(
        symbol="foreign_parse",
        convention="C",
        trust_domain=trust,
        effects=effects,
        isolation_verified=False,
        required_context=("system",),
    )


def _policy(*, effects=frozenset({"ffi"})):
    return SandboxPolicy(
        policy_id="ffi.parse.v1",
        allowed_effects=effects,
        memory_limit_bytes=16 * 1024 * 1024,
        timeout_ms=100,
    )


class AttestingProvider:
    name = "test-sandbox"

    def __init__(
        self,
        *,
        capabilities=REQUIRED_SANDBOX_CAPABILITIES,
        symbol="foreign_parse",
        policy_id="ffi.parse.v1",
        established=True,
        fail=False,
    ):
        self.capabilities = frozenset(capabilities)
        self.symbol = symbol
        self.policy_id = policy_id
        self.established = established
        self.fail = fail
        self.calls = 0

    def attest(self, boundary, policy):
        self.calls += 1
        if self.fail:
            raise RuntimeError("sandbox backend unavailable")
        return SandboxAttestation(
            symbol=self.symbol,
            provider=self.name,
            target="process:isolated-child",
            policy_id=self.policy_id,
            capabilities=self.capabilities,
            isolation_established=self.established,
        )


class SotlasTrustSandboxTests(unittest.TestCase):
    def test_complete_attestation_is_the_only_path_to_verified_isolation(self):
        original = _boundary()
        provider = AttestingProvider()
        certified = certify_isolated_boundary(original, provider, _policy())

        self.assertFalse(original.isolation_verified)
        self.assertTrue(certified.isolation_verified)
        self.assertTrue(certified.boundary.isolation_verified)
        self.assertEqual(certified.boundary.symbol, original.symbol)
        self.assertEqual(certified.boundary.effects, original.effects)
        self.assertEqual(certified.attestation.provider, "test-sandbox")
        self.assertEqual(provider.calls, 1)

    def test_missing_capability_or_unestablished_isolation_fails_closed(self):
        incomplete = REQUIRED_SANDBOX_CAPABILITIES - {"syscall_filtering"}
        with self.assertRaisesRegex(TrustSandboxError, "lacks required capabilities"):
            certify_isolated_boundary(
                _boundary(), AttestingProvider(capabilities=incomplete), _policy()
            )
        with self.assertRaisesRegex(TrustSandboxError, "did not establish isolation"):
            certify_isolated_boundary(
                _boundary(), AttestingProvider(established=False), _policy()
            )

    def test_attestation_cannot_drift_symbol_or_policy_identity(self):
        with self.assertRaisesRegex(TrustSandboxError, "symbol diverges"):
            certify_isolated_boundary(
                _boundary(), AttestingProvider(symbol="other"), _policy()
            )
        with self.assertRaisesRegex(TrustSandboxError, "policy identity diverges"):
            certify_isolated_boundary(
                _boundary(), AttestingProvider(policy_id="other-policy"), _policy()
            )

    def test_policy_denies_effects_before_provider_is_called(self):
        provider = AttestingProvider()
        with self.assertRaisesRegex(TrustSandboxError, "does not permit boundary effects"):
            certify_isolated_boundary(
                _boundary(effects=("ffi", "network")), provider, _policy()
            )
        self.assertEqual(provider.calls, 0)

    def test_only_isolated_boundaries_are_certifiable(self):
        with self.assertRaisesRegex(TrustSandboxError, "only valid for @trust\(isolated\)"):
            certify_isolated_boundary(_boundary(trust="trusted"), AttestingProvider(), _policy())

    def test_provider_failure_does_not_become_a_verified_claim(self):
        with self.assertRaisesRegex(TrustSandboxError, "failed to attest"):
            certify_isolated_boundary(_boundary(), AttestingProvider(fail=True), _policy())

    def test_compatibility_mirror_is_byte_identical(self):
        canonical = ROOT / "compiler" / "sotlas_compile" / "trust_sandbox.py"
        mirror = ROOT / "tools" / "sotlas_compile" / "trust_sandbox.py"
        self.assertEqual(canonical.read_bytes(), mirror.read_bytes())


if __name__ == "__main__":
    unittest.main()
