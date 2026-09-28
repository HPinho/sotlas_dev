"""Environment diagnostics for the Sotlas preview toolchain.

The doctor intentionally reports capabilities instead of pretending every
machine can use every backend.  Source checking and C11 emission need the
canonical Python frontend; native C11 execution additionally needs a C
compiler, while direct LLVM lowering needs Clang/LLVM.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import platform
import shutil
import sys
from pathlib import Path
from typing import Any, Sequence

from . import SOTLAS_LANG_VERSION, SOTLAS_VERSION
from .llvm_toolchain import LLVMToolchain, canonical_llvm_frontend


_MIN_PYTHON = (3, 10)


def _python_version() -> str:
    return ".".join(str(part) for part in sys.version_info[:3])


def _first_path(*candidates: str) -> Path | None:
    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return Path(resolved)
    return None


def collect_report() -> dict[str, Any]:
    """Collect deterministic preview capability information for this host."""
    python_ok = sys.version_info >= _MIN_PYTHON

    frontend_ok = False
    frontend_detail = "canonical frontend unavailable"
    try:
        frontend = canonical_llvm_frontend()
        frontend_ok = all(
            callable(getattr(frontend, name, None))
            for name in ("parse", "check", "emit_c")
        )
        frontend_detail = (
            "canonical sotlas_compile frontend loaded"
            if frontend_ok
            else "canonical frontend is missing parse/check/emit_c"
        )
    except Exception as error:  # pragma: no cover - exercised through mocks
        frontend_detail = f"{type(error).__name__}: {error}"

    llvm = LLVMToolchain()
    clang = llvm.find_tool("clang")
    llvm_ok = clang is not None
    llvm_version = llvm.get_version() if llvm_ok else None

    c_compiler = _first_path("clang", "gcc", "cc", "cl")
    if c_compiler is None and clang is not None:
        # LLVMToolchain also searches canonical install directories that may
        # not be present in PATH, especially on Windows.
        c_compiler = clang

    lsp_available = importlib.util.find_spec("sotlas_compile.lsp") is not None

    core_ready = python_ok and frontend_ok
    capabilities = {
        "check": core_ready,
        "emit_c11": core_ready,
        "native_c11": core_ready and c_compiler is not None,
        "llvm_native": core_ready and llvm_ok,
        "lsp": core_ready and lsp_available,
    }
    native_ready = capabilities["native_c11"] or capabilities["llvm_native"]

    return {
        "sotlas_version": SOTLAS_VERSION,
        "language_version": SOTLAS_LANG_VERSION,
        "host": {
            "platform": platform.system().lower() or sys.platform,
            "machine": platform.machine() or "unknown",
        },
        "status": "ready" if core_ready else "blocked",
        "core_ready": core_ready,
        "native_ready": native_ready,
        "checks": {
            "python": {
                "ok": python_ok,
                "version": _python_version(),
                "requirement": ">=3.10",
            },
            "canonical_frontend": {
                "ok": frontend_ok,
                "detail": frontend_detail,
            },
            "c_compiler": {
                "ok": c_compiler is not None,
                "path": str(c_compiler) if c_compiler is not None else None,
            },
            "llvm": {
                "ok": llvm_ok,
                "clang": str(clang) if clang is not None else None,
                "version": llvm_version,
            },
            "lsp": {
                "ok": lsp_available,
            },
        },
        "capabilities": capabilities,
    }


def _mark(ok: bool) -> str:
    return "OK" if ok else "--"


def render_text(report: dict[str, Any]) -> str:
    """Render the human-readable doctor report."""
    checks = report["checks"]
    capabilities = report["capabilities"]
    lines = [
        f"Sotlas doctor {report['sotlas_version']} (language {report['language_version']})",
        f"Host: {report['host']['platform']} / {report['host']['machine']}",
        "",
        f"[{_mark(checks['python']['ok'])}] Python {checks['python']['version']} ({checks['python']['requirement']})",
        f"[{_mark(checks['canonical_frontend']['ok'])}] Canonical frontend: {checks['canonical_frontend']['detail']}",
        f"[{_mark(checks['c_compiler']['ok'])}] C compiler: {checks['c_compiler']['path'] or 'not found'}",
        f"[{_mark(checks['llvm']['ok'])}] LLVM/Clang: {checks['llvm']['version'] or 'not found'}",
        f"[{_mark(checks['lsp']['ok'])}] LSP package",
        "",
        "Capabilities:",
    ]
    for name in ("check", "emit_c11", "native_c11", "llvm_native", "lsp"):
        lines.append(f"  {name:12} {'yes' if capabilities[name] else 'no'}")
    lines.extend(
        [
            "",
            f"Core preview: {'READY' if report['core_ready'] else 'BLOCKED'}",
            f"Native toolchain: {'READY' if report['native_ready'] else 'OPTIONAL TOOLS MISSING'}",
        ]
    )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sotlas-doctor",
        description="Diagnose the Sotlas preview installation and native toolchain.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit a deterministic JSON capability report.",
    )
    parser.add_argument(
        "--require-native",
        action="store_true",
        help="Return nonzero unless at least one native compilation path is available.",
    )
    parser.add_argument(
        "--require-llvm",
        action="store_true",
        help="Return nonzero unless the direct LLVM/Clang path is available.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = collect_report()
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(render_text(report))

    if not report["core_ready"]:
        return 1
    if args.require_native and not report["native_ready"]:
        return 2
    if args.require_llvm and not report["capabilities"]["llvm_native"]:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
