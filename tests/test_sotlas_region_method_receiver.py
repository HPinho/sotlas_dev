"""REGION method receivers require an explicit non-owning domain."""
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"


def _load_package():
    name = "sotlas_region_method_receiver_package"
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


class SotlasRegionMethodReceiverTests(unittest.TestCase):
    def test_region_owner_can_be_direct_method_receiver(self):
        source = """module app::region_direct_receiver;
sole struct Token {
    value: u32;
    fn inspect(self: direct Token) -> u32 { return self.value; }
}
fn read(token: region Token) -> u32 { return token.inspect(); }
"""
        module = bootstrap.parse(source, filename="<region-direct-receiver>")
        bootstrap.check(module)

    def test_region_owner_plain_reference_receiver_is_fail_closed(self):
        source = """module app::region_plain_receiver;
sole struct Token { value: u32; }
impl Token {
    fn inspect(self: &Token) -> u32 { return self.value; }
}
fn read(token: region Token) -> u32 { return token.inspect(); }
"""
        module = bootstrap.parse(source, filename="<region-plain-receiver>")
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            r"region owner 'token'.*method receiver.*direct or whisper",
        ):
            bootstrap.check(module)

    def test_region_alias_plain_reference_receiver_is_fail_closed(self):
        source = """module app::region_alias_receiver;
sole struct Token { value: u32; }
impl Token {
    fn inspect(self: &Token) -> u32 { return self.value; }
}
fn read(token: region Token) -> u32 {
    let alias = &token;
    return alias.inspect();
}
"""
        module = bootstrap.parse(source, filename="<region-alias-receiver>")
        # The narrow REGION pass deliberately does not infer a new reference
        # type for unannotated aliases.  Losing receiver type identity therefore
        # fails closed at method resolution instead of guessing a self contract.
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            r"region owner 'token'.*unresolved method 'inspect'",
        ):
            bootstrap.check(module)


if __name__ == "__main__":
    unittest.main()
