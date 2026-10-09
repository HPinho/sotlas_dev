"""Native Linux file compiler and real native generation-chain gates."""
from pathlib import Path
import hashlib
import os
import platform
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "compiler"))
sys.path.insert(0, str(ROOT / "tools"))
from sotlas.bootstrap_pipeline import build_stage1_native_compiler

LINUX_X64 = sys.platform.startswith("linux") and platform.machine().lower() in ("x86_64", "amd64")


def merged_native_driver_source() -> bytes:
    directory = ROOT / "bootstrap/sotlas/native_compiler"
    names = ("token", "ast", "lexer", "parser", "sema", "backend/target_ir", "backend/lower_scalar", "backend/x86_64_scalar")
    data = b"".join((directory / (name + ".sotlas")).read_bytes() + b"\n" for name in names)
    data += (ROOT / "bootstrap/sotlas/native_driver/linux.sotlas").read_bytes() + b"\n"
    # All imports are represented exactly once above. Avoid a host resolver
    # loading a second copy when validating this self-build input.
    return re.sub(rb"^import [^\r\n]+;\r?\n", b"", data, flags=re.M)


class NativeLinuxDriverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="sotlas-native-linux-")
        cls.directory = Path(cls.temp.name)
        cls.producer = cls.directory / ("producer.exe" if os.name == "nt" else "producer")
        build_stage1_native_compiler(cls.producer, verbose=False)
        cls.seed = cls.directory / "sotlas-native"
        obj = cls.directory / "driver.o"
        cls.run_tool([str(cls.producer), "--compile-obj", str(ROOT / "bootstrap/sotlas/native_driver/linux.sotlas"), str(obj)], 180)
        cls.run_tool([str(cls.producer), "--link-exe", str(obj), str(cls.seed), "sotlas_linux_main"], 60)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    @classmethod
    def run_tool(cls, args, timeout=60, expected=0, env=None):
        result = subprocess.run(args, capture_output=True, timeout=timeout, cwd=ROOT, env=env)
        if result.returncode != expected:
            raise AssertionError(f"{args}: exit {result.returncode}, expected {expected}: {result.stderr!r}")
        return result

    def test_driver_image_is_static_elf_without_c_interpreter(self):
        import struct
        data = self.seed.read_bytes()
        self.assertEqual(data[:6], b"\x7fELF\x02\x01")
        offset = struct.unpack_from("<Q", data, 32)[0]
        size, count = struct.unpack_from("<HH", data, 54)
        self.assertNotIn(3, [struct.unpack_from("<I", data, offset + i * size)[0] for i in range(count)])
        self.assertNotIn(2, [struct.unpack_from("<I", data, offset + i * size)[0] for i in range(count)])

    @unittest.skipUnless(LINUX_X64, "execution requires Linux x86-64")
    def test_compiles_files_without_python_clang_or_c_runtime(self):
        source = self.directory / "sample.sotlas"
        source.write_text("module gate; fn twice(x: u32) -> u32 { return x * 2; } pub fn main_entry() -> u32 { return twice(21); }")
        binary = self.directory / "sample"
        environment = {"PATH": str(self.directory / "no-tools")}
        self.run_tool([str(self.seed), str(source), str(binary)], env=environment)
        self.run_tool([str(binary)], expected=42, env=environment)
        reference = self.directory / "sample_reference.o"
        actual = self.directory / "sample_native.o"
        self.run_tool([str(self.producer), "--compile-obj", str(source), str(reference)])
        self.run_tool([str(self.seed), str(source), str(actual), "--object"], env=environment)
        self.assertEqual(reference.read_bytes(), actual.read_bytes())

    @unittest.skipUnless(LINUX_X64, "execution requires Linux x86-64")
    def test_explicit_multifile_project_object_and_executable_match_producer(self):
        """Native source assembly has identical object bytes and invokes no host tools."""
        first = self.directory / "project_math.sotlas"
        second = self.directory / "project_app.sotlas"
        first.write_text(
            "module gate::math; fn project_answer() -> u32 { return 6 * 7; }",
            encoding="utf-8",
        )
        second.write_text(
            "module gate::app; pub fn main_entry() -> u32 { return project_answer(); }",
            encoding="utf-8",
        )
        environment = {"PATH": str(self.directory / "no-tools")}
        output = self.directory / "project_sample"
        self.run_tool(
            [str(self.seed), "--project", str(output), str(first), str(second)],
            env=environment,
        )
        self.run_tool([str(output)], expected=42, env=environment)

        native_object = self.directory / "project_native.o"
        hosted_object = self.directory / "project_hosted.o"
        merged = self.directory / "project_merged.sotlas"
        merged.write_bytes(first.read_bytes() + b"\n" + second.read_bytes() + b"\n")
        self.run_tool(
            [str(self.seed), "--project-object", str(native_object), str(first), str(second)],
            env=environment,
        )
        self.run_tool([str(self.producer), "--compile-obj", str(merged), str(hosted_object)])
        self.assertEqual(native_object.read_bytes(), hosted_object.read_bytes())

    @unittest.skipUnless(LINUX_X64, "execution requires Linux x86-64")
    def test_explicit_project_failures_preserve_previous_artifact(self):
        """A missing source, unresolved import or oversized input cannot truncate output."""
        first = self.directory / "project_valid.sotlas"
        first.write_text(
            "module gate::math; fn project_answer() -> u32 { return 42; }",
            encoding="utf-8",
        )
        second = self.directory / "project_invalid.sotlas"
        second.write_text(
            "module gate::app; import gate::missing::*; "
            "pub fn main_entry() -> u32 { return project_answer(); }",
            encoding="utf-8",
        )
        output = self.directory / "project_preserved"
        sentinel = b"preexisting native binary must not be touched"
        output.write_bytes(sentinel)
        environment = {"PATH": str(self.directory / "no-tools")}
        self.run_tool(
            [str(self.seed), "--project", str(output), str(first),
             str(self.directory / "missing_file.sotlas")],
            expected=2, env=environment,
        )
        self.assertEqual(output.read_bytes(), sentinel)
        self.run_tool(
            [str(self.seed), "--project", str(output), str(first), str(second)],
            expected=12, env=environment,
        )
        self.assertEqual(output.read_bytes(), sentinel)
        second.write_bytes(b"module gate::app; " + b" " * 1048576)
        self.run_tool(
            [str(self.seed), "--project", str(output), str(first), str(second)],
            expected=3, env=environment,
        )
        self.assertEqual(output.read_bytes(), sentinel)
        self.run_tool(
            [str(self.seed), "--project", str(output), str(first)],
            expected=1, env=environment,
        )
        self.assertEqual(output.read_bytes(), sentinel)

    @unittest.skipUnless(LINUX_X64, "execution requires Linux x86-64")
    def test_project_rejects_invalid_arity_and_empty_source_without_output(self):
        """Every project mode validates its full argv and inputs before output I/O."""
        valid = self.directory / "bounded_valid.sotlas"
        valid.write_text("module gate; pub fn main_entry() -> u32 { return 42; }")
        empty = self.directory / "bounded_empty.sotlas"
        empty.write_bytes(b"")
        output = self.directory / "bounded_preserved"
        sentinel = b"preserve existing artifact on invalid project invocation"
        output.write_bytes(sentinel)
        environment = {"PATH": str(self.directory / "no-tools")}
        for mode in ("--project", "--project-object", "--project-compiler"):
            with self.subTest(mode=mode):
                self.run_tool([str(self.seed), mode, str(output)], expected=1, env=environment)
                self.run_tool([str(self.seed), mode, str(output), str(valid)],
                              expected=1, env=environment)
                self.run_tool([str(self.seed), mode, str(output), str(valid), str(empty)],
                              expected=3, env=environment)
                self.assertEqual(output.read_bytes(), sentinel)
        self.run_tool([str(self.seed), "--project", str(output)] + [str(valid)] * 65,
                      expected=1, env=environment)
        self.assertEqual(output.read_bytes(), sentinel)

    @unittest.skipUnless(LINUX_X64, "execution requires Linux x86-64")
    def test_resolved_mode_rejects_unknown_suffixes_before_output(self):
        """Every resolved option requires an exact terminator after the suffix."""
        first = self.directory / "resolved_arg_first.sotlas"
        second = self.directory / "resolved_arg_second.sotlas"
        first.write_text("module gate::first; fn source_fn() -> u32 { return 42; }")
        second.write_text(
            "module gate::second; pub fn main_entry() -> u32 { return source_fn(); }"
        )
        output = self.directory / "resolved_arg_preserve"
        sentinel = b"original output is never truncated on bad CLI spelling"
        output.write_bytes(sentinel)
        environment = {"PATH": str(self.directory / "no-tools")}
        for option in ("--project-resolv", "--project-resolve-other",
                       "--project-resolve-object-extra",
                       "--project-resolve-compiler-extra"):
            with self.subTest(option=option):
                self.run_tool([str(self.seed), option, str(output),
                               str(first), str(second)], expected=1, env=environment)
                self.assertEqual(output.read_bytes(), sentinel)

    @unittest.skipUnless(LINUX_X64, "execution requires Linux x86-64")
    def test_native_cli_legacy_paths_survive_resolved_dispatch(self):
        """Certified flat project/executable/object modes remain fully functional."""
        first = self.directory / "cli_math.sotlas"
        second = self.directory / "cli_app.sotlas"
        first.write_text("module gate::math; fn cli_answer() -> u32 { return 42; }")
        second.write_text(
            "module gate::app; pub fn main_entry() -> u32 { return cli_answer(); }"
        )
        env = {"PATH": str(self.directory / "no-tools")}
        exe = self.directory / "cli_legacy_exe"
        self.run_tool([str(self.seed), "--project", str(exe),
                       str(first), str(second)], env=env)
        self.run_tool([str(exe)], expected=42, env=env)
        obj = self.directory / "cli_legacy.o"
        self.run_tool([str(self.seed), "--project-object", str(obj),
                       str(first), str(second)], env=env)
        self.assertEqual(obj.read_bytes()[:4], b"\x7fELF")
        output = self.directory / "cli_preserved"
        output.write_bytes(b"keep artifact")
        self.run_tool([str(self.seed), "--project", str(output),
                       str(first), str(self.directory / "missing.sotlas")],
                      expected=2, env=env)
        self.assertEqual(output.read_bytes(), b"keep artifact")

    @unittest.skipUnless(LINUX_X64, "execution requires Linux x86-64")
    def test_resolved_project_topological_sort_and_exact_native_object(self):
        """Native resolver orders forward references and strips only real import tokens."""
        math = self.directory / "resolve_math.sotlas"
        bridge = self.directory / "resolve_bridge.sotlas"
        app = self.directory / "resolve_app.sotlas"
        math.write_text("module gate::math;\nfn base_answer() -> u32 { return 40; }\n")
        bridge.write_text(
            "module gate::bridge;\nimport gate::math::*;\n"
            "fn add_two() -> u32 { return base_answer() + 2; }\n"
        )
        app.write_text(
            "module gate::app;\nimport gate::bridge::*;\n"
            'pub fn main_entry() -> u32 { return add_two(); }\n'
        )
        environment = {"PATH": str(self.directory / "no-tools")}
        sources = [app, bridge, math]  # deliberately reversed dependencies
        executable = self.directory / "resolved_executable"
        self.run_tool([str(self.seed), "--project-resolve", str(executable),
                       *map(str, sources)], 180, env=environment)
        self.run_tool([str(executable)], expected=42, env=environment)
        native = self.directory / "resolved_native.o"
        hosted = self.directory / "resolved_hosted.o"
        merged = self.directory / "resolved_reference.sotlas"
        merged.write_bytes(b"".join(
            src.read_bytes().replace(b"import gate::math::*;", b"").replace(
                b"import gate::bridge::*;", b"") + b"\n"
            for src in (math, bridge, app)
        ))
        self.run_tool([str(self.seed), "--project-resolve-object", str(native),
                       *map(str, sources)], 180, env=environment)
        self.run_tool([str(self.producer), "--compile-obj", str(merged), str(hosted)], 180)
        self.assertEqual(native.read_bytes(), hosted.read_bytes())

    @unittest.skipUnless(LINUX_X64, "execution requires Linux x86-64")
    def test_resolved_project_rejects_broken_dependency_graph_without_writing(self):
        """Duplicate, missing, cyclic and unsupported imports are fail-closed."""
        output = self.directory / "resolved_preserved"
        sentinel = b"native dependency validation must not touch this file"
        output.write_bytes(sentinel)
        environment = {"PATH": str(self.directory / "no-tools")}
        a = self.directory / "resolve_graph_a.sotlas"
        b = self.directory / "resolve_graph_b.sotlas"
        cases = (
            ("missing", "module gate::a; import gate::absent::*; fn fa() -> u32 { return 1; }",
             "module gate::b; fn fb() -> u32 { return 2; }"),
            ("duplicate", "module gate::a; fn fa() -> u32 { return 1; }",
             "module gate::a; fn fb() -> u32 { return 2; }"),
            ("cycle", "module gate::a; import gate::b::*; fn fa() -> u32 { return 1; }",
             "module gate::b; import gate::a::*; fn fb() -> u32 { return 2; }"),
            ("self_import", "module gate::a; import gate::a::*; fn fa() -> u32 { return 1; }",
             "module gate::b; fn fb() -> u32 { return 2; }"),
            ("duplicate_import", "module gate::a; import gate::b::*; import gate::b::*; fn fa() -> u32 { return 1; }",
             "module gate::b; fn fb() -> u32 { return 2; }"),
            ("alias_unsupported", "module gate::a; import gate::b as weird; fn fa() -> u32 { return 1; }",
             "module gate::b; fn fb() -> u32 { return 2; }"),
        )
        for description, first, second in cases:
            with self.subTest(case=description):
                a.write_text(first)
                b.write_text(second)
                self.run_tool([str(self.seed), "--project-resolve", str(output),
                               str(a), str(b)], 120, expected=12, env=environment)
                self.assertEqual(output.read_bytes(), sentinel)

    @unittest.skipUnless(LINUX_X64, "execution requires Linux x86-64")
    def test_resolved_original_modules_rebuild_identical_native_compiler(self):
        """No host-side source merge is used by either native compiler generation."""
        module_root = ROOT / "bootstrap/sotlas/native_compiler"
        names = ("token", "ast", "lexer", "parser", "sema", "backend/target_ir",
                 "backend/lower_scalar", "backend/x86_64_scalar")
        sources = [module_root / (name + ".sotlas") for name in names]
        sources.append(ROOT / "bootstrap/sotlas/native_driver/linux.sotlas")
        environment = {"PATH": str(self.directory / "no-tools")}
        native_stage2 = self.directory / "resolved_stage2"
        native_stage3 = self.directory / "resolved_stage3"
        self.run_tool([str(self.seed), "--project-resolve-compiler",
                       str(native_stage2), *map(str, sources)], 600, env=environment)
        self.run_tool([str(native_stage2), "--project-resolve-compiler",
                       str(native_stage3), *map(str, sources)], 600, env=environment)
        self.assertEqual(native_stage2.read_bytes(), native_stage3.read_bytes())
        source = self.directory / "resolved_stage3_example.sotlas"
        source.write_text("module gate; pub fn main_entry() -> u32 { return 42; }")
        output = self.directory / "resolved_stage3_example"
        self.run_tool([str(native_stage3), str(source), str(output)], 120, env=environment)
        self.run_tool([str(output)], expected=42, env=environment)

    @unittest.skipUnless(LINUX_X64, "execution requires Linux x86-64")
    def test_invalid_input_does_not_truncate_existing_output(self):
        source = self.directory / "invalid.sotlas"
        source.write_text("module gate; pub fn main_entry() -> u32 { return 4294967296; }")
        output = self.directory / "preserved"
        output.write_bytes(b"preserve this artifact")
        self.run_tool([str(self.seed), str(source), str(output)], expected=6)
        self.assertEqual(output.read_bytes(), b"preserve this artifact")
        self.run_tool([str(self.seed)], expected=1)
        self.run_tool([str(self.seed), str(source), str(output), "--unknown"], expected=1)
        self.run_tool([str(self.seed), str(self.directory / "missing.sotlas"), str(output)], expected=2)
        source.write_text("module gate; import missing::*; pub fn main_entry() -> u32 { return 42; }")
        self.run_tool([str(self.seed), str(source), str(output)], expected=12)
        self.assertEqual(output.read_bytes(), b"preserve this artifact")

    @unittest.skipUnless(LINUX_X64, "execution requires Linux x86-64")
    def test_native_stage2_stage3_fixed_point_and_self_object_equivalence(self):
        merged = self.directory / "compiler_merged.sotlas"
        merged.write_bytes(merged_native_driver_source())
        environment = {"PATH": str(self.directory / "no-tools")}
        reference = self.directory / "reference.o"
        native = self.directory / "native.o"
        self.run_tool([str(self.producer), "--compile-obj", str(merged), str(reference)], 180)
        self.run_tool([str(self.seed), str(merged), str(native), "--object"], 600, env=environment)
        self.assertEqual(reference.read_bytes(), native.read_bytes())
        stage2, stage3 = self.directory / "stage2", self.directory / "stage3"
        self.run_tool([str(self.seed), str(merged), str(stage2), "--compiler"], 600, env=environment)
        self.run_tool([str(stage2), str(merged), str(stage3), "--compiler"], 600, env=environment)
        self.assertEqual(stage2.read_bytes(), stage3.read_bytes())
        print("Native Linux fixed point:", hashlib.sha256(stage2.read_bytes()).hexdigest())
        source = self.directory / "stage3_sample.sotlas"
        source.write_text("module gate; pub fn main_entry() -> u32 { return 42; }")
        binary = self.directory / "stage3_sample"
        self.run_tool([str(stage3), str(source), str(binary)], env=environment)
        self.run_tool([str(binary)], expected=42, env=environment)

    def test_binary_string_escape_payload_and_malformed_hex_rejection(self):
        import struct
        source = self.directory / "hex.sotlas"
        source.write_text(r'module gate; pub fn main_entry() -> u32 { let data: *const u8 = "\x00\x01\x7f\xFF\xab"; return 0; }')
        output = source.with_suffix(".o")
        self.run_tool([str(self.producer), "--compile-obj", str(source), str(output)])
        data = output.read_bytes()
        headers = struct.unpack_from("<Q", data, 40)[0]
        payloads = []
        for index in range(struct.unpack_from("<H", data, 60)[0]):
            header = headers + index * 64
            section_type = struct.unpack_from("<I", data, header + 4)[0]
            flags = struct.unpack_from("<Q", data, header + 8)[0]
            if section_type == 1 and flags == 2:
                start, length = struct.unpack_from("<QQ", data, header + 24)
                payloads.append(data[start:start + length])
        self.assertIn(b"\x00\x01\x7f\xff\xab\x00", payloads)
        for literal in (r'"\xQ0"', r'"\x4"'):
            bad = self.directory / ("bad_hex_" + str(len(literal)) + ".sotlas")
            bad.write_text("module gate; pub fn main_entry() -> u32 { let data: *const u8 = " + literal + "; return 0; }")
            result = self.run_tool([str(self.producer), "--compile-obj", str(bad), str(bad.with_suffix('.o'))], expected=10)
            self.assertFalse(bad.with_suffix('.o').exists(), result.stderr)

    def test_malformed_kernel_adapter_and_process_entry_signatures_fail(self):
        for name, body in (
            ("syscall", "@extern(C) fn sotlas_linux_write(fd: u64, data: u64, n: u64) -> i64; "
             "pub fn main_entry() -> u32 { let r: i64 = sotlas_linux_write(1, 0, 0); return r as u32; }"),
            ("entry", "pub fn sotlas_linux_main(argc: u32) -> u32 { return argc; }"),
        ):
            with self.subTest(name=name):
                source = self.directory / (name + ".sotlas")
                output = source.with_suffix(".o")
                source.write_text("module gate; " + body)
                self.run_tool([str(self.producer), "--compile-obj", str(source), str(output)], expected=10)
                self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
