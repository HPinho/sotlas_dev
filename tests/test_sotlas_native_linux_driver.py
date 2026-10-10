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
    def test_cross_builds_complete_darwin_compiler_without_host_tools(self):
        root = self.directory / "darwin-source-tree"
        namespace = root / "sotlas/compiler"
        core = ROOT / "bootstrap/sotlas/native_compiler"
        names = ("token", "ast", "lexer", "parser", "sema", "backend/target_ir", "backend/lower_scalar", "backend/x86_64_scalar")
        for name in names:
            destination = namespace / (name + ".sotlas")
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes((core / (name + ".sotlas")).read_bytes())
        entry = namespace / "darwin_driver.sotlas"
        entry.write_bytes((ROOT / "bootstrap/sotlas/native_driver/darwin.sotlas").read_bytes())
        actual = self.directory / "darwin-compiler"
        obj = actual.with_suffix(".o")
        reference = self.directory / "darwin-reference"
        # The hosted oracle's fallback search mixes repository and copied
        # roots. Compile the identical original sources for this reference;
        # the native compiler must resolve the independent namespace tree.
        original = ROOT / "bootstrap/sotlas/native_driver/darwin.sotlas"
        self.run_tool([str(self.producer), "--compile-obj", str(original), str(obj)], timeout=180)
        self.run_tool([str(self.producer), "--link-macho", str(obj), str(reference), "sotlas_darwin_main"])
        environment = {"PATH": str(self.directory / "no-tools")}
        self.run_tool([str(self.seed), "--build-mac-cc", str(actual), str(root), str(entry)], env=environment, timeout=180)
        self.assertEqual(actual.read_bytes(), reference.read_bytes())
        self.assertEqual(actual.read_bytes()[:4], b"\xcf\xfa\xed\xfe")
        self.run_tool([str(self.seed), "--build-mac-cc-extra", str(actual), str(root), str(entry)], expected=1, env=environment)
        self.assertEqual(actual.read_bytes(), reference.read_bytes())

    @unittest.skipUnless(LINUX_X64, "execution requires Linux x86-64")
    def test_cross_compiles_macho_without_host_tools(self):
        source = self.directory / "mac_sample.sotlas"
        source.write_text("module gate; fn twice(x:u32)->u32{return x*2;} pub fn main_entry()->u32{return twice(21);}")
        obj = source.with_suffix(".o")
        expected = self.directory / "mac_reference"
        actual = self.directory / "mac_actual"
        self.run_tool([str(self.producer), "--compile-obj", str(source), str(obj)])
        self.run_tool([str(self.producer), "--link-macho", str(obj), str(expected), "main_entry"])
        environment = {"PATH": str(self.directory / "no-tools")}
        self.run_tool([str(self.seed), "--build-mac", str(actual), str(self.directory), str(source)], env=environment)
        self.assertEqual(actual.read_bytes(), expected.read_bytes())
        self.assertEqual(actual.read_bytes()[:4], b"\xcf\xfa\xed\xfe")
        source.write_text("module gate; @extern(C) fn sotlas_darwin_close(fd:u64)->i64; @system pub fn main_entry()->u32{let n:i64=sotlas_darwin_close(18446744073709551615);if n<0{return 42;}return 1;}")
        self.run_tool([str(self.producer), "--compile-obj", str(source), str(obj)])
        self.run_tool([str(self.producer), "--link-macho", str(obj), str(expected), "main_entry"])
        self.run_tool([str(self.seed), "--build-mac", str(actual), str(self.directory), str(source)], env=environment)
        self.assertEqual(actual.read_bytes(), expected.read_bytes())
        source.write_text("module gate; @extern(C) fn sotlas_linux_close(fd:u64)->i64; @system pub fn main_entry()->u32{return sotlas_linux_close(0) as u32;}")
        previous = actual.read_bytes()
        self.run_tool([str(self.seed), "--build-mac", str(actual), str(self.directory), str(source)], expected=9, env=environment)
        self.assertEqual(actual.read_bytes(), previous)

    @unittest.skipUnless(LINUX_X64, "execution requires Linux x86-64")
    def test_cross_compiles_windows_pe_without_host_tools(self):
        source = self.directory / "windows_sample.sotlas"
        source.write_text("module gate; fn twice(x:u32)->u32{return x*2;} pub fn main_entry()->u32{return twice(21);}")
        obj = self.directory / "windows_sample.o"
        expected = self.directory / "windows_reference.exe"
        actual = self.directory / "windows_actual.exe"
        self.run_tool([str(self.producer), "--compile-obj", str(source), str(obj)])
        self.run_tool([str(self.producer), "--link-pe", str(obj), str(expected), "main_entry"])
        environment = {"PATH": str(self.directory / "no-tools")}
        self.run_tool([str(self.seed), str(source), str(actual), "--windows"], env=environment)
        self.assertEqual(actual.read_bytes(), expected.read_bytes())
        self.assertEqual(actual.read_bytes()[:2], b"MZ")
        self.run_tool([str(self.seed), "--build-win", str(actual), str(self.directory), str(source)], env=environment)
        self.assertEqual(actual.read_bytes(), expected.read_bytes())
        source.write_text("module gate; @extern(C) fn sotlas_linux_close(fd:u64)->i64; @system pub fn main_entry()->u32{return sotlas_linux_close(0) as u32;}")
        previous = actual.read_bytes()
        self.run_tool([str(self.seed), str(source), str(actual), "--windows"], expected=9, env=environment)
        self.assertEqual(actual.read_bytes(), previous)

    @unittest.skipUnless(LINUX_X64, "execution requires Linux x86-64")
    def test_native_check_matches_object_validation_without_files(self):
        environment = {"PATH": str(self.directory / "no-tools")}
        source = self.directory / "check_input.sotlas"
        output = self.directory / "check_reference.o"
        sentinel = b"object output must be preserved by a failed check"
        cases = (
            ("module gate; fn square(x: u32) -> u32 { return x * x; }", 0),
            ("module gate; pub fn broken(", 5),
            ("module gate; import absent::*; fn value() -> u32 { return 42; }", 12),
            ("module gate; fn value() -> u32 { return missing(); }", 6),
            ("module gate; pub struct Oversized { pub data: [u8; 257]; } fn value() -> u32 { return 42; }", 7),
        )
        for body, code in cases:
            with self.subTest(code=code):
                source.write_text(body)
                output.write_bytes(sentinel)
                before = {path.name: path.read_bytes() for path in self.directory.iterdir() if path.is_file()}
                result = self.run_tool([str(self.seed), "--check", str(source)], expected=code, env=environment)
                self.assertEqual(result.stdout, b"")
                after = {path.name: path.read_bytes() for path in self.directory.iterdir() if path.is_file()}
                self.assertEqual(before, after)
                self.run_tool([str(self.seed), str(source), str(output), "--object"], expected=code, env=environment)
        self.run_tool([str(self.seed), "--check", str(self.directory / "absent.sotlas")], expected=2)
        source.write_bytes(b"")
        self.run_tool([str(self.seed), "--check", str(source)], expected=3)
        for arguments in (("--check",), ("--check", str(source), str(output))):
            self.run_tool([str(self.seed), *arguments], expected=1)

    @unittest.skipUnless(LINUX_X64, "execution requires Linux x86-64")
    def test_native_check_build_discovers_dependencies_without_artifacts(self):
        root = self.directory / "check_tree"
        namespace = root / "gate"
        namespace.mkdir(parents=True)
        leaf = namespace / "math.sotlas"
        entry = namespace / "app.sotlas"
        leaf.write_text("module gate::math; fn square(x: u32) -> u32 { return x * x; }")
        entry.write_text("module gate::app; import gate::math::*; fn value() -> u32 { return square(7); }")
        before = {str(path.relative_to(root)): path.read_bytes() for path in root.rglob("*") if path.is_file()}
        environment = {"PATH": str(self.directory / "no-tools")}
        self.run_tool([str(self.seed), "--check-build", str(root), str(entry)], env=environment)
        after = {str(path.relative_to(root)): path.read_bytes() for path in root.rglob("*") if path.is_file()}
        self.assertEqual(before, after)
        leaf.write_text("module gate::math; import gate::app::*; fn square(x: u32) -> u32 { return x * x; }")
        self.run_tool([str(self.seed), "--check-build", str(root), str(entry)], expected=12, env=environment)
        self.run_tool([str(self.seed), "--check-build", str(root)], expected=1, env=environment)
        self.run_tool([str(self.seed), "--check-build", str(root), str(entry), "unexpected"], expected=1, env=environment)

    @unittest.skipUnless(LINUX_X64, "execution requires Linux x86-64")
    def test_native_string_symbols_beyond_256_execute_and_overflow_preserves_output(self):
        functions = []
        for group in range(8):
            bindings = "\n".join(
                f'let p{index}: *const u8 = "v{group * 64 + index:03d}";'
                for index in range(64)
            )
            functions.append(f"fn group{group}() -> u32 {{ {bindings} "
                             "return unsafe { *(p63 + 1) } as u32; }")
        body = "module gate;\n" + "\n".join(functions)
        body += "\npub fn main_entry() -> u32 { return group7(); }"
        source = self.directory / "all_string_symbols.sotlas"
        source.write_text(body)
        output = self.directory / "all_string_symbols"
        environment = {"PATH": str(self.directory / "no-tools")}
        self.run_tool([str(self.seed), str(source), str(output)], env=environment)
        self.run_tool([str(output)], expected=ord("5"), env=environment)
        previous = output.read_bytes()
        source.write_text(body.replace("return group7();",
                                      'let extra: *const u8 = "overflow"; return group7();'))
        self.run_tool([str(self.seed), str(source), str(output)], expected=7, env=environment)
        self.assertEqual(output.read_bytes(), previous)

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
    def test_discovers_module_files_from_entry_and_root(self):
        root = self.directory / "discovered"
        (root / "gate").mkdir(parents=True)
        dependency = root / "gate/math.sotlas"
        bridge = root / "gate/bridge.sotlas"
        entry = root / "gate/app.sotlas"
        dependency.write_text("module gate::math; fn base() -> u32 { return 40; }")
        bridge.write_text("module gate::bridge; import gate::math::*; fn add() -> u32 { return base() + 2; }")
        entry.write_text("module gate::app; import gate::bridge::*; pub fn main_entry() -> u32 { return add(); }")
        environment = {"PATH": str(self.directory / "no-tools")}
        executable = self.directory / "discovered_app"
        self.run_tool([str(self.seed), "--build", str(executable), str(root), str(entry)], 180, env=environment)
        self.run_tool([str(executable)], expected=42, env=environment)
        discovered = self.directory / "discovered.o"
        explicit = self.directory / "explicit.o"
        self.run_tool([str(self.seed), "--build-obj", str(discovered), str(root), str(entry)], 180, env=environment)
        self.run_tool([str(self.seed), "--project-resolve-object", str(explicit), str(entry), str(bridge), str(dependency)], 180, env=environment)
        self.assertEqual(discovered.read_bytes(), explicit.read_bytes())
        preserved = self.directory / "discovery_preserved"
        preserved.write_bytes(b"keep output")
        dependency.unlink()
        self.run_tool([str(self.seed), "--build", str(preserved), str(root), str(entry)], expected=2, env=environment)
        self.assertEqual(preserved.read_bytes(), b"keep output")
        dependency.write_text("module gate::math; import gate::app::*; fn base() -> u32 { return 40; }")
        self.run_tool([str(self.seed), "--build", str(preserved), str(root), str(entry)], expected=12, env=environment)
        self.assertEqual(preserved.read_bytes(), b"keep output")

    def test_native_bundle_reproducibility_and_static_seed_contract(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("native_packager", ROOT / "packaging/native_linux.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        first = self.directory / "bundle_a/native"
        second = self.directory / "bundle_b/native"
        archive_a = module.assemble(self.seed, first, "1.0.0rc1")
        archive_b = module.assemble(self.seed, second, "1.0.0rc1")
        self.assertEqual(archive_a.read_bytes(), archive_b.read_bytes())
        self.assertEqual((first / "bin/sotlas-native").read_bytes(), self.seed.read_bytes())
        self.assertFalse(list(first.rglob("*.py")))
        fake = self.directory / "invalid_seed"
        fake.write_bytes(b"not an ELF compiler")
        with self.assertRaises(ValueError):
            module.assemble(fake, self.directory / "bad_bundle", "1.0.0rc1")

    @unittest.skipUnless(LINUX_X64, "execution requires Linux x86-64")
    def test_installs_native_bundle_without_host_language_tools(self):
        import importlib.util
        import shutil
        spec = importlib.util.spec_from_file_location("native_packager", ROOT / "packaging/native_linux.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        bundle = self.directory / "install_bundle"
        module.assemble(self.seed, bundle, "1.0.0rc1")
        utilities = self.directory / "system_utilities"
        utilities.mkdir()
        for name in ("uname", "find", "sha256sum", "cut", "grep", "mkdir", "cp", "chmod"):
            (utilities / name).symlink_to(shutil.which(name))
        environment = {"PATH": str(utilities)}
        installed = self.directory / "installed_native"
        self.run_tool(["/bin/bash", str(bundle / "install-native.sh"), str(bundle), str(installed)], env=environment)
        source = self.directory / "installed_sample.sotlas"
        source.write_text("module gate; pub fn main_entry() -> u32 { return 42; }")
        output = self.directory / "installed_sample"
        self.run_tool([str(installed / "bin/sotlas-native"), str(source), str(output)], env={"PATH": str(self.directory / "no-tools")})
        self.run_tool([str(output)], expected=42, env={"PATH": str(self.directory / "no-tools")})
        (bundle / "bin/sotlas-native").write_bytes(b"tampered compiler")
        rejected = self.directory / "rejected_install"
        result = subprocess.run(["/bin/bash", str(bundle / "install-native.sh"), str(bundle), str(rejected)], env=environment, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(rejected.exists())

    @unittest.skipUnless(LINUX_X64, "execution requires Linux x86-64")
    def test_resolved_project_accepts_contextual_keyword_segments(self):
        """Keywords remain namespace identifiers; comments and strings are not imports."""
        dependency = self.directory / "keyword_dependency.sotlas"
        entry = self.directory / "keyword_entry.sotlas"
        dependency.write_text(
            "module system::gate;\n"
            "// import missing::comment::*;\n"
            'fn keyword_answer() -> u32 { let text: *const u8 = "import missing::string::*;"; return 42; }\n',
            encoding="utf-8",
        )
        entry.write_text(
            "module gate::system;\nimport system::gate::*;\n"
            "pub fn main_entry() -> u32 { return keyword_answer(); }\n",
            encoding="utf-8",
        )
        output = self.directory / "keyword_project"
        environment = {"PATH": str(self.directory / "no-tools")}
        self.run_tool([str(self.seed), "--project-resolve", str(output),
                       str(entry), str(dependency)], 180, env=environment)
        self.run_tool([str(output)], expected=42, env=environment)
        dependency.write_text("module system::42; fn keyword_answer() -> u32 { return 42; }")
        output.write_bytes(b"preserve invalid-path output")
        self.run_tool([str(self.seed), "--project-resolve", str(output),
                       str(entry), str(dependency)], expected=12, env=environment)
        self.assertEqual(output.read_bytes(), b"preserve invalid-path output")

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
        self.run_tool([str(native_stage3), "--check", str(source)], env=environment)
        self.run_tool([str(native_stage3), "--check-build", str(self.directory), str(source)], env=environment)
        windows = self.directory / "resolved_stage3_windows.exe"
        self.run_tool([str(native_stage3), str(source), str(windows), "--windows"], env=environment)
        reference_obj = self.directory / "resolved_stage3_windows.o"
        reference_pe = self.directory / "resolved_stage3_windows_reference.exe"
        self.run_tool([str(self.producer), "--compile-obj", str(source), str(reference_obj)])
        self.run_tool([str(self.producer), "--link-pe", str(reference_obj), str(reference_pe), "main_entry"])
        self.assertEqual(windows.read_bytes(), reference_pe.read_bytes())
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
