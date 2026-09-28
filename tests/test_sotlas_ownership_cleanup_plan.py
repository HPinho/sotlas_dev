from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
COMPILER_DIR = ROOT / "compiler"
if str(COMPILER_DIR) not in sys.path:
    sys.path.insert(0, str(COMPILER_DIR))

from sotlas_compile.ownership_cleanup import (
    ExclusiveValueShape,
    OwnedFieldShape,
    OwnedStorage,
    OwnershipCleanupError,
    build_exclusive_cleanup_plan,
    expand_cleanup_events,
)


class SotlasOwnershipCleanupPlanTests(unittest.TestCase):
    def test_parent_deinit_precedes_reverse_owned_field_cleanup(self):
        leaf_a = ExclusiveValueShape("A", deinit_symbol="A_deinit")
        leaf_b = ExclusiveValueShape("B", deinit_symbol="B_deinit")
        parent = ExclusiveValueShape(
            "Parent",
            deinit_symbol="Parent_deinit",
            owned_fields=(
                OwnedFieldShape("first", leaf_a),
                OwnedFieldShape("second", leaf_b),
            ),
        )
        events = expand_cleanup_events(build_exclusive_cleanup_plan(parent))
        self.assertEqual(
            [(event.action, event.path, event.symbol) for event in events],
            [
                ("invoke_deinit", (), "Parent_deinit"),
                ("invoke_deinit", ("second",), "B_deinit"),
                ("end_owned_lifetime", ("second",), None),
                ("invoke_deinit", ("first",), "A_deinit"),
                ("end_owned_lifetime", ("first",), None),
                ("end_owned_lifetime", (), None),
            ],
        )

    def test_multidimensional_fixed_array_is_expanded_in_reverse_order(self):
        item = ExclusiveValueShape("Item", deinit_symbol="Item_deinit")
        matrix = ExclusiveValueShape(
            "MatrixOwner",
            owned_fields=(
                OwnedFieldShape(
                    "items",
                    item,
                    storage=OwnedStorage.FIXED_ARRAY,
                    dimensions=(2, 2),
                ),
            ),
        )
        events = expand_cleanup_events(build_exclusive_cleanup_plan(matrix))
        element_deinits = [
            event.path for event in events if event.action == "invoke_deinit"
        ]
        self.assertEqual(
            element_deinits,
            [
                ("items", 1, 1),
                ("items", 1, 0),
                ("items", 0, 1),
                ("items", 0, 0),
            ],
        )

    def test_deinit_using_self_with_owned_descendants_fails_closed(self):
        child = ExclusiveValueShape("Child", deinit_symbol="Child_deinit")
        parent = ExclusiveValueShape(
            "Parent",
            deinit_symbol="Parent_deinit",
            deinit_uses_self=True,
            owned_fields=(OwnedFieldShape("child", child),),
        )
        with self.assertRaisesRegex(
            OwnershipCleanupError,
            "accesses self while owned descendants require recursive cleanup",
        ):
            build_exclusive_cleanup_plan(parent)

    def test_invalid_array_shapes_and_duplicate_fields_fail_closed(self):
        leaf = ExclusiveValueShape("Leaf")
        with self.assertRaisesRegex(OwnershipCleanupError, "requires dimensions"):
            build_exclusive_cleanup_plan(
                ExclusiveValueShape(
                    "Owner",
                    owned_fields=(
                        OwnedFieldShape(
                            "items", leaf, storage=OwnedStorage.FIXED_ARRAY
                        ),
                    ),
                )
            )
        with self.assertRaisesRegex(OwnershipCleanupError, "declared more than once"):
            build_exclusive_cleanup_plan(
                ExclusiveValueShape(
                    "Owner",
                    owned_fields=(
                        OwnedFieldShape("x", leaf),
                        OwnedFieldShape("x", leaf),
                    ),
                )
            )

    def test_event_expansion_is_bounded(self):
        leaf = ExclusiveValueShape("Leaf")
        owner = ExclusiveValueShape(
            "Owner",
            owned_fields=(
                OwnedFieldShape(
                    "items",
                    leaf,
                    storage=OwnedStorage.FIXED_ARRAY,
                    dimensions=(100, 100),
                ),
            ),
        )
        plan = build_exclusive_cleanup_plan(owner)
        with self.assertRaisesRegex(OwnershipCleanupError, "exceeds bound"):
            expand_cleanup_events(plan, max_array_elements=4096)

    def test_compatibility_mirror_is_byte_identical(self):
        canonical = ROOT / "compiler" / "sotlas_compile" / "ownership_cleanup.py"
        mirror = ROOT / "tools" / "sotlas_compile" / "ownership_cleanup.py"
        self.assertEqual(canonical.read_bytes(), mirror.read_bytes())


if __name__ == "__main__":
    unittest.main()
