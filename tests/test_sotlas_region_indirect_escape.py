"""REGION lifetime gates for indirect function-pointer calls."""
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"


def _load_package():
    name = "sotlas_region_indirect_escape_package"
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
bootstrap = package.bootstrap


class SotlasRegionIndirectEscapeTests(unittest.TestCase):
    def test_region_reference_cannot_cross_function_pointer_field_call(self):
        source = """module app::region_indirect_escape;
sole struct Token { value: u32; }
struct Dispatch { callback: fn(&Token) -> void; }
fn run(dispatch: Dispatch, token: region Token) -> void {
    dispatch.callback(&token);
    return;
}
"""
        module = bootstrap.parse(source, filename="<region-indirect-escape>")
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            r"region owner 'token'.*indirect function-pointer call.*no-escape",
        ):
            bootstrap.check(module)

    def test_region_alias_cannot_hide_function_pointer_escape(self):
        source = """module app::region_indirect_alias_escape;
sole struct Token { value: u32; }
struct Dispatch { callback: fn(&Token) -> void; }
fn run(dispatch: Dispatch, token: region Token) -> void {
    let alias = &token;
    dispatch.callback(alias);
    return;
}
"""
        module = bootstrap.parse(
            source, filename="<region-indirect-alias-escape>"
        )
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            r"region owner 'token'.*indirect function-pointer call.*no-escape",
        ):
            bootstrap.check(module)


if __name__ == "__main__":
    unittest.main()
