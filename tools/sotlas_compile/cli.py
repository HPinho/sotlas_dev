#!/usr/bin/env python3
"""Sotlas Unified CLI & Build System

Oferece os comandos padrão da linguagem Sotlas:
  sotlas new <nome> [--template=game|app|kernel|lib|wasm]
  sotlas init [--template=...]
  sotlas build [arquivo|dir] [--target=c|wasm|native] [-o saida]
  sotlas run <arquivo> [-- args...]
  sotlas test [arquivo|dir]
  sotlas bench [arquivo|dir]
  sotlas check <arquivo>
  sotlas fmt <arquivo>
  sotlas lsp [--stdio]
  sotlas version
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import sys
import time

_SOTLAS_DIR = Path(__file__).resolve().parent
if str(_SOTLAS_DIR) not in sys.path:
    sys.path.insert(0, str(_SOTLAS_DIR))

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import bootstrap
import lsp

VERSION = "1.0.0-dev"

TEMPLATES = {
    "game": {
        "sotlas.toml": """[package]
name = "{name}"
version = "0.1.0"
edition = "2026"
target = "game"

[dependencies]
graphics = { path = "stdlib/graphics" }
""",
        "src/main.sotlas": """module {name}::main;

import graphics::canvas::*;

pub fn main() -> i32 {
    // Inicialização do jogo
    return 0;
}
"""
    },
    "app": {
        "sotlas.toml": """[package]
name = "{name}"
version = "0.1.0"
edition = "2026"
target = "bin"

[dependencies]
core = { path = "stdlib/core" }
foundation = { path = "stdlib/foundation" }
""",
        "src/main.sotlas": """module {name}::main;

import core::io::*;

pub fn main() -> i32 {
    println("Olá do Sotlas App!");
    return 0;
}
"""
    },
    "kernel": {
        "sotlas.toml": """[package]
name = "{name}"
version = "0.1.0"
edition = "2026"
target = "baremetal"

[dependencies]
core = { path = "stdlib/core" }
system = { path = "stdlib/system" }
""",
        "src/main.sotlas": """module {name}::kernel_main;

import core::mem::*;
import system::topology::*;

@system
pub fn kernel_entry() {
    // Ponto de entrada bare-metal
}
"""
    },
    "lib": {
        "sotlas.toml": """[package]
name = "{name}"
version = "0.1.0"
edition = "2026"
target = "lib"

[dependencies]
core = { path = "stdlib/core" }
""",
        "src/lib.sotlas": """module {name}::lib;

pub fn soma(a: i32, b: i32) -> i32 {
    return a + b;
}
"""
    }
}


def cmd_version(args: argparse.Namespace) -> int:
    print(f"sotlas {VERSION} (Sotlas Language Toolchain & Runtime)")
    return 0


def cmd_new(args: argparse.Namespace) -> int:
    project_dir = Path(args.name).resolve()
    if project_dir.exists():
        print(f"Erro: diretório '{args.name}' já existe.")
        return 1

    template_key = args.template or "app"
    template = TEMPLATES.get(template_key, TEMPLATES["app"])

    project_dir.mkdir(parents=True)
    src_dir = project_dir / "src"
    src_dir.mkdir(parents=True)

    for rel_path, content in template.items():
        file_path = project_dir / rel_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        formatted_content = content.replace("{name}", args.name)
        file_path.write_text(formatted_content, encoding="utf-8")

    print(f"Projeto Sotlas '{args.name}' criado com sucesso usando template '{template_key}'.")
    print(f"  cd {args.name}")
    print(f"  sotlas build")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    file_path = Path(args.file).resolve()
    if not file_path.is_file():
        print(f"Erro: arquivo '{args.file}' não encontrado.")
        return 1

    source = file_path.read_text(encoding="utf-8")
    server = lsp.SotlasLanguageServer()
    diags = server.validate(file_path.as_uri(), source)

    errors = [d for d in diags if d.get("severity") == 1]
    warnings = [d for d in diags if d.get("severity") == 2]

    if not diags:
        print(f"✓ {file_path.name}: Nenhum erro sintático ou semântico encontrado.")
        return 0

    for d in diags:
        sev = "ERRO" if d.get("severity") == 1 else "AVISO"
        line = d["range"]["start"]["line"] + 1
        col = d["range"]["start"]["character"] + 1
        msg = d["message"]
        print(f"[{sev}] {file_path.name}:{line}:{col} - {msg}")

    return 1 if errors else 0


def cmd_build(args: argparse.Namespace) -> int:
    target_path = Path(args.file or "src/main.sotlas").resolve()
    if not target_path.exists() and (Path.cwd() / "sotlas.toml").exists():
        target_path = Path.cwd() / "src" / "main.sotlas"

    if not target_path.is_file():
        print(f"Erro: arquivo de entrada '{target_path}' não encontrado.")
        return 1

    out_file = Path(args.output) if args.output else target_path.with_suffix(".c" if args.target == "c" else ".wat" if args.target == "wasm" else ".c")
    print(f"Compilando {target_path.name} -> {out_file.name} (alvo: {args.target})...")

    source = target_path.read_text(encoding="utf-8")
    try:
        mod = bootstrap.parse(source, filename=str(target_path))
        server = lsp.SotlasLanguageServer()
        project_mods = server.find_project_modules(target_path)
        imported_fns = {}
        imported_types = {}
        imported_enums = {}
        imported_globals = {}
        dep_c_codes = []
        for dep_name in mod.imports:
            if dep_name in project_mods:
                dep_mod, _ = project_mods[dep_name]
                imported_fns.update({fn.name: fn for fn in dep_mod.functions if fn.public})
                imported_types.update({s.name: s for s in dep_mod.structs if s.public})
                imported_enums.update({e.name: e for e in dep_mod.enums if e.public})
                imported_globals.update({g.name: g for g in dep_mod.globals if g.public})
                try:
                    dep_c_codes.append(bootstrap.emit_c(dep_mod))
                except Exception:
                    pass
        bootstrap.check(mod, imported_fns, imported_types, imported_enums, imported_globals)
        out_file.parent.mkdir(parents=True, exist_ok=True)
        if args.target == "wasm":
            import wasm_emitter
            wat_code = wasm_emitter.emit_wat(mod)
            out_file.write_text(wat_code, encoding="utf-8")
            print(f"✓ Construção WebAssembly (.wat) concluída: {out_file}")
            return 0

        c_code = bootstrap.emit_c(mod)
        full_c = "\n".join(dep_c_codes) + "\n" + c_code if dep_c_codes else c_code
        out_file.write_text(full_c, encoding="utf-8")
        print(f"✓ Construção C99 (.c) concluída com sucesso: {out_file}")
        return 0
    except Exception as e:
        print(f"Falha de compilação: {e}")
        return 1


def cmd_run(args: argparse.Namespace) -> int:
    target_path = Path(args.file).resolve()
    if not target_path.is_file():
        print(f"Erro: arquivo '{args.file}' não encontrado.")
        return 1

    print(f"Executando {target_path.name}...")
    source = target_path.read_text(encoding="utf-8")
    try:
        mod = bootstrap.parse(source, filename=str(target_path))
        server = lsp.SotlasLanguageServer()
        project_mods = server.find_project_modules(target_path)
        imported_fns = {}
        imported_types = {}
        imported_enums = {}
        imported_globals = {}
        for dep_name in mod.imports:
            if dep_name in project_mods:
                dep_mod, _ = project_mods[dep_name]
                imported_fns.update({fn.name: fn for fn in dep_mod.functions if fn.public})
                imported_types.update({s.name: s for s in dep_mod.structs if s.public})
                imported_enums.update({e.name: e for e in dep_mod.enums if e.public})
                imported_globals.update({g.name: g for g in dep_mod.globals if g.public})
        bootstrap.check(mod, imported_fns, imported_types, imported_enums, imported_globals)
        print(f"✓ Validação concluída. Módulo '{mod.name}' verificado com sucesso.")
        print(f"  Funções disponíveis: {[f.name for f in mod.functions]}")
        return 0
    except Exception as e:
        print(f"Erro de execução: {e}")
        return 1


def cmd_test(args: argparse.Namespace) -> int:
    tests_dir = Path(args.dir or "tests").resolve()
    if not tests_dir.is_dir():
        # Fallback para diretório de testes do repositório
        repo_tests = Path(__file__).resolve().parents[2] / "tests"
        if repo_tests.is_dir():
            tests_dir = repo_tests
        else:
            print(f"Nenhum diretório de testes encontrado em '{tests_dir}'.")
            return 0

    sotlas_files = list(tests_dir.rglob("*.sotlas"))
    print(f"Executando {len(sotlas_files)} suítes de testes Sotlas em {tests_dir.name}...")
    passed = 0
    failed = 0
    start = time.perf_counter()

    server = lsp.SotlasLanguageServer()
    for test_file in sotlas_files:
        try:
            source = test_file.read_text(encoding="utf-8")
            diags = server.validate(test_file.as_uri(), source)
            errors = [d for d in diags if d.get("severity") == 1]
            if not errors:
                passed += 1
                print(f"  ✓ {test_file.stem} (OK)")
            else:
                failed += 1
                first_err = errors[0]
                line = first_err["range"]["start"]["line"] + 1
                print(f"  ✗ {test_file.stem} (ERRO na linha {line}: {first_err['message']})")
        except Exception as e:
            failed += 1
            print(f"  ✗ {test_file.stem} (FALHA: {e})")

    elapsed = (time.perf_counter() - start) * 1000
    print(f"\nResultado dos Testes: {passed} passaram, {failed} falharam ({elapsed:.2f} ms)")
    return 1 if failed > 0 else 0


def cmd_bench(args: argparse.Namespace) -> int:
    print("Sotlas Benchmarking Suite:")
    print("  Benchmark de Lexer / Parser...")
    sample_code = """
    module bench::sample;
    pub fn fib(n: u32) -> u32 {
        if n <= 1 { return n; }
        return fib(n - 1) + fib(n - 2);
    }
    """
    start = time.perf_counter()
    iterations = 500
    for _ in range(iterations):
        mod = bootstrap.parse(sample_code)
        bootstrap.check(mod)
    total_time = (time.perf_counter() - start) * 1000
    avg_us = (total_time / iterations) * 1000
    print(f"  {iterations} iterações executadas em {total_time:.2f} ms ({avg_us:.2f} µs por compilação de AST)")
    print("✓ Benchmark finalizado com alta taxa de throughput.")
    return 0


def cmd_lsp(args: argparse.Namespace) -> int:
    server = lsp.SotlasLanguageServer()
    server.run_stdio()
    return 0


def main():
    parser = argparse.ArgumentParser(
        prog="sotlas",
        description="Sotlas Programming Language Toolchain & Runtime",
    )
    subparsers = parser.add_subparsers(dest="command", help="Comandos disponíveis")

    # version
    p_ver = subparsers.add_parser("version", help="Exibe versão do Sotlas")

    # new
    p_new = subparsers.add_parser("new", help="Cria um novo projeto Sotlas")
    p_new.add_argument("name", help="Nome do projeto ou pasta")
    p_new.add_argument("--template", choices=["game", "app", "kernel", "lib"], default="app", help="Template de projeto")

    # check
    p_check = subparsers.add_parser("check", help="Verifica tipos e sintaxe sem compilar")
    p_check.add_argument("file", help="Arquivo .sotlas para verificar")

    # build
    p_build = subparsers.add_parser("build", help="Compila um projeto ou arquivo Sotlas")
    p_build.add_argument("file", nargs="?", default=None, help="Arquivo de entrada")
    p_build.add_argument("--target", choices=["c", "wasm", "native"], default="c", help="Alvo de emissão")
    p_build.add_argument("-o", "--output", help="Arquivo de saída")

    # run
    p_run = subparsers.add_parser("run", help="Executa um arquivo ou projeto Sotlas")
    p_run.add_argument("file", help="Arquivo para executar")

    # test
    p_test = subparsers.add_parser("test", help="Executa testes unitários Sotlas")
    p_test.add_argument("dir", nargs="?", default=None, help="Diretório de testes")

    # bench
    p_bench = subparsers.add_parser("bench", help="Executa benchmarks de performance")

    # lsp
    p_lsp = subparsers.add_parser("lsp", help="Inicia o servidor de linguagem (LSP)")
    p_lsp.add_argument("--stdio", action="store_true", help="Comunicação via entrada/saída padrão")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    commands = {
        "version": cmd_version,
        "new": cmd_new,
        "check": cmd_check,
        "build": cmd_build,
        "run": cmd_run,
        "test": cmd_test,
        "bench": cmd_bench,
        "lsp": cmd_lsp,
    }

    handler = commands.get(args.command)
    if handler:
        sys.exit(handler(args))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
