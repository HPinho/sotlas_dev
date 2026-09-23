"""Sotlas LLVM Toolchain — Orquestrador de Emissão Direta de Código Objeto e Binários Nativos via LLVM / LLD.

Este módulo localiza a instalação do LLVM (Clang, LLD, LLC, LLDB),
executa a compilação direta de LLVM IR textual (.ll) ou código C11 gerado
para código objeto nativo (.o / .obj) e linkedita executáveis nativos standalone (.exe / ELF),
eliminando a necessidade de qualquer compilador C externo clássico (GCC).
"""
from __future__ import annotations
import importlib
import importlib.util
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import List, Optional, Tuple, Union


# Locais canônicos de busca de ferramentas LLVM
DEFAULT_LLVM_PATHS = [
    Path(r"C:\Program Files\LLVM\bin"),
    Path(r"C:\Program Files (x86)\LLVM\bin"),
    Path(r"C:\LLVM\bin"),
    Path("/usr/local/opt/llvm/bin"),
    Path("/usr/lib/llvm/bin"),
    Path("/usr/bin"),
]


class LLVMToolchainError(Exception):
    """Erro emitido durante a execução de ferramentas da toolchain LLVM."""
    pass


def canonical_llvm_frontend():
    """Load the compiler-owned frontend even when tools mirrors are imported."""
    package_name = "_sotlas_compile_canonical_llvm"
    if package_name not in sys.modules:
        package_dir = (
            Path(__file__).resolve().parents[2]
            / "compiler"
            / "sotlas_compile"
        )
        spec = importlib.util.spec_from_file_location(
            package_name,
            package_dir / "__init__.py",
            submodule_search_locations=[str(package_dir)],
        )
        if spec is None or spec.loader is None:
            raise LLVMToolchainError(
                "canonical Sotlas compiler frontend could not be loaded"
            )
        package = importlib.util.module_from_spec(spec)
        sys.modules[package_name] = package
        spec.loader.exec_module(package)
    return importlib.import_module(f"{package_name}.bootstrap")


def require_llvm_ownership_supported(module, frontend):
    """Return a canonical plan for the verified, trivial direct-only subset.

    Other ownership-bearing source remains closed until its graph, cleanup,
    and runtime operations have complete LLVM lowering.
    """
    frontend.check(module)
    sole_names = {
        item.name for item in getattr(module, "structs", ())
        if getattr(item, "is_sole", False)
    }

    def carries_domain(type_obj) -> bool:
        if type_obj is None:
            return False
        if getattr(type_obj, "ownership_domain", None) is not None:
            return True
        if getattr(type_obj, "is_array", False):
            return carries_domain(getattr(type_obj, "elem_type", None))
        if getattr(type_obj, "is_fn_ptr", False):
            return any(carries_domain(item) for item in getattr(type_obj, "fn_params", ())) or carries_domain(getattr(type_obj, "fn_ret", None))
        return (
            not getattr(type_obj, "pointer", False)
            and not getattr(type_obj, "is_reference", False)
            and getattr(type_obj, "name", None) in sole_names
        )

    functions = list(getattr(module, "functions", ()))
    for class_decl in getattr(module, "classes", ()):
        functions.extend(getattr(class_decl, "methods", ()))
    has_domain = bool(sole_names)
    has_domain = has_domain or any(
        carries_domain(type_obj)
        for function in functions
        for type_obj in (
            *(type_obj for _, type_obj in getattr(function, "params", ())),
            getattr(function, "result", None),
        )
    )
    has_domain = has_domain or any(
        carries_domain(getattr(field, "type", None))
        for struct in getattr(module, "structs", ())
        for field in getattr(struct, "fields", ())
    )
    has_domain = has_domain or any(
        carries_domain(getattr(item, "type", None))
        for item in getattr(module, "globals", ())
    )
    has_domain = has_domain or any(
        carries_domain(getattr(variant, "payload_type", None))
        for enum in getattr(module, "enums", ())
        for variant in getattr(enum, "variants", ())
    )
    if not has_domain:
        return None

    from sotlas_compile import typed_ast
    from sotlas.sir import lower_ownership_module_semantics
    try:
        semantic = typed_ast.build_phase1_semantic_snapshot(module)
        checked = SimpleNamespace(
            parsed_module=module,
            semantic=semantic,
            ownership_sir=lower_ownership_module_semantics(
                semantic.ownership, semantic.ownership_domains
            ),
        )
    except Exception as error:
        raise LLVMToolchainError(
            "LLVM backend does not lower canonical Ownership Domains yet"
        ) from error
    graph = checked.semantic.ownership_domains
    nonowning_only = (
        bool(graph.direct_accesses or graph.whisper_borrows)
        and not graph.transfers
        and not graph.planned_transitions
        and not graph.shared_accounts
        and not graph.shared_alias_points
    )
    if nonowning_only:
        primitive_names = {
            "void", "bool", "u8", "i8", "u16", "i16", "u32", "i32",
            "u64", "i64", "usize", "isize", "f32", "f64",
        }
        for struct in getattr(module, "structs", ()):
            if not getattr(struct, "is_sole", False):
                continue
            for field in getattr(struct, "fields", ()):
                type_obj = getattr(field, "type", None)
                if (
                    type_obj is None
                    or getattr(type_obj, "name", None) not in primitive_names
                    or getattr(type_obj, "pointer", False)
                    or getattr(type_obj, "is_array", False)
                    or getattr(type_obj, "is_reference", False)
                    or getattr(type_obj, "is_fn_ptr", False)
                ):
                    nonowning_only = False
                    break
        sole_names = {
            item.name for item in getattr(module, "structs", ())
            if getattr(item, "is_sole", False)
        }
        if any(
            function.name == f"{name}_deinit"
            for function in getattr(module, "functions", ())
            for name in sole_names
        ):
            nonowning_only = False
        functions = tuple(getattr(module, "functions", ()))
        function_by_name = {function.name: function for function in functions}
        if (
            getattr(module, "classes", ())
            or getattr(module, "enums", ())
            or getattr(module, "globals", ())
        ):
            nonowning_only = False
        for function in functions:
            result_type = getattr(function, "result", None)
            if (
                getattr(result_type, "name", None) != "void"
                or getattr(result_type, "ownership_domain", None) is not None
            ):
                nonowning_only = False
                break
            body = tuple(getattr(function, "body", ()) or ())
            if not body or type(body[-1]).__name__ != "Return":
                nonowning_only = False
                break
            params = tuple(getattr(function, "params", ()))
            if any(
                getattr(type_obj, "ownership_domain", None)
                not in (None, "direct", "whisper")
                for _, type_obj in params
            ):
                nonowning_only = False
                break
            direct_params = {
                name for name, type_obj in params
                if getattr(type_obj, "ownership_domain", None) in ("direct", "whisper")
            }
            if len(direct_params) != sum(
                getattr(type_obj, "ownership_domain", None) in ("direct", "whisper")
                for _, type_obj in params
            ):
                nonowning_only = False
                break
            if direct_params and len(body) not in (1, 2):
                nonowning_only = False
                break
            for statement in body[:-1]:
                statement_kind = type(statement).__name__
                value = getattr(statement, "value", None)
                if (
                    statement_kind not in ("Expression", "Defer")
                    or type(value).__name__ != "Call"
                ):
                    nonowning_only = False
                    break
                callee = function_by_name.get(value.callee)
                target_params = tuple(
                    getattr(callee, "params", ()) if callee is not None else ()
                )
                if (
                    not target_params
                    or len(target_params) != len(value.args)
                    or any(
                        getattr(param_type, "ownership_domain", None)
                        not in ("direct", "whisper")
                        for _, param_type in target_params
                    )
                ):
                    nonowning_only = False
                    break
                caller_params = dict(params)
                for argument, (_, target_type) in zip(
                    value.args, target_params
                ):
                    if type(argument).__name__ == "Name":
                        source_name = getattr(argument, "value", None)
                        source_type = caller_params.get(source_name)
                        forwarded = (
                            source_type is not None
                            and (
                                getattr(source_type, "ownership_domain", None)
                                == getattr(target_type, "ownership_domain", None)
                                or (
                                    getattr(source_type, "ownership_domain", None)
                                    == "direct"
                                    and getattr(target_type, "ownership_domain", None)
                                    == "whisper"
                                )
                            )
                            and getattr(source_type, "name", None)
                            == getattr(target_type, "name", None)
                        )
                    else:
                        source = getattr(argument, "value", None)
                        source_name = getattr(source, "value", None)
                        source_type = caller_params.get(source_name)
                        forwarded = False
                    borrowed_owner = (
                        type(argument).__name__ == "Unary"
                        and getattr(argument, "op", None) == "&"
                        and type(source).__name__ == "Name"
                        and source_type is not None
                        and getattr(source_type, "name", None) in sole_names
                        and getattr(source_type, "name", None)
                        == getattr(target_type, "name", None)
                    ) if type(argument).__name__ != "Name" else False
                    if not (forwarded or borrowed_owner):
                        nonowning_only = False
                        break
            if not nonowning_only:
                break
    if not nonowning_only:
        raise LLVMToolchainError(
            "LLVM backend does not lower canonical Ownership Domains yet"
        )
    return checked


def generate_llvm_sir(module, frontend):
    """Generate SIR for the verified linear direct/whisper access subset."""
    from sotlas.sir import SIRGenerator, generate_checked_ownership_sir

    ownership_plan = require_llvm_ownership_supported(module, frontend)
    if ownership_plan is not None:
        return generate_checked_ownership_sir(ownership_plan).module
    return SIRGenerator(
        module_name=getattr(module, "name", "main")
    ).generate_from_ast(module)


class LLVMToolchain:
    """Gerenciador e orquestrador de compilação nativa via LLVM / LLD."""

    def __init__(self, custom_llvm_dir: Optional[Union[str, Path]] = None) -> None:
        self.llvm_dir: Optional[Path] = None
        if custom_llvm_dir:
            p = Path(custom_llvm_dir)
            if p.is_dir():
                self.llvm_dir = p

        if not self.llvm_dir:
            env_dir = os.environ.get("SOTLAS_LLVM_DIR")
            if env_dir and Path(env_dir).is_dir():
                self.llvm_dir = Path(env_dir)

        if not self.llvm_dir:
            for candidate in DEFAULT_LLVM_PATHS:
                if candidate.is_dir() and (candidate / ("clang.exe" if os.name == "nt" else "clang")).exists():
                    self.llvm_dir = candidate
                    break

    def find_tool(self, tool_name: str) -> Optional[Path]:
        """Localiza uma ferramenta LLVM específica (ex: 'clang', 'lld-link', 'llc', 'lldb')."""
        exe_suffix = ".exe" if os.name == "nt" else ""
        canonical_name = f"{tool_name}{exe_suffix}"

        if self.llvm_dir:
            candidate = self.llvm_dir / canonical_name
            if candidate.is_file():
                return candidate

        # Tenta no PATH do sistema
        which_path = shutil.which(tool_name)
        if which_path:
            return Path(which_path)

        return None

    def is_available(self) -> bool:
        """Verifica se o compilador Clang / LLVM está acessível no ambiente."""
        return self.find_tool("clang") is not None

    def get_version(self) -> str:
        """Retorna a versão do Clang / LLVM instalado."""
        clang = self.find_tool("clang")
        if not clang:
            return "Indisponível"
        try:
            res = subprocess.run([str(clang), "--version"], capture_output=True, text=True, check=True)
            first_line = res.stdout.splitlines()[0] if res.stdout else ""
            return first_line.strip()
        except Exception as e:
            return f"Erro ao detectar versão: {e}"

    def compile_llvm_ir_to_obj(
        self,
        ir_path_or_text: Union[str, Path],
        output_obj_path: Union[str, Path],
        opt_level: int = 2,
        target: Optional[str] = None
    ) -> Path:
        """Compila LLVM IR (.ll) diretamente para arquivo objeto (.obj / .o)."""
        clang = self.find_tool("clang")
        if not clang:
            raise LLVMToolchainError("Compilador Clang / LLVM não encontrado no sistema.")

        out_obj = Path(output_obj_path).resolve()
        out_obj.parent.mkdir(parents=True, exist_ok=True)

        cmd = [str(clang), "-c", f"-O{opt_level}"]
        if target:
            cmd += ["-target", target]

        temp_ir = None
        try:
            if isinstance(ir_path_or_text, Path) or (isinstance(ir_path_or_text, str) and os.path.exists(ir_path_or_text)):
                input_file = str(ir_path_or_text)
            else:
                # É código textual
                fd, temp_ir = tempfile.mkstemp(suffix=".ll", prefix="sotlas_ir_")
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(str(ir_path_or_text))
                input_file = temp_ir

            cmd += [input_file, "-o", str(out_obj)]
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode != 0:
                raise LLVMToolchainError(f"Falha na compilação LLVM IR -> OBJ:\n{res.stderr}")

            return out_obj
        finally:
            if temp_ir and os.path.exists(temp_ir):
                try:
                    os.remove(temp_ir)
                except OSError:
                    pass

    def compile_c_to_obj(
        self,
        c_path_or_text: Union[str, Path],
        output_obj_path: Union[str, Path],
        opt_level: int = 2,
        is_freestanding: bool = False,
        extra_flags: Optional[List[str]] = None
    ) -> Path:
        """Compila código C11 diretamente para arquivo objeto nativo (.obj / .o) via Clang."""
        clang = self.find_tool("clang")
        if not clang:
            raise LLVMToolchainError("Compilador Clang / LLVM não encontrado no sistema.")

        out_obj = Path(output_obj_path).resolve()
        out_obj.parent.mkdir(parents=True, exist_ok=True)

        cmd = [str(clang), "-std=c11", "-c", f"-O{opt_level}", "-Wall", "-Wextra"]
        if is_freestanding:
            cmd += [
                "-ffreestanding", "-nostdlib", "-nostdinc",
                "-mno-red-zone", "-mno-mmx", "-mno-sse", "-mno-sse2"
            ]
        if extra_flags:
            cmd += extra_flags

        temp_c = None
        try:
            if isinstance(c_path_or_text, Path) or (isinstance(c_path_or_text, str) and os.path.exists(c_path_or_text)):
                input_file = str(c_path_or_text)
            else:
                fd, temp_c = tempfile.mkstemp(suffix=".c", prefix="sotlas_c_")
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(str(c_path_or_text))
                input_file = temp_c

            cmd += [input_file, "-o", str(out_obj)]
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode != 0:
                raise LLVMToolchainError(f"Falha na compilação C11 -> OBJ com Clang:\n{res.stderr}")

            return out_obj
        finally:
            if temp_c and os.path.exists(temp_c):
                try:
                    os.remove(temp_c)
                except OSError:
                    pass

    def find_linker(self) -> Optional[Tuple[str, Path]]:
        """Localiza o linker mais rápido e adequado disponível:
        1. lld-link / ld.lld / lld (Linker LLVM)
        2. clang / gcc
        """
        if os.name == "nt":
            candidates = [("clang", "clang"), ("gcc", "gcc"), ("lld-link", "lld-link")]
        else:
            candidates = [("clang", "clang"), ("ld.lld", "ld.lld"), ("lld", "lld"), ("gcc", "gcc")]

        for kind, name in candidates:
            tool = self.find_tool(name)
            if tool:
                return (kind, tool)
        return None

    def link_native_binary(
        self,
        obj_files: List[Union[str, Path]],
        output_exe_path: Union[str, Path],
        extra_flags: Optional[List[str]] = None
    ) -> Path:
        """Linkedita um ou mais arquivos objeto em um executável nativo standalone (.exe / binário)."""
        linker_info = self.find_linker()
        if not linker_info:
            raise LLVMToolchainError(
                "Nenhum linker compatível (LLD / Clang / GCC) foi encontrado no sistema.\n"
                "Para compilar executáveis nativos standalone, instale o LLVM (ex: 'winget install LLVM.LLVM' no Windows "
                "ou 'sudo apt install lld clang' no Linux) ou defina a variável SOTLAS_LLVM_DIR."
            )

        kind, linker_bin = linker_info
        out_exe = Path(output_exe_path).resolve()
        out_exe.parent.mkdir(parents=True, exist_ok=True)

        if kind == "lld-link":
            cmd = [str(linker_bin)] + [str(p) for p in obj_files] + [f"/out:{out_exe}", "/nologo"]
            if extra_flags:
                cmd += extra_flags
        else:
            cmd = [str(linker_bin)] + [str(p) for p in obj_files] + ["-o", str(out_exe)]
            if extra_flags:
                cmd += extra_flags

        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            raise LLVMToolchainError(f"Falha na linkedição nativa com {kind} ({linker_bin}):\n{res.stderr}")

        # Em POSIX, alguns linkers/ambientes de CI podem produzir o arquivo
        # sem bits de execução. O contrato de `link_native_binary` é retornar
        # um executável pronto para `subprocess.run`.
        if os.name != "nt":
            mode = out_exe.stat().st_mode
            out_exe.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

        return out_exe

    def compile_source_to_native(
        self,
        source_text: str,
        source_name: str,
        output_path: Union[str, Path],
        emit_type: str = "exe",  # "exe", "obj", "llvm"
        backend: str = "llvm",   # "llvm", "c11"
        is_freestanding: bool = False,
        emit_debug: bool = True
    ) -> Path:
        """Pipeline fim a fim: compila código-fonte Sotlas diretamente para .ll, .obj ou .exe."""
        out = Path(output_path).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)

        from sotlas.codegen_llvm import CodegenLLVM
        production_frontend = canonical_llvm_frontend()
        from sotlas import compile_source

        if emit_type == "llvm":
            ast = production_frontend.parse(source_text, filename=source_name)
            sir_mod = generate_llvm_sir(ast, production_frontend)
            llvm_gen = CodegenLLVM(sir_mod, is_baremetal=is_freestanding, emit_debug=emit_debug)
            ir_code = llvm_gen.emit()
            out.write_text(ir_code, encoding="utf-8")
            return out

        safe_stem = re.sub(r'[^a-zA-Z0-9_]', '_', Path(source_name).stem) or "sotlas_module"

        if backend == "llvm":
            ast = production_frontend.parse(source_text, filename=source_name)
            sir_mod = generate_llvm_sir(ast, production_frontend)
            llvm_gen = CodegenLLVM(sir_mod, is_baremetal=is_freestanding, emit_debug=emit_debug)
            ir_code = llvm_gen.emit()

            if emit_type == "obj":
                return self.compile_llvm_ir_to_obj(ir_code, out)
            else:
                # Compila para obj temporário e linka para exe
                with tempfile.TemporaryDirectory() as tmpdir:
                    tmp_obj = Path(tmpdir) / f"{safe_stem}.obj"
                    self.compile_llvm_ir_to_obj(ir_code, tmp_obj)
                    return self.link_native_binary([tmp_obj], out)
        else:
            # Backend c11 com Clang nativo
            c_code = compile_source(source_text, source_name)
            if emit_type == "obj":
                return self.compile_c_to_obj(c_code, out, is_freestanding=is_freestanding)
            else:
                with tempfile.TemporaryDirectory() as tmpdir:
                    tmp_obj = Path(tmpdir) / f"{safe_stem}.obj"
                    self.compile_c_to_obj(c_code, tmp_obj, is_freestanding=is_freestanding)
                    return self.link_native_binary([tmp_obj], out)


# Instância global padrão da toolchain
default_toolchain = LLVMToolchain()
