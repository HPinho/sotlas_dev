"""M16.4h1c3 x86-64 nominal by-value struct addressing gates."""
from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"
_PACKAGE = "_sotlas_nominal_struct_machine_compile"


def _load_package():
    package = sys.modules.get(_PACKAGE)
    if package is not None:
        return package
    spec = importlib.util.spec_from_file_location(
        _PACKAGE,
        PACKAGE_DIR / "__init__.py",
        submodule_search_locations=[str(PACKAGE_DIR)],
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load canonical sotlas_compile package")
    package = importlib.util.module_from_spec(spec)
    sys.modules[_PACKAGE] = package
    spec.loader.exec_module(package)
    return package


package = _load_package()
canonical_sir = importlib.import_module(f"{_PACKAGE}.canonical_sir")
target_ir_calls = importlib.import_module(f"{_PACKAGE}.target_ir_calls")
target_ir_addressing = importlib.import_module(f"{_PACKAGE}.target_ir_addressing")
machine = importlib.import_module(f"{_PACKAGE}.machine_x86_64")
machine_layout = importlib.import_module(
    f"{_PACKAGE}._machine_x86_64_struct_layout"
)


_SOURCE = """module test::nominal_struct_machine;
sole struct Token {
    value: u32;
}
struct Envelope {
    token: Token;
    count: u32;
}
pub fn read_count(ptr: *mut Envelope) -> u32 {
    unsafe { return ptr.count; }
}
"""


def _target_ir_from_source():
    checked = package.analyze_source_phase1(
        _SOURCE,
        filename="<nominal-struct-machine>",
    )
    result, _ = canonical_sir.build_canonical_checked_ownership_sir(checked)
    return target_ir_calls.lower_sir_to_typed_target_ir(result.module)


def _nested_alignment_target_ir():
    return {
        "schema": "sotlas.target-ir.v1",
        "struct_layouts": [
            {
                "name": "Inner",
                "fields": [
                    {"name": "head", "type": "u8"},
                    {"name": "wide", "type": "u64"},
                ],
            },
            {
                "name": "Outer",
                "fields": [
                    {"name": "prefix", "type": "u8"},
                    {
                        "name": "inner",
                        "type": "Inner",
                        "representation": "nominal_struct",
                    },
                    {"name": "tail", "type": "u16"},
                ],
            },
        ],
        "functions": [],
    }


class SotlasNominalStructMachineAddressingTests(unittest.TestCase):
    def test_source_target_ir_nominal_closure_passes_address_validation(self):
        target_ir = _target_ir_from_source()
        self.assertIsNone(
            target_ir_addressing.validate_target_ir_addressing(target_ir)
        )

    def test_x86_64_layout_recursively_derives_nominal_size_alignment_and_offsets(self):
        target_ir = _nested_alignment_target_ir()
        self.assertIsNone(
            target_ir_addressing.validate_target_ir_addressing(target_ir)
        )

        layouts = machine_layout.plan_x86_64_sysv_struct_layouts(target_ir)
        inner = layouts["Inner"]
        outer = layouts["Outer"]

        self.assertEqual(inner["fields"]["head"]["offset_bytes"], 0)
        self.assertEqual(inner["fields"]["wide"]["offset_bytes"], 8)
        self.assertEqual(inner["size_bytes"], 16)
        self.assertEqual(inner["alignment_bytes"], 8)

        self.assertEqual(outer["fields"]["prefix"]["offset_bytes"], 0)
        self.assertEqual(outer["fields"]["inner"]["offset_bytes"], 8)
        self.assertEqual(outer["fields"]["inner"]["size_bytes"], 16)
        self.assertEqual(outer["fields"]["inner"]["alignment_bytes"], 8)
        self.assertEqual(
            outer["fields"]["inner"]["representation"],
            "nominal_struct",
        )
        self.assertEqual(outer["fields"]["tail"]["offset_bytes"], 24)
        self.assertEqual(outer["size_bytes"], 32)
        self.assertEqual(outer["alignment_bytes"], 8)

    def test_source_layout_accounts_for_nominal_field_before_scalar_projection(self):
        target_ir = _target_ir_from_source()
        layouts = machine_layout.plan_x86_64_sysv_struct_layouts(target_ir)

        token = layouts["Token"]
        envelope = layouts["Envelope"]
        self.assertEqual(token["size_bytes"], 4)
        self.assertEqual(token["alignment_bytes"], 4)
        self.assertEqual(envelope["fields"]["token"]["offset_bytes"], 0)
        self.assertEqual(envelope["fields"]["token"]["size_bytes"], 4)
        self.assertEqual(envelope["fields"]["count"]["offset_bytes"], 4)
        self.assertEqual(envelope["size_bytes"], 8)
        self.assertEqual(envelope["alignment_bytes"], 4)

    def test_machine_emits_scalar_field_address_after_nominal_storage(self):
        assembly = machine.compile_source_to_x86_64_sysv_assembly(
            _SOURCE,
            "<nominal-struct-machine>",
        )
        self.assertIn(".globl read_count", assembly)
        self.assertIn("lea rax, [rcx+4]", assembly)
        self.assertIn("mov eax, DWORD PTR [rcx]", assembly)

    def test_missing_nominal_dependency_fails_closed(self):
        target_ir = _nested_alignment_target_ir()
        target_ir["struct_layouts"] = [
            layout
            for layout in target_ir["struct_layouts"]
            if layout["name"] != "Inner"
        ]
        with self.assertRaisesRegex(
            target_ir_addressing.TargetIRAddressingError,
            "undeclared or invalid nominal struct",
        ):
            target_ir_addressing.validate_target_ir_addressing(target_ir)
        with self.assertRaisesRegex(
            machine.MachineBackendError,
            "references undeclared struct",
        ):
            machine_layout.plan_x86_64_sysv_struct_layouts(target_ir)

    def test_nominal_by_value_cycle_fails_closed(self):
        target_ir = {
            "schema": "sotlas.target-ir.v1",
            "struct_layouts": [
                {
                    "name": "A",
                    "fields": [{
                        "name": "b",
                        "type": "B",
                        "representation": "nominal_struct",
                    }],
                },
                {
                    "name": "B",
                    "fields": [{
                        "name": "a",
                        "type": "A",
                        "representation": "nominal_struct",
                    }],
                },
            ],
            "functions": [],
        }
        with self.assertRaisesRegex(
            target_ir_addressing.TargetIRAddressingError,
            "by-value cycle",
        ):
            target_ir_addressing.validate_target_ir_addressing(target_ir)
        with self.assertRaisesRegex(
            machine.MachineBackendError,
            "by-value cycle",
        ):
            machine_layout.plan_x86_64_sysv_struct_layouts(target_ir)

    def test_target_ir_nominal_fields_still_cannot_smuggle_physical_bytes(self):
        target_ir = _nested_alignment_target_ir()
        target_ir["struct_layouts"][1]["fields"][1]["offset_bytes"] = 8
        with self.assertRaisesRegex(
            target_ir_addressing.TargetIRAddressingError,
            "cannot carry target layout bytes",
        ):
            target_ir_addressing.validate_target_ir_addressing(target_ir)

    @unittest.skipUnless(
        sys.platform.startswith("linux"),
        "x86-64 SysV execution gate is Linux-specific",
    )
    def test_linux_e2e_reads_scalar_after_nested_c_struct(self):
        compiler = shutil.which("cc") or shutil.which("clang") or shutil.which("gcc")
        if compiler is None:
            self.skipTest("native C compiler is required for nominal struct gate")

        assembly = machine.compile_source_to_x86_64_sysv_assembly(
            _SOURCE,
            "<nominal-struct-machine>",
        )
        with tempfile.TemporaryDirectory(prefix="sotlas_nominal_struct_") as temp:
            directory = Path(temp)
            asm_path = directory / "machine.s"
            caller_path = directory / "caller.c"
            executable = directory / "nominal_struct_machine"
            asm_path.write_text(assembly, encoding="utf-8")
            caller_path.write_text(
                """
#include <stdint.h>
struct Token {
    uint32_t value;
};
struct Envelope {
    struct Token token;
    uint32_t count;
};
extern uint32_t read_count(struct Envelope *ptr);
int main(void) {
    struct Envelope item = { { UINT32_C(0x11223344) }, UINT32_C(0x89ABCDEF) };
    return read_count(&item) == item.count ? 0 : 1;
}
""",
                encoding="utf-8",
            )
            build = subprocess.run(
                [compiler, str(caller_path), str(asm_path), "-o", str(executable)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(build.returncode, 0, build.stderr)
            run = subprocess.run(
                [str(executable)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(run.returncode, 0, run.stderr)

    def test_compiler_and_tools_machine_layout_paths_remain_identical(self):
        for relative in (
            "target_ir_addressing.py",
            "_machine_x86_64_struct_layout.py",
        ):
            self.assertEqual(
                (ROOT / "compiler" / "sotlas_compile" / relative).read_text(
                    encoding="utf-8"
                ),
                (ROOT / "tools" / "sotlas_compile" / relative).read_text(
                    encoding="utf-8"
                ),
                relative,
            )


if __name__ == "__main__":
    unittest.main()
