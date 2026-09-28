"""Release gates for standalone preview bundles."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_SCRIPT = ROOT / "packaging" / "package.py"


class SotlasPreviewPackagingTests(unittest.TestCase):
    def test_macos_bundle_contains_and_resolves_canonical_frontend(self):
        with tempfile.TemporaryDirectory(prefix="sotlas-preview-package-") as tmp:
            dist = Path(tmp) / "dist"
            result = subprocess.run(
                [
                    sys.executable,
                    str(PACKAGE_SCRIPT),
                    "--target",
                    "darwin",
                    "--dist-dir",
                    str(dist),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

            archive = dist / "sotlas-v1.0.0rc1-macos-x64.tar.gz"
            self.assertTrue(archive.is_file())
            checksum_file = dist / "SHA256SUMS.txt"
            checksums = checksum_file.read_text(encoding="utf-8")
            self.assertIn(archive.name, checksums)

            unpacked = Path(tmp) / "unpacked"
            unpacked.mkdir()
            with tarfile.open(archive, "r:gz") as tf:
                tf.extractall(unpacked)

            bundle = unpacked / "sotlas-v1.0.0rc1-macos-x64"
            canonical = bundle / "compiler" / "sotlas_compile" / "bootstrap.py"
            historical = bundle / "tools" / "sotlas_compile" / "bootstrap.py"
            self.assertTrue(canonical.is_file())
            self.assertTrue(historical.is_file())
            self.assertEqual(
                canonical.read_bytes(),
                (ROOT / "compiler" / "sotlas_compile" / "bootstrap.py").read_bytes(),
            )

            env = os.environ.copy()
            env["PYTHONPATH"] = os.pathsep.join(
                [str(bundle / "compiler"), str(bundle / "tools")]
            )
            probe = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    (
                        "from pathlib import Path; "
                        "from sotlas.llvm_toolchain import canonical_llvm_frontend; "
                        "m=canonical_llvm_frontend(); "
                        "print(Path(m.__file__).resolve())"
                    ),
                ],
                cwd=bundle,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(probe.returncode, 0, probe.stdout + probe.stderr)
            normalized = probe.stdout.strip().replace("\\", "/")
            self.assertIn("/compiler/sotlas_compile/bootstrap.py", normalized)
            self.assertNotIn("/tools/sotlas_compile/bootstrap.py", normalized)

    def test_packager_exposes_all_three_preview_targets(self):
        source = PACKAGE_SCRIPT.read_text(encoding="utf-8")
        self.assertIn('choices=["all", "windows", "linux", "darwin"]', source)
        self.assertIn('sotlas-v{version}-windows-x64', source)
        self.assertIn('sotlas-v{version}-linux-x64', source)
        self.assertIn('sotlas-v{version}-macos-x64', source)


if __name__ == "__main__":
    unittest.main()
