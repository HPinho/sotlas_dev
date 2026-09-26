"""Phase 4: production frontend syntax bridge for State Spaces."""
from __future__ import annotations

import unittest
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import importlib
import importlib.util
import sys

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"


def _load_canonical_package():
    name = "sotlas_state_phase1_public_package"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(
        name,
        PACKAGE_DIR / "__init__.py",
        submodule_search_locations=[str(PACKAGE_DIR)],
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


sotlas_compile = _load_canonical_package()
bootstrap = sotlas_compile.bootstrap
StateSpaceFrontendError = importlib.import_module(
    f"{sotlas_compile.__name__}.state_frontend"
).StateSpaceFrontendError


class SotlasStateFrontendTests(unittest.TestCase):
    def _source(self, signature: str = "pub fn configure(dev: Device<Discovered>) -> Device<Configured> { unsafe { return transition(move(dev), Configured); } }") -> str:
        return f"""
        module test::state_frontend;

        sole struct Device {{ id: u32; }}

        pub space Device {{
            state Discovered
            state Configured
            state Running

            Discovered -> Configured
            Configured -> Running
        }}

        {signature}
        """

    def test_production_parser_preserves_public_space_ast(self):
        module = bootstrap.parse(self._source(), filename="<state-space-parser>")
        self.assertEqual(len(module.state_spaces), 1)
        decl = module.state_spaces[0]
        self.assertTrue(decl.public)
        self.assertEqual(decl.name, "Device")
        self.assertEqual(
            tuple(state.name for state in decl.states),
            ("Discovered", "Configured", "Running"),
        )
        self.assertEqual(
            tuple((edge.source, edge.target) for edge in decl.transitions),
            (("Discovered", "Configured"), ("Configured", "Running")),
        )

    def test_state_payload_contracts_are_preserved_from_source(self):
        source = """
        module test::payloads;
        space Download {
            state idle
            state downloading(progress: Percent)
            state completed(File)
            idle -> downloading
            downloading -> completed
        }
        """
        module = bootstrap.parse(source, filename="<state-payloads>")
        decl = module.state_spaces[0]
        downloading = decl.states[1]
        completed = decl.states[2]
        self.assertEqual(
            (downloading.payload[0].name, downloading.payload[0].type_name),
            ("progress", "Percent"),
        )
        self.assertIsNone(completed.payload[0].name)
        self.assertEqual(completed.payload[0].type_name, "File")

    def test_explicit_initial_state_is_preserved_in_frontend_plan(self):
        source = self._source().replace(
            "state Discovered", "initial state Discovered"
        )
        module = bootstrap.parse(source, filename="<state-initial>")
        self.assertEqual(module.state_spaces[0].initial_state, "Discovered")
        plan = bootstrap.plan_state_space_frontend(module)
        self.assertEqual(plan.space("Device").initial_state, "Discovered")

    def test_fresh_struct_can_only_receive_explicit_initial_typestate(self):
        valid = self._source(
            "fn make() -> Device<Discovered> { "
            "let dev: Device<Discovered> = Device { id: 37u32 }; "
            "return move(dev); }"
        ).replace("state Discovered", "initial state Discovered")
        module = bootstrap.parse(valid, filename="<state-initial-valid>")
        module._state_phase1_internal = True
        bootstrap.check(module)

        invalid = valid.replace(
            "Device<Discovered> = Device", "Device<Configured> = Device"
        )
        invalid_module = bootstrap.parse(
            invalid, filename="<state-initial-invalid>"
        )
        invalid_module._state_phase1_internal = True
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            "can only begin in initial state Discovered",
        ):
            bootstrap.check(invalid_module)

    def test_typestate_construction_requires_declared_initial_state(self):
        source = self._source(
            "fn make() -> Device<Discovered> { "
            "let dev: Device<Discovered> = Device { id: 37u32 }; "
            "return move(dev); }"
        )
        module = bootstrap.parse(source, filename="<state-no-initial>")
        module._state_phase1_internal = True
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            "has no declared initial state",
        ):
            bootstrap.check(module)

    def test_frontend_plan_reuses_canonical_state_graph_and_typestate(self):
        module = bootstrap.parse(self._source(), filename="<state-plan>")
        plan = bootstrap.plan_state_space_frontend(module)
        space = plan.space("Device")
        self.assertTrue(space.allows("Discovered", "Configured"))
        self.assertFalse(space.allows("Discovered", "Running"))
        self.assertEqual(
            tuple(item.display() for item in plan.qualified_types),
            ("Device<Discovered>", "Device<Configured>"),
        )

    def test_public_coverage_api_uses_frontend_certified_space(self):
        module = bootstrap.parse(self._source(), filename="<state-coverage-api>")
        space = bootstrap.plan_state_space_frontend(module).space("Device")
        complete = sotlas_compile.require_exhaustive_state_space_coverage(
            space, ("Discovered", "Configured", "Running")
        )
        self.assertTrue(complete.complete)
        self.assertEqual(complete.coverage_text(), "3/3")
        partial = sotlas_compile.analyze_state_space_coverage(
            space, ("Configured",)
        )
        self.assertEqual(partial.missing_states, ("Discovered", "Running"))

    def test_public_typestate_syntax_is_preserved_in_function_signature(self):
        module = bootstrap.parse(self._source(), filename="<state-signature>")
        function = module.functions[0]
        self.assertEqual(function.params[0][1].name, "Device")
        self.assertEqual(function.params[0][1].display(), "Device<Discovered>")
        self.assertEqual(function.result.name, "Device")
        self.assertEqual(function.result.display(), "Device<Configured>")

    def test_generic_syntax_remains_ordinary_when_no_same_named_space_exists(self):
        source = """
        module test::generic_compat;
        struct Box<T> { value: u32; }
        pub fn id(value: Box<u32>) -> Box<u32> { return value; }
        """
        module = bootstrap.parse(source, filename="<generic-compat>")
        self.assertFalse(getattr(module, "state_spaces", ()))
        self.assertEqual(module.functions[0].params[0][1].name, "Box")

    def test_unknown_state_is_rejected_by_canonical_frontend_plan(self):
        module = bootstrap.parse(
            self._source(
                "pub fn start(dev: Device<Missing>) -> void { return; }"
            ),
            filename="<unknown-state>",
        )
        with self.assertRaisesRegex(
            StateSpaceFrontendError,
            r"Device<Missing> references unknown state",
        ):
            bootstrap.plan_state_space_frontend(module)

    def test_duplicate_state_is_rejected_by_canonical_frontend_plan(self):
        source = """
        module test::duplicate_state;
        space Device {
            state Ready
            state Ready
        }
        """
        module = bootstrap.parse(source, filename="<duplicate-state>")
        with self.assertRaisesRegex(
            StateSpaceFrontendError,
            r"repeats state 'Ready'",
        ):
            bootstrap.plan_state_space_frontend(module)

    def test_unknown_transition_target_is_rejected(self):
        source = """
        module test::unknown_target;
        space Device {
            state Ready
            Ready -> Missing
        }
        """
        module = bootstrap.parse(source, filename="<unknown-target>")
        with self.assertRaisesRegex(
            StateSpaceFrontendError,
            r"unknown target 'Missing'",
        ):
            bootstrap.plan_state_space_frontend(module)

    def test_duplicate_space_name_is_rejected(self):
        source = """
        module test::duplicate_space;
        space Device { state A }
        space Device { state B }
        """
        module = bootstrap.parse(source, filename="<duplicate-space>")
        with self.assertRaisesRegex(
            StateSpaceFrontendError,
            r"declared more than once",
        ):
            bootstrap.plan_state_space_frontend(module)

    def test_indirect_typestate_shape_remains_fail_closed_for_v1(self):
        source = """
        module test::indirect_state;
        space Device { state Ready }
        pub fn inspect(dev: &Device<Ready>) -> void { return; }
        """
        module = bootstrap.parse(source, filename="<indirect-state>")
        with self.assertRaisesRegex(
            StateSpaceFrontendError,
            r"currently requires a direct by-value type",
        ):
            bootstrap.plan_state_space_frontend(module)

    def test_production_check_accepts_supported_state_subset(self):
        module = bootstrap.parse(self._source(), filename="<state-check>")
        bootstrap.check(module)
        self.assertTrue(bootstrap.plan_state_space_frontend(module).spaces)
        self.assertIsNotNone(module.state_space_typed_snapshot)

    def test_c_emission_lowers_state_qualified_types_to_nominal_c_type(self):
        module = bootstrap.parse(self._source(
            "pub fn configure(dev: Device<Discovered>) -> Device<Configured> "
            "{ unsafe { return transition(move(dev), Configured); } }"
        ), filename="<state-c>")
        generated = bootstrap.emit_c(module)
        self.assertIn("Device configure", generated)

    def test_production_discern_requires_complete_state_coverage(self):
        source = self._source(
            "pub fn inspect(dev: Device<Discovered>) -> u32 { "
            "discern dev { Discovered => { return 1u32; } "
            "Configured => { return 2u32; } "
            "Running => { return 3u32; } } }"
        )
        module = bootstrap.parse(source, filename="<state-discern>")
        bootstrap.check(module)
        generated = bootstrap.emit_c(module)
        # The C11 representation erases typestate, so lowering selects the
        # sole branch proven reachable by the binding's static state.
        self.assertIn("return ((uint32_t)(1))", generated)
        self.assertNotIn("((uint32_t)(2))", generated)
        self.assertNotIn("((uint32_t)(3))", generated)

    def test_production_discern_rejects_missing_and_duplicate_states(self):
        missing = self._source(
            "fn inspect(dev: Device<Discovered>) -> u32 { "
            "discern dev { Discovered => { return 1u32; } } }"
        )
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError, "missing: Configured, Running"
        ):
            bootstrap.compile_source(missing, filename="<state-discern-missing>")

        duplicate = self._source(
            "fn inspect(dev: Device<Discovered>) -> u32 { "
            "discern dev { Discovered => { return 1u32; } "
            "Discovered => { return 2u32; } "
            "Configured => { return 3u32; } "
            "Running => { return 4u32; } } }"
        )
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError, "repeats state 'Discovered'"
        ):
            bootstrap.compile_source(duplicate, filename="<state-discern-duplicate>")

    def test_discern_state_branch_executes_natively(self):
        compiler = shutil.which("gcc") or shutil.which("clang")
        if compiler is None:
            self.skipTest("host C compiler not available")
        source = self._source(
            "pub fn inspect(dev: Device<Discovered>) -> i32 { "
            "discern dev { Discovered => { return 41; } "
            "Configured => { return 42; } "
            "Running => { return 43; } } }"
        ) + "\nfn main() -> i32 { let dev: Device<Discovered> = Device { id: 0u32 }; " \
            "return inspect(dev); }\n"
        generated = bootstrap.compile_source(source, filename="<state-discern-native>")
        with tempfile.TemporaryDirectory(prefix="sotlas-state-discern-") as temp_dir:
            c_file = Path(temp_dir) / "state_discern.c"
            executable = Path(temp_dir) / "state_discern"
            c_file.write_text(generated, encoding="utf-8")
            compiled = subprocess.run(
                [compiler, "-std=c11", "-Wall", "-Wextra", "-Werror",
                 str(c_file), "-o", str(executable)],
                capture_output=True, text=True,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            executed = subprocess.run(
                [str(executable)], capture_output=True, text=True
            )
            self.assertEqual(executed.returncode, 41, executed.stderr)

    def test_payload_state_spaces_remain_fail_closed_in_production(self):
        source = self._source().replace(
            "state Configured", "state Configured(Error)"
        )
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            "payload lowering remains PREVIEW",
        ):
            bootstrap.compile_source(source, filename="<state-payload>")

    def test_state_transition_runs_through_native_c_backend(self):
        compiler = shutil.which("gcc") or shutil.which("clang")
        if compiler is None:
            self.skipTest("host C compiler not available")
        source = self._source(
            "pub fn configure(dev: Device<Discovered>) -> Device<Configured> "
            "{ unsafe { return transition(move(dev), Configured); } }"
        ).replace("state Discovered", "initial state Discovered") \
        + "\nfn main() -> i32 { let dev: Device<Discovered> = Device { id: 37u32 }; " \
            "let configured = configure(move(dev)); " \
            "return configured.id as i32; }\n"
        generated = bootstrap.compile_source(
            source, filename="<state-native>"
        )
        with tempfile.TemporaryDirectory(prefix="sotlas-state-") as temp_dir:
            c_file = Path(temp_dir) / "state_transition.c"
            executable = Path(temp_dir) / "state_transition"
            c_file.write_text(generated, encoding="utf-8")
            compiled = subprocess.run(
                [compiler, "-std=c11", "-Wall", "-Wextra", "-Werror",
                 str(c_file), "-o", str(executable)],
                capture_output=True, text=True,
                env={**os.environ, "PATH": str(Path(compiler).parent)
                     + os.pathsep + os.environ.get("PATH", "")},
            )
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            executed = subprocess.run(
                [str(executable)], capture_output=True, text=True
            )
            self.assertEqual(executed.returncode, 37, executed.stderr)

    def test_invalid_state_semantics_become_production_frontend_error(self):
        source = """
        module test::invalid_state_check;
        space Device {
            state Ready
            Ready -> Missing
        }
        """
        module = bootstrap.parse(source, filename="<invalid-state-check>")
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            r"unknown target 'Missing'",
        ):
            bootstrap.check(module)

    def test_ordinary_non_state_module_keeps_existing_check_and_c_backend(self):
        source = """
        module test::ordinary;
        pub fn value() -> u32 { return 7; }
        """
        module = bootstrap.parse(source, filename="<ordinary>")
        bootstrap.check(module)
        emitted = bootstrap.emit_c(module, include_preamble=False)
        self.assertIn("uint32_t value(void)", emitted)


if __name__ == "__main__":
    unittest.main()
