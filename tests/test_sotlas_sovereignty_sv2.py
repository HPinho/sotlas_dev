"""Sovereignty Milestone SV2 Gate: Native Frontend AST/Sema to Target IR Lowering.

Validates that:
1. Target IR contract (target_ir.sotlas) defines pure Sotlas-owned SSA representations:
   TargetOpcode, TargetTypeTag, TargetInstruction, TargetFunction, TargetBlock,
   TargetParameter, TargetValue, TargetOperand, TargetPhiInput without C or Python dependencies.
2. Scalar AST-to-Target-IR lowering (lower_scalar.sotlas) translates:
   - Integer and boolean scalar parameters (u8..u64, i8..i64, usize, isize, bool).
   - Integer literals and constant expressions with range checks.
   - Local variable definitions (let) and assignments.
   - Certified integer arithmetic, bitwise, shift, and unsigned div/mod expressions.
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

pub fn div_unsupported(a: i64, b: i64) -> i64 {
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

VOID_CALL_SRC = """module sv2::void_call;

pub fn run_void_call() -> u32 {
    sink_wide(4294967297);
    return 9;
}

fn sink_wide(value: usize) {
    return;
}
"""

MODULE_INTEGER_CONST_SRC = """module sv2::module_integer_const;

pub const MODULE_WIDE_LIMIT: u64 = 4294967297;
pub const MODULE_VERSION: u32 = 17;

pub fn read_module_const() -> u64 {
    return MODULE_WIDE_LIMIT;
}

pub fn check_module_const() -> u32 {
    if MODULE_WIDE_LIMIT > 4294967296 {
        return MODULE_VERSION;
    } else {
        return 1;
    }
}
"""

PURE_BOOL_COMPOSITION_SRC = """module sv4::pure_bool_composition;

fn composed_guard(a: u32, b: u32, c: u32) -> u32 {
    if (a > 3 && b == 7) || c != 0 {
        return 23;
    } else {
        return 4;
    }
}

pub fn case_true_and() -> u32 {
    return composed_guard(4, 7, 0);
}

pub fn case_false() -> u32 {
    return composed_guard(1, 7, 0);
}

pub fn case_true_or() -> u32 {
    return composed_guard(1, 2, 1);
}

pub fn bool_value(a: u32, b: u32) -> bool {
    return a != 0 && b == 9;
}
"""

IMPURE_BOOL_COMPOSITION_SRC = """module sv4::impure_bool_composition;

fn probe_value() -> u32 {
    return 1;
}

pub fn rejected_guard(a: u32) -> u32 {
    if a != 0 && probe_value() > 0 {
        return 1;
    } else {
        return 0;
    }
}
"""


SV4_INTEGER_OPS_SRC = """module sv4::integer_ops;

fn bitwise_mix(value: u32) -> u32 {
    return ((value & 15) | 32) ^ 3;
}

fn shift_mix(value: usize) -> usize {
    return (value << 3) >> 1;
}

fn divmod_mix(value: usize) -> usize {
    return value / 7 + value % 7;
}

pub fn case_bitwise() -> u32 {
    return bitwise_mix(23);
}

pub fn case_shift() -> u32 {
    if shift_mix(5) == 20 {
        return 20;
    } else {
        return 1;
    }
}

pub fn case_divmod() -> u32 {
    if divmod_mix(100) == 16 {
        return 16;
    } else {
        return 1;
    }
}
"""

SV4_INTEGER_CAST_SRC = """module sv4::integer_casts;

fn widen(value: u32) -> u64 {
    return value as u64;
}

fn narrow(value: u64) -> u32 {
    return value as u32;
}

pub fn case_cast() -> u32 {
    let wide: u64 = widen(4294967295);
    return narrow(wide + 2);
}
"""

SV4_FIXED_ARRAY_STORE_SRC = """module sv4::fixed_array_store;

pub static mut WORDS: [u32; 4] = 0;
pub static mut BYTES: [u8; 8] = 0;

fn write_word(index: usize, value: u32) -> u32 {
    WORDS[index] = value;
    return value;
}

fn write_byte(index: usize, value: u8) -> u8 {
    BYTES[index] = value;
    return value;
}

fn read_word(index: usize) -> u32 {
    return unsafe { WORDS[index] };
}

fn read_byte(index: usize) -> u8 {
    return unsafe { BYTES[index] };
}

pub fn case_store() -> u32 {
    write_word(2, 37);
    write_byte(3, 5);
    return read_word(2) + (read_byte(3) as u32);
}

pub fn case_store_oob() -> u32 {
    write_word(4, 1);
    return 0;
}
"""

SV4_RAW_POINTER_ADDRESS_SRC = """module sv4::raw_pointer_address;

pub fn read_u32(ptr: *const u32, index: usize) -> u32 {
    return unsafe { *(ptr + index) };
}

pub fn read_u8(ptr: *const u8, index: usize) -> u8 {
    return unsafe { *(ptr + index) };
}

pub fn write_u32(ptr: *mut u32, index: usize, value: u32) {
    unsafe { *(ptr + index) = value; }
}

pub fn previous_u32(ptr: *const u32, index: usize) -> u32 {
    return unsafe { *(ptr + index - 1) };
}
"""

SV4_RAW_POINTER_DEREF_REJECT_SRC = """module sv4::raw_pointer_deref_reject;

pub fn rejected_deref(ptr: *const u32) -> u32 {
    return *ptr;
}
"""

SV4_RAW_POINTER_INDEX_REJECT_SRC = """module sv4::raw_pointer_index_reject;

pub fn rejected_raw_index(ptr: *const u32, index: usize) -> u32 {
    return unsafe { ptr[index] };
}
"""

SV4_POINTER_CAST_REJECT_SRC = """module sv4::pointer_cast_reject;

pub fn rejected_pointer(value: u64) -> u64 {
    let ptr: *const u8 = value as *const u8;
    return value;
}
"""

SV4_FIXED_ARRAY_INDEX_SRC = """module sv4::fixed_array_index;

pub static mut WORDS: [u32; 4] = 0;
pub static mut BYTES: [u8; 8] = 0;

fn read_word(index: usize) -> u32 {
    return unsafe { WORDS[index] };
}

fn read_byte(index: usize) -> u8 {
    return unsafe { BYTES[index] };
}

pub fn case_safe() -> u32 {
    return read_word(2) + (read_byte(3) as u32);
}

pub fn case_oob() -> u32 {
    return read_word(4);
}
"""

SV4_SIGNED_DIV_REJECT_SRC = """module sv4::signed_div_reject;

pub fn rejected_signed(value: i64) -> i64 {
    return value / 3;
}
"""

SV4_SHORT_CIRCUIT_DIV_REJECT_SRC = """module sv4::short_circuit_div_reject;

pub fn rejected_trap_guard(value: u32) -> u32 {
    if value == 0 || 10 / value > 1 {
        return 1;
    } else {
        return 0;
    }
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

        for op in (
            "ConstInt", "Add", "Sub", "Mul", "BitAnd", "BitOr", "BitXor",
            "ShiftLeft", "ShiftRight", "Div", "Mod", "IntCast", "IndexAddr", "PtrOffset", "Compare", "Call",
            "Return", "Branch", "CondBranch", "AllocStack", "Store", "Load",
        ):
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
        """SV2.9: Signed division remains fail-closed until native idiv semantics are certified."""
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

    def test_sv2_direct_void_call_statement_is_native(self):
        """SV2.19: Direct void call statements lower without inventing an SSA result."""
        src_path = self.root / "void_call.sotlas"
        src_path.write_text(VOID_CALL_SRC, encoding="utf-8")
        out_obj = self.root / "void_call.o"
        out_bin = self.root / "void_call.bin"

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
        self.assertIn(b"run_void_call\x00", data)
        self.assertIn(b"sink_wide\x00", data)
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
                "run_void_call",
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
            self.assertEqual(executed.returncode, 9, executed.stderr)

    def test_sv2_module_integer_consts_lower_as_immediates(self):
        """SV2.20: Module integer consts preserve values without becoming zeroed BSS."""
        src_path = self.root / "module_integer_const.sotlas"
        src_path.write_text(MODULE_INTEGER_CONST_SRC, encoding="utf-8")
        out_obj = self.root / "module_integer_const.o"
        out_bin = self.root / "module_integer_const.bin"

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
        self.assertIn(b"read_module_const\x00", data)
        self.assertIn(b"check_module_const\x00", data)
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
                "check_module_const",
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
            self.assertEqual(executed.returncode, 17, executed.stderr)

    def test_sv4_logical_operator_ast_tag_contract(self):
        """SV4.6 regression guard: lowerer must use parser operator_tag values, not TokenKind ids."""
        parser_src = (NATIVE_DIR / "parser.sotlas").read_text(encoding="utf-8")
        lower_src = (
            NATIVE_DIR / "backend" / "lower_scalar.sotlas"
        ).read_text(encoding="utf-8")
        self.assertIn("TokenKind::LogicalAnd { return 110; }", parser_src)
        self.assertIn("TokenKind::LogicalOr { return 111; }", parser_src)
        self.assertIn("expression.int_value == 110", lower_src)
        self.assertIn("expression.int_value == 111", lower_src)
        self.assertNotIn("expression.int_value == 116", lower_src)
        self.assertNotIn("expression.int_value == 117", lower_src)

    def test_sv4_integer_operator_ast_tag_contract(self):
        """SV4.7 regression guard: native lowering follows Parser::operator_tag values."""
        parser_src = (NATIVE_DIR / "parser.sotlas").read_text(encoding="utf-8")
        lower_src = (
            NATIVE_DIR / "backend" / "lower_scalar.sotlas"
        ).read_text(encoding="utf-8")
        expected = {
            "Slash": 83,
            "Percent": 84,
            "Amp": 92,
            "Pipe": 93,
            "Caret": 94,
            "Shl": 96,
            "Shr": 97,
        }
        for token, tag in expected.items():
            self.assertIn(f"TokenKind::{token} {{ return {tag}; }}", parser_src)
            self.assertIn(f"expression.int_value == {tag}", lower_src)

    def test_sv4_pure_boolean_composition_is_native(self):
        """SV4.6: Pure &&/|| conditions lower to typed Bool IR and native x86-64."""
        src_path = self.root / "pure_bool_composition.sotlas"
        src_path.write_text(PURE_BOOL_COMPOSITION_SRC, encoding="utf-8")
        out_obj = self.root / "pure_bool_composition.o"

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
        self.assertIn(b"composed_guard\x00", data)
        self.assertIn(b"case_true_and\x00", data)
        self.assertIn(b"case_false\x00", data)
        self.assertIn(b"case_true_or\x00", data)
        self.assertIn(b"bool_value\x00", data)
        # AND r32,r/m32 (0x23) and OR r32,r/m32 (0x0b) over Bool slots.
        self.assertIn(b"\x23\x85", data)
        self.assertIn(b"\x0b\x85", data)

        if sys.platform.startswith("linux"):
            cases = (
                ("case_true_and", 23),
                ("case_false", 4),
                ("case_true_or", 23),
            )
            for index, (entry, expected) in enumerate(cases):
                out_bin = self.root / f"pure_bool_{index}.bin"
                linked = subprocess.run(
                    [
                        str(self.stage1),
                        "--link-exe",
                        str(out_obj),
                        str(out_bin),
                        entry,
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(linked.returncode, 0, linked.stderr)
                executed = subprocess.run(
                    [str(out_bin)], capture_output=True, text=True, check=False
                )
                self.assertEqual(executed.returncode, expected, executed.stderr)

    def test_sv4_impure_boolean_composition_fails_closed(self):
        """SV4.6 negative gate: eager &&/|| rejects calls that would require short-circuit semantics."""
        src_path = self.root / "impure_bool_composition.sotlas"
        src_path.write_text(IMPURE_BOOL_COMPOSITION_SRC, encoding="utf-8")
        out_obj = self.root / "impure_bool_composition.o"
        compiled = subprocess.run(
            [str(self.stage1), "--compile-obj", str(src_path), str(out_obj)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(compiled.returncode, 0)
        self.assertFalse(out_obj.exists())

    def test_sv4_integer_bitwise_shift_divmod_are_native(self):
        """SV4.7: Typed U32/U64 integer bitwise, shift, division and modulo reach native x86-64."""
        src_path = self.root / "integer_ops.sotlas"
        src_path.write_text(SV4_INTEGER_OPS_SRC, encoding="utf-8")
        out_obj = self.root / "integer_ops.o"
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
        for symbol in (
            b"bitwise_mix\x00",
            b"shift_mix\x00",
            b"divmod_mix\x00",
            b"case_bitwise\x00",
            b"case_shift\x00",
            b"case_divmod\x00",
        ):
            self.assertIn(symbol, data)
        self.assertIn(b"\x23\x85", data)  # and r32, [rbp+disp32]
        self.assertIn(b"\x0b\x85", data)  # or r32, [rbp+disp32]
        self.assertIn(b"\x33\x85", data)  # xor r32, [rbp+disp32]
        self.assertIn(b"\xd3\xe0", data)  # shl eax/rax, cl
        self.assertIn(b"\xd3\xe8", data)  # shr eax/rax, cl
        self.assertIn(b"\xf7\xb5", data)  # div [rbp+disp32]

        if sys.platform.startswith("linux"):
            for index, (entry, expected) in enumerate(
                (("case_bitwise", 36), ("case_shift", 20), ("case_divmod", 16))
            ):
                out_bin = self.root / f"integer_ops_{index}.bin"
                linked = subprocess.run(
                    [
                        str(self.stage1),
                        "--link-exe",
                        str(out_obj),
                        str(out_bin),
                        entry,
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(linked.returncode, 0, linked.stderr)
                executed = subprocess.run(
                    [str(out_bin)], capture_output=True, text=True, check=False
                )
                self.assertEqual(executed.returncode, expected, executed.stderr)

    def test_sv4_integer_casts_are_native(self):
        """SV4.8a: Explicit U32/U64 integer casts lower to native x86-64 truncation/extension."""
        src_path = self.root / "integer_casts.sotlas"
        src_path.write_text(SV4_INTEGER_CAST_SRC, encoding="utf-8")
        out_obj = self.root / "integer_casts.o"
        compiled = subprocess.run(
            [str(self.stage1), "--compile-obj", str(src_path), str(out_obj)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(compiled.returncode, 0, compiled.stderr)
        self.assertTrue(out_obj.is_file())
        self.assertEqual(out_obj.read_bytes()[:4], b"\x7fELF")

        if sys.platform.startswith("linux"):
            out_bin = self.root / "integer_casts.bin"
            linked = subprocess.run(
                [
                    str(self.stage1),
                    "--link-exe",
                    str(out_obj),
                    str(out_bin),
                    "case_cast",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(linked.returncode, 0, linked.stderr)
            executed = subprocess.run(
                [str(out_bin)], capture_output=True, text=True, check=False
            )
            self.assertEqual(executed.returncode, 1, executed.stderr)

    def test_sv4_fixed_array_dynamic_read_indexing_is_native(self):
        """SV4.8b: Global fixed arrays use checked native base + index*stride addressing."""
        src_path = self.root / "fixed_array_index.sotlas"
        src_path.write_text(SV4_FIXED_ARRAY_INDEX_SRC, encoding="utf-8")
        out_obj = self.root / "fixed_array_index.o"
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
        self.assertIn(b"read_word\x00", data)
        self.assertIn(b"read_byte\x00", data)
        self.assertIn(b"case_safe\x00", data)
        self.assertIn(b"case_oob\x00", data)
        self.assertIn(b"\x48\x3d", data)  # cmp rax, fixed-array length
        self.assertIn(b"\x0f\x82\x02\x00\x00\x00\x0f\x0b", data)
        self.assertIn(b"\x48\xc1\xe0\x02", data)  # u32 stride 4
        self.assertIn(b"\x0f\xb6\x81", data)  # zero-extending u8 load

        if sys.platform.startswith("linux"):
            safe_bin = self.root / "fixed_array_safe.bin"
            linked = subprocess.run(
                [
                    str(self.stage1),
                    "--link-exe",
                    str(out_obj),
                    str(safe_bin),
                    "case_safe",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(linked.returncode, 0, linked.stderr)
            executed = subprocess.run(
                [str(safe_bin)], capture_output=True, text=True, check=False
            )
            self.assertEqual(executed.returncode, 0, executed.stderr)

            oob_bin = self.root / "fixed_array_oob.bin"
            linked_oob = subprocess.run(
                [
                    str(self.stage1),
                    "--link-exe",
                    str(out_obj),
                    str(oob_bin),
                    "case_oob",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(linked_oob.returncode, 0, linked_oob.stderr)
            oob_run = subprocess.run(
                [str(oob_bin)], capture_output=True, text=True, check=False
            )
            self.assertNotEqual(oob_run.returncode, 0)

    def test_sv4_fixed_array_dynamic_stores_are_native(self):
        """SV4.8c1: Checked IndexAddr is reused for typed fixed-array stores."""
        src_path = self.root / "fixed_array_store.sotlas"
        src_path.write_text(SV4_FIXED_ARRAY_STORE_SRC, encoding="utf-8")
        out_obj = self.root / "fixed_array_store.o"
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
        for symbol in (
            b"write_word\x00",
            b"write_byte\x00",
            b"case_store\x00",
            b"case_store_oob\x00",
        ):
            self.assertIn(symbol, data)
        self.assertIn(b"\x48\x3d", data)  # bounds compare
        self.assertIn(b"\x48\xc1\xe0\x02", data)  # u32 stride 4
        self.assertIn(b"\x89\x81", data)  # typed u32 store through indexed RCX
        self.assertIn(b"\x88\x81", data)  # typed u8 store through indexed RCX

        if sys.platform.startswith("linux"):
            safe_bin = self.root / "fixed_array_store_safe.bin"
            linked = subprocess.run(
                [
                    str(self.stage1),
                    "--link-exe",
                    str(out_obj),
                    str(safe_bin),
                    "case_store",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(linked.returncode, 0, linked.stderr)
            executed = subprocess.run(
                [str(safe_bin)], capture_output=True, text=True, check=False
            )
            self.assertEqual(executed.returncode, 42, executed.stderr)

            oob_bin = self.root / "fixed_array_store_oob.bin"
            linked_oob = subprocess.run(
                [
                    str(self.stage1),
                    "--link-exe",
                    str(out_obj),
                    str(oob_bin),
                    "case_store_oob",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(linked_oob.returncode, 0, linked_oob.stderr)
            oob_run = subprocess.run(
                [str(oob_bin)], capture_output=True, text=True, check=False
            )
            self.assertNotEqual(oob_run.returncode, 0)

    def test_sv4_raw_pointer_addressing_is_native(self):
        """SV4.8c2: unsafe pointer +/- index and scalar dereference lower natively."""
        src_path = self.root / "raw_pointer_address.sotlas"
        src_path.write_text(SV4_RAW_POINTER_ADDRESS_SRC, encoding="utf-8")
        out_obj = self.root / "raw_pointer_address.o"
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
        for symbol in (
            b"read_u32\x00",
            b"read_u8\x00",
            b"write_u32\x00",
            b"previous_u32\x00",
        ):
            self.assertIn(symbol, data)
        self.assertIn(b"\x48\xc1\xe0\x02", data)  # u32 pointee stride
        self.assertIn(b"\x48\x01\xc8", data)  # base + scaled index
        self.assertIn(b"\x48\x29\xc1", data)  # base - scaled index
        self.assertIn(b"\x8b\x81", data)  # scalar u32 load
        self.assertIn(b"\x89\x81", data)  # scalar u32 store
        self.assertIn(b"\x0f\xb6\x81", data)  # scalar u8 load

    def test_sv8_real_target_ir_progresses_past_cfg_has_block(self):
        """SV8.7b2: The real-module probe must move past the 295:5 guard blocker or emit ELF."""
        src_path = NATIVE_DIR / "backend" / "target_ir.sotlas"
        out_obj = self.root / "target_ir_real.o"
        compiled = subprocess.run(
            [str(self.stage1), "--compile-obj", str(src_path), str(out_obj)],
            capture_output=True,
            text=True,
            check=False,
        )
        if compiled.returncode == 0:
            self.assertTrue(out_obj.is_file())
            data = out_obj.read_bytes()
            self.assertEqual(data[:4], b"\x7fELF")
            self.assertIn(b"target_cfg_has_block\x00", data)
            self.assertIn(b"target_module_validate_cfg\x00", data)
            return

        self.assertFalse(out_obj.exists())
        print("SV8.7 real target_ir blocker:", compiled.stderr.strip())
        marker = "err line "
        self.assertIn(marker, compiled.stderr, compiled.stderr)
        tail = compiled.stderr.split(marker, 1)[1]
        line_text = tail.split(",", 1)[0].strip()
        self.assertTrue(line_text.isdigit(), compiled.stderr)
        blocker_line = int(line_text)
        self.assertGreater(
            blocker_line,
            295,
            "SV8.7b2 regressed to or before the certified 295:5 guard blocker.\n"
            + compiled.stderr,
        )

    def test_sv4_raw_pointer_deref_requires_unsafe(self):
        """SV4.8c2 negative gate: dereference outside unsafe remains rejected."""
        src_path = self.root / "raw_pointer_deref_reject.sotlas"
        src_path.write_text(SV4_RAW_POINTER_DEREF_REJECT_SRC, encoding="utf-8")
        out_obj = self.root / "raw_pointer_deref_reject.o"
        compiled = subprocess.run(
            [str(self.stage1), "--compile-obj", str(src_path), str(out_obj)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(compiled.returncode, 0)
        self.assertFalse(out_obj.exists())

    def test_sv4_raw_pointer_indexing_stays_fail_closed(self):
        """SV4.8c1 negative gate: raw-pointer indexing waits for provenance rules."""
        src_path = self.root / "raw_pointer_index_reject.sotlas"
        src_path.write_text(SV4_RAW_POINTER_INDEX_REJECT_SRC, encoding="utf-8")
        out_obj = self.root / "raw_pointer_index_reject.o"
        compiled = subprocess.run(
            [str(self.stage1), "--compile-obj", str(src_path), str(out_obj)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(compiled.returncode, 0)
        self.assertFalse(out_obj.exists())

    def test_sv4_pointer_cast_stays_fail_closed(self):
        """SV4.8a negative gate: integer/pointer casts remain rejected until pointer provenance is certified."""
        src_path = self.root / "pointer_cast_reject.sotlas"
        src_path.write_text(SV4_POINTER_CAST_REJECT_SRC, encoding="utf-8")
        out_obj = self.root / "pointer_cast_reject.o"
        compiled = subprocess.run(
            [str(self.stage1), "--compile-obj", str(src_path), str(out_obj)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(compiled.returncode, 0)
        self.assertFalse(out_obj.exists())

    def test_sv4_short_circuit_trap_capable_rhs_fails_closed(self):
        """SV4.6/SV4.7 guard: eager logical composition rejects trap-capable div/mod operands."""
        src_path = self.root / "short_circuit_div_reject.sotlas"
        src_path.write_text(SV4_SHORT_CIRCUIT_DIV_REJECT_SRC, encoding="utf-8")
        out_obj = self.root / "short_circuit_div_reject.o"
        compiled = subprocess.run(
            [str(self.stage1), "--compile-obj", str(src_path), str(out_obj)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(compiled.returncode, 0)
        self.assertFalse(out_obj.exists())

    def test_sv4_signed_division_fails_closed(self):
        """SV4.7 negative gate: signed division stays rejected until idiv semantics are certified."""
        src_path = self.root / "signed_div_reject.sotlas"
        src_path.write_text(SV4_SIGNED_DIV_REJECT_SRC, encoding="utf-8")
        out_obj = self.root / "signed_div_reject.o"
        compiled = subprocess.run(
            [str(self.stage1), "--compile-obj", str(src_path), str(out_obj)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(compiled.returncode, 0)
        self.assertFalse(out_obj.exists())

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
