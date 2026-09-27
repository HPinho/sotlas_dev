"""Execute a checked scalar Flow plan through its generated C11 ABI."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from .flow_frontend import TypedFlowPlan
from .typed_ast import Phase1SemanticError


class FlowNativeRunError(Phase1SemanticError):
    """Raised when a checked Flow plan cannot run through the C11 backend."""


_SIGNED_TYPES = frozenset({"i8", "i16", "i32", "i64", "isize"})
_UNSIGNED_TYPES = frozenset({"u8", "u16", "u32", "u64", "usize"})


def _c_string(value: str) -> str:
    """Return an ASCII C string literal for a JSON string value."""
    return json.dumps(value, ensure_ascii=True)


def _render_caller(plan: TypedFlowPlan, entry_name: str, bootstrap) -> str:
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
    value_names: dict[str, str] = {}
    for index, stage in enumerate(stages):
        type_name = stage.result_type.name
        if type_name not in _SIGNED_TYPES | _UNSIGNED_TYPES | {"bool", "f32", "f64"}:
            raise FlowNativeRunError(
                f"C11 Flow runner does not support output type {type_name!r}"
            )
        value_name = f"stage_value_{index}"
        value_names[stage.name] = value_name
        declarations.append(f"  {stage.result_type.c()} {value_name} = 0;")
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
        if type_name == "bool":
            output.append(
                f'  fputs({value_name} ? "true" : "false", stdout);\n'
            )
        elif type_name in _SIGNED_TYPES:
            output.append(
                f'  printf("%lld", (long long){value_name});\n'
            )
        elif type_name in _UNSIGNED_TYPES:
            output.append(
                f'  printf("%llu", (unsigned long long){value_name});\n'
            )
        else:
            output.append(
                f"  if (isnan((double){value_name})) fputs(\"NaN\", stdout);\n"
                f"  else if (isinf((double){value_name})) fputs("
                f"signbit((double){value_name}) ? \"-Infinity\" : \"Infinity\", stdout);\n"
                f"  else printf(\"%.17g\", (double){value_name});\n"
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


def run_c11_flow(source: str, filename: str, flow_name: str) -> dict[str, object]:
    """Check, compile, and execute a Flow plan with the generated C11 backend.

    This path runs the same checked stage graph as the reference interpreter.
    It currently requires a local Clang or GCC installation and the C11 scalar
    Flow subset implemented by the canonical compiler.
    """
    from sotlas.llvm_toolchain import default_toolchain, canonical_llvm_frontend
    from .phase1_pipeline import analyze_source_phase1

    checked = analyze_source_phase1(source, filename=filename)
    plans = tuple(checked.flows or ())
    matches = tuple(plan for plan in plans if plan.name == flow_name)
    if len(matches) != 1:
        raise FlowNativeRunError(
            f"C11 Flow runner requires exactly one plan named {flow_name!r}"
        )
    plan = matches[0]
    frontend = canonical_llvm_frontend()
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
        f"sotlas_flow_{checked.parsed_module.name}_{flow_name}"
    )
    caller = _render_caller(plan, entry_name, frontend)

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
        executed = subprocess.run(
            [str(executable)], capture_output=True, text=True, check=False
        )
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
