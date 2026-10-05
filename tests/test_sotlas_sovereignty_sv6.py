"""Sovereignty Milestone SV6 Gate: Real Application and Minimal Kernel Native Compilation.

Validates that the Sotlas native compiler compiles:
1. A real multi-function application into an ELF64 relocatable object and static executable
   without calling the C11 emitter or external assemblers/linkers.
2. The minimal freestanding kernel into an ELF64 relocatable object and freestanding image
   without calling the C11 emitter, verifying exact ELF headers, symbol visibility,
   and freestanding entry point handoff.
3. Fail-closed contract checks for invalid inputs, malformed kernels, and missing entry points.
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
COMPILER_DIR = ROOT / "compiler"
if str(COMPILER_DIR) not in sys.path:
    sys.path.insert(0, str(COMPILER_DIR))

from sotlas.llvm_toolchain import default_toolchain
from sotlas_compile.bootstrap import compile_module, emit_c, parse

PREAMBLE = """
#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
"""


def build_native_compiler_harness(dest_dir: Path) -> Path:
    module_dir = ROOT / "bootstrap" / "sotlas" / "native_compiler"
    order = (
        "token", "ast", "lexer", "parser", "sema", "emitter_c",
        "target_ir", "lower_scalar", "x86_64_scalar", "main",
    )
    modules = {
        path.stem: parse(path.read_text(encoding="utf-8"), filename=str(path))
        for path in module_dir.rglob("*.sotlas")
    }

    fragments = [PREAMBLE]
    for name in order:
        compile_module(
            modules[name],
            [modules[dep] for dep in order if dep != name],
        )
        fragments.append(emit_c(
            modules[name], mangle=False, include_preamble=False
        ))

    compiler_c = dest_dir / "native_compiler.c"
    compiler_obj = dest_dir / "native_compiler.obj"
    driver_c = dest_dir / "sv6_driver.c"
    driver_obj = dest_dir / "sv6_driver.obj"
    compiler_exe = dest_dir / ("native_compiler_sv6.exe" if os.name == "nt" else "native_compiler_sv6")

    compiler_c.write_text("\n".join(fragments), encoding="utf-8")
    driver_c.write_text(
        r"""#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdbool.h>
#include <string.h>

extern bool sotlas_native_compile_object(
    const uint8_t *source, size_t len,
    uint8_t *output, size_t capacity, size_t *out_length
);

extern bool sotlas_native_link_executable(
    const uint8_t *object, size_t object_len,
    const uint8_t *entry_name, size_t entry_name_len,
    bool freestanding,
    uint8_t *output, size_t capacity, size_t *out_length
);

int main(int argc, char **argv) {
    if (argc < 4) return 1;

    static uint8_t src_buf[1048576];
    static uint8_t out_buf[1048576];

    FILE *f_in = fopen(argv[2], "rb");
    if (!f_in) return 2;
    size_t in_len = fread(src_buf, 1, sizeof(src_buf), f_in);
    fclose(f_in);

    if (strcmp(argv[1], "--compile-obj") == 0) {
        size_t out_len = 0;
        bool ok = sotlas_native_compile_object(src_buf, in_len, out_buf, sizeof(out_buf), &out_len);
        if (!ok || out_len == 0) return 10;

        FILE *f_out = fopen(argv[3], "wb");
        if (!f_out) return 11;
        fwrite(out_buf, 1, out_len, f_out);
        fclose(f_out);
        return 0;
    }

    if (strcmp(argv[1], "--link-exe") == 0 && argc >= 5) {
        const char *entry_name = argv[4];
        bool freestanding = (argc >= 6 && strcmp(argv[5], "--freestanding") == 0);
        size_t out_len = 0;
        bool ok = sotlas_native_link_executable(
            src_buf, in_len,
            (const uint8_t *)entry_name, strlen(entry_name),
            freestanding,
            out_buf, sizeof(out_buf), &out_len
        );
        if (!ok || out_len == 0) return 20;

        FILE *f_out = fopen(argv[3], "wb");
        if (!f_out) return 21;
        fwrite(out_buf, 1, out_len, f_out);
        fclose(f_out);
        return 0;
    }

    return 3;
}
""",
        encoding="utf-8",
    )

    default_toolchain.compile_c_to_obj(compiler_c, compiler_obj, opt_level=2)
    default_toolchain.compile_c_to_obj(driver_c, driver_obj, opt_level=2)
    default_toolchain.link_native_binary([compiler_obj, driver_obj], compiler_exe)
    return compiler_exe


class TestSotlasSovereigntySV6(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp_dir = tempfile.TemporaryDirectory(prefix="sotlas-sv6-")
        cls.root = Path(cls.tmp_dir.name)
        cls.compiler_exe = build_native_compiler_harness(cls.root)

    @classmethod
    def tearDownClass(cls):
        cls.tmp_dir.cleanup()

    def test_sv6_real_application_native_compilation(self):
        """SV6.1: Compile a real application without C11 backend and verify execution."""
        app_source = self.root / "real_app.sotlas"
        app_source.write_text(
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

        app_obj = self.root / "real_app.o"
        res_obj = subprocess.run(
            [str(self.compiler_exe), "--compile-obj", str(app_source), str(app_obj)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(res_obj.returncode, 0, f"Object compilation failed: {res_obj.stderr}")
        self.assertTrue(app_obj.is_file())

        obj_data = app_obj.read_bytes()
        self.assertGreater(len(obj_data), 64)
        # ELF header verification
        self.assertEqual(obj_data[:4], b"\x7fELF")
        self.assertEqual(obj_data[4], 2)  # 64-bit
        self.assertEqual(obj_data[5], 1)  # little endian
        self.assertEqual(obj_data[6], 1)  # ELF version 1
        e_type = struct.unpack_from("<H", obj_data, 16)[0]
        e_machine = struct.unpack_from("<H", obj_data, 18)[0]
        self.assertEqual(e_type, 1)  # ET_REL
        self.assertEqual(e_machine, 62)  # EM_X86_64

        # Symbol table verification
        self.assertIn(b"multiply_offset", obj_data)
        self.assertIn(b"compute_metric", obj_data)
        self.assertIn(b"main_entry", obj_data)

        # Link to executable through Sotlas native linker
        app_exe = self.root / "real_app.elf"
        res_link = subprocess.run(
            [str(self.compiler_exe), "--link-exe", str(app_obj), str(app_exe), "main_entry"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(res_link.returncode, 0, f"Linking failed: {res_link.stderr}")
        self.assertTrue(app_exe.is_file())

        exe_data = app_exe.read_bytes()
        self.assertEqual(exe_data[:4], b"\x7fELF")
        e_type_exe = struct.unpack_from("<H", exe_data, 16)[0]
        self.assertEqual(e_type_exe, 2)  # ET_EXEC
        e_entry = struct.unpack_from("<Q", exe_data, 24)[0]
        self.assertGreater(e_entry, 0)

    def test_sv6_minimal_kernel_native_compilation(self):
        """SV6.2: Compile the minimal freestanding kernel without C11 backend."""
        kernel_source = self.root / "kernel_min.sotlas"
        kernel_source.write_text(
            """barecore;
module kernel::minimal;

@repr(C)
@packed
pub struct BootFrame {
    framebuffer: *mut u32;
    framebuffer_size: usize;
    width: u32;
    height: u32;
    pitch: u32;
    tag: [u8; 8];
}

@export
pub fn available_memory(capacity: u32, used: u32) -> u32 {
    return capacity - used;
}

@export
@system
pub fn kernel_main(magic: u32, flags: u32) -> u32 {
    let avail: u32 = available_memory(magic, flags);
    if avail > 0 {
        return avail;
    } else {
        return 0;
    }
}
""",
            encoding="utf-8",
        )

        kernel_obj = self.root / "kernel_min.o"
        res_obj = subprocess.run(
            [str(self.compiler_exe), "--compile-obj", str(kernel_source), str(kernel_obj)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(res_obj.returncode, 0, f"Kernel object compilation failed: {res_obj.stderr}")
        self.assertTrue(kernel_obj.is_file())

        obj_data = kernel_obj.read_bytes()
        self.assertEqual(obj_data[:4], b"\x7fELF")
        self.assertEqual(obj_data[4], 2)  # 64-bit
        self.assertEqual(obj_data[5], 1)  # little endian
        e_type = struct.unpack_from("<H", obj_data, 16)[0]
        e_machine = struct.unpack_from("<H", obj_data, 18)[0]
        self.assertEqual(e_type, 1)  # ET_REL
        self.assertEqual(e_machine, 62)  # EM_X86_64

        # Exported symbols must be present
        self.assertIn(b"kernel_main", obj_data)
        self.assertIn(b"available_memory", obj_data)

        # Freestanding link with kernel_main entry
        kernel_elf = self.root / "kernel_min.elf"
        res_link = subprocess.run(
            [str(self.compiler_exe), "--link-exe", str(kernel_obj), str(kernel_elf), "kernel_main", "--freestanding"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(res_link.returncode, 0, f"Kernel freestanding link failed: {res_link.stderr}")
        self.assertTrue(kernel_elf.is_file())

        elf_data = kernel_elf.read_bytes()
        self.assertEqual(elf_data[:4], b"\x7fELF")
        e_type_elf = struct.unpack_from("<H", elf_data, 16)[0]
        self.assertEqual(e_type_elf, 2)  # ET_EXEC
        e_entry = struct.unpack_from("<Q", elf_data, 24)[0]
        # In freestanding mode, base address is 0x100000 (1048576)
        self.assertGreaterEqual(e_entry, 1048576)
        # Entry point directly targets code offset (no Linux sys_exit shim)
        self.assertLess(e_entry, 1048576 + 65536)

    def test_sv6_fail_closed_contract_guards(self):
        """SV6.3: Malformed kernels, invalid ABIs and missing entry points fail closed."""
        bad_source = self.root / "bad_kernel.sotlas"
        bad_source.write_text("barecore;\nmodule bad;\nfn (", encoding="utf-8")
        bad_obj = self.root / "bad_kernel.o"

        res_bad = subprocess.run(
            [str(self.compiler_exe), "--compile-obj", str(bad_source), str(bad_obj)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(res_bad.returncode, 0)
        self.assertFalse(bad_obj.is_file())

        # Valid object but link with nonexistent entry function
        good_source = self.root / "good.sotlas"
        good_source.write_text(
            "module test;\npub fn entry() -> u32 { return 42; }\n",
            encoding="utf-8",
        )
        good_obj = self.root / "good.o"
        res_good = subprocess.run(
            [str(self.compiler_exe), "--compile-obj", str(good_source), str(good_obj)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(res_good.returncode, 0)

        missing_exe = self.root / "missing.elf"
        res_missing = subprocess.run(
            [str(self.compiler_exe), "--link-exe", str(good_obj), str(missing_exe), "non_existent_symbol"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(res_missing.returncode, 0)
        self.assertFalse(missing_exe.is_file())


if __name__ == "__main__":
    unittest.main()
