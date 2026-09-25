"""Strict SIR must not silently drop direct privileged ABI authority."""
from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"


def _load_package():
    name = "sotlas_authority_sir_abi_fail_closed_package"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(
        name,
        PACKAGE_DIR / "__init__.py",
        submodule_search_locations=[str(PACKAGE_DIR)],
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


package = _load_package()
authority = importlib.import_module(f"{package.__name__}.authority")
authority_sir = importlib.import_module(f"{package.__name__}.authority_sir")


class SotlasAuthoritySIRABIFailClosedTests(unittest.TestCase):
    def test_named_abi_edge_is_rejected_until_sir_has_abi_representation(self):
        plan = authority.AuthorityDomainPlan(
            contracts=(
                authority.AuthorityContract(
                    function="read_status",
                    capabilities=("io.port",),
                ),
            ),
            calls=(
                authority.AuthorityCallEdge(
                    caller="read_status",
                    callee="__inb",
                    point_id="call@4:5",
                    required_capabilities=("io.port",),
                    target_kind="abi_intrinsic",
                ),
            ),
        )
        with self.assertRaisesRegex(
            authority_sir.AuthoritySIRError,
            "cannot yet certify direct ABI/intrinsic authority edges",
        ):
            authority_sir.certify_authority_sir(plan, object())

    def test_legacy_intrinsic_edge_is_also_rejected_until_representable(self):
        plan = authority.AuthorityDomainPlan(
            contracts=(
                authority.AuthorityContract(
                    function="halt_cpu",
                    legacy_unrestricted=True,
                ),
            ),
            calls=(
                authority.AuthorityCallEdge(
                    caller="halt_cpu",
                    callee="__hlt",
                    point_id="call@4:5",
                    required_capabilities=(),
                    target_kind="legacy_intrinsic",
                ),
            ),
        )
        with self.assertRaisesRegex(
            authority_sir.AuthoritySIRError,
            "cannot yet certify direct ABI/intrinsic authority edges",
        ):
            authority_sir.certify_authority_sir(plan, object())


if __name__ == "__main__":
    unittest.main()
