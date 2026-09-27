#!/usr/bin/env python3
"""Render the reviewed phase-gate evidence manifest as Markdown."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "phase_gate_matrix.json"
OUTPUT = ROOT / "docs" / "phase_gate_matrix.md"


def render() -> str:
    manifest = json.loads(SOURCE.read_text(encoding="utf-8"))
    phases = manifest.get("phases")
    expected = list(range(18))
    if not isinstance(phases, list) or [item.get("phase") for item in phases] != expected:
        raise ValueError("phase gate manifest must declare phases 0 through 17 in order")

    lines = [
        "# Phase Gate Evidence Matrix",
        "",
        "This matrix is generated from `phase_gate_matrix.json`. The Python test suite",
        "checks that every listed gate exists; CI runs that suite and the dedicated",
        "phase subsets listed in `.github/workflows/ci.yml`. Evidence and boundaries",
        "describe the tested 1.0 subset. They are not claims of full language support.",
        "",
        "| Phase | Area | Gate files | Evidence exercised | Known boundary |",
        "|---:|---|---|---|---|",
    ]
    for item in phases:
        tests = ", ".join(f"`{Path(path).name}`" for path in item["tests"])
        lines.append(
            f"| {item['phase']} | {item['area']} | {tests} | "
            f"{item['evidence']} | {item['boundary']} |"
        )
    lines.extend([
        "",
        "## Cross-cutting validation",
        "",
        "The CI workflow also checks canonical `check` → C11 emission for every",
        "example marked `backend_contract`, runs native examples marked `native_run`,",
        "builds and installs the Python wheel, installs the packaged VS Code extension",
        "in a clean profile, and tests/lints/builds the website.",
        "",
        "The matrix intentionally calls out reference runtimes and prototype subsets.",
        "A passing test for one of those paths does not promote it to native, device,",
        "or general-purpose support.",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check", action="store_true",
        help="fail if the committed Markdown differs from the reviewed manifest",
    )
    args = parser.parse_args()
    rendered = render()
    if args.check:
        current = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else ""
        if current != rendered:
            print("phase gate matrix is stale; run scripts/generate_phase_gate_matrix.py", file=sys.stderr)
            return 1
        return 0
    OUTPUT.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
