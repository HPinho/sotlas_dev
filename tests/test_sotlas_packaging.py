"""Testes do sistema de empacotamento, distribuição e instalação oficial do Sotlas."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
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
        self.assertIn('"sotlas-v$Version-windows-x64"', text)
        self.assertNotIn("sotlas-v0.2.0", text)

    def test_install_sh_exists(self):
        install_sh = ROOT / "packaging" / "install.sh"
        self.assertTrue(install_sh.is_file(), "packaging/install.sh deve existir")
        text = install_sh.read_text(encoding="utf-8")
        self.assertIn("SOTLAS_HOME", text)
        self.assertIn("sotlas", text)
        self.assertIn('sotlas-v${VERSION}-${PACKAGE_SUFFIX}', text)
        self.assertIn('PACKAGE_SUFFIX="linux-x64"', text)
        self.assertIn('PACKAGE_SUFFIX="macos-x64"', text)
        self.assertNotIn("sotlas-v0.2.0", text)

    def test_packager_uses_current_runtime_version_and_fails_closed(self):
        from importlib.util import module_from_spec, spec_from_file_location

        path = ROOT / "packaging" / "package.py"
        spec = spec_from_file_location("sotlas_release_packager", path)
        self.assertIsNotNone(spec)
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.get_version(), "1.0.0rc1")
        source = path.read_text(encoding="utf-8")
        self.assertIn("raise RuntimeError", source)

    def test_windows_launchers_do_not_retry_failed_cli_commands(self):
        from importlib.util import module_from_spec, spec_from_file_location

        path = ROOT / "packaging" / "package.py"
        spec = spec_from_file_location("sotlas_launcher_packager", path)
        self.assertIsNotNone(spec)
        module = module_from_spec(spec)
        spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory(prefix="sotlas-launchers-") as temporary:
            bin_dir = Path(temporary) / "bin"
            bin_dir.mkdir()
            module.create_windows_launchers(bin_dir)
            for name in ("sotlas.cmd", "sotlas-lsp.cmd"):
                with self.subTest(launcher=name):
                    text = (bin_dir / name).read_text(encoding="utf-8").lower()
                    self.assertIn("where py", text)
                    self.assertIn("if errorlevel 1 goto use_python", text)
                    self.assertIn("endlocal & exit /b %sotlas_exit%", text)
                    self.assertNotIn("if errorlevel 1 (", text)

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
            tmp_root = Path(tmp)
            dist_dir = tmp_root / "dist"
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
                any(dist_dir.glob("sotlas-v*-macos-x64.tar.gz")),
                "Bundle macOS x64 do preview deve ser gerado",
            )
            checksum_path = dist_dir / "SHA256SUMS.txt"
            self.assertTrue(checksum_path.is_file(), "SHA256SUMS.txt deve ser gerado")
            checksums = checksum_path.read_text(encoding="utf-8")
            self.assertIn("macos-x64.tar.gz", checksums)

            bundle_zip = next(dist_dir.glob("*.zip"))
            with zipfile.ZipFile(bundle_zip) as archive:
                entries = archive.namelist()
            self.assertFalse(
                any("/web/node_modules/" in entry.replace("\\", "/") for entry in entries),
                "Development dependencies must not be copied into release bundles",
            )

            windows_bundle = next(dist_dir.glob("sotlas-v*-windows-x64"))
            manifest_path = windows_bundle / "sotlas-toolchain.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["release"], "preview")
            self.assertEqual(
                manifest["components"],
                ["python-compiler", "cli", "standard-library", "web-source"],
            )

            canonical = windows_bundle / "compiler" / "sotlas_compile" / "bootstrap.py"
            historical = windows_bundle / "tools" / "sotlas_compile" / "bootstrap.py"
            self.assertTrue(canonical.is_file(), "bundle deve conter frontend canônico")
            self.assertTrue(historical.is_file(), "espelho histórico deve permanecer compatível")
            self.assertEqual(
                canonical.read_bytes(),
                (ROOT / "compiler" / "sotlas_compile" / "bootstrap.py").read_bytes(),
            )

            env = os.environ.copy()
            env["PYTHONPATH"] = os.pathsep.join(
                [str(windows_bundle / "compiler"), str(windows_bundle / "tools")]
            )
            probe = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    (
                        "from pathlib import Path; "
                        "from sotlas.llvm_toolchain import canonical_llvm_frontend; "
                        "m=canonical_llvm_frontend(); print(Path(m.__file__).resolve())"
                    ),
                ],
                cwd=windows_bundle,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(probe.returncode, 0, probe.stdout + probe.stderr)
            resolved = probe.stdout.strip().replace("\\", "/")
            self.assertIn("/compiler/sotlas_compile/bootstrap.py", resolved)
            self.assertNotIn("/tools/sotlas_compile/bootstrap.py", resolved)

            # Reuse the real archive produced above to prove the release-facing
            # Unix installer, with no checkout PYTHONPATH fallback.
            suffix = None
            if sys.platform.startswith("linux"):
                suffix = "linux-x64"
            elif sys.platform == "darwin":
                suffix = "macos-x64"
            if suffix is not None and shutil.which("bash"):
                release_archive = next(dist_dir.glob(f"sotlas-v*-{suffix}.tar.gz"))
                install_dir = tmp_root / "installed-preview"
                fake_home = tmp_root / "home"
                fake_home.mkdir()
                installer_env = os.environ.copy()
                installer_env["HOME"] = str(fake_home)
                installer_env["SOTLAS_INSTALL_DIR"] = str(install_dir)
                installer_env.pop("PYTHONPATH", None)
                install = subprocess.run(
                    [
                        "bash",
                        str(ROOT / "packaging" / "install.sh"),
                        "--source-archive",
                        str(release_archive),
                    ],
                    cwd=tmp_root,
                    env=installer_env,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(
                    install.returncode,
                    0,
                    f"archive installer falhou:\n{install.stdout}\n{install.stderr}",
                )
                self.assertTrue((install_dir / "bin" / "sotlas").is_file())
                self.assertTrue(
                    (install_dir / "compiler" / "sotlas_compile" / "bootstrap.py").is_file()
                )
                launcher = subprocess.run(
                    [str(install_dir / "bin" / "sotlas"), "version"],
                    cwd=tmp_root,
                    env=installer_env,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(launcher.returncode, 0, launcher.stdout + launcher.stderr)
                self.assertIn("Sotlas 1.0.0rc1", launcher.stdout)

if __name__ == "__main__":
    unittest.main()
