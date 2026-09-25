"""Phase 3: canonical Authority contracts for privileged ABI intrinsics."""
from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"


def _load_package():
    name = "sotlas_authority_abi_package"
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
bootstrap = importlib.import_module(f"{package.__name__}.bootstrap")
authority = importlib.import_module(f"{package.__name__}.authority")
authority_abi = importlib.import_module(f"{package.__name__}.authority_abi")


PORT_IO = """module app::authority_port_io;
@system(io.port)
fn read_status() -> void {
    __inb(0x3F8u16);
    return;
}
"""


WRONG_CAPABILITY = """module app::authority_port_io_wrong;
@system(pci.config)
fn read_status() -> void {
    __inb(0x3F8u16);
    return;
}
"""


NO_CAPABILITY = """module app::authority_port_io_none;
fn read_status() -> void {
    __inb(0x3F8u16);
    return;
}
"""


UNCONTRACTED_INTRINSIC = """module app::authority_cli_named;
@system(io.port)
fn disable_interrupts() -> void {
    __cli();
    return;
}
"""


LEGACY_INTRINSIC = """module app::authority_cli_legacy;
@system
fn disable_interrupts() -> void {
    __cli();
    return;
}
"""


LEGACY_PORT_IO = """module app::authority_port_io_legacy;
@system
fn read_status() -> void {
    __inb(0x3F8u16);
    return;
}
"""


class SotlasAuthorityABITests(unittest.TestCase):
    def _plan(self, source: str):
        parsed = bootstrap.parse(source, filename="<authority-abi>")
        return authority.plan_authority_domains(parsed)

    def test_port_io_registry_is_narrow_and_named(self):
        expected = {
            "__inb", "__outb", "__inw", "__outw", "__inl", "__outl"
        }
        contracts = authority_abi.AUTHORITY_ABI_CONTRACTS
        self.assertEqual({item.symbol for item in contracts}, expected)
        self.assertTrue(
            all(item.capabilities == ("io.port",) for item in contracts)
        )
        self.assertTrue(
            all(item.kind == "abi_intrinsic" for item in contracts)
        )

    def test_named_io_port_capability_certifies_builtin_call(self):
        plan = self._plan(PORT_IO)
        calls = plan.calls_from("read_status")
        self.assertEqual(len(calls), 1)
        edge = calls[0]
        self.assertEqual(edge.callee, "__inb")
        self.assertEqual(edge.required_capabilities, ("io.port",))
        self.assertEqual(edge.target_kind, "abi_intrinsic")
        self.assertTrue(edge.point_id.startswith("call@"))

    def test_different_named_capability_cannot_use_port_io(self):
        with self.assertRaisesRegex(
            authority.AuthorityDomainError,
            "missing capabilities: io.port",
        ):
            self._plan(WRONG_CAPABILITY)

    def test_unprivileged_function_cannot_use_port_io(self):
        with self.assertRaisesRegex(
            authority.AuthorityDomainError,
            "missing capabilities: io.port",
        ):
            self._plan(NO_CAPABILITY)

    def test_named_capability_cannot_use_uncontracted_privileged_intrinsic(self):
        with self.assertRaisesRegex(
            authority.AuthorityDomainError,
            "requires legacy unrestricted @system authority",
        ):
            self._plan(UNCONTRACTED_INTRINSIC)

    def test_bare_system_retains_legacy_access_to_uncontracted_intrinsic(self):
        plan = self._plan(LEGACY_INTRINSIC)
        calls = plan.calls_from("disable_interrupts")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].callee, "__cli")
        self.assertEqual(calls[0].required_capabilities, ())
        self.assertEqual(calls[0].target_kind, "legacy_intrinsic")

    def test_bare_system_can_cross_named_abi_boundary_for_compatibility(self):
        plan = self._plan(LEGACY_PORT_IO)
        calls = plan.calls_from("read_status")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].required_capabilities, ("io.port",))
        self.assertEqual(calls[0].target_kind, "abi_intrinsic")


if __name__ == "__main__":
    unittest.main()
