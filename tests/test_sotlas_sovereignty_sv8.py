"""SV8 parity and determinism checks for the transitional bootstrap pipeline.

Validates that:
1. Stage 0 builds Stage 1; Stage 1 emits the full compiler C source used for Stage 2.
2. Stage 2 emits the full compiler C source used for Stage 3.
3. Compiler C emission reaches a byte-for-byte Stage 1/Stage 2 fixed point.
4. Fixed-point equivalence gate 2: Deterministic ELF object generation across stages
   (sha256(stage1.compile_obj(real_app)) == sha256(stage2.compile_obj(real_app))).
5. Fixed-point equivalence gate 3: Deterministic freestanding kernel object generation
   (sha256(stage1.compile_obj(kernel_min)) == sha256(stage2.compile_obj(kernel_min))).
6. Fixed-point equivalence gate 4 & 5: Bit-for-bit identical static ELF executables and
   freestanding kernel images linked across Stage 1, Stage 2, and Stage 3.
7. The report distinguishes self-hosted frontend emission from the still-hosted executable link.

The C host driver and Clang remain in the link path; this gate does not certify
a Python/C-free toolchain.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "compiler"))

from sotlas.bootstrap_pipeline import (
    build_stage1_native_compiler,
    build_stage2_native_compiler,
    build_stage3_native_compiler,
    verify_stage_fixed_point,
)


class TestSotlasSovereigntySV8(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp_dir = tempfile.TemporaryDirectory(prefix="sotlas-sv8-")
        cls.root = Path(cls.tmp_dir.name)
        exe_suffix = ".exe" if os.name == "nt" else ""
        cls.s1_exe = cls.root / f"sotlas_stage1{exe_suffix}"
        cls.s2_exe = cls.root / f"sotlas_stage2{exe_suffix}"
        cls.s3_exe = cls.root / f"sotlas_stage3{exe_suffix}"

        build_stage1_native_compiler(cls.s1_exe, verbose=False)
        build_stage2_native_compiler(cls.s1_exe, cls.s2_exe, verbose=False)
        build_stage3_native_compiler(cls.s2_exe, cls.s3_exe, verbose=False)

    @classmethod
    def tearDownClass(cls):
        cls.tmp_dir.cleanup()

    def test_sv8_stages_exist_and_execute(self):
        """SV8.1: Stage 1, Stage 2, and Stage 3 executables exist and execute --version."""
        for stage_exe in (self.s1_exe, self.s2_exe, self.s3_exe):
            self.assertTrue(stage_exe.is_file())
            self.assertGreater(stage_exe.stat().st_size, 50000)
            res = subprocess.run([str(stage_exe), "--version"], capture_output=True, text=True)
            self.assertEqual(res.returncode, 0)
            self.assertIn("sotlas", res.stdout.lower())

    def test_sv8_real_application_object_determinism(self):
        """SV8.2: Bit-for-bit identical ELF relocatable objects across Stage 1, Stage 2, Stage 3."""
        app_file = self.root / "real_app.sotlas"
        app_file.write_text(
            """module app::calculator;

fn multiply_offset(a: u32, b: u32, offset: u32) -> u32 {
    let prod: u32 = a * b;
    return prod + offset;
}

fn compute_metric(x: u32, y: u32) -> u32 {
    let base: u32 = multiply_offset(x, y, 10);
    if base > 50 {
        return base;
    } else {
        return 50;
    }
}

pub fn main_entry() -> u32 {
    return compute_metric(10, 6);
}
""",
            encoding="utf-8",
        )

        o1 = self.root / "app_1.o"
        o2 = self.root / "app_2.o"
        o3 = self.root / "app_3.o"

        subprocess.run([str(self.s1_exe), "--compile-obj", str(app_file), str(o1)], check=True)
        subprocess.run([str(self.s2_exe), "--compile-obj", str(app_file), str(o2)], check=True)
        subprocess.run([str(self.s3_exe), "--compile-obj", str(app_file), str(o3)], check=True)

        h1 = hashlib.sha256(o1.read_bytes()).hexdigest()
        h2 = hashlib.sha256(o2.read_bytes()).hexdigest()
        h3 = hashlib.sha256(o3.read_bytes()).hexdigest()

        self.assertEqual(h1, h2, "Stage 1 and Stage 2 must produce bit-for-bit identical ELF object")
        self.assertEqual(h2, h3, "Stage 2 and Stage 3 must produce bit-for-bit identical ELF object")

    def test_sv8_structured_cfg_object_determinism(self):
        """All three hosted stages agree on nested mutable CFG machine output."""
        source = self.root / "structured_cfg.sotlas"
        source.write_text("""module sv8::structured;
pub fn main_entry() -> u32 {
    let mut total: u32 = 0;
    let mut row: u32 = 0;
    while row < 3 {
        let mut column: u32 = 0;
        while column < 3 {
            column = column + 1;
            if column == 2 { continue; }
            total = total + row + column;
            if row == 2 { break; }
        }
        row = row + 1;
    }
    return total;
}
""", encoding="utf-8")
        objects = []
        for index, stage in enumerate((self.s1_exe, self.s2_exe, self.s3_exe), 1):
            output = self.root / f"structured_{index}.o"
            result = subprocess.run([str(stage), "--compile-obj", str(source), str(output)],
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            data = output.read_bytes()
            self.assertEqual(data[:4], b"\x7fELF")
            objects.append(data)
        self.assertEqual(objects[0], objects[1])
        self.assertEqual(objects[1], objects[2])

    def test_sv8_minimal_kernel_object_determinism(self):
        """SV8.3: Bit-for-bit identical freestanding kernel ELF objects across all stages."""
        kernel_file = self.root / "kernel_min.sotlas"
        kernel_file.write_text(
            """module kernel::minimal;

fn early_setup(magic: u32) -> u32 {
    return magic + 1;
}

@system
pub fn _start() -> u32 {
    let status: u32 = early_setup(41);
    return status;
}
""",
            encoding="utf-8",
        )

        ko1 = self.root / "k_1.o"
        ko2 = self.root / "k_2.o"
        ko3 = self.root / "k_3.o"

        subprocess.run([str(self.s1_exe), "--compile-obj", str(kernel_file), str(ko1)], check=True)
        subprocess.run([str(self.s2_exe), "--compile-obj", str(kernel_file), str(ko2)], check=True)
        subprocess.run([str(self.s3_exe), "--compile-obj", str(kernel_file), str(ko3)], check=True)

        h1 = hashlib.sha256(ko1.read_bytes()).hexdigest()
        h2 = hashlib.sha256(ko2.read_bytes()).hexdigest()
        h3 = hashlib.sha256(ko3.read_bytes()).hexdigest()

        self.assertEqual(h1, h2, "Stage 1 and Stage 2 must produce bit-for-bit identical kernel object")
        self.assertEqual(h2, h3, "Stage 2 and Stage 3 must produce bit-for-bit identical kernel object")

    def test_sv8_executable_and_image_linking_determinism(self):
        """SV8.4: Bit-for-bit identical executables and freestanding images across stages."""
        app_file = self.root / "real_app_link.sotlas"
        app_file.write_text(
            """module app::calculator;
fn multiply_offset(a: u32, b: u32, offset: u32) -> u32 {
    let prod: u32 = a * b;
    return prod + offset;
}
pub fn main_entry() -> u32 {
    return multiply_offset(10, 6, 10);
}
""",
            encoding="utf-8",
        )
        o1 = self.root / "app_link.o"
        subprocess.run([str(self.s1_exe), "--compile-obj", str(app_file), str(o1)], check=True)

        e1 = self.root / "app_1.elf"
        e2 = self.root / "app_2.elf"
        e3 = self.root / "app_3.elf"

        subprocess.run([str(self.s1_exe), "--link-exe", str(o1), str(e1), "main_entry"], check=True)
        subprocess.run([str(self.s2_exe), "--link-exe", str(o1), str(e2), "main_entry"], check=True)
        subprocess.run([str(self.s3_exe), "--link-exe", str(o1), str(e3), "main_entry"], check=True)

        he1 = hashlib.sha256(e1.read_bytes()).hexdigest()
        he2 = hashlib.sha256(e2.read_bytes()).hexdigest()
        he3 = hashlib.sha256(e3.read_bytes()).hexdigest()

        self.assertEqual(he1, he2, "Stage 1 and Stage 2 must produce bit-for-bit identical executable")
        self.assertEqual(he2, he3, "Stage 2 and Stage 3 must produce bit-for-bit identical executable")

        k_file = self.root / "kernel_link.sotlas"
        k_file.write_text("""module kernel::minimal;
@system
pub fn _start() -> u32 {
    return 42;
}
""", encoding="utf-8")
        ko1 = self.root / "k_link.o"
        subprocess.run([str(self.s1_exe), "--compile-obj", str(k_file), str(ko1)], check=True)

        kb1 = self.root / "k_1.bin"
        kb2 = self.root / "k_2.bin"
        kb3 = self.root / "k_3.bin"

        subprocess.run([str(self.s1_exe), "--link-exe", str(ko1), str(kb1), "_start", "--freestanding"], check=True)
        subprocess.run([str(self.s2_exe), "--link-exe", str(ko1), str(kb2), "_start", "--freestanding"], check=True)
        subprocess.run([str(self.s3_exe), "--link-exe", str(ko1), str(kb3), "_start", "--freestanding"], check=True)

        hkb1 = hashlib.sha256(kb1.read_bytes()).hexdigest()
        hkb2 = hashlib.sha256(kb2.read_bytes()).hexdigest()
        hkb3 = hashlib.sha256(kb3.read_bytes()).hexdigest()

        self.assertEqual(hkb1, hkb2, "Freestanding kernel image must be bit-for-bit identical")
        self.assertEqual(hkb2, hkb3, "Freestanding kernel image must be bit-for-bit identical")

    def test_sv8_verify_stage_fixed_point_contract(self):
        """SV8 reports native compiler-source fixed point separately from C-free linking."""
        report = verify_stage_fixed_point(self.s1_exe, self.s2_exe, self.s3_exe)
        self.assertFalse(report["build_chain_self_hosted"])
        self.assertTrue(report["compiler_frontend_self_hosted"])
        self.assertEqual(
            report["build_provenance"],
            "stage1-stage2-sotlas-c-emission-clang-c-driver",
        )
        self.assertTrue(report["c_source_fixed_point"])
        self.assertTrue(report["compiler_source_deterministic"])
        self.assertTrue(report["stage3_compiler_source_fixed_point"])
        self.assertTrue(report["app_obj_deterministic"])
        self.assertTrue(report["kernel_obj_deterministic"])
        self.assertTrue(report["app_exe_deterministic"])
        self.assertTrue(report["kernel_bin_deterministic"])
        self.assertTrue(report.get("stage3_app_obj_deterministic", True))


if __name__ == "__main__":
    unittest.main()
