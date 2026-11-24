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
        self.assertIn('$requestedVersion = $runtimeVersion', text)
        self.assertIn("id: release_version", text)
        self.assertIn("Release version mismatch", text)
        self.assertIn("SOTLAS_VERSION", text)
        self.assertIn('tag_name: "v${{ steps.release_version.outputs.version }}"', text)
        self.assertIn("prerelease: true", text)
        self.assertNotIn("prerelease: false", text)

    def test_manual_release_requires_main_and_full_test_suite(self):
        text = RELEASE_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn('$env:RELEASE_REF -cne "refs/heads/main"', text)
        self.assertIn("Manual preview releases must be dispatched from main", text)
        self.assertIn("Run full release test suite", text)
        self.assertIn('python -m pip install -e .', text)
        self.assertIn('python -m unittest discover -s tests -p "test_*.py"', text)
        self.assertIn("Full Sotlas release test suite failed", text)

    def test_release_uses_the_changelog_and_preserves_published_versions(self):
        text = RELEASE_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn('Get-Content CHANGELOG.md -Raw', text)
        self.assertIn('body_path: build/preview-release-notes.md', text)
        self.assertIn('git ls-remote origin $tagRef', text)
        self.assertIn('Release $tag already exists. Use a new version.', text)

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

    def test_release_compiles_and_requires_the_windows_installer(self):
        text = RELEASE_WORKFLOW.read_text(encoding="utf-8")
        step = text.split("- name: Compile Inno Setup Windows Installer", 1)[1].split("- name:", 1)[0]
        self.assertIn("choco install innosetup --version=", step)
        self.assertIn("& $iscc packaging/windows/sotlas.iss", step)
        self.assertIn("Missing Windows installer", step)
        self.assertNotIn("continue-on-error", step)


if __name__ == "__main__":
    unittest.main()
