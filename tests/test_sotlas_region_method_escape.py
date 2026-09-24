"""REGION reference escape checks across resolved method boundaries."""
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"


def _load_package():
    name = "sotlas_region_method_escape_package"
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


class SotlasRegionMethodEscapeTests(unittest.TestCase):
    def test_region_reference_can_cross_method_direct_and_whisper_params(self):
        source = """module app::region_method_safe;
sole struct Token { value: u32; }
sole struct Inspector {
    value: u32;
    fn inspect_direct(&self, token: direct Token) -> void { return; }
    fn inspect_whisper(&self, token: whisper Token) -> void { return; }
}
fn run(inspector: Inspector, token: region Token) -> void {
    inspector.inspect_direct(&token);
    inspector.inspect_whisper(&token);
    return;
}
"""
        module = bootstrap.parse(source, filename="<region-method-safe>")
        bootstrap.check(module)

    def test_region_reference_cannot_escape_through_plain_reference_method_param(self):
        source = """module app::region_method_escape;
sole struct Token { value: u32; }
sole struct Inspector {
    value: u32;
    fn capture(&self, token: &Token) -> void { return; }
}
fn run(inspector: Inspector, token: region Token) -> void {
    inspector.capture(&token);
    return;
}
"""
        module = bootstrap.parse(source, filename="<region-method-escape>")
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            r"cannot escape through method .*capture.*direct or whisper",
        ):
            bootstrap.check(module)

    def test_region_alias_cannot_hide_escape_through_method_param(self):
        source = """module app::region_method_alias_escape;
sole struct Token { value: u32; }
sole struct Inspector {
    value: u32;
    fn capture(&self, token: &Token) -> void { return; }
}
fn run(inspector: Inspector, token: region Token) -> void {
    let alias = &token;
    inspector.capture(alias);
    return;
}
"""
        module = bootstrap.parse(source, filename="<region-method-alias-escape>")
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            r"cannot escape through method .*capture.*direct or whisper",
        ):
            bootstrap.check(module)


if __name__ == "__main__":
    unittest.main()
