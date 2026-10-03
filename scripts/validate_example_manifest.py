"""Validate the example manifest against the checked-in example tree."""
from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
import sys


ALLOWED_STATUSES = {"SUPPORTED", "EXPERIMENTAL", "PROTOTYPE", "DESIGNED", "PLANNED"}


def validate_manifest(examples_root: Path) -> list[str]:
    """Return manifest errors, allowing multiple examples within a directory."""
    manifest_path = examples_root / "manifest.json"
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return [f"cannot read {manifest_path}: {error}"]

    items = data.get("examples") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return ["examples/manifest.json must contain an 'examples' list"]

    errors: list[str] = []
    ids = [item.get("id") for item in items if isinstance(item, dict)]
    if len(ids) != len(items):
        errors.append("every manifest example must be an object")
    if any(not isinstance(item_id, str) or not item_id for item_id in ids):
        errors.append("every manifest example must have a non-empty string id")
    if len(ids) != len(set(ids)):
        errors.append("duplicate example id in examples/manifest.json")

    numbered = {
        path.name
        for path in examples_root.iterdir()
        if path.is_dir() and len(path.name) >= 2 and path.name[:2].isdigit()
    }
    covered_roots: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        item_id = item.get("id")
        entry = item.get("entry")
        if item.get("status") not in ALLOWED_STATUSES:
            errors.append(f"invalid status for {item_id}: {item.get('status')}")
        if not isinstance(entry, str) or not entry:
            errors.append(f"missing entry for {item_id}: {entry}")
            continue
        entry_path = PurePosixPath(entry)
        if entry_path.is_absolute() or ".." in entry_path.parts:
            errors.append(f"entry escapes examples directory for {item_id}: {entry}")
            continue
        parts = entry_path.parts
        if not parts or parts[0] != "examples" or len(parts) < 2:
            errors.append(f"entry must be rooted under examples/ for {item_id}: {entry}")
            continue
        example_root = parts[1]
        if example_root not in numbered:
            errors.append(f"entry references unknown example directory for {item_id}: {entry}")
            continue
        if isinstance(item_id, str) and item_id != example_root and not item_id.startswith(example_root + "_"):
            errors.append(
                f"example id {item_id!r} must match its directory {example_root!r} "
                "or use it as a prefix"
            )
        covered_roots.add(example_root)
        if not (examples_root.parent / Path(*parts)).is_file() and not (
            examples_root.parent / Path(*parts)
        ).is_dir():
            errors.append(f"missing entry for {item_id}: {entry}")
        if item.get("native_run") is True and item.get("backend_contract") is not True:
            errors.append(f"native-run example must also satisfy backend contract: {item_id}")

    if covered_roots != numbered:
        errors.append(
            "manifest example-directory coverage mismatch: "
            f"unlisted={sorted(numbered - covered_roots)}, "
            f"unknown={sorted(covered_roots - numbered)}"
        )
    return errors


def main() -> int:
    root = Path(__file__).resolve().parents[1] / "examples"
    errors = validate_manifest(root)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("example manifest: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
