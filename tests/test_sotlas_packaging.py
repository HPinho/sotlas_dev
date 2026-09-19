"""Testes do sistema de empacotamento, distribuição e instalação oficial do Sotlas."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

class TestSotlasPackaging(unittest.TestCase):
    def test_packager_script_exists(self):
        packager = ROOT / "packaging" / "package.py"
        self.assertTrue(packager.is_file(), "packaging/package.py deve existir")

    def test_install_ps1_exists(self):
        install_ps1 = ROOT / "packaging" / "install.ps1"
        self.assertTrue(install_ps1.is_file(), "packaging/install.ps1 deve existir")
        text = install_ps1.read_text(encoding="utf-8")
        self.assertIn("SOTLAS_HOME", text)
        self.assertIn("sotlas.cmd", text)

    def test_install_sh_exists(self):
        install_sh = ROOT / "packaging" / "install.sh"
        self.assertTrue(install_sh.is_file(), "packaging/install.sh deve existir")
        text = install_sh.read_text(encoding="utf-8")
        self.assertIn("SOTLAS_HOME", text)
        self.assertIn("sotlas", text)

    def test_inno_setup_script_exists(self):
        iss_file = ROOT / "packaging" / "windows" / "sotlas.iss"
        self.assertTrue(iss_file.is_file(), "packaging/windows/sotlas.iss deve existir")
        text = iss_file.read_text(encoding="utf-8")
        self.assertIn("[Setup]", text)
        self.assertIn("[Files]", text)
        self.assertIn("[Icons]", text)

    def test_release_workflow_exists(self):
        release_yml = ROOT / ".github" / "workflows" / "release.yml"
        self.assertTrue(release_yml.is_file(), ".github/workflows/release.yml deve existir")
        text = release_yml.read_text(encoding="utf-8")
        self.assertIn("softprops/action-gh-release", text)
        self.assertIn("package.py", text)

    def test_bundle_artifacts_exist(self):
        # O teste deve ser hermético: gera seu próprio bundle em vez de assumir
        # que outro job/etapa já criou ROOT/dist.
        with tempfile.TemporaryDirectory(prefix="sotlas_packaging_") as tmp:
            dist_dir = Path(tmp) / "dist"
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "packaging" / "package.py"),
                    "--dist-dir",
                    str(dist_dir),
                    "--target",
                    "all",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                result.returncode,
                0,
                f"packaging/package.py falhou:\n{result.stdout}\n{result.stderr}",
            )
            self.assertTrue(dist_dir.is_dir(), "dist temporário deve ser criado")
            self.assertTrue(any(dist_dir.glob("*.zip")), "Arquivo .zip deve ser gerado")
            self.assertTrue(any(dist_dir.glob("*.tar.gz")), "Arquivo .tar.gz deve ser gerado")
            self.assertTrue(
                (dist_dir / "SHA256SUMS.txt").is_file(),
                "SHA256SUMS.txt deve ser gerado",
            )

if __name__ == "__main__":
    unittest.main()
