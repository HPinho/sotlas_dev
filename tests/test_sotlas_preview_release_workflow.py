"""Static release gates for the public Sotlas preview workflow."""
from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
RELEASE_WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"


class SotlasPreviewReleaseWorkflowTests(unittest.TestCase):
    def test_preview_release_is_version_checked_and_marked_prerelease(self):
        text = RELEASE_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn('default: "1.0.0rc1"', text)
        self.assertIn("id: release_version", text)
        self.assertIn("Release version mismatch", text)
        self.assertIn("SOTLAS_VERSION", text)
        self.assertIn('tag_name: "v${{ steps.release_version.outputs.version }}"', text)
        self.assertIn("prerelease: true", text)
        self.assertNotIn("prerelease: false", text)

    def test_release_requires_cross_platform_portable_artifacts(self):
        text = RELEASE_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("windows-x64.zip", text)
        self.assertIn("linux-x64.tar.gz", text)
        self.assertIn("macos-x64.tar.gz", text)
        self.assertIn("Missing required preview artifact", text)

    def test_release_builds_and_smokes_python_distribution(self):
        text = RELEASE_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("python -m build . --outdir dist", text)
        self.assertIn("python -m sotlas.cli version", text)
        self.assertIn("python -m sotlas.cli check examples/01_hello_systems/main.sotlas", text)
        self.assertIn("dist/*.whl", text)
        self.assertIn("dist/SHA256SUMS.txt", text)


if __name__ == "__main__":
    unittest.main()
