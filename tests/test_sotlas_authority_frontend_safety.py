"""Production frontend enforcement for named Authority ABI contracts."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"


def _load_package():
    name = "sotlas_authority_frontend_safety_package"
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


MATCHING = """module app::authority_frontend_port;
@system(io.port)
fn read_status() -> void {
    __inb(0x3F8u16);
    return;
}
"""


WRONG = """module app::authority_frontend_wrong;
@system(pci.config)
fn read_status() -> void {
    __inb(0x3F8u16);
    return;
}
"""


NONE = """module app::authority_frontend_none;
fn read_status() -> void {
    __inb(0x3F8u16);
    return;
}
"""


NAMED_UNCONTRACTED = """module app::authority_frontend_cli;
@system(io.port)
fn disable_interrupts() -> void {
    __cli();
    return;
}
"""


LEGACY = """module app::authority_frontend_legacy;
@system
fn disable_interrupts() -> void {
    __cli();
    return;
}
"""


INTERRUPT_LEGACY = """module app::authority_frontend_interrupt;
@interrupt
fn irq() -> void {
    unsafe {
        __sti();
    }
    return;
}
"""


class SotlasAuthorityFrontendSafetyTests(unittest.TestCase):
    def _check(self, source: str):
        module = bootstrap.parse(source, filename="<authority-frontend>")
        bootstrap.check(module)
        return module

    def test_compile_source_accepts_exact_port_io_capability(self):
        c_text = package.compile_source(MATCHING, filename="<authority-frontend>")
        self.assertIn("__inb(", c_text)

    def test_phase1_attaches_canonical_abi_edge(self):
        checked = package.analyze_source_phase1(
            MATCHING,
            filename="<authority-frontend>",
        )
        calls = checked.authority.calls_from("read_status")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].callee, "__inb")
        self.assertEqual(calls[0].required_capabilities, ("io.port",))
        self.assertEqual(calls[0].target_kind, "abi_intrinsic")

    def test_wrong_named_capability_is_rejected_by_production_check(self):
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            "missing capabilities: io.port",
        ):
            self._check(WRONG)

    def test_unprivileged_port_io_is_rejected_by_production_check(self):
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            "missing capabilities: io.port",
        ):
            self._check(NONE)

    def test_named_port_capability_does_not_unlock_other_intrinsics(self):
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            "intrínseco privilegiado exige função @system",
        ):
            self._check(NAMED_UNCONTRACTED)

    def test_bare_system_keeps_legacy_intrinsic_access(self):
        self._check(LEGACY)

    def test_interrupt_context_keeps_legacy_intrinsic_access(self):
        self._check(INTERRUPT_LEGACY)


if __name__ == "__main__":
    unittest.main()
