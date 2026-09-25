"""Canonical declaration origins for tracked ownership bindings."""
import importlib
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"


def _load_package():
    name = "sotlas_ownership_origin_package"
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


package = _load_package()
origins = importlib.import_module(f"{package.__name__}.ownership_origin")
typed_ast = importlib.import_module(f"{package.__name__}.typed_ast")


SOURCE = """module app::ownership_origins;
sole struct Token { value: u32; }

fn pass(token: region Token) -> region Token {
    return token;
}

fn run(token: region Token) -> void {
    let out: region Token = pass(move token);
    return;
}
"""


class SotlasOwnershipOriginTests(unittest.TestCase):
    def test_parameter_and_call_result_declarations_have_distinct_origin_semantics(self):
        checked = package.analyze_source_phase1(
            SOURCE,
            filename="<ownership-origins>",
        )
        plan = origins.plan_checked_ownership_origins(
            checked,
            function="run",
            domain=typed_ast.OwnershipDomain.REGION,
        )

        self.assertEqual(set(plan.bindings), {"token", "out"})
        parameter = plan.origin("token")
        self.assertEqual(parameter.declaration_kind, "parameter")
        self.assertEqual(parameter.producer, "parameter")
        self.assertTrue(parameter.produces_identity)
        self.assertEqual(parameter.point_id, "param_origin@run::token")

        result = plan.origin("out")
        self.assertEqual(result.declaration_kind, "local")
        self.assertEqual(result.producer, "call")
        self.assertFalse(result.produces_identity)
        self.assertEqual(result.callee, "pass")
        self.assertTrue(result.point_id.startswith("local_origin@"))
        self.assertNotEqual(parameter.point_id, result.point_id)

    def test_origin_plan_is_domain_neutral_but_filterable(self):
        checked = package.analyze_source_phase1(
            SOURCE,
            filename="<ownership-origins-domain>",
        )
        region = origins.plan_checked_ownership_origins(
            checked,
            function="pass",
            domain=typed_ast.OwnershipDomain.REGION,
        )
        unfiltered = origins.plan_checked_ownership_origins(
            checked,
            function="pass",
        )
        self.assertEqual(region.origins, unfiltered.origins)
        self.assertEqual(region.origin("token").domain, typed_ast.OwnershipDomain.REGION)

    def test_unknown_function_fails_closed(self):
        checked = package.analyze_source_phase1(
            SOURCE,
            filename="<ownership-origins-missing>",
        )
        with self.assertRaisesRegex(
            origins.OwnershipOriginError,
            "exactly one parsed function",
        ):
            origins.plan_checked_ownership_origins(
                checked,
                function="missing",
                domain=typed_ast.OwnershipDomain.REGION,
            )


if __name__ == "__main__":
    unittest.main()
