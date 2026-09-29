"""Public Sotlas command driver with source-profile target inference.

The existing CLI remains responsible for parsing commands and performing the
actual build. This thin driver reconciles source execution semantics with the
concrete machine target and artifact kind before delegation, so ``barecore``
can never silently fall back to a hosted target or hosted executable link.
"""
from __future__ import annotations

from pathlib import Path
import sys

from . import cli
from .execution_target import ExecutionTargetError
from .llvm_toolchain import canonical_llvm_frontend, default_toolchain
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
_ARTIFACT_FLAGS = {
    "--emit-c": "c",
    "--emit-obj": "obj",
    "--emit-llvm": "llvm",
    "--emit-asm": "asm",
}
_ARTIFACT_SUFFIXES = {
    ".c": "c",
    ".o": "obj",
    ".obj": "obj",
    ".ll": "llvm",
    ".s": "asm",
    ".asm": "asm",
}


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


def _command_source_index(argv: list[str], command: str) -> int | None:
    if len(argv) < 3 or argv[1] != command:
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


def _explicit_artifact_kind(argv: list[str]) -> str | None:
    for flag, kind in _ARTIFACT_FLAGS.items():
        if flag in argv:
            return kind
    emit = _option_value(argv, "--emit")
    if emit == "asm":
        return "asm"
    output = _option_value(argv, "--output") or _option_value(argv, "-o")
    if output is None:
        return None
    return _ARTIFACT_SUFFIXES.get(Path(output).suffix.lower(), "exe")


def _parse_source_profile(source_path: Path):
    source = source_path.read_text(encoding="utf-8")
    frontend = canonical_llvm_frontend()
    try:
        module = frontend.parse(source, filename=str(source_path))
    except frontend.SotlasBootstrapError:
        return None
    return frontend.plan_target_profile(module)


def _prepare_compile_argv(argv: list[str], source_index: int) -> list[str]:
    prepared = list(argv)
    source_path = Path(prepared[source_index])
    if not source_path.is_file():
        return prepared

    profile_plan = _parse_source_profile(source_path)
    if profile_plan is None:
        # Preserve the canonical CLI's diagnostics for malformed source.
        return prepared

    options = prepared[2:]
    requested_target = _option_value(options, "--target")
    cpu_features = _option_values(options, "--cpu-feature")
    target_plan = resolve_source_execution_target(
        profile_plan.profile,
        source_profile_explicit=profile_plan.explicit,
        requested_target=requested_target,
        cpu_features=cpu_features,
    )

    if requested_target is None and target_plan.selected_target != "host":
        prepared.extend(["--target", target_plan.selected_target])

    if profile_plan.profile != "barecore":
        return prepared

    artifact_kind = _explicit_artifact_kind(prepared[2:])
    linker = _option_value(prepared[2:], "--linker")

    if artifact_kind is None:
        if linker is None:
            artifact_kind = "obj"
            prepared.append("--emit-obj")
        elif linker == "internal":
            artifact_kind = "exe"
        else:
            raise ExecutionTargetError(
                "barecore executable linking requires --linker internal until "
                "a freestanding external-linker contract is implemented"
            )

    if artifact_kind == "exe" and linker != "internal":
        raise ExecutionTargetError(
            "barecore executable linking requires --linker internal until "
            "a freestanding external-linker contract is implemented"
        )

    if artifact_kind == "obj":
        if linker == "gcc":
            raise ExecutionTargetError(
                "barecore object emission cannot use --linker gcc; use the "
                "LLVM object path or --emit-c"
            )
        if not default_toolchain.is_available():
            raise ExecutionTargetError(
                "barecore object emission requires Clang/LLVM; use --emit-c "
                "to emit portable freestanding C11 when LLVM is unavailable"
            )

    return prepared


def _prepare_run_argv(argv: list[str], source_index: int) -> list[str]:
    prepared = list(argv)
    source_path = Path(prepared[source_index])
    if not source_path.is_file():
        return prepared
    profile_plan = _parse_source_profile(source_path)
    if profile_plan is None:
        return prepared
    if profile_plan.profile == "barecore":
        raise ExecutionTargetError(
            "barecore source cannot be executed as a hosted process with 'sotlas run'"
        )
    if profile_plan.profile == "web":
        raise ExecutionTargetError(
            "web source profile cannot be executed by the native 'sotlas run' driver"
        )
    return prepared


def prepare_argv(argv: list[str]) -> list[str]:
    """Return argv reconciled with source-profile target and artifact semantics."""

    compile_source = _command_source_index(argv, "compile")
    if compile_source is not None:
        return _prepare_compile_argv(argv, compile_source)

    run_source = _command_source_index(argv, "run")
    if run_source is not None:
        return _prepare_run_argv(argv, run_source)

    return list(argv)


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
