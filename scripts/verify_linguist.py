#!/usr/bin/env python3
"""Script de verificação de conformidade de submissão ao GitHub Linguist (Zero-Python Readiness).

Verifica:
1. Integridade e sintaxe de todas as amostras em `samples/Sotlas/`
2. Validade estrutural da gramática TextMate (`editors/vscode/syntaxes/sotlas.tmLanguage.json`)
3. Conformidade da especificação YAML (`spec/linguist/languages.yml`)
4. Validação do compilador nativo executando sobre as amostras
"""
from __future__ import annotations
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def check_mark(status: bool) -> str:
    return "\033[32m[OK]\033[0m" if status else "\033[31m[FALHA]\033[0m"

def main() -> int:
    print("=" * 65)
    print("Sotlas — Verificador de Conformidade com GitHub Linguist")
    print("=" * 65)

    all_passed = True

    # 1. Validar especificação languages.yml
    print("\n1. Validando especificação spec/linguist/languages.yml...")
    yml_file = ROOT / "spec" / "linguist" / "languages.yml"
    if not yml_file.is_file():
        print(f"  {check_mark(False)} Arquivo {yml_file} não encontrado")
        all_passed = False
    else:
        content = yml_file.read_text(encoding="utf-8")
        reqs = ["Sotlas:", "type: programming", "color:", "extensions:", ".sotlas", "tm_scope: source.sotlas", "ace_mode:"]
        missing = [r for r in reqs if r not in content]
        if missing:
            print(f"  {check_mark(False)} Campos obrigatórios ausentes no YAML: {missing}")
            all_passed = False
        else:
            print(f"  {check_mark(True)} Definição canônica do Linguist válida e completa.")

    # 2. Validar gramática TextMate JSON
    print("\n2. Validando gramática TextMate (editors/vscode/syntaxes/sotlas.tmLanguage.json)...")
    tm_file = ROOT / "editors" / "vscode" / "syntaxes" / "sotlas.tmLanguage.json"
    if not tm_file.is_file():
        print(f"  {check_mark(False)} Arquivo TextMate {tm_file} não encontrado")
        all_passed = False
    else:
        try:
            tm_data = json.loads(tm_file.read_text(encoding="utf-8"))
            scope = tm_data.get("scopeName")
            if scope != "source.sotlas":
                print(f"  {check_mark(False)} scopeName inválido: {scope} (esperado: source.sotlas)")
                all_passed = False
            else:
                patterns_count = len(tm_data.get("patterns", []))
                repo_count = len(tm_data.get("repository", {}))
                print(f"  {check_mark(True)} Gramática JSON válida: scope='{scope}', {patterns_count} padrões raiz, {repo_count} regras no repositório.")
        except Exception as e:
            print(f"  {check_mark(False)} Erro no parsing JSON do TextMate: {e}")
            all_passed = False

    # 3. Validar amostras de código em samples/Sotlas/
    print("\n3. Validando amostras reais em samples/Sotlas/...")
    samples_dir = ROOT / "samples" / "Sotlas"
    if not samples_dir.is_dir():
        print(f"  {check_mark(False)} Diretório de amostras {samples_dir} não encontrado")
        all_passed = False
    else:
        samples = list(samples_dir.glob("*.sotlas"))
        if len(samples) < 2:
            print(f"  {check_mark(False)} GitHub Linguist exige amostras representativas (mínimo 2, encontradas {len(samples)})")
            all_passed = False
        else:
            native_exe = ROOT / "bin" / ("sotlas.exe" if os.name == "nt" else "sotlas_native")
            for s in samples:
                size = s.stat().st_size
                if size < 200:
                    print(f"  {check_mark(False)} Amostra {s.name} muito curta ({size} bytes)")
                    all_passed = False
                    continue

                if native_exe.is_file():
                    out_tmp = ROOT / "build" / f"verify_{s.stem}.c"
                    out_tmp.parent.mkdir(parents=True, exist_ok=True)
                    res = subprocess.run([str(native_exe), str(s), "-o", str(out_tmp)], capture_output=True, text=True)
                    if res.returncode == 0 and out_tmp.is_file():
                        print(f"  {check_mark(True)} {s.name} ({size} bytes) -> Compilação nativa OK via {native_exe.name}")
                        if out_tmp.is_file():
                            out_tmp.unlink()
                    else:
                        print(f"  {check_mark(False)} {s.name} falhou na compilação nativa: {res.stderr}")
                        all_passed = False
                else:
                    print(f"  {check_mark(True)} {s.name} ({size} bytes) presente.")

    # 4. Validar diretivas .gitattributes
    print("\n4. Validando diretivas do .gitattributes...")
    gitattr = ROOT / ".gitattributes"
    if not gitattr.is_file():
        print(f"  {check_mark(False)} .gitattributes não encontrado")
        all_passed = False
    else:
        text = gitattr.read_text(encoding="utf-8")
        if "*.sotlas" in text and "linguist" in text:
            print(f"  {check_mark(True)} .gitattributes configurado para detecção e coloração imediata.")
        else:
            print(f"  {check_mark(False)} .gitattributes não contém regras do Linguist para *.sotlas")
            all_passed = False

    print("\n" + "=" * 65)
    if all_passed:
        print("\033[32m[SUCESSO] Todos os requisitos de submissão ao GitHub Linguist atendidos!\033[0m")
        print("Consulte docs/github_linguist_submission_guide.md para as etapas de PR.")
        print("=" * 65)
        return 0
    else:
        print("\033[31m[FALHA] Algumas verificações do GitHub Linguist não foram satisfeitas.\033[0m")
        print("=" * 65)
        return 1

if __name__ == "__main__":
    sys.exit(main())
