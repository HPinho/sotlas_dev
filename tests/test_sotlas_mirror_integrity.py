"""Structural guards against destructive compiler/tools mirror regressions.

The byte-for-byte reality gate catches ordinary mirror drift, but equal damage on
both sides could still pass it.  These checks are intentionally independent of
feature correctness: they reject placeholder/stub replacements, invalid Python,
and catastrophic truncation of the large semantic modules that form the current
Sotlas baseline.
"""
from __future__ import annotations

import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
COMPILER = ROOT / "compiler"
TOOLS = ROOT / "tools"

_STUB_BODIES = {
    "placeholder",
    "pass",
    "...",
    "todo",
    "stub",
}

# These are deliberately conservative lower bounds, not exact snapshots.  A
# legitimate large refactor may update them explicitly after review, while an
# accidental one-line replacement or wholesale semantic deletion fails fast.
_CRITICAL_MIRRORS = {
    Path("sotlas/sir/generator.py"): (
        400,
        (
            "class SIRGenerator",
            "OwnershipDomainPointInst",
            "def generate_from_ast(",
        ),
    ),
    Path("sotlas/sir/ownership.py"): (
        400,
        (
            "class OwnershipDomainSIRPlan",
            "lower_ownership_domain_graph",
            "lower_ownership_module_semantics",
        ),
    ),
    Path("sotlas_compile/typed_ast.py"): (
        400,
        (
            "class OwnershipDomain",
            "class OwnershipDomainGraph",
            'MATURITY = "ISOLATED_PHASE1"',
        ),
    ),
    Path("sotlas_compile/bootstrap.py"): (
        400,
        (
            "class Parser",
            "def parse(",
            "def check(",
        ),
    ),
}


def _paired_python_paths() -> tuple[Path, ...]:
    return tuple(sorted(
        path.relative_to(COMPILER)
        for path in COMPILER.rglob("*.py")
        if (TOOLS / path.relative_to(COMPILER)).is_file()
    ))


class SotlasMirrorIntegrityTests(unittest.TestCase):
    def test_all_python_mirrors_are_parseable_non_stub_modules(self):
        paired = _paired_python_paths()
        self.assertTrue(paired, "compiler/tools mirror inventory unexpectedly empty")

        for relative in paired:
            for root in (COMPILER, TOOLS):
                path = root / relative
                source = path.read_text(encoding="utf-8")
                normalized = source.strip().lower()
                with self.subTest(path=str(path.relative_to(ROOT))):
                    self.assertNotIn(
                        normalized,
                        _STUB_BODIES,
                        f"critical mirror collapsed to a stub: {path.relative_to(ROOT)}",
                    )
                    self.assertGreaterEqual(
                        len(source.strip()),
                        16,
                        f"mirror is suspiciously empty: {path.relative_to(ROOT)}",
                    )
                    try:
                        tree = ast.parse(source, filename=str(path))
                    except SyntaxError as exc:
                        self.fail(
                            f"mirror is not valid Python: {path.relative_to(ROOT)}: {exc}"
                        )
                    meaningful = sum(
                        isinstance(
                            node,
                            (
                                ast.FunctionDef,
                                ast.AsyncFunctionDef,
                                ast.ClassDef,
                                ast.Import,
                                ast.ImportFrom,
                                ast.Assign,
                                ast.AnnAssign,
                            ),
                        )
                        for node in tree.body
                    )
                    self.assertGreater(
                        meaningful,
                        0,
                        f"mirror has no meaningful top-level declarations: {path.relative_to(ROOT)}",
                    )

    def test_large_semantic_mirrors_cannot_be_catastrophically_truncated(self):
        for relative, (minimum_lines, required_markers) in _CRITICAL_MIRRORS.items():
            for root in (COMPILER, TOOLS):
                path = root / relative
                source = path.read_text(encoding="utf-8")
                line_count = len(source.splitlines())
                with self.subTest(path=str(path.relative_to(ROOT))):
                    self.assertGreaterEqual(
                        line_count,
                        minimum_lines,
                        (
                            f"critical mirror looks truncated: {path.relative_to(ROOT)} "
                            f"has {line_count} lines; expected at least {minimum_lines}"
                        ),
                    )
                    for marker in required_markers:
                        self.assertIn(
                            marker,
                            source,
                            (
                                f"critical semantic marker {marker!r} disappeared from "
                                f"{path.relative_to(ROOT)}"
                            ),
                        )


if __name__ == "__main__":
    unittest.main()
