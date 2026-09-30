"""M16.4a source-to-native pointer-read coverage for x86-64 SysV."""
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
COMPILER_PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"
_CANONICAL_PACKAGE = "_sotlas_machine_pointer_compile"


def _load_compiler_package():
    package = sys.modules.get(_CANONICAL_PACKAGE)
    if package is None:
        spec = importlib.util.spec_from_file_location(
            _CANONICAL_PACKAGE,
            COMPILER_PACKAGE_DIR / "__init__.py",
            submodule_search_locations=[str(COMPILER_PACKAGE_DIR)],
        )
        if spec is None or spec.loader is None:
            raise RuntimeError("cannot load canonical sotlas_compile package")
        package = importlib.util.module_from_spec(spec)
        sys.modules[_CANONICAL_PACKAGE] = package
        spec.loader.exec_module(package)
    return package


_load_compiler_package()
_machine = importlib.import_module(f"{_CANONICAL_PACKAGE}.machine_x86_64")
_phase1 = importlib.import_module(f"{_CANONICAL_PACKAGE}.phase1_pipeline")
_canonical_sir = importlib.import_module(f"{_CANONICAL_PACKAGE}.canonical_sir")
_target_calls = importlib.import_module(f"{_CANONICAL_PACKAGE}.target_ir_calls")


SOURCE = """
module test::machine_pointer_load;
pub fn read_u8(ptr: *mut u8) -> u8 {
    unsafe { return *ptr; }
}
pub fn read_u16(ptr: *mut u16) -> u16 {
    unsafe { return *ptr; }
}
pub fn read_u32(ptr: *mut u32) -> u32 {
    unsafe { return *ptr; }
}
pub fn read_u64(ptr: *mut u64) -> u64 {
    unsafe { return *ptr; }
}
"""


class SotlasX8664PointerTests(unittest.TestCase):
    def _checked_sir(self):
        checked = _phase1.analyze_source_phase1(
            SOURCE, filename="machine_pointer_load.sotlas"
        )
        checked_sir, _ = _canonical_sir.build_canonical_checked_ownership_sir(
            checked
        )
        return checked_sir.module

    def test_checked_source_lowers_dereference_to_typed_sir_loads(self):
        module = self._checked_sir()
        self.assertEqual(tuple(module.unlowered_functions), ())
        functions = {fn.name: fn for fn in module.functions}
        for name, pointee in (
            ("read_u8", "u8"),
            ("read_u16", "u16"),
            ("read_u32", "u32"),
            ("read_u64", "u64"),
        ):
            fn = functions[name]
            self.assertEqual(fn.parameters[0].type_name, f"{pointee}*")
            loads = [
                instruction
                for block in fn.blocks
                for instruction in block.instructions
                if type(instruction).__name__ == "LoadInst"
                and instruction.source.name == "ptr"
            ]
            self.assertEqual(len(loads), 1, name)
            self.assertEqual(loads[0].result.type_name, pointee)

    def test_target_ir_preserves_pointer_parameter_and_indirect_load(self):
        target_ir = _target_calls.lower_sir_to_typed_target_ir(self._checked_sir())
        functions = {item["name"]: item for item in target_ir["functions"]}
        function = functions["read_u32"]
        self.assertEqual(function["parameters"][0]["name"], "ptr")
        self.assertEqual(function["parameters"][0]["type"], "u32*")
        loads = [
            instruction
            for block in function["blocks"]
            for instruction in block["instructions"]
            if instruction["op"] == "load" and instruction["operands"] == ["ptr"]
        ]
        self.assertEqual(len(loads), 1)
        self.assertEqual(loads[0]["type"], "u32")

    def test_machine_emits_width_correct_indirect_memory_reads(self):
        assembly = _machine.compile_source_to_x86_64_sysv_assembly(
            SOURCE, "machine_pointer_load.sotlas"
        )
        self.assertIn("movzx eax, BYTE PTR [rcx]", assembly)
        self.assertIn("movzx eax, WORD PTR [rcx]", assembly)
        self.assertIn("mov eax, DWORD PTR [rcx]", assembly)
        self.assertIn("mov rax, QWORD PTR [rcx]", assembly)
        for name in ("read_u8", "read_u16", "read_u32", "read_u64"):
            self.assertIn(f".globl {name}", assembly)
        self.assertNotIn("LLVM", assembly)

    def test_non_pointer_indirect_load_fails_closed(self):
        target_ir = {
            "schema": "sotlas.target-ir.v1",
            "functions": [{
                "name": "bad_load",
                "parameters": [{"name": "value", "type": "u32"}],
                "return_type": "u32",
                "blocks": [{
                    "label": "entry",
                    "instructions": [
                        {"op": "load", "result": "loaded", "operands": ["value"], "type": "u32"},
                        {"op": "return", "operands": ["loaded"]},
                    ],
                }],
            }],
        }
        with self.assertRaisesRegex(
            _machine.MachineBackendError,
            "indirect load source must be a supported pointer type",
        ):
            _machine.emit_x86_64_sysv_assembly(target_ir)

    @unittest.skipUnless(
        sys.platform.startswith("linux"),
        "x86-64 SysV execution gate is Linux-specific",
    )
    def test_linux_e2e_reads_c_memory_at_source_pointer_width(self):
        compiler = shutil.which("cc") or shutil.which("clang") or shutil.which("gcc")
        if compiler is None:
            self.skipTest("native C compiler is required for pointer execution gate")

        assembly = _machine.compile_source_to_x86_64_sysv_assembly(
            SOURCE, "machine_pointer_load.sotlas"
        )
        with tempfile.TemporaryDirectory(prefix="sotlas_machine_pointer_") as temp:
            directory = Path(temp)
            asm_path = directory / "machine.s"
            caller_path = directory / "caller.c"
            executable = directory / "machine_pointer_load"
            asm_path.write_text(assembly, encoding="utf-8")
            caller_path.write_text(
                """
#include <stdint.h>
extern uint8_t read_u8(uint8_t *ptr);
extern uint16_t read_u16(uint16_t *ptr);
extern uint32_t read_u32(uint32_t *ptr);
extern uint64_t read_u64(uint64_t *ptr);
int main(void) {
    uint8_t v8 = UINT8_C(0xA5);
    uint16_t v16 = UINT16_C(0xBEEF);
    uint32_t v32 = UINT32_C(0x89ABCDEF);
    uint64_t v64 = UINT64_C(0x0123456789ABCDEF);
    if (read_u8(&v8) != v8) return 1;
    if (read_u16(&v16) != v16) return 2;
    if (read_u32(&v32) != v32) return 3;
    if (read_u64(&v64) != v64) return 4;
    return 0;
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
            run = subprocess.run([str(executable)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)

    def test_compiler_and_tools_pointer_backend_files_remain_identical(self):
        for relative in (
            "scalar_if_return_cfg_generator.py",
            "_machine_x86_64_types.py",
            "_machine_x86_64_call_validation.py",
            "_machine_x86_64_call_plan.py",
            "_machine_x86_64_call_abi.py",
            "_machine_x86_64_call_instruction_emit.py",
        ):
            compiler_path = ROOT / "compiler" / "sotlas_compile" / relative
            tools_path = ROOT / "tools" / "sotlas_compile" / relative
            self.assertEqual(
                compiler_path.read_text(encoding="utf-8"),
                tools_path.read_text(encoding="utf-8"),
                relative,
            )


if __name__ == "__main__":
    unittest.main()
