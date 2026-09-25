"""Phase 4: production frontend syntax bridge for State Spaces."""
from __future__ import annotations

import unittest

from tools.sotlas_compile import bootstrap
from tools.sotlas_compile.state_frontend import (
    StateSpaceFrontendError,
)


class SotlasStateFrontendTests(unittest.TestCase):
    def _source(self, signature: str = "pub fn configure(dev: Device<Discovered>) -> Device<Configured> { return dev; }") -> str:
        return f"""
        module test::state_frontend;

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

    def test_public_typestate_syntax_is_preserved_in_function_signature(self):
        module = bootstrap.parse(self._source(), filename="<state-signature>")
        function = module.functions[0]
        self.assertEqual(function.params[0][1].name, "Device<Discovered>")
        self.assertEqual(function.result.name, "Device<Configured>")

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

    def test_production_check_validates_then_rejects_preview_backend_gap(self):
        module = bootstrap.parse(self._source(), filename="<preview-check>")
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            r"State Spaces estão em PREVIEW.*fail-closed",
        ):
            bootstrap.check(module)
        self.assertTrue(module.state_space_frontend_plan.spaces)

    def test_direct_c_emission_cannot_bypass_preview_gate(self):
        module = bootstrap.parse(self._source(), filename="<preview-c>")
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            r"State Spaces estão em PREVIEW",
        ):
            bootstrap.emit_c(module)

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
