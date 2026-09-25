"""Phase 3: named Authority Domain for x86 MSR access."""
from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"


def _load_package():
    name = "sotlas_authority_msr_package"
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
bootstrap = package.bootstrap
authority = importlib.import_module(f"{package.__name__}.authority")
authority_abi = importlib.import_module(f"{package.__name__}.authority_abi")


MATCHING = """module app::authority_msr;
@system(cpu.msr)
fn touch_msr() -> void {
    let value: u64 = __rdmsr(0x10u32);
    __wrmsr(0x10u32, value);
    return;
}
"""


WRONG = """module app::authority_msr_wrong;
@system(cpu.interrupts)
fn read_msr() -> void {
    let value: u64 = __rdmsr(0x10u32);
    return;
}
"""


NONE = """module app::authority_msr_none;
fn read_msr() -> void {
    let value: u64 = __rdmsr(0x10u32);
    return;
}
"""


class SotlasAuthorityMSRTests(unittest.TestCase):
    def _plan(self, source: str):
        parsed = bootstrap.parse(source, filename="<authority-msr>")
        return authority.plan_authority_domains(parsed)

    def test_registry_maps_only_msr_intrinsics_to_cpu_msr(self):
        self.assertEqual(
            authority_abi.authority_abi_contract("__rdmsr").capabilities,
            ("cpu.msr",),
        )
        self.assertEqual(
            authority_abi.authority_abi_contract("__wrmsr").capabilities,
            ("cpu.msr",),
        )
        self.assertIsNone(authority_abi.authority_abi_contract("__read_cr0"))

    def test_named_msr_capability_certifies_read_and_write(self):
        plan = self._plan(MATCHING)
        calls = plan.calls_from("touch_msr")
        self.assertEqual([item.callee for item in calls], ["__rdmsr", "__wrmsr"])
        self.assertTrue(
            all(item.required_capabilities == ("cpu.msr",) for item in calls)
        )
        self.assertTrue(all(item.target_kind == "abi_intrinsic" for item in calls))

    def test_interrupt_capability_does_not_grant_msr_access(self):
        with self.assertRaisesRegex(
            authority.AuthorityDomainError,
            "missing capabilities: cpu.msr",
        ):
            self._plan(WRONG)

    def test_unprivileged_function_does_not_gain_msr_access(self):
        with self.assertRaisesRegex(
            authority.AuthorityDomainError,
            "missing capabilities: cpu.msr",
        ):
            self._plan(NONE)

    def test_production_frontend_accepts_exact_msr_capability(self):
        c_text = package.compile_source(MATCHING, filename="<authority-msr>")
        self.assertIn("__rdmsr(", c_text)
        self.assertIn("__wrmsr(", c_text)

    def test_production_frontend_rejects_wrong_msr_capability(self):
        module = bootstrap.parse(WRONG, filename="<authority-msr>")
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            "missing capabilities: cpu.msr",
        ):
            bootstrap.check(module)


if __name__ == "__main__":
    unittest.main()
