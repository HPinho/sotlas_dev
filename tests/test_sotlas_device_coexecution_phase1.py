"""Integration tests for DEVICE coexecution proof on real Phase-1 SIR CFGs."""
import importlib
import importlib.util
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
COMPILE_DIR = ROOT / "compiler" / "sotlas_compile"
SOTLAS_DIR = ROOT / "compiler" / "sotlas"


def _load_compile_package():
    name = "sotlas_device_coexecution_phase1_compile_package"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(
        name,
        COMPILE_DIR / "__init__.py",
        submodule_search_locations=[str(COMPILE_DIR)],
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_backend_package():
    name = "sotlas_device_coexecution_phase1_backend_package"
    if name not in sys.modules:
        package = types.ModuleType(name)
        package.__path__ = [str(SOTLAS_DIR)]
        package.__package__ = name
        sys.modules[name] = package
    return sys.modules[name]


compile_package = _load_compile_package()
try:
    importlib.import_module("sotlas.sir")
except ImportError:
    compiler_dir = str(ROOT / "compiler")
    if compiler_dir not in sys.path:
        sys.path.insert(0, compiler_dir)
backend_package = _load_backend_package()
ownership_sir = importlib.import_module(f"{backend_package.__name__}.sir.ownership")
coexec = importlib.import_module(f"{backend_package.__name__}.sir.device_coexecution")
typed_ast = importlib.import_module(f"{compile_package.__name__}.typed_ast")

OwnershipDomain = typed_ast.OwnershipDomain

SEQUENTIAL_SOURCE = """module test::device_coexecute_sequential;
sole struct Buffer { value: u32; }
fn accept_device(buffer: device Buffer) -> void { return; }
fn submit(cpu_a: Buffer, cpu_b: Buffer,
          device_a: device Buffer, device_b: device Buffer) -> void {
    accept_device(move device_a);
    accept_device(move device_b);
    handover cpu_a to device_a;
    handover cpu_b to device_b;
    return;
}
"""

BRANCH_SOURCE = """module test::device_coexecute_branch;
sole struct Buffer { value: u32; }
fn accept_device(buffer: device Buffer) -> void { return; }
fn submit(flag: bool, cpu_a: Buffer, cpu_b: Buffer,
          device_a: device Buffer, device_b: device Buffer) -> void {
    if flag {
        accept_device(move device_a);
        handover cpu_a to device_a;
        return;
    } else {
        accept_device(move device_b);
        handover cpu_b to device_b;
        return;
    }
}
"""


def _device_points(checked):
    return tuple(
        transition.point_id
        for transition in checked.semantic.ownership_domains.planned_transitions
        if transition.function == "submit"
        and transition.source is OwnershipDomain.EXCLUSIVE
        and transition.target is OwnershipDomain.DEVICE
        and transition.operation == "handover"
    )


class SotlasDeviceCoexecutionPhase1Tests(unittest.TestCase):
    def test_real_sequential_handover_cfg_gets_coexecution_certificate(self):
        checked = compile_package.analyze_source_phase1(
            SEQUENTIAL_SOURCE,
            filename="<device-coexecute-sequential>",
        )
        points = _device_points(checked)
        self.assertEqual(len(points), 2)
        generated = ownership_sir.generate_checked_ownership_sir(checked)
        certificate = coexec.certify_device_submission_coexecution(
            generated.module,
            function="submit",
            point_ids=points,
        )
        self.assertEqual(certificate.point_ids, points)
        self.assertEqual(certificate.bindings, ("cpu_a", "cpu_b"))
        self.assertTrue(certificate.acyclic)
        self.assertTrue(certificate.block_path)

    def test_real_alternative_branch_handover_cfg_is_not_coexecuting(self):
        checked = compile_package.analyze_source_phase1(
            BRANCH_SOURCE,
            filename="<device-coexecute-branch>",
        )
        points = _device_points(checked)
        self.assertEqual(len(points), 2)
        generated = ownership_sir.generate_checked_ownership_sir(checked)
        with self.assertRaisesRegex(
            coexec.DeviceCoexecutionError,
            "not co-executable",
        ):
            coexec.certify_device_submission_coexecution(
                generated.module,
                function="submit",
                point_ids=points,
            )


if __name__ == "__main__":
    unittest.main()
