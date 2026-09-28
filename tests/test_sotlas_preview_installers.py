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
        self.assertIn('-m sotlas.doctor', source)
        self.assertNotIn('BUNDLE_PATH="$REPO_ROOT/dist/sotlas-v${VERSION}-linux-x64"', source)

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
        self.assertIn('$env:PYTHONPATH = "$InstallDir\\compiler;$InstallDir\\tools;$OldPythonPath"', source)
        self.assertIn('-m sotlas.doctor', source)
        self.assertNotIn('Expand-Archive -Path $SourceZip -DestinationPath $InstallDir', source)

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
