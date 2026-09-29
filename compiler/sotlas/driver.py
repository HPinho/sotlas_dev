"""Public Sotlas command driver with source-profile target inference.

The existing CLI remains responsible for parsing commands and performing the
actual build. This thin driver only reconciles a source-level execution profile
with the concrete machine target before delegating, so ``target barecore;``
cannot silently fall back to a hosted build.
"""
from __future__ import annotations

from pathlib import Path
import sys

from . import cli
from .execution_target import ExecutionTargetError
from .llvm_toolchain import canonical_llvm_frontend
from .source_target import resolve_source_execution_target


_OPTIONS_WITH_VALUE = frozenset({
    "-o",
    "--output",
    "--target",
    "--cpu-feature",
    "--backend",
    "--cc",
    "--linker",
    "--entry",
    "--emit",
})


def _option_value(argv: list[str], option: str) -> str | None:
    for index, token in enumerate(argv):
        if token == option:
            if index + 1 < len(argv):
                return argv[index + 1]
            return None
        prefix = option + "="
        if token.startswith(prefix):
            return token[len(prefix):]
    return None


def _option_values(argv: list[str], option: str) -> tuple[str, ...]:
    values: list[str] = []
    for index, token in enumerate(argv):
        if token == option:
            if index + 1 < len(argv):
                values.append(argv[index + 1])
            continue
        prefix = option + "="
        if token.startswith(prefix):
            values.append(token[len(prefix):])
    return tuple(values)


def _compile_source_index(argv: list[str]) -> int | None:
    if len(argv) < 3 or argv[1] != "compile":
        return None

    skip_next = False
    for index in range(2, len(argv)):
        token = argv[index]
        if skip_next:
            skip_next = False
            continue
        if token in _OPTIONS_WITH_VALUE:
            skip_next = True
            continue
        if token.startswith("-"):
            continue
        return index
    return None


def prepare_argv(argv: list[str]) -> list[str]:
    """Return argv with an inferred compile target when the source requires it."""

    prepared = list(argv)
    source_index = _compile_source_index(prepared)
    if source_index is None:
        return prepared

    source_path = Path(prepared[source_index])
    if not source_path.is_file():
        return prepared

    source = source_path.read_text(encoding="utf-8")
    frontend = canonical_llvm_frontend()
    try:
        module = frontend.parse(source, filename=str(source_path))
    except frontend.SotlasBootstrapError:
        # Preserve the canonical CLI's diagnostics for malformed source.
        return prepared

    profile_plan = frontend.plan_target_profile(module)
    requested_target = _option_value(prepared[2:], "--target")
    cpu_features = _option_values(prepared[2:], "--cpu-feature")
    target_plan = resolve_source_execution_target(
        profile_plan.profile,
        source_profile_explicit=profile_plan.explicit,
        requested_target=requested_target,
        cpu_features=cpu_features,
    )

    if requested_target is None and target_plan.selected_target != "host":
        prepared.extend(["--target", target_plan.selected_target])
    return prepared


def main() -> int:
    original_argv = sys.argv
    try:
        try:
            sys.argv = prepare_argv(list(original_argv))
        except ExecutionTargetError as error:
            print(f"sotlas: erro de target: {error}", file=sys.stderr)
            return 2
        return cli.main()
    finally:
        sys.argv = original_argv


__all__ = ["main", "prepare_argv"]
