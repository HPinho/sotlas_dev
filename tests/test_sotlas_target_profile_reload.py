"""Regression coverage for reload-safe target-profile installation."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "compiler"))

from sotlas_compile import target_profile


class SotlasTargetProfileReloadTests(unittest.TestCase):
    def test_stale_install_flag_does_not_hide_reloaded_raw_parser(self):
        def raw_parse(source, filename=None):
            return SimpleNamespace(source=source, filename=filename)

        def raw_emit(module, *args, **kwargs):
            return "/* raw */"

        bootstrap = SimpleNamespace(parse=raw_parse, emit_c=raw_emit)
        target_profile.install(bootstrap)
        first_wrapper = bootstrap.parse
        self.assertIsNot(first_wrapper, raw_parse)
        self.assertTrue(bootstrap._TARGET_PROFILE_FRONTEND_INSTALLED)

        # Model importlib.reload semantics: functions defined by bootstrap.py are
        # reset, while extension-only sentinel attributes can survive in the
        # module dictionary.
        bootstrap.parse = raw_parse
        bootstrap.emit_c = raw_emit

        target_profile.install(bootstrap)
        self.assertIsNot(bootstrap.parse, raw_parse)
        self.assertIsNot(bootstrap.parse, first_wrapper)
        self.assertIs(
            bootstrap._TARGET_PROFILE_PARSE_WRAPPER,
            bootstrap.parse,
        )


if __name__ == "__main__":
    unittest.main()
