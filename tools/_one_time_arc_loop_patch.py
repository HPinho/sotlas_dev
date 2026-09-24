from pathlib import Path

path = Path("compiler/sotlas_compile/bootstrap.py")
text = path.read_text(encoding="utf-8")
needle = (
    "                    for d in loop_defers:\n"
    "                        if d.body is not None:\n"
)
replacement = (
    "                    for d in loop_defers:\n"
    "                        if (\n"
    "                            loop_shared_cleanup_entry_count is not None\n"
    "                            and isinstance(d.value, Call)\n"
    "                            and d.value.callee.startswith(\"__sotlas_shared_release_\")\n"
    "                        ):\n"
    "                            continue\n"
    "                        if d.body is not None:\n"
)
count = text.count(needle)
if count != 2:
    raise SystemExit(f"expected exactly 2 loop defer sites, found {count}")
path.write_text(text.replace(needle, replacement), encoding="utf-8")
