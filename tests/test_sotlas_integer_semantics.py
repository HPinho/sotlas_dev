from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
COMPILER_DIR = ROOT / "compiler"
if str(COMPILER_DIR) not in sys.path:
    sys.path.insert(0, str(COMPILER_DIR))

from sotlas_compile.integer_semantics import (
    IntegerOverflowError,
    IntegerSemanticsError,
    OverflowMode,
    evaluate_integer_binary,
    integer_type_semantics,
)


class SotlasIntegerSemanticsTests(unittest.TestCase):
    def test_checked_rejects_signed_and_unsigned_overflow(self):
        with self.assertRaisesRegex(
            IntegerOverflowError, r"checked add overflows i8: 127, 1"
        ):
            evaluate_integer_binary("add", 127, 1, "i8", OverflowMode.CHECKED)
        with self.assertRaisesRegex(
            IntegerOverflowError, r"checked add overflows u8: 255, 1"
        ):
            evaluate_integer_binary("add", 255, 1, "u8", "checked")

    def test_wrapping_is_finite_width_and_two_complement_for_signed_types(self):
        self.assertEqual(
            evaluate_integer_binary("add", 255, 1, "u8", "wrapping").value,
            0,
        )
        signed = evaluate_integer_binary("add", 127, 1, "i8", "wrapping")
        self.assertEqual(signed.value, -128)
        self.assertTrue(signed.overflowed)
        self.assertEqual(
            evaluate_integer_binary("sub", -128, 1, "i8", "wrapping").value,
            127,
        )

    def test_saturating_clamps_to_nearest_endpoint(self):
        self.assertEqual(
            evaluate_integer_binary("add", 250, 20, "u8", "saturating").value,
            255,
        )
        self.assertEqual(
            evaluate_integer_binary("sub", -120, 20, "i8", "saturating").value,
            -128,
        )
        self.assertEqual(
            evaluate_integer_binary("mul", 60, 3, "i8", "saturating").value,
            127,
        )

    def test_non_overflowing_results_are_identical_across_modes(self):
        for mode in OverflowMode:
            result = evaluate_integer_binary("mul", -6, 7, "i16", mode)
            self.assertEqual(result.value, -42)
            self.assertFalse(result.overflowed)

    def test_target_sized_integers_require_supported_pointer_width(self):
        self.assertEqual(integer_type_semantics("usize", pointer_bits=32).maximum, 2**32 - 1)
        self.assertEqual(integer_type_semantics("isize", pointer_bits=64).minimum, -(2**63))
        with self.assertRaisesRegex(IntegerSemanticsError, "unsupported pointer width"):
            integer_type_semantics("usize", pointer_bits=16)

    def test_operands_must_already_fit_their_declared_type(self):
        with self.assertRaisesRegex(IntegerSemanticsError, "outside the range of u8"):
            evaluate_integer_binary("add", 256, 0, "u8", "wrapping")
        with self.assertRaises(TypeError):
            evaluate_integer_binary("add", True, 1, "u8", "checked")

    def test_unknown_operations_modes_and_types_fail_closed(self):
        with self.assertRaisesRegex(IntegerSemanticsError, "unsupported integer arithmetic"):
            evaluate_integer_binary("div", 4, 2, "u8", "checked")
        with self.assertRaisesRegex(IntegerSemanticsError, "unsupported overflow mode"):
            evaluate_integer_binary("add", 1, 2, "u8", "undefined")
        with self.assertRaisesRegex(IntegerSemanticsError, "unsupported Sotlas integer type"):
            evaluate_integer_binary("add", 1, 2, "f32", "checked")

    def test_compatibility_mirror_is_byte_identical(self):
        canonical = ROOT / "compiler" / "sotlas_compile" / "integer_semantics.py"
        mirror = ROOT / "tools" / "sotlas_compile" / "integer_semantics.py"
        self.assertEqual(canonical.read_bytes(), mirror.read_bytes())


if __name__ == "__main__":
    unittest.main()
