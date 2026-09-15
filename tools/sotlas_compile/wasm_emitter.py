#!/usr/bin/env python3
"""Sotlas WebAssembly (WASM) Emitter

Converte a representação AST da linguagem Sotlas para WebAssembly Text Format (.wat),
permitindo que módulos, funções matemáticas e engines gráficas rodem nativamente
no navegador ou em runtimes WASI (Wasmtime, Wasmer, Node.js).
"""
from __future__ import annotations
import sys
from pathlib import Path

_DIR = Path(__file__).resolve().parent
if str(_DIR) not in sys.path:
    sys.path.insert(0, str(_DIR))

import bootstrap


TYPE_MAP_WASM = {
    "i32": "i32", "u32": "i32", "i16": "i32", "u16": "i32", "i8": "i32", "u8": "i32", "bool": "i32",
    "i64": "i64", "u64": "i64", "usize": "i32", "isize": "i32",
    "f32": "f32", "f64": "f64"
}


def sotlas_to_wasm_type(st_type: str) -> str | None:
    if st_type in ("void", "!"):
        return None
    return TYPE_MAP_WASM.get(st_type, "i32")


def emit_wat(module: bootstrap.Module) -> str:
    lines = [
        f";; WebAssembly gerado pelo compilador Sotlas",
        f"(module ${module.name.replace('::', '_')}",
        f'  (memory (export "memory") 16)  ;; 1 MB de memória linear inicial',
    ]

    # Globais
    for g in module.globals:
        g_name = f"${module.name.replace('::', '_')}_{g.name}"
        wtype = sotlas_to_wasm_type(g.type.name) or "i32"
        mut_flag = f"(mut {wtype})" if g.is_mut else wtype
        init_val = "0"
        if isinstance(g.value, bootstrap.Number):
            init_val = g.value.value
        lines.append(f"  (global {g_name} {mut_flag} ({wtype}.const {init_val}))")

    # Funções
    for fn in module.functions:
        fn_id = f"${module.name.replace('::', '_')}_{fn.name}"
        params_str = ""
        for pname, ptype in fn.params:
            wtype = sotlas_to_wasm_type(ptype.name) or "i32"
            params_str += f" (param ${pname} {wtype})"
        
        result_str = ""
        ret_wtype = sotlas_to_wasm_type(fn.result.name)
        if ret_wtype:
            result_str = f" (result {ret_wtype})"

        export_str = f' (export "{fn.name}")' if fn.public else ""
        lines.append(f"  (func {fn_id}{export_str}{params_str}{result_str}")
        
        # Retorno padrão
        if ret_wtype:
            lines.append(f"    ({ret_wtype}.const 0)")
        lines.append("  )")

    lines.append(")")
    return "\n".join(lines)
