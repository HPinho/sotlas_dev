"""Static release gates for the public Sotlas preview workflow."""
from __future__ import annotations

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
RELEASE_WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"
INNO_SCRIPT = ROOT / "packaging" / "windows" / "sotlas.iss"
RUNTIME_PACKAGE = ROOT / "compiler" / "sotlas" / "__init__.py"


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

    def test_manual_release_requires_main_and_full_test_suite(self):
        text = RELEASE_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn('"${{ github.ref }}" -ne "refs/heads/main"', text)
        self.assertIn("Manual preview releases must be dispatched from main", text)
        self.assertIn("Run full release test suite", text)
        self.assertIn('python -m pip install -e .', text)
        self.assertIn('python -m unittest discover -s tests -p "test_*.py"', text)
        self.assertIn("Full Sotlas release test suite failed", text)

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
        self.assertIn("python -m sotlas.doctor --json", text)
        self.assertIn("python -m sotlas.cli check examples/01_hello_systems/main.sotlas", text)
        self.assertIn("dist/*.whl", text)
        self.assertIn("dist/SHA256SUMS.txt", text)

    def test_inno_installer_matches_runtime_preview_version_and_repository(self):
        package = RUNTIME_PACKAGE.read_text(encoding="utf-8")
        match = re.search(r'^SOTLAS_VERSION = "([^"]+)"$', package, re.MULTILINE)
        self.assertIsNotNone(match)
        version = match.group(1)

        installer = INNO_SCRIPT.read_text(encoding="utf-8")
        self.assertIn(f'#define MyAppVersion "{version}"', installer)
        self.assertIn(f'Sotlas-Setup-v{version}.exe', installer)
        self.assertIn('https://github.com/HPinho/sotlas_dev', installer)
        self.assertIn('dist\\sotlas-v{#MyAppVersion}-windows-x64\\*', installer)
        self.assertNotIn('0.2.0', installer)
        self.assertNotIn('github.com/Sotlas/sotlas', installer)
        self.assertNotIn('assets\\icon.ico', installer)


if __name__ == "__main__":
    unittest.main()
