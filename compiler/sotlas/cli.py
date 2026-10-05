"""Sotlas CLI — driver canônico e unificado para a linguagem Sotlas.

Uso:
    sotlas compile arquivo.sotlas [-o saída] [--target x86_64-freestanding] [--emit-c]
    sotlas check   arquivo.sotlas
    sotlas run     arquivo.sotlas
    sotlas dump-ast arquivo.sotlas
    sotlas dump-sir arquivo.sotlas
    sotlas sir-report arquivo.sotlas
    sotlas dump-llvm arquivo.sotlas [--debug]
    sotlas fmt     arquivo.sotlas [--check]
    sotlas lint    arquivo.sotlas
    sotlas doc     arquivo.sotlas [-o saída.md]
    sotlas new     meu_projeto [--lib]
    sotlas init    [--lib]
    sotlas build   [--path .]
    sotlas add     dependencia [--version "^0.1.0"]
    sotlas lsp     [--stdio]
    sotlas test    [--pattern PATTERN]
    sotlas version
"""
from __future__ import annotations
import argparse
import json
import math
import sys
import subprocess
import tempfile
import threading
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from sotlas import SOTLAS_VERSION
from sotlas.llvm_toolchain import canonical_llvm_frontend
from sotlas.execution_target import ExecutionTargetError, resolve_execution_target
from sotlas.sir import SIRGenerator

production_frontend = canonical_llvm_frontend()
compile_source = production_frontend.compile_source
SotlasBootstrapError = production_frontend.SotlasBootstrapError


def _compile_cli_source(source_text: str, source_name: str) -> str:
    """Compile through the project-aware canonical C11 path used by run."""
    from sotlas.llvm_toolchain import LLVMToolchain
    return LLVMToolchain.compile_c11_source(source_text, source_name)

SOTLAS_EXT = ".sotlas"
_TARGET_CHOICES = (
    "host", "x86_64-freestanding", "x86_64-unknown-none-elf",
    "x86_64-pc-none", "x86_64-unknown-linux-gnu",
    "x86_64-pc-windows-msvc", "x86_64-apple-darwin",
    "aarch64-freestanding", "aarch64-unknown-none-elf",
    "aarch64-unknown-linux-gnu", "aarch64-pc-windows-msvc",
    "aarch64-apple-darwin",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sotlas",
        description=f"Compilador e Driver Sotlas v{SOTLAS_VERSION}",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # Subcomando: compile
    cp = sub.add_parser("compile", help=f"Compila um arquivo {SOTLAS_EXT} para binário ou C11")
    cp.add_argument("source", help=f"Arquivo fonte {SOTLAS_EXT}")
    cp.add_argument("-o", "--output", default=None, help="Arquivo de saída")
    cp.add_argument(
        "--target",
        choices=_TARGET_CHOICES,
        default="host",
        help="Alvo de compilação",
    )
    cp.add_argument("--cpu-feature", action="append", default=[], metavar="FEATURE", help="Habilita feature de CPU do target; pode ser repetida")
    cp.add_argument(
        "--emit-c",
        action="store_true",
        help="Emite apenas o C11 intermediário (não invoca o compilador C)",
    )
    cp.add_argument(
        "--emit-obj",
        action="store_true",
        help="Emite diretamente código objeto nativo (.o / .obj) via LLVM",
    )
    cp.add_argument(
        "--emit-llvm",
        action="store_true",
        help="Emite código LLVM IR textual (.ll) com DWARF",
    )
    cp.add_argument(
        "--emit-asm",
        action="store_true",
        help="Emite assembly nativo do subset LLVM SIR verificado (.s)",
    )
    cp.add_argument(
        "--emit",
        choices=["asm"],
        default=None,
        help="Formato adicional de saída (atualmente: asm)",
    )
    cp.add_argument(
        "--backend",
        choices=["native", "llvm", "c11", "sotlas-x86_64"],
        default="native",
        help="Compilation backend (native Sotlas, LLVM, legacy C11, or the Sotlas-owned x86-64 preview)",
    )
    cp.add_argument(
        "--cc",
        default="gcc",
        help="Compilador C alternativo a invocar no modo C11 (padrão: gcc)",
    )
    cp.add_argument(
        "--linker",
        choices=["internal", "lld", "gcc", "auto"],
        default="auto",
        help=(
            "Linker a usar na fase final:\n"
            "  internal — linker ELF64 interno (sem LLVM/binutils, Linux ou bare-metal x86_64);\n"
            "  lld      — usa lld/clang do LLVM;\n"
            "  gcc      — usa gcc/ld do sistema;\n"
            "  auto     — detecta o melhor disponível (padrão)"
        ),
    )
    cp.add_argument(
        "--entry",
        default=None,
        help="Símbolo de entry point para o linker interno (padrão: _start para freestanding, main_entry ou main para hosted)",
    )

    # Subcomando: check
    chk = sub.add_parser("check", help="Valida pelo pipeline canônico completo sem gravar artefatos")
    chk.add_argument("source", help=f"Arquivo fonte {SOTLAS_EXT}")

    # Subcomando: run
    rn = sub.add_parser("run", help="Compila e executa um programa Sotlas diretamente")
    rn.add_argument("source", help=f"Arquivo fonte {SOTLAS_EXT}")
    rn.add_argument("--cc", default="gcc", help="Compilador C a invocar (padrão: gcc)")

    # Subcomando: dump-ast
    dast = sub.add_parser("dump-ast", help="Exibe a estrutura da AST analisada")
    dast.add_argument("source", help=f"Arquivo fonte {SOTLAS_EXT}")

    # Subcomando: dump-sir
    dsir = sub.add_parser("dump-sir", help="Exibe o protótipo SIR (não é lowering de produção)")
    dsir.add_argument("source", help=f"Arquivo fonte {SOTLAS_EXT}")

    # Subcomando: contract-report
    crep = sub.add_parser(
        "contract-report",
        help="Emite relatório JSON de provas e contratos de função verificados",
    )
    crep.add_argument("source", help=f"Arquivo fonte {SOTLAS_EXT}")

    flow_report = sub.add_parser(
        "flow-report",
        help="Emite JSON determinístico dos planos Flow reconciliados com o SIR",
    )
    flow_report.add_argument("source", help=f"Arquivo fonte {SOTLAS_EXT}")

    flow_run = sub.add_parser(
        "flow-run",
        help="Run a checked Flow plan on the CPU",
    )
    flow_run.add_argument("source", help=f"Source file {SOTLAS_EXT}")
    flow_run.add_argument("--flow", required=True, help="Name of the Flow plan to execute")
    flow_run.add_argument(
        "--workers", type=int, default=None,
        help="Maximum concurrent independent stages (default: runtime setting)",
    )
    flow_run.add_argument(
        "--backend", choices=("reference", "c11"), default="reference",
        help="Execution backend: reference scheduler or a compiled native C11 runner",
    )
    flow_run.add_argument(
        "--timeout", type=float, default=None, metavar="SECONDS",
        help="Cancel Flow execution after this many seconds",
    )

    sir_report = sub.add_parser(
        "sir-report",
        help="Emite inventário JSON do subset SIR canônico validado",
    )
    sir_report.add_argument("source", help=f"Arquivo fonte {SOTLAS_EXT}")

    target_ir_report = sub.add_parser(
        "target-ir-report",
        help="Emite o Target IR v1 derivado do subset SIR canônico validado",
    )
    target_ir_report.add_argument("source", help=f"Arquivo fonte {SOTLAS_EXT}")

    allocation_report = sub.add_parser(
        "register-allocation-report",
        help="Report linear liveness/allocation for straight-line scalar functions",
    )
    allocation_report.add_argument("source", help=f"Arquivo fonte {SOTLAS_EXT}")
    allocation_report.add_argument(
        "--registers", type=int, default=4,
        help="Number of virtual register slots in the preview (default: 4)",
    )

    stack_report = sub.add_parser(
        "stack-layout-report",
        help="Report target-neutral scalar local stack slots from checked Target IR",
    )
    stack_report.add_argument("source", help=f"Source file {SOTLAS_EXT}")
    stack_report.add_argument(
        "--alignment", type=int, default=16,
        help="Abstract frame alignment in bytes (default: 16; must be a power of two)",
    )

    liveness_report = sub.add_parser(
        "target-ir-liveness-report",
        help="Report CFG liveness and SSA interference from checked Target IR",
    )
    liveness_report.add_argument("source", help=f"Source file {SOTLAS_EXT}")

    source_map_report = sub.add_parser(
        "target-ir-source-map-report",
        help="Report source-stable locations preserved by checked Target IR",
    )
    source_map_report.add_argument("source", help=f"Source file {SOTLAS_EXT}")

    target_report = sub.add_parser(
        "target-report",
        help="Emite JSON determinístico do contrato do target selecionado",
    )
    target_report.add_argument(
        "--target",
        choices=_TARGET_CHOICES,
        default="host",
        help="Target a inspecionar",
    )
    target_report.add_argument(
        "--cpu-feature", action="append", default=[], metavar="FEATURE",
        help="Habilita feature; pode ser repetida",
    )

    # Subcomando: dump-llvm
    dllvm = sub.add_parser("dump-llvm", help="Emite LLVM IR experimental a partir do protótipo SIR")
    dllvm.add_argument("source", help=f"Arquivo fonte {SOTLAS_EXT}")
    dllvm.add_argument("--debug", action="store_true", help="Emite metadados de depuração DWARF")

    # Subcomando: fmt
    fmt_p = sub.add_parser("fmt", help="Formata arquivos de código-fonte Sotlas")
    fmt_p.add_argument("target", help="Arquivo ou diretório a formatar")
    fmt_p.add_argument("--check", action="store_true", help="Apenas verifica a formatação sem alterar arquivos")

    # Subcomando: lint
    lint_p = sub.add_parser("lint", help="Executa o linter de boas práticas e segurança")
    lint_p.add_argument("target", help="Arquivo ou diretório a analisar")

    # Subcomando: doc
    doc_p = sub.add_parser("doc", help="Gera documentação Markdown a partir de comentários '///'")
    doc_p.add_argument("target", help="Arquivo fonte .sotlas")
    doc_p.add_argument("-o", "--output", default=None, help="Arquivo de saída Markdown")

    # Subcomando: new
    new_p = sub.add_parser("new", help="Cria um novo projeto Sotlas com Sotlas.toml")
    new_p.add_argument("name", help="Nome do projeto")
    new_p.add_argument("--lib", action="store_true", help="Cria uma biblioteca em vez de binário executável")

    # Subcomando: init
    init_p = sub.add_parser("init", help="Inicializa um pacote Sotlas no diretório atual")
    init_p.add_argument("--lib", action="store_true", help="Inicializa como biblioteca")

    # Subcomando: build
    build_p = sub.add_parser("build", help="Compila um pacote Sotlas lendo o Sotlas.toml")
    build_p.add_argument("--path", default=".", help="Diretório do projeto (padrão: .)")

    # Subcomando: add
    add_p = sub.add_parser("add", help="Adiciona uma dependência ao Sotlas.toml")
    add_p.add_argument("dependency", help="Nome da dependência")
    add_p.add_argument("--version", default="^0.1.0", help="Especificação de versão (padrão: ^0.1.0)")

    # Subcomando: lsp
    lsp_p = sub.add_parser("lsp", help="Inicia o servidor de linguagem (Language Server Protocol)")
    lsp_p.add_argument("--stdio", action="store_true", default=True, help="Modo stdio padrão")

    # Subcomando: test
    tst = sub.add_parser("test", help="Executa a suíte de testes unitários da linguagem")
    tst.add_argument("-p", "--pattern", default="test_*.py", help="Padrão de arquivos de teste")

    # Subcomando: repl
    sub.add_parser("repl", help="Inicia o terminal interativo (REPL) da linguagem Sotlas")

    # Subcomando: studio
    std_p = sub.add_parser("studio", help="Inicia o ambiente Sotlas Studio / Web Playground")
    std_p.add_argument("--port", type=int, default=8080, help="Porta TCP do servidor (padrão: 8080)")
    std_p.add_argument("--no-browser", action="store_true", help="Não abre automaticamente o navegador")

    # Subcomando: dump-wasm
    dwasm = sub.add_parser("dump-wasm", help="Emite código WebAssembly Text (.wat) diretamente (bypass de C)")
    dwasm.add_argument("source", help=f"Arquivo fonte {SOTLAS_EXT}")

    # Subcomando: bootstrap
    boot_p = sub.add_parser("bootstrap", help="Compila o compilador auto-hospedado gerando sotlas_native.exe")
    boot_p.add_argument("-o", "--output", default=None, help="Caminho do executável nativo a gerar")
    boot_p.add_argument("--no-verify", action="store_true", help="Pula o teste de verificação da auto-hospedagem")

    # Subcomando: version
    sub.add_parser("version", help="Exibe a versão do compilador")

    return parser


_build_parser = build_parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.cmd == "version":
        print(f"Sotlas {SOTLAS_VERSION}")
        return 0
    if args.cmd == "check":
        return _run_check(args.source)
    if args.cmd == "compile":
        return _run_compile(args)
    if args.cmd == "run":
        return _run_exec(args)
    if args.cmd == "dump-ast":
        return _run_dump_ast(args.source)
    if args.cmd == "dump-sir":
        return _run_dump_sir(args.source)
    if args.cmd == "contract-report":
        return _run_contract_report(args.source)
    if args.cmd == "flow-report":
        return _run_flow_report(args.source)
    if args.cmd == "flow-run":
        return _run_flow_run(
            args.source, args.flow, args.workers, args.backend, args.timeout
        )
    if args.cmd == "sir-report":
        return _run_sir_report(args.source)
    if args.cmd == "target-ir-report":
        return _run_target_ir_report(args.source)
    if args.cmd == "register-allocation-report":
        return _run_register_allocation_report(args.source, args.registers)
    if args.cmd == "stack-layout-report":
        return _run_stack_layout_report(args.source, args.alignment)
    if args.cmd == "target-ir-liveness-report":
        return _run_target_ir_liveness_report(args.source)
    if args.cmd == "target-ir-source-map-report":
        return _run_target_ir_source_map_report(args.source)
    if args.cmd == "target-report":
        return _run_target_report(args.target, args.cpu_feature)
    if args.cmd == "dump-llvm":
        return _run_dump_llvm(args.source, emit_debug=args.debug)
    if args.cmd == "fmt":
        return _run_fmt(args)
    if args.cmd == "lint":
        return _run_lint(args.target)
    if args.cmd == "doc":
        return _run_doc(args)
    if args.cmd == "new":
        return _run_new(args)
    if args.cmd == "init":
        return _run_init(args)
    if args.cmd == "build":
        return _run_build(args)
    if args.cmd == "add":
        return _run_add(args)
    if args.cmd == "lsp":
        return _run_lsp()
    if args.cmd == "test":
        return _run_tests(args.pattern)
    if args.cmd == "repl":
        from sotlas.repl import start_repl
        return start_repl()
    if args.cmd == "studio":
        from sotlas.studio import start_studio
        return start_studio(port=args.port, open_browser=not args.no_browser)
    if args.cmd == "dump-wasm":
        return _run_dump_wasm(args.source)
    if args.cmd == "bootstrap":
        return _run_bootstrap(args)
    return 1


def _read_source(source_path: str) -> tuple[Path, str] | None:
    src = Path(source_path)
    if not src.exists():
        print(f"sotlas: erro: arquivo não encontrado: {source_path}", file=sys.stderr)
        return None
    if src.suffix not in (SOTLAS_EXT, ".st"):
        print(
            f"sotlas: aviso: extensão não reconhecida '{src.suffix}' (esperado {SOTLAS_EXT})",
            file=sys.stderr,
        )
    return src, src.read_text(encoding="utf-8")


def _run_check(source_path: str) -> int:
    loaded = _read_source(source_path)
    if loaded is None:
        return 1
    _, text = loaded
    try:
        # `check` e `compile` compartilham o mesmo contrato de aceitação.
        # O C11 gerado permanece apenas em memória neste comando.
        _compile_cli_source(text, source_path)
    except SotlasBootstrapError as error:
        print(f"sotlas: erro: {error}", file=sys.stderr)
        return 1
    print(f"sotlas: ok — {source_path}")
    return 0


def _run_dump_ast(source_path: str) -> int:
    loaded = _read_source(source_path)
    if loaded is None:
        return 1
    _, text = loaded
    try:
        module = production_frontend.parse(text, filename=source_path)
        print(f"Module: {module.name}")
        for fn in module.functions:
            sys_tag = "@system " if getattr(fn, "is_system", False) else ""
            print(f"  {sys_tag}fn {fn.name}({len(fn.params)} params) -> {fn.result}")
        for s in module.structs:
            print(f"  struct {s.name} ({len(s.fields)} fields)")
        for e in module.enums:
            print(f"  enum {e.name} ({len(e.variants)} variants)")
    except SotlasBootstrapError as error:
        print(f"sotlas: erro: {error}", file=sys.stderr)
        return 1
    return 0


def _run_dump_sir(source_path: str) -> int:
    loaded = _read_source(source_path)
    if loaded is None:
        return 1
    _, text = loaded
    try:
        module = production_frontend.parse(text, filename=source_path)
        gen = SIRGenerator()
        sir_mod = gen.generate_from_ast(module)
        print(sir_mod.dump())
    except SotlasBootstrapError as error:
        print(f"sotlas: erro: {error}", file=sys.stderr)
        return 1
    return 0


def _run_contract_report(source_path: str) -> int:
    loaded = _read_source(source_path)
    if loaded is None:
        return 1
    _, text = loaded
    try:
        from sotlas_compile import (
            analyze_source_phase1,
            build_canonical_checked_ownership_sir,
        )

        checked = analyze_source_phase1(text, filename=source_path)
        checked_sir, _ = build_canonical_checked_ownership_sir(checked)
        module = checked_sir.module
        report = {
            "schema": "sotlas.contract-report.v1",
            "module": module.name,
            "proofs": [
                {
                    "kind": "requires_call",
                    "function": proof.function,
                    "line": proof.line,
                    "column": proof.column,
                    "predicate": proof.predicate,
                    "arguments": [
                        {"name": name, "value": value}
                        for name, value in proof.arguments
                    ],
                    "refinements": list(proof.refinements),
                    "status": "proven",
                }
                for proof in module.contract_proofs
            ],
            "runtime_preconditions": [
                {"function": item.function, "predicate": item.predicate}
                for item in module.contract_preconditions
            ],
            "runtime_postconditions": [
                {"function": item.function, "predicate": item.predicate}
                for item in module.contract_postconditions
            ],
        }
        json.dump(report, sys.stdout, ensure_ascii=False, sort_keys=True, indent=2)
        sys.stdout.write("\n")
    except Exception as error:
        print(f"sotlas: erro ao gerar contract report: {error}", file=sys.stderr)
        return 1
    return 0


def _run_flow_report(source_path: str) -> int:
    loaded = _read_source(source_path)
    if loaded is None:
        return 1
    _, text = loaded
    try:
        from sotlas_compile import (
            analyze_source_phase1,
            build_canonical_checked_ownership_sir,
            validate_sir_flow_plans,
        )

        checked = analyze_source_phase1(text, filename=source_path)
        checked_sir, _ = build_canonical_checked_ownership_sir(checked)
        module = checked_sir.module
        plans = validate_sir_flow_plans(module)
        report = {
            "schema": "sotlas.flow-report.v1",
            "module": module.name,
            "flows": [
                {
                    "name": plan.name,
                    "schedule": [list(batch) for batch in plan.parallel_stages],
                    "stages": [
                        {
                            "name": stage.name,
                            "function": stage.function,
                            "result_type": stage.result_type,
                            "effects": list(stage.effects),
                            "arguments": [
                                {
                                    "parameter_index": argument.parameter_index,
                                    "parameter": argument.parameter_name,
                                    "type": argument.type_name,
                                    "producer_stage": argument.value.producer_stage,
                                    "producer_function": argument.value.producer_function,
                                }
                                for argument in stage.arguments
                            ],
                        }
                        for stage in plan.stages
                    ],
                }
                for plan in plans
            ],
        }
        print(json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    except Exception as error:
        print(f"sotlas: erro ao gerar flow report: {error}", file=sys.stderr)
        return 1
    return 0


def _run_flow_run(
    source_path: str,
    flow_name: str,
    workers: int | None,
    backend: str = "reference",
    timeout: float | None = None,
) -> int:
    loaded = _read_source(source_path)
    if loaded is None:
        return 1
    _, text = loaded
    try:
        if timeout is not None and (not math.isfinite(timeout) or timeout <= 0):
            raise ValueError("--timeout must be a finite positive number")
        if backend == "c11":
            if workers is not None:
                raise ValueError(
                    "--workers applies to the reference backend; C11 Flow runs "
                    "in deterministic serial order"
                )
            from sotlas_compile.flow_native_runner import run_c11_flow

            outputs = run_c11_flow(
                text, source_path, flow_name, timeout=timeout
            )
        else:
            from sotlas_compile import (
                FlowCancelledError,
                analyze_source_phase1,
                build_canonical_checked_ownership_sir,
                execute_flow_cfg,
                lower_flow_to_cfg,
            )

            checked = analyze_source_phase1(text, filename=source_path)
            from sotlas_compile import validate_flow_execution_source
            validate_flow_execution_source(checked.parsed_module, flow_name)
            checked_sir, _ = build_canonical_checked_ownership_sir(checked)
            cfg = lower_flow_to_cfg(checked_sir.module, flow_name)
            cancel_event = threading.Event() if timeout is not None else None
            if (
                timeout is not None
                and timeout < time.get_clock_info("monotonic").resolution
            ):
                raise TimeoutError(
                    f"Flow execution exceeded the {timeout:g} second timeout"
                )
            deadline = (
                time.monotonic() + timeout if timeout is not None else None
            )
            timer = None
            if cancel_event is not None:
                timer = threading.Timer(timeout, cancel_event.set)
                timer.daemon = True
                timer.start()
            try:
                result = execute_flow_cfg(
                    checked_sir.module,
                    cfg,
                    max_workers=workers,
                    cancel_event=cancel_event,
                    deadline=deadline,
                )
            except Exception as error:
                if timeout is not None and isinstance(error, FlowCancelledError):
                    raise TimeoutError(
                        f"Flow execution exceeded the {timeout:g} second timeout"
                    ) from error
                raise
            finally:
                if timer is not None:
                    timer.cancel()
            if deadline is not None and time.monotonic() >= deadline:
                raise TimeoutError(
                    f"Flow execution exceeded the {timeout:g} second timeout"
                )
            outputs = dict(result.outputs)
        report = {
            "schema": "sotlas.flow-result.v1",
            "module": production_frontend.parse(
                text, filename=source_path
            ).name,
            "flow": flow_name,
            "backend": backend,
            "outputs": outputs,
        }
        print(json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    except Exception as error:
        print(f"sotlas: Flow execution failed: {error}", file=sys.stderr)
        return 1
    return 0


def _run_sir_report(source_path: str) -> int:
    loaded = _read_source(source_path)
    if loaded is None:
        return 1
    _, text = loaded
    try:
        from collections import Counter
        from sotlas_compile import (
            analyze_source_phase1,
            build_canonical_checked_ownership_sir,
            validate_sir_flow_plans,
        )

        checked = analyze_source_phase1(text, filename=source_path)
        checked_sir, _ = build_canonical_checked_ownership_sir(checked)
        module = checked_sir.module
        plans = validate_sir_flow_plans(module)
        functions = []
        instruction_counts = Counter()
        block_count = 0
        for function in module.functions:
            blocks = []
            for block in function.blocks:
                block_count += 1
                opcodes = [
                    type(instruction).__name__.removesuffix("Inst").lower()
                    for instruction in block.instructions
                ]
                instruction_counts.update(opcodes)
                blocks.append({"label": block.label, "operations": opcodes})
            functions.append({
                "name": function.name,
                "parameters": [
                    {"name": parameter.name, "type": parameter.type_name}
                    for parameter in function.parameters
                ],
                "return_type": function.return_type,
                "system": function.is_system,
                "required_cpu_features": list(function.required_cpu_features),
                "blocks": blocks,
            })
        report = {
            "schema": "sotlas.sir-report.v1",
            "module": module.name,
            "representation": "canonical_checked_subset",
            "functions": functions,
            "flows": [plan.name for plan in plans],
            "summary": {
                "function_count": len(functions),
                "block_count": block_count,
                "instruction_count": sum(instruction_counts.values()),
                "operations": dict(sorted(instruction_counts.items())),
            },
        }
        print(json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    except Exception as error:
        print(f"sotlas: erro ao gerar sir report: {error}", file=sys.stderr)
        return 1
    return 0


def _run_target_report(target_name: str, cpu_features: list[str]) -> int:
    try:
        target = resolve_execution_target(target_name, cpu_features=cpu_features)
    except ExecutionTargetError as error:
        print(f"sotlas: erro: {error}", file=sys.stderr)
        return 2
    report = {
        "schema": "sotlas.target-report.v1",
        "target": {
            "triple": target.triple,
            "architecture": target.architecture,
            "abi": target.abi,
            "pointer_width": target.pointer_width,
            "endianness": target.endianness,
            "cpu": target.cpu,
            "cpu_features": list(target.cpu_features),
            "llvm_target_features": target.llvm_target_features,
            "data_layout": target.data_layout,
            "freestanding": target.is_freestanding,
        },
    }
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0


def _run_target_ir_report(source_path: str) -> int:
    loaded = _read_source(source_path)
    if loaded is None:
        return 1
    _, text = loaded
    try:
        from sotlas_compile import (
            analyze_source_phase1,
            build_canonical_checked_ownership_sir,
            validate_sir_flow_plans,
        )
        from sotlas_compile.target_ir import lower_sir_to_target_ir

        checked = analyze_source_phase1(text, filename=source_path)
        checked_sir, _ = build_canonical_checked_ownership_sir(checked)
        validate_sir_flow_plans(checked_sir.module)
        report = lower_sir_to_target_ir(checked_sir.module)
        print(json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    except Exception as error:
        print(f"sotlas: error generating target IR report: {error}", file=sys.stderr)
        return 1
    return 0


def _run_register_allocation_report(source_path: str, register_count: int) -> int:
    loaded = _read_source(source_path)
    if loaded is None:
        return 1
    _, text = loaded
    try:
        from sotlas_compile import (
            analyze_source_phase1,
            build_canonical_checked_ownership_sir,
            validate_sir_flow_plans,
        )
        from sotlas_compile.target_ir import (
            allocate_target_ir_registers,
            lower_sir_to_target_ir,
        )

        checked = analyze_source_phase1(text, filename=source_path)
        checked_sir, _ = build_canonical_checked_ownership_sir(checked)
        validate_sir_flow_plans(checked_sir.module)
        target_ir = lower_sir_to_target_ir(checked_sir.module)
        report = allocate_target_ir_registers(target_ir, register_count=register_count)
        print(json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    except Exception as error:
        print(f"sotlas: error generating register allocation preview: {error}", file=sys.stderr)
        return 1
    return 0


def _run_stack_layout_report(source_path: str, stack_alignment: int) -> int:
    loaded = _read_source(source_path)
    if loaded is None:
        return 1
    _, text = loaded
    try:
        from sotlas_compile import (
            analyze_source_phase1,
            build_canonical_checked_ownership_sir,
            validate_sir_flow_plans,
        )
        from sotlas_compile.target_ir import (
            layout_target_ir_stack,
            lower_sir_to_target_ir,
        )

        checked = analyze_source_phase1(text, filename=source_path)
        checked_sir, _ = build_canonical_checked_ownership_sir(checked)
        validate_sir_flow_plans(checked_sir.module)
        target_ir = lower_sir_to_target_ir(checked_sir.module)
        report = layout_target_ir_stack(target_ir, stack_alignment=stack_alignment)
        print(json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    except Exception as error:
        print(f"sotlas: error generating stack layout preview: {error}", file=sys.stderr)
        return 1
    return 0


def _run_target_ir_liveness_report(source_path: str) -> int:
    loaded = _read_source(source_path)
    if loaded is None:
        return 1
    _, text = loaded
    try:
        from sotlas_compile import (
            analyze_source_phase1,
            build_canonical_checked_ownership_sir,
            validate_sir_flow_plans,
        )
        from sotlas_compile.target_ir import (
            analyze_target_ir_liveness,
            lower_sir_to_target_ir,
        )

        checked = analyze_source_phase1(text, filename=source_path)
        checked_sir, _ = build_canonical_checked_ownership_sir(checked)
        validate_sir_flow_plans(checked_sir.module)
        target_ir = lower_sir_to_target_ir(checked_sir.module)
        report = analyze_target_ir_liveness(target_ir)
        print(json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    except Exception as error:
        print(f"sotlas: error generating Target IR liveness report: {error}", file=sys.stderr)
        return 1
    return 0


def _run_target_ir_source_map_report(source_path: str) -> int:
    loaded = _read_source(source_path)
    if loaded is None:
        return 1
    _, text = loaded
    try:
        from sotlas_compile import (
            analyze_source_phase1,
            build_canonical_checked_ownership_sir,
            validate_sir_flow_plans,
        )
        from sotlas_compile.target_ir import (
            lower_sir_to_target_ir,
            map_target_ir_source_points,
        )

        checked = analyze_source_phase1(text, filename=source_path)
        checked_sir, _ = build_canonical_checked_ownership_sir(checked)
        validate_sir_flow_plans(checked_sir.module)
        target_ir = lower_sir_to_target_ir(checked_sir.module)
        report = map_target_ir_source_points(target_ir)
        print(json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    except Exception as error:
        print(f"sotlas: error generating Target IR source map: {error}", file=sys.stderr)
        return 1
    return 0


def _run_dump_llvm(source_path: str, emit_debug: bool = False) -> int:
    loaded = _read_source(source_path)
    if loaded is None:
        return 1
    _, text = loaded
    try:
        from sotlas.codegen_llvm import CodegenLLVM
        from sotlas.llvm_toolchain import (
            canonical_llvm_frontend,
            generate_llvm_sir,
        )
        production_frontend = canonical_llvm_frontend()
        module = production_frontend.parse(text, filename=source_path)
        sir_mod = generate_llvm_sir(module, production_frontend)
        llvm_ir = CodegenLLVM(sir_mod, emit_debug=emit_debug).emit()
        print(llvm_ir)
    except Exception as error:
        print(f"sotlas: erro ao emitir LLVM IR: {error}", file=sys.stderr)
        return 1
    return 0


def _run_dump_wasm(source_path: str) -> int:
    loaded = _read_source(source_path)
    if loaded is None:
        return 1
    _, text = loaded
    try:
        from sotlas.studio import StudioHandler
        handler = StudioHandler.__new__(StudioHandler)
        res = handler.compile_source_all_backends(text)
        if res.get("status") == "ok":
            print(res.get("wasm", ""))
            return 0
        else:
            print(f"sotlas: erro ao emitir WebAssembly: {res.get('error')}", file=sys.stderr)
            return 1
    except Exception as error:
        print(f"sotlas: erro ao emitir WebAssembly: {error}", file=sys.stderr)
        return 1


def _run_fmt(args) -> int:
    target = Path(args.target)
    from sotlas.formatter import format_file
    if target.is_file():
        ok = format_file(target, check_only=args.check)
        return 0 if ok else 1
    elif target.is_dir():
        all_ok = True
        for p in target.glob("**/*.sotlas"):
            if not format_file(p, check_only=args.check):
                all_ok = False
        return 0 if all_ok else 1
    else:
        print(f"sotlas fmt: caminho não encontrado: {target}", file=sys.stderr)
        return 1


def _run_lint(target_path: str) -> int:
    target = Path(target_path)
    from sotlas.linter import lint_file
    if target.is_file():
        return lint_file(target)
    elif target.is_dir():
        ret = 0
        for p in target.glob("**/*.sotlas"):
            if lint_file(p) != 0:
                ret = 1
        return ret
    else:
        print(f"sotlas lint: caminho não encontrado: {target}", file=sys.stderr)
        return 1


def _run_doc(args) -> int:
    target = Path(args.target)
    from sotlas.docgen import docgen_file
    out_file = Path(args.output) if args.output else None
    return docgen_file(target, out_file)


def _run_new(args) -> int:
    from sotlas.package_manager import init_package
    target_dir = Path(args.name)
    init_package(target_dir, args.name, is_lib=args.lib)
    print(f"sotlas: novo pacote '{args.name}' criado com sucesso em {target_dir}")
    return 0


def _run_init(args) -> int:
    from sotlas.package_manager import init_package
    target_dir = Path.cwd()
    name = target_dir.name
    init_package(target_dir, name, is_lib=args.lib)
    print(f"sotlas: pacote '{name}' inicializado com sucesso em {target_dir}")
    return 0


def _run_build(args) -> int:
    from sotlas.package_manager import build_package
    target_dir = Path(args.path)
    return build_package(target_dir)


def _run_add(args) -> int:
    from sotlas.package_manager import add_dependency
    target_dir = Path.cwd()
    return add_dependency(target_dir, args.dependency, dep_spec=args.version)


def _run_compile(args) -> int:
    loaded = _read_source(args.source)
    if loaded is None:
        return 1
    src, text = loaded

    try:
        target_spec = resolve_execution_target(
            args.target, cpu_features=tuple(args.cpu_feature)
        )
    except ExecutionTargetError as error:
        print(f"sotlas: erro de target: {error}", file=sys.stderr)
        return 2

    linker_mode = getattr(args, "linker", "auto")
    if linker_mode == "internal":
        if (
            target_spec.architecture != "x86_64"
            or getattr(args, "target", "host") not in {
                "host", "x86_64-freestanding", "x86_64-unknown-none-elf",
                "x86_64-unknown-linux-gnu",
            }
        ):
            print(
                "sotlas: linker interno suporta apenas host Linux e x86-64 freestanding/Linux",
                file=sys.stderr,
            )
            return 2
        return _run_compile_internal_linker(args, src, text)

    emit_type = "exe"
    output_arg = getattr(args, "output", None)
    if getattr(args, "emit_asm", False) or getattr(args, "emit", None) == "asm" or (
        output_arg and str(output_arg).endswith((".s", ".asm"))
    ):
        emit_type = "asm"
    elif getattr(args, "emit_llvm", False) or (output_arg and str(output_arg).endswith(".ll")):
        emit_type = "llvm"
    elif getattr(args, "emit_obj", False) or (output_arg and str(output_arg).endswith((".o", ".obj"))):
        emit_type = "obj"
    elif getattr(args, "emit_c", False) or (output_arg and str(output_arg).endswith(".c")):
        emit_type = "c"

    backend = getattr(args, "backend", "native")

    if backend == "native":
        from sotlas.bootstrap_pipeline import (
            build_stage1_native_compiler,
            _ROOT,
        )
        exe_suffix = ".exe" if sys.platform == "win32" else ""
        stage1_path = _ROOT / "build" / f"sotlas_stage1{exe_suffix}"
        if not stage1_path.is_file():
            try:
                stage1_path = build_stage1_native_compiler(output_exe=stage1_path, verbose=False)
            except Exception as error:
                print(
                    "sotlas: backend nativo indisponivel: nao foi possivel construir "
                    f"o compilador Stage 1: {error}",
                    file=sys.stderr,
                )
                print(
                    "sotlas: nenhum fallback implicito para C11 ou LLVM foi executado; "
                    "selecione --backend c11 ou --backend llvm explicitamente",
                    file=sys.stderr,
                )
                return 1

        if not stage1_path.is_file():
            print(
                f"sotlas: backend nativo indisponivel: Stage 1 nao encontrado em {stage1_path}",
                file=sys.stderr,
            )
            return 1

        def report_native_failure(action: str, result=None) -> int:
            detail = ""
            if result is not None:
                detail = (result.stderr or result.stdout or "").strip()
            suffix = f":\n{detail}" if detail else ""
            print(f"sotlas: backend nativo falhou ao {action}{suffix}", file=sys.stderr)
            print(
                "sotlas: nenhum fallback implicito para C11 ou LLVM foi executado",
                file=sys.stderr,
            )
            return 1

        if emit_type == "obj":
            out_path = Path(output_arg) if output_arg else src.with_suffix(".o")
            out_path.parent.mkdir(parents=True, exist_ok=True)
            res = subprocess.run(
                [str(stage1_path), "--compile-obj", str(src), str(out_path)],
                capture_output=True,
                text=True,
            )
            if res.returncode != 0 or not out_path.is_file():
                return report_native_failure("emitir o objeto ELF64", res)
            print(f"sotlas: objeto ELF64 nativo emitido em {out_path}")
            return 0

        if emit_type == "c":
            out_path = Path(output_arg) if output_arg else src.with_suffix(".c")
            out_path.parent.mkdir(parents=True, exist_ok=True)
            res = subprocess.run(
                [str(stage1_path), "--emit-c", str(src), str(out_path)],
                capture_output=True,
                text=True,
            )
            if res.returncode != 0 or not out_path.is_file():
                return report_native_failure("emitir C11 explicitamente", res)
            print(f"sotlas: C11 emitido pelo compilador nativo em {out_path}")
            return 0

        if emit_type == "exe":
            is_freestanding = getattr(args, "target", "host") in (
                "x86_64-freestanding", "x86_64-unknown-none-elf",
                "aarch64-freestanding", "aarch64-unknown-none-elf",
            )
            out_path = Path(output_arg) if output_arg else src.with_suffix(".exe" if sys.platform == "win32" else ".bin")
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_obj = Path(tmpdir) / "mod.o"
                res_obj = subprocess.run(
                    [str(stage1_path), "--compile-obj", str(src), str(tmp_obj)],
                    capture_output=True,
                    text=True,
                )
                if res_obj.returncode != 0 or not tmp_obj.is_file():
                    return report_native_failure("compilar o objeto intermediario", res_obj)

                entry_arg = getattr(args, "entry", None)
                if entry_arg:
                    candidate_entries = [entry_arg]
                elif is_freestanding:
                    candidate_entries = ["_start", "kernel_main"]
                else:
                    candidate_entries = ["main_entry", "main"]

                link_failures = []
                for sym in candidate_entries:
                    cmd = [str(stage1_path), "--link-exe", str(tmp_obj), str(out_path), sym]
                    if is_freestanding:
                        cmd.append("--freestanding")
                    res_link = subprocess.run(cmd, capture_output=True, text=True)
                    if res_link.returncode == 0 and out_path.is_file():
                        print(f"sotlas: executável nativo gerado com sucesso em {out_path}")
                        return 0
                    detail = (res_link.stderr or res_link.stdout or "").strip()
                    link_failures.append(f"{sym}: {detail or 'falha sem diagnostico'}")

                print(
                    "sotlas: backend nativo nao encontrou um entrypoint linkavel:\n  "
                    + "\n  ".join(link_failures),
                    file=sys.stderr,
                )
                print(
                    "sotlas: nenhum fallback implicito para C11 ou LLVM foi executado",
                    file=sys.stderr,
                )
                return 1

        print(
            f"sotlas: backend nativo nao suporta o formato de saida {emit_type!r}",
            file=sys.stderr,
        )
        return 2

    if backend == "sotlas-x86_64" and emit_type not in ("asm", "obj"):
        print(
            "sotlas: --backend sotlas-x86_64 requires --emit-asm, --emit-obj, or a .s/.asm/.o/.obj output",
            file=sys.stderr,
        )
        return 2

    if emit_type == "asm" or (backend == "sotlas-x86_64" and emit_type == "obj"):
        if backend == "sotlas-x86_64":
            supported_targets = {
                "x86_64-freestanding",
                "x86_64-unknown-none-elf",
                "x86_64-unknown-linux-gnu",
            }
            if args.target not in supported_targets and not (
                args.target == "host" and sys.platform.startswith("linux")
            ):
                print(
                    "sotlas: the Sotlas-owned assembly backend requires an x86-64 SysV target",
                    file=sys.stderr,
                )
                return 2
            from sotlas_compile.machine_x86_64 import (
                MachineBackendError,
                compile_source_to_x86_64_sysv_assembly,
            )

            default_suffix = ".s" if emit_type == "asm" else (
                ".obj" if sys.platform == "win32" else ".o"
            )
            out_path = Path(args.output) if args.output else src.with_suffix(default_suffix)
            try:
                assembly = compile_source_to_x86_64_sysv_assembly(
                    text, args.source
                )
                out_path.parent.mkdir(parents=True, exist_ok=True)
                if emit_type == "asm":
                    out_path.write_text(assembly, encoding="utf-8")
                    print(f"sotlas: Sotlas-owned x86-64 assembly emitted to {out_path}")
                    return 0

                assembler_command = [args.cc, "-x", "assembler", "-c", "-o", str(out_path), "-"]
                if args.target != "host":
                    target_triple = {
                        "x86_64-freestanding": "x86_64-unknown-none-elf",
                        "x86_64-unknown-none-elf": "x86_64-unknown-none-elf",
                        "x86_64-unknown-linux-gnu": "x86_64-unknown-linux-gnu",
                    }[args.target]
                    assembler_command[1:1] = ["-target", target_triple]
                result = subprocess.run(
                    assembler_command,
                    input=assembly,
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    print(
                        f"sotlas: assembler failed for Sotlas-owned x86-64 output:\n{result.stderr}",
                        file=sys.stderr,
                    )
                    return result.returncode or 1
                print(f"sotlas: Sotlas-owned x86-64 object emitted to {out_path}")
                return 0
            except (MachineBackendError, OSError, ValueError) as error:
                print(f"sotlas: x86-64 machine backend error: {error}", file=sys.stderr)
                return 1
        if backend != "llvm":
            print("sotlas: --emit-asm requires --backend llvm or sotlas-x86_64", file=sys.stderr)
            return 2
        from sotlas.llvm_toolchain import default_toolchain
        out_path = Path(args.output) if args.output else src.with_suffix(".s")
        try:
            result_path = default_toolchain.compile_source_to_native(
                text,
                args.source,
                out_path,
                emit_type="asm",
                backend="llvm",
                target=None if args.target == "host" else args.target,
                cpu_features=tuple(args.cpu_feature),
            )
            print(f"sotlas: assembly nativo emitido via LLVM em {result_path}")
            return 0
        except Exception as error:
            print(f"sotlas: erro LLVM: {error}", file=sys.stderr)
            return 1

    # ── Modo linker interno: pipeline completamente autônomo ──────────────
    force_gcc = (linker_mode == "gcc")

    try:
        c_code = _compile_cli_source(text, args.source)
    except SotlasBootstrapError as error:
        print(f"sotlas: erro: {error}", file=sys.stderr)
        return 1

    from sotlas.llvm_toolchain import default_toolchain

    # Se linker == "gcc", força desligar LLVM mesmo quando disponível
    force_gcc = (linker_mode == "gcc")
    is_llvm = (
        not force_gcc
        and default_toolchain.is_available()
        and (backend == "llvm" or emit_type in ("obj", "llvm"))
    )

    if args.output:
        out_path = Path(args.output)
    else:
        suffix_map = {
            "llvm": ".ll",
            "obj": ".obj" if sys.platform == "win32" else ".o",
            "c": ".c",
            "exe": ".exe" if sys.platform == "win32" else ".bin"
        }
        out_path = src.with_suffix(suffix_map.get(emit_type, ".bin"))

    if emit_type == "c":
        c_path = out_path.with_suffix(".c")
        c_path.write_text(c_code, encoding="utf-8")
        print(f"sotlas: C11 emitido em {c_path}")
        return 0

    if is_llvm:
        is_freestanding = args.target in (
            "x86_64-freestanding", "x86_64-unknown-none-elf",
            "aarch64-freestanding", "aarch64-unknown-none-elf",
        )
        try:
            res_path = default_toolchain.compile_source_to_native(
                text,
                args.source,
                out_path,
                emit_type=emit_type,
                backend="c11",
                is_freestanding=is_freestanding,
                target=None if args.target == "host" else args.target,
                cpu_features=tuple(args.cpu_feature),
            )
            print(f"sotlas: {emit_type.upper()} gerado via LLVM em {res_path}")
            return 0
        except Exception as err:
            print(f"sotlas: erro LLVM: {err}", file=sys.stderr)
            return 1

    # Fallback para GCC clássico quando LLVM não estiver ativo
    c_file = out_path.with_suffix(".c")
    c_file.write_text(c_code, encoding="utf-8")

    cc_flags = ["-std=c11", "-Wall", "-Wextra"]
    if args.target in (
        "x86_64-freestanding", "x86_64-unknown-none-elf",
        "aarch64-freestanding", "aarch64-unknown-none-elf",
    ):
        cc_flags += ["-ffreestanding", "-nostdlib", "-nostdinc"]
        if args.target.startswith("x86_64"):
            cc_flags += [
                "-mno-red-zone", "-mno-mmx", "-mno-sse", "-mno-sse2",
            ]

    cmd = [args.cc, str(c_file)]
    if args.target != "host":
        target_triple = {
            "x86_64-freestanding": "x86_64-unknown-none-elf",
            "aarch64-freestanding": "aarch64-unknown-none-elf",
        }.get(args.target, args.target)
        cmd += ["-target", target_triple]
    if args.target.startswith("aarch64") and args.cpu_feature:
        if "clang" not in Path(args.cc).name.lower():
            print(
                "sotlas: features AArch64 explícitas exigem Clang/LLVM neste backend",
                file=sys.stderr,
            )
            return 2
        for feature in args.cpu_feature:
            cmd += ["-Xclang", "-target-feature", "-Xclang", f"+{feature}"]
    else:
        cmd += [f"-m{feature}" for feature in args.cpu_feature]
    cmd += ["-o", str(out_path)] + cc_flags
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"sotlas: erro do compilador C:\n{result.stderr}", file=sys.stderr)
            return result.returncode
        print(f"sotlas: binário gerado em {out_path}")
        return 0
    except FileNotFoundError:
        print(
            f"sotlas: compilador C '{args.cc}' não encontrado — use --emit-c para gerar apenas o C11",
            file=sys.stderr,
        )
        return 1


def _run_compile_internal_linker(args, src: Path, text: str) -> int:
    """Pipeline de compilação totalmente autônomo usando o linker ELF64 interno.

    Fluxo:
      Sotlas source → Lexer/Parser/Sema → CodegenC (C11 freestanding) → ELF emitter
      → elf_linker.py (sem LLVM, sem GCC) → ELF64 ET_EXEC

    Nota: este modo só suporta alvos Linux ou bare-metal x86_64/aarch64.
    Para Windows PE/COFF, use --linker=auto (LLVM).
    """
    import tempfile
    import os
    from sotlas.llvm_toolchain import default_toolchain, LLVMToolchainError
    from sotlas.elf_linker import ELFLinker, ELFLinkerError

    if args.output:
        out_path = Path(args.output)
    else:
        out_path = src.with_suffix(".bin")

    target = getattr(args, "target", "host")
    entry  = getattr(args, "entry", "_start") or "_start"

    if sys.platform == "win32" and target == "host":
        print(
            "sotlas: aviso: o linker interno produz binários ELF64 (Linux/bare-metal).\n"
            "  Para executáveis Windows nativos, use --linker=lld ou --linker=auto.",
            file=sys.stderr,
        )

    # Passo 1: compilar código Sotlas → C11 freestanding
    try:
        c_code = _compile_cli_source(text, args.source)
    except SotlasBootstrapError as err:
        print(f"sotlas: erro: {err}", file=sys.stderr)
        return 1

    # Passo 2: compilar C11 → objeto .o (ainda precisa de clang para este passo intermediário)
    # Se clang não estiver disponível, emite aviso e sugere --emit-c
    if not default_toolchain.is_available():
        print(
            "sotlas: aviso: Clang não encontrado. O linker interno requer Clang apenas para\n"
            "  compilar C11 → .o (este passo intermediário usa apenas `clang -c`).\n"
            "  Alternativamente use --emit-c e compile manualmente com qualquer compilador C.",
            file=sys.stderr,
        )
        return 1

    with tempfile.TemporaryDirectory(prefix="sotlas_link_") as tmpdir:
        tmp_obj = Path(tmpdir) / (src.stem + ".o")
        try:
            is_freestanding = (target == "x86_64-freestanding")
            default_toolchain.compile_c_to_obj(
                c_code, tmp_obj,
                opt_level=2,
                is_freestanding=is_freestanding,
                extra_flags=["-fno-pie", "-fno-pic"],  # necessário para relocações estáticas
            )
        except LLVMToolchainError as err:
            print(f"sotlas: erro ao compilar C → .o: {err}", file=sys.stderr)
            return 1

        # Passo 3: linkar .o → ELF64 executável usando o linker interno
        triple = "x86_64-linux-gnu" if "x86_64" in target or target == "host" else target
        try:
            linker = ELFLinker(
                entry_symbol=entry,
                target_triple=triple,
                load_address=None,  # usa default: 0x400000
            )
            linker.add_object(str(tmp_obj))
            linker.link(str(out_path))
        except ELFLinkerError as err:
            print(f"sotlas: erro de linkagem interna: {err}", file=sys.stderr)
            return 1

    print(f"sotlas: executável ELF64 gerado via linker interno em {out_path}")
    return 0


def _run_exec(args) -> int:
    loaded = _read_source(args.source)
    if loaded is None:
        return 1
    src, text = loaded

    from sotlas.llvm_toolchain import default_toolchain
    if default_toolchain.is_available():
        with tempfile.TemporaryDirectory() as tmpdir:
            exe_path = Path(tmpdir) / ("test.exe" if sys.platform == "win32" else "test.bin")
            try:
                default_toolchain.compile_source_to_native(text, args.source, exe_path, emit_type="exe", backend="c11")
                run_res = subprocess.run([str(exe_path)])
                return run_res.returncode
            except Exception as e:
                print(f"sotlas run: erro LLVM: {e}", file=sys.stderr)
                return 1

    try:
        c_code = _compile_cli_source(text, args.source)
    except SotlasBootstrapError as error:
        print(f"sotlas: erro: {error}", file=sys.stderr)
        return 1

    exe_path = src.with_suffix(".exe" if sys.platform == "win32" else ".out")
    c_file = src.with_suffix(".tmp.c")
    c_file.write_text(c_code, encoding="utf-8")

    cmd = [args.cc, "-std=c11", str(c_file), "-o", str(exe_path)]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            print(f"sotlas: erro de compilação C:\n{res.stderr}", file=sys.stderr)
            return res.returncode
        run_res = subprocess.run([str(exe_path)])
        return run_res.returncode
    finally:
        c_file.unlink(missing_ok=True)
        exe_path.unlink(missing_ok=True)


def _run_bootstrap(args) -> int:
    from sotlas.bootstrap_pipeline import build_self_hosted_compiler, verify_self_hosted_compiler
    out = Path(args.output) if args.output else None
    try:
        exe = build_self_hosted_compiler(out)
        print(f"sotlas: compilador nativo auto-hospedado gerado com sucesso: {exe}")
        if not args.no_verify:
            ok = verify_self_hosted_compiler(exe)
            if ok:
                print("sotlas: verificação do compilador auto-hospedado: OK (100% aprovado)")
                return 0
            else:
                print("sotlas: erro na verificação do compilador auto-hospedado", file=sys.stderr)
                return 1
        return 0
    except Exception as e:
        print(f"sotlas bootstrap: erro: {e}", file=sys.stderr)
        return 1


def _run_lsp() -> int:
    try:
        from sotlas_compile.lsp import run_stdio_server
        return run_stdio_server()
    except Exception as e:
        print(f"sotlas: erro ao iniciar LSP: {e}", file=sys.stderr)
        return 1


def _run_tests(pattern: str) -> int:
    import unittest
    tests_dir = _ROOT / "tests" if (_ROOT / "tests").is_dir() else _ROOT.parent / "tests"
    suite = unittest.defaultTestLoader.discover(str(tests_dir), pattern=pattern)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
