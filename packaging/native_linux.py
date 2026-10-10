"""Build reproducible native Linux seed bundles; Python is build-time only."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import struct
import subprocess
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
CORE = ("token", "ast", "lexer", "parser", "sema", "backend/target_ir", "backend/lower_scalar", "backend/x86_64_scalar")


def validate_seed(path: Path) -> None:
    data = path.read_bytes()
    if len(data) < 64 or data[:6] != b"\x7fELF\x02\x01" or struct.unpack_from("<HH", data, 16) != (2, 62):
        raise ValueError("Seed must be a Linux x86-64 ELF executable")
    start = struct.unpack_from("<Q", data, 32)[0]
    size, count = struct.unpack_from("<HH", data, 54)
    if size != 56 or count == 0 or start + size * count > len(data):
        raise ValueError("Invalid seed program headers")
    for index in range(count):
        if struct.unpack_from("<I", data, start + index * size)[0] in (2, 3):
            raise ValueError("Native seed must not require a dynamic linker or C runtime")


def build_seed(output: Path) -> None:
    sys.path.insert(0, str(ROOT / "compiler"))
    sys.path.insert(0, str(ROOT / "tools"))
    from sotlas.bootstrap_pipeline import build_stage1_native_compiler
    with tempfile.TemporaryDirectory(prefix="sotlas-native-seed-") as temporary:
        directory = Path(temporary)
        producer = directory / ("producer.exe" if sys.platform == "win32" else "producer")
        obj = directory / "driver.o"
        build_stage1_native_compiler(producer, verbose=False)
        subprocess.run([str(producer), "--compile-obj", str(ROOT / "bootstrap/sotlas/native_driver/linux.sotlas"), str(obj)], check=True, cwd=ROOT)
        subprocess.run([str(producer), "--link-exe", str(obj), str(output), "sotlas_linux_main"], check=True, cwd=ROOT)


def assemble(seed: Path, destination: Path, version: str) -> Path:
    validate_seed(seed)
    if destination.exists():
        raise ValueError("Bundle destination already exists")
    if not version or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-" for c in version):
        raise ValueError("Invalid bundle version")
    destination.mkdir(parents=True)
    files = {"bin/sotlas-native": seed.read_bytes()}
    for name in CORE:
        relative = "src/sotlas/compiler/" + name + ".sotlas"
        files[relative] = (ROOT / ("bootstrap/sotlas/native_compiler/" + name + ".sotlas")).read_bytes().replace(b"\r\n", b"\n")
    files["src/sotlas/compiler/linux_driver.sotlas"] = (ROOT / "bootstrap/sotlas/native_driver/linux.sotlas").read_bytes().replace(b"\r\n", b"\n")
    files["src/sotlas/compiler/windows_driver.sotlas"] = (ROOT / "bootstrap/sotlas/native_driver/windows.sotlas").read_bytes().replace(b"\r\n", b"\n")
    files["src/sotlas/compiler/darwin_driver.sotlas"] = (ROOT / "bootstrap/sotlas/native_driver/darwin.sotlas").read_bytes().replace(b"\r\n", b"\n")
    files["docs/native-driver.md"] = (ROOT / "bootstrap/sotlas/native_driver/README.md").read_bytes().replace(b"\r\n", b"\n")
    files["install-native.sh"] = (ROOT / "packaging/install-native.sh").read_bytes().replace(b"\r\n", b"\n")
    hashes = {name: hashlib.sha256(data).hexdigest() for name, data in sorted(files.items())}
    files["manifest.json"] = (json.dumps({"schema": 1, "version": version, "target": "linux-x86_64",
        "profile": "native-compiler-source-subset", "sha256": hashes}, indent=2, sort_keys=True) + "\n").encode()
    files["SHA256SUMS"] = "".join(hashlib.sha256(data).hexdigest() + "  " + name + "\n"
        for name, data in sorted(files.items())).encode()
    for name, data in files.items():
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        target.chmod(0o755 if name in ("bin/sotlas-native", "install-native.sh") else 0o644)
    archive = destination.with_suffix(".tar.gz")
    with archive.open("wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode="w") as tar:
            for name, data in sorted(files.items()):
                info = tarfile.TarInfo(destination.name + "/" + name)
                info.size = len(data)
                info.mode = 0o755 if name in ("bin/sotlas-native", "install-native.sh") else 0o644
                info.mtime = 0
                tar.addfile(info, io.BytesIO(data))
    archive.with_name(archive.name + ".sha256").write_text(hashlib.sha256(archive.read_bytes()).hexdigest() + "  " + archive.name + "\n")
    return archive


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=Path, help="Existing native seed; otherwise build from current sources")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--version", default="1.0.0rc1")
    arguments = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="sotlas-native-package-") as temporary:
        seed = arguments.seed
        if seed is None:
            seed = Path(temporary) / "sotlas-native"
            build_seed(seed)
        print(assemble(seed, arguments.output, arguments.version))


if __name__ == "__main__":
    main()
