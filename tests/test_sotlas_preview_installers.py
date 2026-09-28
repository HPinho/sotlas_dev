"""Release gates for the Windows/Linux/macOS preview installer scripts."""
from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class SotlasPreviewInstallerTests(unittest.TestCase):
    def test_unix_installer_selects_the_host_bundle_fail_closed(self):
        path = ROOT / "packaging" / "install.sh"
        source = path.read_text(encoding="utf-8")

        self.assertIn("set -euo pipefail", source)
        self.assertIn('OS_NAME="$(uname -s)"', source)
        self.assertIn('ARCH="$(uname -m)"', source)
        self.assertIn('PACKAGE_TARGET="linux"', source)
        self.assertIn('PACKAGE_SUFFIX="linux-x64"', source)
        self.assertIn('PACKAGE_TARGET="darwin"', source)
        self.assertIn('PACKAGE_SUFFIX="macos-x64"', source)
        self.assertIn('Unsupported preview architecture', source)
        self.assertIn('--target "$PACKAGE_TARGET"', source)
        self.assertIn("sys.version_info >= (3, 10)", source)
        self.assertIn('-m sotlas.doctor', source)
        self.assertNotIn('BUNDLE_PATH="$REPO_ROOT/dist/sotlas-v${VERSION}-linux-x64"', source)

    def test_unix_release_archive_path_is_bounded_and_host_specific(self):
        source = (ROOT / "packaging" / "install.sh").read_text(encoding="utf-8")

        self.assertIn('--source-archive', source)
        self.assertIn('Source archive does not exist', source)
        self.assertIn('Archive does not match this host ($PACKAGE_SUFFIX)', source)
        self.assertIn('tar -tzf "$archive"', source)
        self.assertIn('Unsafe path in preview archive', source)
        self.assertIn('tar -xzf "$archive" -C "$extract_root"', source)
        self.assertIn('payload_count', source)
        self.assertIn('Portable archive must contain exactly one Sotlas toolchain root', source)
        self.assertIn('Source checkout not found. Use --source-archive', source)
        self.assertIn('PYTHONPATH="$INSTALL_PYTHONPATH" "$PYTHON_BIN" -m sotlas.doctor', source)

    def test_windows_archive_install_normalizes_the_payload_root(self):
        path = ROOT / "packaging" / "install.ps1"
        source = path.read_text(encoding="utf-8")

        self.assertIn('SourceZip does not exist', source)
        self.assertIn('$ExtractRoot', source)
        self.assertIn('$PayloadRoots', source)
        self.assertIn('$PayloadRoots.Count -ne 1', source)
        self.assertIn('$PayloadRoot = $PayloadRoots[0].FullName', source)
        self.assertIn('Copy-Item -Path (Join-Path $PayloadRoot "*")', source)
        self.assertIn('missing $SotlasLauncher', source)
        self.assertIn('sys.version_info >= (3, 10)', source)
        self.assertIn('$env:PYTHONPATH = "$InstallDir\\compiler;$InstallDir\\tools;$OldPythonPath"', source)
        self.assertIn('-m sotlas.doctor', source)
        self.assertNotIn('Expand-Archive -Path $SourceZip -DestinationPath $InstallDir', source)

    def test_release_workflow_smokes_the_packaged_doctor(self):
        source = (ROOT / ".github" / "workflows" / "release.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn('python -m sotlas.doctor --json', source)
        self.assertIn('prerelease: true', source)

    @unittest.skipUnless(shutil.which("bash"), "bash unavailable")
    def test_unix_installer_has_valid_shell_syntax(self):
        result = subprocess.run(
            ["bash", "-n", str(ROOT / "packaging" / "install.sh")],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    @unittest.skipUnless(shutil.which("pwsh"), "PowerShell unavailable")
    def test_windows_installer_parses_as_powershell(self):
        script = str(ROOT / "packaging" / "install.ps1")
        command = (
            "$ErrorActionPreference='Stop'; "
            f"[scriptblock]::Create((Get-Content -Raw -LiteralPath '{script}')) | Out-Null"
        )
        result = subprocess.run(
            ["pwsh", "-NoProfile", "-Command", command],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
