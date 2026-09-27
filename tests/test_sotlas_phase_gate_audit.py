"""Keep the published phase matrix tied to real, checked-in test gates."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SotlasPhaseGateAuditTests(unittest.TestCase):
    def test_every_roadmap_phase_has_existing_evidence_and_a_boundary(self):
        manifest = json.loads(
            (ROOT / "docs" / "phase_gate_matrix.json").read_text(encoding="utf-8")
        )
        phases = manifest["phases"]
        self.assertEqual([item["phase"] for item in phases], list(range(18)))
        for item in phases:
            with self.subTest(phase=item["phase"]):
                self.assertTrue(item["tests"])
                self.assertTrue(item["evidence"].strip())
                self.assertTrue(item["boundary"].strip())
                for relative in item["tests"]:
                    self.assertTrue((ROOT / relative).is_file(), relative)

    def test_committed_matrix_matches_the_evidence_manifest(self):
        result = subprocess.run(
            [sys.executable, "scripts/generate_phase_gate_matrix.py", "--check"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
