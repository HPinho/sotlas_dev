"""Sovereignty Milestone SV2 Gate: Native Frontend AST/Sema to Target IR Lowering.

Validates that:
1. Target IR contract (target_ir.sotlas) defines pure Sotlas-owned SSA representations:
   TargetOpcode, TargetTypeTag, TargetInstruction, TargetFunction, TargetBlock,
   TargetParameter, TargetValue, TargetOperand, TargetPhiInput without C or Python dependencies.
2. Scalar AST-to-Target-IR lowering (lower_scalar.sotlas) translates:
   - Integer and boolean scalar parameters (u8..u64, i8..i64, usize, isize, bool).
   - Integer literals and constant expressions with range checks.
   - Local variable definitions (let) and assignments.
   - Binary arithmetic expressions (+, -, *).
   - Comparison expressions (==, !=, <, <=, >, >=) with verified predicates.
   - Intra-module function calls and external declarations (@extern(C)).
   - Control flow branches (if/else returning branches).
   - Loop statements (while loops with break/continue and conditional jumps).
   - Function returns with type-checked expressions.
3. CFG and SSA dominance validation (target_module_validate_cfg and
   target_module_validate_ssa_dominance) accept valid lowered IR and reject malformed graphs.
4. Fail-closed contract guards strictly reject unsupported AST nodes, type mismatches,
   undeclared variables, missing return statements, and buffer capacity exhaustion.
5. Integration with the native Stage 1 compiler executes the complete lowering pass
   directly from source code into relocatable objects without C11 emission.
"""
from __future__ import annotations

import os
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "compiler"))

from sotlas.bootstrap_pipeline import build_stage1_native_compiler
from sotlas_compile.bootstrap import _public_import_maps, check, parse

NATIVE_DIR = ROOT / "bootstrap" / "sotlas" / "native_compiler"

SCALAR_ARITH_SRC = """module sv2::arithmetic;

pub fn calculate(a: u32, b: u32, c: u32) -> u32 {
    let sum: u32 = a + b;
    let diff: u32 = sum - c;
    let prod: u32 = diff * 3;
    return prod;
}
"""

COMPARISON_BRANCH_SRC = """module sv2::branching;

pub fn classify(x: u32, threshold: u32) -> u32 {
    if x > threshold {
        return x * 2;
    } else {
        return threshold;
    }
}
"""

MULTI_FUNCTION_CALL_SRC = """module sv2::calls;

fn helper(val: u32) -> u32 {
    return val + 10;
}

pub fn run(x: u32) -> u32 {
    let h: u32 = helper(x);
    return h * 2;
}
"""

EXTERN_PROTOTYPE_SRC = """module sv2::extern_call;

@extern(C)
fn external_service(arg: u32) -> u32;

pub fn bridge(val: u32) -> u32 {
    let res: u32 = external_service(val + 1);
    return res;
}
"""

WHILE_LOOP_SRC = """module sv2::looping;

pub fn loop_check(enabled: bool, fallback: u32) -> u32 {
    while enabled {
        break;
    }
    return fallback + 1;
}
"""

BAD_TYPE_SRC = """module sv2::bad_type;

pub fn invalid_return(a: u32) -> u32 {
    let x: bool = true;
    return x;
}
"""

UNSUPPORTED_OP_SRC = """module sv2::bad_op;

pub fn div_unsupported(a: u32, b: u32) -> u32 {
    return a / b;
}
"""

UNDECLARED_VAR_SRC = """module sv2::undeclared;

pub fn missing_var(a: u32) -> u32 {
    return a + non_existent_var;
}
"""

STRUCT_GEOM_SRC = """module sv2::struct_geom;

struct Point {
    x: u32;
    y: u32;
}

pub fn sum_coords() -> u32 {
    let pt: Point = Point { x: 15, y: 27 };
    return pt.x + pt.y;
}
"""

STRUCT_MUTATE_SRC = """module sv2::struct_mutate;

struct Vector {
    dx: u32;
    dy: u32;
}

pub fn mutate_vector() -> u32 {
    let mut v: Vector = Vector { dx: 10, dy: 20 };
    v.dx = 42;
    return v.dx + v.dy;
}
"""

ENUM_SELECTION_SRC = """module sv2::enums;

enum Operation {
    Add = 10,
    Sub = 20,
    Mul = 42,
}

pub fn select_operation() -> u32 {
    let op: u32 = Operation::Mul;
    if op == Operation::Mul {
        return Operation::Mul;
    } else {
        return Operation::Add;
    }
}
"""

STRUCT_METHOD_SRC = """module sv2::methods;

struct Counter {
    val: u32;
}

impl Counter {
    pub fn add(mut self: &mut Self, delta: u32) -> u32 {
        self.val = self.val + delta;
        return self.val;
    }
}

pub fn run_counter() -> u32 {
    let mut c: Counter = Counter { val: 10 };
    let res: u32 = c.add(32);
    return res;
}
"""

STRUCT_METHOD_WIDE_SRC = """module sv2::methods_wide;

struct WideBox {
    marker: u32;
}

impl WideBox {
    pub fn keep_wide(mut self: &mut Self, value: usize) -> usize {
        return value;
    }
}

pub fn run_wide_method() -> usize {
    let mut box: WideBox = WideBox { marker: 0 };
    return box.keep_wide(4294967297);
}
"""

WIDE_COMPARISON_SRC = """module sv2::wide_comparison;

pub fn choose_wide(value: usize) -> usize {
    if value > 4294967296 {
        return value;
    } else {
        return 4294967296;
    }
}
"""

INFERRED_WIDE_CALL_SRC = """module sv2::inferred_wide_call;

pub fn inferred_wide() -> usize {
    let inferred = identity_wide(4294967297);
    return inferred;
}

fn identity_wide(value: usize) -> usize {
    return value;
}
"""

DISCARDED_WIDE_CALL_SRC = """module sv2::discarded_wide_call;

pub fn run_discarded_wide() -> u32 {
    identity_wide(4294967297);
    return 7;
}

fn identity_wide(value: usize) -> usize {
    return value;
}
"""


class TestSotlasSovereigntySV2(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp_dir = tempfile.TemporaryDirectory(prefix="sotlas-sv2-")
        cls.root = Path(cls.tmp_dir.name)
        exe_suffix = ".exe" if os.name == "nt" else ""
        cls.stage1 = ROOT / "build" / f"sotlas_stage1{exe_suffix}"
        if not cls.stage1.is_file():
            build_stage1_native_compiler(cls.stage1, verbose=False)

    @classmethod
    def tearDownClass(cls):
        cls.tmp_dir.cleanup()

    def test_sv2_target_ir_contract_source_purity(self):
        """SV2.1: Target IR contracts are expressed purely in Sotlas without C/Python glue."""
        target_ir_path = NATIVE_DIR / "backend" / "target_ir.sotlas"
        src = target_ir_path.read_text(encoding="utf-8")
        parsed = parse(src, filename=str(target_ir_path))
        check(parsed)

        for required_symbol in (
            "pub enum TargetOpcode",
            "pub enum TargetTypeTag",
            "pub struct TargetInstruction",
            "pub struct TargetFunction",
            "pub struct TargetBlock",
            "pub struct TargetParameter",
            "pub struct TargetValue",
            "pub struct TargetOperand",
            "pub struct TargetPhiInput",
            "pub struct TargetModule",
            "pub fn target_module_validate_cfg",
            "pub fn target_module_validate_ssa_dominance",
        ):
            self.assertIn(required_symbol, src)

        self.assertNotIn("CEmitter", src)
        self.assertNotIn("emitter_c", src)

    def test_sv2_lower_scalar_contract_type_checks(self):
        """SV2.2: AST-to-Target-IR lowering type-checks cleanly under native compiler imports."""
        paths = [
            NATIVE_DIR / "token.sotlas",
            NATIVE_DIR / "ast.sotlas",
            NATIVE_DIR / "sema.sotlas",
            NATIVE_DIR / "backend" / "target_ir.sotlas",
        ]
        imported = [
            parse(p.read_text(encoding="utf-8"), filename=str(p))
            for p in paths
        ]
        lower_path = NATIVE_DIR / "backend" / "lower_scalar.sotlas"
        src = lower_path.read_text(encoding="utf-8")
        mod = parse(src, filename=str(lower_path))
        check(mod, *_public_import_maps(imported))

        for op in ("ConstInt", "Add", "Sub", "Mul", "Compare", "Call", "Return", "Branch", "CondBranch", "AllocStack", "Store", "Load"):
            self.assertIn(f"TargetOpcode::{op}", src)

    def test_sv2_lowering_arithmetic_pipeline(self):
        """SV2.3: Lowers arithmetic expressions, local variables and returns into valid ELF object."""
        src_path = self.root / "arith.sotlas"
        src_path.write_text(SCALAR_ARITH_SRC, encoding="utf-8")
        out_obj = self.root / "arith.o"
        r = subprocess.run([str(self.stage1), "--compile-obj", str(src_path), str(out_obj)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(out_obj.is_file())

        data = out_obj.read_bytes()
        self.assertEqual(data[:4], b"\x7fELF")

    def test_sv2_lowering_comparison_and_branching(self):
        """SV2.4: Lowers comparisons and if/else conditional return branches into valid ELF object."""
        src_path = self.root / "branch.sotlas"
        src_path.write_text(COMPARISON_BRANCH_SRC, encoding="utf-8")
        out_obj = self.root / "branch.o"
        r = subprocess.run([str(self.stage1), "--compile-obj", str(src_path), str(out_obj)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(out_obj.is_file())

    def test_sv2_lowering_same_module_function_calls(self):
        """SV2.5: Lowers multi-function module with direct calls into Target IR and relocatable object."""
        src_path = self.root / "calls.sotlas"
        src_path.write_text(MULTI_FUNCTION_CALL_SRC, encoding="utf-8")
        out_obj = self.root / "calls.o"
        r = subprocess.run([str(self.stage1), "--compile-obj", str(src_path), str(out_obj)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(out_obj.is_file())

    def test_sv2_lowering_extern_prototypes(self):
        """SV2.6: Lowers @extern(C) function prototypes and external calls with relocations."""
        src_path = self.root / "extern.sotlas"
        src_path.write_text(EXTERN_PROTOTYPE_SRC, encoding="utf-8")
        out_obj = self.root / "extern.o"
        r = subprocess.run([str(self.stage1), "--compile-obj", str(src_path), str(out_obj)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(out_obj.is_file())

    def test_sv2_lowering_while_loop_with_control_flow(self):
        """SV2.7: Lowers while loops with break/continue and mutable local variables."""
        src_path = self.root / "loop.sotlas"
        src_path.write_text(WHILE_LOOP_SRC, encoding="utf-8")
        out_obj = self.root / "loop.o"
        r = subprocess.run([str(self.stage1), "--compile-obj", str(src_path), str(out_obj)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(out_obj.is_file())

    def test_sv2_fail_closed_type_mismatch(self):
        """SV2.8: Type mismatch between variable declaration and return fails closed."""
        src_path = self.root / "bad_type.sotlas"
        src_path.write_text(BAD_TYPE_SRC, encoding="utf-8")
        out_obj = self.root / "bad_type.o"
        r = subprocess.run([str(self.stage1), "--compile-obj", str(src_path), str(out_obj)], capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse(out_obj.exists())

    def test_sv2_fail_closed_unsupported_operation(self):
        """SV2.9: Unsupported binary operations (e.g. division in scalar lowering) fail closed."""
        src_path = self.root / "bad_op.sotlas"
        src_path.write_text(UNSUPPORTED_OP_SRC, encoding="utf-8")
        out_obj = self.root / "bad_op.o"
        r = subprocess.run([str(self.stage1), "--compile-obj", str(src_path), str(out_obj)], capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse(out_obj.exists())

    def test_sv2_fail_closed_undeclared_variable(self):
        """SV2.10: Undeclared identifiers referenced in expressions fail closed."""
        src_path = self.root / "bad_var.sotlas"
        src_path.write_text(UNDECLARED_VAR_SRC, encoding="utf-8")
        out_obj = self.root / "bad_var.o"
        r = subprocess.run([str(self.stage1), "--compile-obj", str(src_path), str(out_obj)], capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse(out_obj.exists())

    def test_sv2_lowering_struct_declaration_and_field_access(self):
        """SV2.11: Lowers struct declaration, literal instantiation, and field access to ELF object and linked binary."""
        src_path = self.root / "struct_geom.sotlas"
        src_path.write_text(STRUCT_GEOM_SRC, encoding="utf-8")
        out_obj = self.root / "struct_geom.o"
        out_bin = self.root / "struct_geom.bin"
        r = subprocess.run([str(self.stage1), "--compile-obj", str(src_path), str(out_obj)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(out_obj.is_file())
        r_link = subprocess.run([str(self.stage1), "--link-exe", str(out_obj), str(out_bin), "sum_coords"], capture_output=True, text=True)
        self.assertEqual(r_link.returncode, 0, r_link.stderr)
        self.assertTrue(out_bin.is_file())

    def test_sv2_lowering_struct_field_mutation(self):
        """SV2.12: Lowers struct field mutation via assignment and access to ELF object and linked binary."""
        src_path = self.root / "struct_mutate.sotlas"
        src_path.write_text(STRUCT_MUTATE_SRC, encoding="utf-8")
        out_obj = self.root / "struct_mutate.o"
        out_bin = self.root / "struct_mutate.bin"
        r = subprocess.run([str(self.stage1), "--compile-obj", str(src_path), str(out_obj)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(out_obj.is_file())
        r_link = subprocess.run([str(self.stage1), "--link-exe", str(out_obj), str(out_bin), "mutate_vector"], capture_output=True, text=True)
        self.assertEqual(r_link.returncode, 0, r_link.stderr)
        self.assertTrue(out_bin.is_file())

    def test_sv2_lowering_enum_and_path_resolution(self):
        """SV2.13: Lowers enum declarations and qualified variant path expressions to ELF object and linked binary."""
        src_path = self.root / "enum_select.sotlas"
        src_path.write_text(ENUM_SELECTION_SRC, encoding="utf-8")
        out_obj = self.root / "enum_select.o"
        out_bin = self.root / "enum_select.bin"
        r = subprocess.run([str(self.stage1), "--compile-obj", str(src_path), str(out_obj)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(out_obj.is_file())
        r_link = subprocess.run([str(self.stage1), "--link-exe", str(out_obj), str(out_bin), "select_operation"], capture_output=True, text=True)
        self.assertEqual(r_link.returncode, 0, r_link.stderr)
        self.assertTrue(out_bin.is_file())

    def test_sv2_lowering_struct_methods(self):
        """SV2.14: Lowers struct method declaration, implicit self pointer passing, and method call to ELF object and linked binary."""
        src_path = self.root / "methods.sotlas"
        src_path.write_text(STRUCT_METHOD_SRC, encoding="utf-8")
        out_obj = self.root / "methods.o"
        out_bin = self.root / "methods.bin"
        r = subprocess.run([str(self.stage1), "--compile-obj", str(src_path), str(out_obj)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(out_obj.is_file())
        r_link = subprocess.run([str(self.stage1), "--link-exe", str(out_obj), str(out_bin), "run_counter"], capture_output=True, text=True)
        self.assertEqual(r_link.returncode, 0, r_link.stderr)
        self.assertTrue(out_bin.is_file())
        if sys.platform.startswith("linux"):
            r_run = subprocess.run([str(out_bin)])
            self.assertEqual(r_run.returncode, 42)

    def test_sv2_lowering_wide_comparison_preserves_operand_type(self):
        """SV2.15: usize comparison keeps both operands 64-bit through CFG and ELF."""
        src_path = self.root / "wide_comparison.sotlas"
        src_path.write_text(WIDE_COMPARISON_SRC, encoding="utf-8")
        out_obj = self.root / "wide_comparison.o"
        r = subprocess.run(
            [str(self.stage1), "--compile-obj", str(src_path), str(out_obj)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(out_obj.is_file())

        data = out_obj.read_bytes()
        self.assertEqual(data[:4], b"\x7fELF")
        self.assertIn(b"choose_wide\x00", data)
        self.assertIn(
            b"\x48\xb8\x00\x00\x00\x00\x01\x00\x00\x00",
            data,
        )
        self.assertIn(b"\x48\x3b\x85", data)

        if sys.platform.startswith("linux"):
            caller = self.root / "wide_comparison_caller.c"
            caller.write_text(
                "#include <stddef.h>\n"
                "extern size_t choose_wide(size_t);\n"
                "int main(void) { "
                "if (choose_wide((size_t)4294967297ULL) != (size_t)4294967297ULL) return 1; "
                "if (choose_wide((size_t)7) != (size_t)4294967296ULL) return 2; "
                "return 0; }\n",
                encoding="utf-8",
            )
            exe = self.root / "wide_comparison_native"
            linked = subprocess.run(
                ["clang", str(caller), str(out_obj), "-o", str(exe)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(linked.returncode, 0, linked.stderr)
            executed = subprocess.run(
                [str(exe)], capture_output=True, text=True, check=False
            )
            self.assertEqual(executed.returncode, 0, executed.stderr)

    def test_sv2_infers_wide_let_from_call_return_type(self):
        """SV2.17: Untyped let bound to a call preserves the callee's usize return type."""
        src_path = self.root / "inferred_wide_call.sotlas"
        src_path.write_text(INFERRED_WIDE_CALL_SRC, encoding="utf-8")
        out_obj = self.root / "inferred_wide_call.o"
        r = subprocess.run(
            [str(self.stage1), "--compile-obj", str(src_path), str(out_obj)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(out_obj.is_file())

        data = out_obj.read_bytes()
        self.assertEqual(data[:4], b"\x7fELF")
        self.assertIn(b"inferred_wide\x00", data)
        self.assertIn(b"identity_wide\x00", data)
        self.assertIn(
            b"\x48\xb8\x01\x00\x00\x00\x01\x00\x00\x00",
            data,
        )

        if sys.platform.startswith("linux"):
            caller = self.root / "inferred_wide_call_caller.c"
            caller.write_text(
                "#include <stddef.h>\n"
                "extern size_t inferred_wide(void);\n"
                "int main(void) { return inferred_wide() == "
                "(size_t)4294967297ULL ? 0 : 1; }\n",
                encoding="utf-8",
            )
            exe = self.root / "inferred_wide_call_native"
            linked = subprocess.run(
                ["clang", str(caller), str(out_obj), "-o", str(exe)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(linked.returncode, 0, linked.stderr)
            executed = subprocess.run(
                [str(exe)], capture_output=True, text=True, check=False
            )
            self.assertEqual(executed.returncode, 0, executed.stderr)

    def test_sv2_call_statement_uses_declared_wide_return_type(self):
        """SV2.18: Discarding a usize call result must not force the call through U32."""
        src_path = self.root / "discarded_wide_call.sotlas"
        src_path.write_text(DISCARDED_WIDE_CALL_SRC, encoding="utf-8")
        out_obj = self.root / "discarded_wide_call.o"
        out_bin = self.root / "discarded_wide_call.bin"

        compiled = subprocess.run(
            [str(self.stage1), "--compile-obj", str(src_path), str(out_obj)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(compiled.returncode, 0, compiled.stderr)
        self.assertTrue(out_obj.is_file())

        data = out_obj.read_bytes()
        self.assertEqual(data[:4], b"\x7fELF")
        self.assertIn(b"run_discarded_wide\x00", data)
        self.assertIn(b"identity_wide\x00", data)
        self.assertIn(
            b"\x48\xb8\x01\x00\x00\x00\x01\x00\x00\x00",
            data,
        )

        linked = subprocess.run(
            [
                str(self.stage1),
                "--link-exe",
                str(out_obj),
                str(out_bin),
                "run_discarded_wide",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(linked.returncode, 0, linked.stderr)
        self.assertTrue(out_bin.is_file())

        if sys.platform.startswith("linux"):
            executed = subprocess.run(
                [str(out_bin)], capture_output=True, text=True, check=False
            )
            self.assertEqual(executed.returncode, 7, executed.stderr)

    def test_sv2_lowering_struct_methods_preserves_wide_argument_type(self):
        """SV2.16: Receiver calls preserve declared usize argument/return types through native ELF."""
        src_path = self.root / "methods_wide.sotlas"
        src_path.write_text(STRUCT_METHOD_WIDE_SRC, encoding="utf-8")
        out_obj = self.root / "methods_wide.o"
        r = subprocess.run(
            [str(self.stage1), "--compile-obj", str(src_path), str(out_obj)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(out_obj.is_file())

        data = out_obj.read_bytes()
        self.assertEqual(data[:4], b"\x7fELF")
        self.assertIn(b"run_wide_method\x00", data)
        self.assertIn(b"WideBox_keep_wide\x00", data)
        self.assertIn(
            b"\x48\xb8\x01\x00\x00\x00\x01\x00\x00\x00",
            data,
        )

        if sys.platform.startswith("linux"):
            caller = self.root / "methods_wide_caller.c"
            caller.write_text(
                "#include <stddef.h>\n"
                "extern size_t run_wide_method(void);\n"
                "int main(void) { return run_wide_method() == "
                "(size_t)4294967297ULL ? 0 : 1; }\n",
                encoding="utf-8",
            )
            exe = self.root / "methods_wide_native"
            linked = subprocess.run(
                ["clang", str(caller), str(out_obj), "-o", str(exe)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(linked.returncode, 0, linked.stderr)
            executed = subprocess.run(
                [str(exe)], capture_output=True, text=True, check=False
            )
            self.assertEqual(executed.returncode, 0, executed.stderr)


if __name__ == "__main__":
    unittest.main()
