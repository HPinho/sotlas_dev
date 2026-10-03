"""Execute a checked scalar Flow plan through its generated C11 ABI."""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from .flow_frontend import TypedFlowPlan, _c11_flow_abi_value_type
from .typed_ast import Phase1SemanticError


class FlowNativeRunError(Phase1SemanticError):
    """Raised when a checked Flow plan cannot run through the C11 backend."""


_SIGNED_TYPES = frozenset({"i8", "i16", "i32", "i64", "isize"})
_UNSIGNED_TYPES = frozenset({"u8", "u16", "u32", "u64", "usize"})


def _c_string(value: str) -> str:
    """Return an ASCII C string literal for a JSON string value."""
    return json.dumps(value, ensure_ascii=True)


def _render_json_value(
    output: list[str], expression: str, type_obj, structs, source_module,
) -> None:
    """Append C statements that print one checked C11 Flow value as JSON."""
    type_name = getattr(type_obj, "name", None)
    if type_name == "bool":
        output.append(f'  fputs({expression} ? "true" : "false", stdout);')
    elif type_name in _SIGNED_TYPES:
        output.append(f'  printf("%lld", (long long){expression});')
    elif type_name in _UNSIGNED_TYPES:
        output.append(f'  printf("%llu", (unsigned long long){expression});')
    elif type_name in {"f32", "f64"}:
        output.extend((
            f'  if (isnan((double){expression})) fputs("NaN", stdout);',
            f'  else if (isinf((double){expression})) fputs('
            f'signbit((double){expression}) ? "-Infinity" : "Infinity", stdout);',
            f'  else printf("%.17g", (double){expression});',
        ))
    else:
        declaration = structs.get(type_name)
        if declaration is None or not _c11_flow_abi_value_type(
            type_obj, source_module
        ):
            raise FlowNativeRunError(
                f"C11 Flow runner does not support output type {type_name!r}"
            )
        output.append("  fputc('{', stdout);")
        for index, field in enumerate(declaration.fields):
            if index:
                output.append("  fputc(',', stdout);")
            key = _c_string(json.dumps(field.name, ensure_ascii=True) + ":")
            output.append(f"  fputs({key}, stdout);")
            _render_json_value(
                output,
                f"({expression}).{field.name}",
                field.type,
                structs,
                source_module,
            )
        output.append("  fputc('}', stdout);")


def _render_caller(
    plan: TypedFlowPlan, entry_name: str, bootstrap, source_module,
) -> str:
    stage_by_name = {stage.name: stage for stage in plan.stages}
    abi_order = tuple(
        name for layer in plan.graph.parallel_stages for name in layer
    )
    stages = tuple(stage_by_name[name] for name in abi_order)
    if not stages or len(stages) != len(stage_by_name):
        raise FlowNativeRunError(f"C11 Flow {plan.name!r} has no stages")
    declarations: list[str] = []
    arguments: list[str] = []
    output: list[str] = []
    structs = {item.name: item for item in source_module.structs}
    value_names: dict[str, str] = {}
    for index, stage in enumerate(stages):
        type_name = stage.result_type.name
        if not _c11_flow_abi_value_type(stage.result_type, source_module):
            raise FlowNativeRunError(
                f"C11 Flow runner does not support output type {type_name!r}"
            )
        value_name = f"stage_value_{index}"
        value_names[stage.name] = value_name
        initializer = (
            "0"
            if type_name in _SIGNED_TYPES | _UNSIGNED_TYPES | {"bool", "f32", "f64"}
            else "{0}"
        )
        declarations.append(
            f"  {stage.result_type.c()} {value_name} = {initializer};"
        )
        arguments.append(f"&{value_name}")

    for display_index, stage in enumerate(
        sorted(plan.stages, key=lambda item: item.name)
    ):
        type_name = stage.result_type.name
        value_name = value_names[stage.name]
        output.append(
            f"  if ({display_index}) fputc(',', stdout);\n"
            f"  fputs({_c_string(json.dumps(stage.name, ensure_ascii=True) + ':')}, stdout);\n"
        )
        _render_json_value(
            output, value_name, stage.result_type, structs, source_module,
        )

    output_parameters = ", ".join(
        f"{stage.result_type.c()} *out_{bootstrap._c_ident(stage.name)}"
        for stage in stages
    )
    return "\n".join((
        "#define main sotlas_flow_embedded_source_main",
        '#include "flow.c"',
        "#undef main",
        "#include <math.h>",
        "#include <stdint.h>",
        "#include <stdio.h>",
        f"extern int32_t {entry_name}_outputs({output_parameters});",
        "int main(void) {",
        *declarations,
        f"  if ({entry_name}_outputs({', '.join(arguments)}) != 1) return 2;",
        '  fputc(\'{\', stdout);',
        *[line for statement in output for line in statement.splitlines()],
        '  fputs("}\\n", stdout);',
        "  return ferror(stdout) ? 3 : 0;",
        "}",
        "",
    ))


def run_c11_flow(
    source: str,
    filename: str,
    flow_name: str,
    *,
    timeout: float | None = None,
) -> dict[str, object]:
    """Check, compile, and execute a Flow plan with the generated C11 backend.

    This path runs the same checked stage graph as the reference interpreter.
    It currently requires a local Clang or GCC installation and the C11 scalar
    scalar, plain-record, or trivial linear-owner subset implemented by the
    canonical compiler.
    """
    from sotlas.llvm_toolchain import default_toolchain, canonical_llvm_frontend
    from .flow_frontend import validate_flow_execution_source

    if timeout is not None and (not math.isfinite(timeout) or timeout <= 0):
        raise FlowNativeRunError(
            "C11 Flow timeout must be a finite positive number"
        )

    frontend = canonical_llvm_frontend()
    try:
        checked = frontend.parse(source, filename=filename)
        frontend.check(checked)
    except Exception as error:
        raise FlowNativeRunError(f"C11 Flow source check failed: {error}") from error
    plans = tuple(getattr(checked, "typed_flows", ()) or ())
    matches = tuple(plan for plan in plans if plan.name == flow_name)
    if len(matches) != 1:
        raise FlowNativeRunError(
            f"C11 Flow runner requires exactly one plan named {flow_name!r}"
        )
    plan = matches[0]
    try:
        validate_flow_execution_source(checked, flow_name, frontend)
    except ValueError as error:
        raise FlowNativeRunError(str(error)) from error
    try:
        c_source = frontend.compile_source(source, filename)
    except Exception as error:
        raise FlowNativeRunError(f"C11 Flow compilation failed: {error}") from error

    compiler = default_toolchain.find_tool("clang") or shutil.which("gcc")
    if compiler is None:
        raise FlowNativeRunError(
            "C11 Flow execution requires Clang or GCC on PATH"
        )
    entry_name = frontend._c_ident(
        f"sotlas_flow_{checked.name}_{flow_name}"
    )
    caller = _render_caller(
        plan, entry_name, frontend, checked
    )

    with tempfile.TemporaryDirectory(prefix="sotlas-flow-c11-") as temporary:
        root = Path(temporary)
        generated_path = root / "flow.c"
        caller_path = root / "caller.c"
        executable = root / ("flow.exe" if os.name == "nt" else "flow")
        generated_path.write_text(c_source, encoding="utf-8")
        caller_path.write_text(caller, encoding="utf-8")
        compiled = subprocess.run(
            [str(compiler), "-std=c11", "-Wall", "-Wextra",
             str(caller_path), "-o", str(executable)],
            capture_output=True,
            text=True,
            check=False,
        )
        if compiled.returncode != 0:
            detail = compiled.stderr.strip() or compiled.stdout.strip()
            raise FlowNativeRunError(
                f"C11 Flow native build failed: {detail}"
            )
        try:
            executed = subprocess.run(
                [str(executable)], capture_output=True, text=True, check=False,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as error:
            raise FlowNativeRunError(
                f"C11 Flow execution exceeded the {timeout:g} second timeout; "
                "the native runner process was terminated"
            ) from error
        if executed.returncode != 0:
            detail = executed.stderr.strip() or executed.stdout.strip()
            raise FlowNativeRunError(
                f"C11 Flow native execution failed (exit {executed.returncode}): {detail}"
            )
        try:
            outputs = json.loads(executed.stdout)
        except json.JSONDecodeError as error:
            raise FlowNativeRunError(
                "C11 Flow runner produced invalid output JSON"
            ) from error
    if not isinstance(outputs, dict) or set(outputs) != {
        stage.name for stage in plan.stages
    }:
        raise FlowNativeRunError("C11 Flow runner returned an incomplete stage set")
    return outputs


__all__ = ["FlowNativeRunError", "run_c11_flow"]
