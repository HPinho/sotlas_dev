from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_package(name: str, directory: Path):
    spec = importlib.util.spec_from_file_location(
        name,
        directory / "__init__.py",
        submodule_search_locations=[str(directory)],
    )
    assert spec is not None and spec.loader is not None
    package = importlib.util.module_from_spec(spec)
    sys.modules[name] = package
    spec.loader.exec_module(package)
    return package


compiler = _load_package(
    "sotlas_contract_frontend_compiler_package",
    ROOT / "compiler" / "sotlas_compile",
)
tools = _load_package(
    "sotlas_contract_frontend_tools_package",
    ROOT / "tools" / "sotlas_compile",
)


class SotlasRequiresContractTests(unittest.TestCase):
    def _source(self, call: str) -> str:
        return f"""
module test::contracts;
fn divide_by(b: i32) -> i32
    requires b != 0
{{
    return 84i32 / b;
}}
fn entry() -> i32 {{ return divide_by({call}); }}
"""

    def test_constant_call_proves_private_function_precondition(self):
        for package in (compiler, tools):
            module = package.bootstrap.parse(self._source("7"))
            package.bootstrap.check(module)
            self.assertEqual(len(module.contract_proofs), 1)
            proof = module.contract_proofs[0]
            self.assertEqual(proof.function, "divide_by")
            self.assertEqual(proof.predicate, "(b != 0)")
            self.assertEqual(proof.arguments, (("b", 7),))

    def test_false_precondition_fails_closed(self):
        for package in (compiler, tools):
            module = package.bootstrap.parse(self._source("0"))
            with self.assertRaisesRegex(
                package.SotlasBootstrapError,
                "requires contract for call to 'divide_by' is not satisfied",
            ):
                package.bootstrap.check(module)

    def test_dynamic_argument_is_guarded_at_runtime(self):
        source = self._source("value").replace(
            "fn entry() -> i32", "fn entry(value: i32) -> i32"
        )
        for package in (compiler, tools):
            module = package.bootstrap.parse(source)
            package.bootstrap.check(module)
            self.assertEqual(module.contract_proofs, ())
            self.assertEqual(
                module.contract_preconditions[0].predicate, "(b != 0)"
            )
            generated = package.bootstrap.emit_c(module)
            self.assertIn("#include <stdlib.h>", generated)
            self.assertIn("if (!((b != 0))) abort();", generated)
        checked = compiler.analyze_source_phase1(source)
        checked_sir, _ = compiler.build_canonical_checked_ownership_sir(checked)
        self.assertEqual(checked_sir.module.contract_proofs, ())
        self.assertIn("sir_requires @divide_by", checked_sir.module.dump())

    def test_branch_refinement_proves_dynamic_preconditions(self):
        source = """
module test::contract_refinement;
fn divide_by(b: i32) -> i32
    requires b != 0
{
    return 84i32 / b;
}
fn entry(value: i32, enabled: bool) -> i32 {
    if value != 0 && enabled {
        return divide_by(value);
    }
    if value == 0 {
        return 0;
    } else {
        return divide_by(value);
    }
}
"""
        for package in (compiler, tools):
            module = package.bootstrap.parse(source)
            package.bootstrap.check(module)
            self.assertEqual(len(module.contract_proofs), 2)
            self.assertEqual(
                [proof.refinements for proof in module.contract_proofs],
                [("(value != 0)",), ("(value != 0)",)],
            )
            self.assertEqual(module.contract_preconditions[0].function, "divide_by")
        checked = compiler.analyze_source_phase1(source)
        checked_sir, _ = compiler.build_canonical_checked_ownership_sir(checked)
        dump = checked_sir.module.dump()
        self.assertEqual(dump.count("sir_proof call @divide_by"), 2)
        self.assertEqual(dump.count("refinements=[(value != 0)]"), 2)

    def test_assignment_invalidates_a_branch_refinement(self):
        source = """
module test::contract_refinement_invalidation;
fn divide_by(b: i32) -> i32
    requires b != 0
{
    return 84i32 / b;
}
fn entry(value: i32) -> i32 {
    let mut copy: i32 = value;
    if copy != 0 {
        copy = 0;
        return divide_by(copy);
    }
    return 0;
}
"""
        for package in (compiler, tools):
            module = package.bootstrap.parse(source)
            package.bootstrap.check(module)
            self.assertEqual(module.contract_proofs, ())
            self.assertEqual(len(module.contract_preconditions), 1)

    def test_complex_call_argument_keeps_the_runtime_guard(self):
        source = """
module test::contract_complex_argument;
fn divide_by(b: i32) -> i32
    requires b != 0
{
    return 84i32 / b;
}
fn dynamic_value() -> i32 { return 2; }
fn entry(value: i32) -> i32 {
    if value != 0 {
        return divide_by(dynamic_value());
    }
    return 0;
}
"""
        for package in (compiler, tools):
            module = package.bootstrap.parse(source)
            package.bootstrap.check(module)
            self.assertEqual(module.contract_proofs, ())
            self.assertIn("if (!((b != 0))) abort();", package.bootstrap.emit_c(module))

    def test_requires_must_be_boolean(self):
        source = """
module test::contracts;
fn positive(value: i32) -> i32
    requires value
{
    return value;
}
"""
        for package in (compiler, tools):
            module = package.bootstrap.parse(source)
            with self.assertRaisesRegex(
                package.SotlasBootstrapError,
                "requires expression must have type bool",
            ):
                package.bootstrap.check(module)

    def test_requires_rejects_runtime_undefined_division_in_predicate(self):
        source = """
module test::contracts;
fn ratio(value: i32, divisor: i32) -> bool
    requires value / divisor != 1
{
    return true;
}
"""
        for package in (compiler, tools):
            module = package.bootstrap.parse(source)
            with self.assertRaisesRegex(
                package.SotlasBootstrapError,
                "supports only compatible comparisons and boolean operators",
            ):
                package.bootstrap.check(module)

    def test_public_function_enforces_precondition_at_runtime(self):
        source = """
module test::contracts;
pub fn positive(value: i32) -> i32
    requires value > 0
{
    return value;
}
"""
        for package in (compiler, tools):
            module = package.bootstrap.parse(source)
            package.bootstrap.check(module)
            self.assertIn("abort();", package.bootstrap.emit_c(module))

    def test_c11_runtime_guard_rejects_external_contract_violation(self):
        cc = shutil.which("cc") or shutil.which("clang") or shutil.which("gcc")
        if cc is None:
            self.skipTest("C11 compiler is unavailable")
        source = """
module test::contract_runtime;
pub fn divide_by(b: i32) -> i32
    requires b != 0
{
    return 84i32 / b;
}
"""
        generated = compiler.bootstrap.compile_source(source)
        with tempfile.TemporaryDirectory(prefix="sotlas_contract_") as temp:
            c_path = Path(temp) / "contract.c"
            exe_path = Path(temp) / "contract"
            c_path.write_text(
                generated + "\nint main(void) { return divide_by(0); }\n",
                encoding="utf-8",
            )
            compiled = subprocess.run(
                [cc, "-std=c11", str(c_path), "-o", str(exe_path)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            executed = subprocess.run(
                [str(exe_path)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(executed.returncode, 0)

    def test_verified_call_proof_is_preserved_in_canonical_sir(self):
        checked = compiler.analyze_source_phase1(self._source("7"))
        checked_sir, _ = compiler.build_canonical_checked_ownership_sir(checked)
        self.assertEqual(len(checked_sir.module.contract_proofs), 1)
        proof = checked_sir.module.contract_proofs[0]
        self.assertEqual(proof.function, "divide_by")
        self.assertEqual(proof.arguments, (("b", 7),))
        self.assertIn("sir_proof call @divide_by", checked_sir.module.dump())
        self.assertEqual(
            checked_sir.module.contract_preconditions[0].predicate,
            "(b != 0)",
        )
        self.assertIn("sir_requires @divide_by", checked_sir.module.dump())


if __name__ == "__main__":
    unittest.main()
