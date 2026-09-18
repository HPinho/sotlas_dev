"""Sotlas Rich Diagnostics — Formatação premium de erros e avisos do compilador.

Fornece:
- Severidade: error, warning, note, help
- Links de arquivo clicáveis
- Contexto de código com setas e sublinhados
- Sugestões de correção (help:)
- Referência à declaração original (note: declarado aqui)
- Contador de erros e avisos sumarizados
- Saída colorida via ANSI (detectada automaticamente)
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


# ---------------------------------------------------------------------------
# Detecção de cores ANSI
# ---------------------------------------------------------------------------

def _supports_ansi() -> bool:
    """Detecta se o terminal suporta cores ANSI."""
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    if sys.platform == "win32":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32  # type: ignore
            # Habilita ENABLE_VIRTUAL_TERMINAL_PROCESSING no Windows 10+
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
            return True
        except Exception:
            return False
    return hasattr(sys.stderr, "isatty") and sys.stderr.isatty()


_ANSI = _supports_ansi()


class _C:
    """Códigos de cor ANSI."""
    RESET   = "\033[0m"  if _ANSI else ""
    BOLD    = "\033[1m"  if _ANSI else ""
    DIM     = "\033[2m"  if _ANSI else ""
    RED     = "\033[31m" if _ANSI else ""
    YELLOW  = "\033[33m" if _ANSI else ""
    BLUE    = "\033[34m" if _ANSI else ""
    CYAN    = "\033[36m" if _ANSI else ""
    WHITE   = "\033[37m" if _ANSI else ""
    B_RED   = "\033[1;31m" if _ANSI else ""
    B_YELLOW = "\033[1;33m" if _ANSI else ""
    B_BLUE  = "\033[1;34m" if _ANSI else ""
    B_CYAN  = "\033[1;36m" if _ANSI else ""


# ---------------------------------------------------------------------------
# Severidade
# ---------------------------------------------------------------------------

class Severity(Enum):
    ERROR   = "error"
    WARNING = "warning"
    NOTE    = "note"
    HELP    = "help"


_SEV_COLOR = {
    Severity.ERROR:   (_C.B_RED,    "error"),
    Severity.WARNING: (_C.B_YELLOW, "warning"),
    Severity.NOTE:    (_C.B_BLUE,   "note"),
    Severity.HELP:    (_C.B_CYAN,   "help"),
}


# ---------------------------------------------------------------------------
# Span de localização
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DiagSpan:
    """Localização de um diagnóstico no código fonte."""
    file: str
    line: int
    col: int
    end_col: Optional[int] = None   # coluna final (inclusiva)
    label: Optional[str] = None     # rótulo opcional para este span


# ---------------------------------------------------------------------------
# Diagnóstico
# ---------------------------------------------------------------------------

@dataclass
class Diagnostic:
    """Um diagnóstico emitido pelo compilador Sotlas."""
    severity: Severity
    message: str
    primary_span: Optional[DiagSpan] = None
    secondary_spans: List[DiagSpan] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    helps: List[str] = field(default_factory=list)
    error_code: Optional[str] = None    # ex: "E0712"
    source_text: Optional[str] = None  # texto completo do arquivo para contexto

    def format(self, source: Optional[str] = None) -> str:
        src = source or self.source_text
        lines_out: List[str] = []
        color, label = _SEV_COLOR[self.severity]

        # Cabeçalho: error[E0001]: mensagem
        code_suffix = f"[{self.error_code}]" if self.error_code else ""
        header = f"{color}{_C.BOLD}{label}{code_suffix}{_C.RESET}{_C.BOLD}: {self.message}{_C.RESET}"
        lines_out.append(header)

        # Localização primária
        if self.primary_span:
            sp = self.primary_span
            arrow = f"{_C.B_BLUE}  --> {_C.RESET}{sp.file}:{sp.line}:{sp.col}"
            lines_out.append(arrow)

            if src and sp.line > 0:
                src_lines = src.splitlines()
                if 0 < sp.line <= len(src_lines):
                    line_str = src_lines[sp.line - 1]
                    line_no = str(sp.line)
                    pad = " " * len(line_no)
                    col_off = max(0, sp.col - 1)
                    end_col = sp.end_col if sp.end_col else sp.col
                    squiggle_len = max(1, end_col - sp.col + 1)
                    squiggle = "^" * squiggle_len
                    if sp.label:
                        squiggle += f" {sp.label}"

                    lines_out.append(f"{_C.B_BLUE}{pad} |{_C.RESET}")
                    lines_out.append(f"{_C.B_BLUE}{line_no} |{_C.RESET} {line_str}")
                    lines_out.append(f"{_C.B_BLUE}{pad} |{_C.RESET} {' ' * col_off}{color}{squiggle}{_C.RESET}")

        # Spans secundários (ex: "declarado aqui")
        for sp in self.secondary_spans:
            if src and sp.line > 0:
                src_lines = src.splitlines()
                if 0 < sp.line <= len(src_lines):
                    line_str = src_lines[sp.line - 1]
                    line_no = str(sp.line)
                    pad = " " * len(line_no)
                    col_off = max(0, sp.col - 1)
                    label_txt = sp.label or "aqui"
                    lines_out.append(f"{_C.B_BLUE}{pad} |{_C.RESET}")
                    lines_out.append(f"{_C.B_BLUE}{line_no} |{_C.RESET} {line_str}")
                    lines_out.append(
                        f"{_C.B_BLUE}{pad} |{_C.RESET} {' ' * col_off}{_C.CYAN}--- {label_txt}{_C.RESET}"
                    )

        # Notas adicionais
        for note in self.notes:
            lines_out.append(f"{_C.B_BLUE}  = note:{_C.RESET} {note}")

        # Sugestões de correção
        for help_msg in self.helps:
            lines_out.append(f"{_C.B_CYAN}  = help:{_C.RESET} {help_msg}")

        return "\n".join(lines_out)

    def __str__(self) -> str:
        return self.format()


# ---------------------------------------------------------------------------
# Emissor de diagnósticos
# ---------------------------------------------------------------------------

class DiagnosticEmitter:
    """Coleta e emite diagnósticos formatados."""

    def __init__(self, source: Optional[str] = None, filename: str = "<stdin>") -> None:
        self._source = source
        self._filename = filename
        self._diagnostics: List[Diagnostic] = []

    def error(
        self,
        message: str,
        line: int = 0,
        col: int = 0,
        end_col: Optional[int] = None,
        label: Optional[str] = None,
        notes: Optional[List[str]] = None,
        helps: Optional[List[str]] = None,
        code: Optional[str] = None,
        secondary_spans: Optional[List[DiagSpan]] = None,
    ) -> None:
        span = DiagSpan(self._filename, line, col, end_col, label) if line > 0 else None
        diag = Diagnostic(
            severity=Severity.ERROR,
            message=message,
            primary_span=span,
            secondary_spans=secondary_spans or [],
            notes=notes or [],
            helps=helps or [],
            error_code=code,
            source_text=self._source,
        )
        self._diagnostics.append(diag)

    def warning(
        self,
        message: str,
        line: int = 0,
        col: int = 0,
        notes: Optional[List[str]] = None,
        helps: Optional[List[str]] = None,
    ) -> None:
        span = DiagSpan(self._filename, line, col) if line > 0 else None
        diag = Diagnostic(
            severity=Severity.WARNING,
            message=message,
            primary_span=span,
            notes=notes or [],
            helps=helps or [],
            source_text=self._source,
        )
        self._diagnostics.append(diag)

    @property
    def has_errors(self) -> bool:
        return any(d.severity == Severity.ERROR for d in self._diagnostics)

    @property
    def error_count(self) -> int:
        return sum(1 for d in self._diagnostics if d.severity == Severity.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for d in self._diagnostics if d.severity == Severity.WARNING)

    def emit_all(self, out=None) -> None:
        """Emite todos os diagnósticos para stderr (ou stream fornecido)."""
        stream = out or sys.stderr
        for diag in self._diagnostics:
            print(diag.format(self._source), file=stream)
            print(file=stream)  # linha em branco entre diagnósticos

        # Sumário final
        parts = []
        if self.error_count:
            parts.append(f"{_C.B_RED}{self.error_count} error(s){_C.RESET}")
        if self.warning_count:
            parts.append(f"{_C.B_YELLOW}{self.warning_count} warning(s){_C.RESET}")
        if parts:
            print("aborting due to " + " and ".join(parts), file=stream)

    def format_all(self) -> str:
        """Retorna string com todos os diagnósticos formatados."""
        import io
        buf = io.StringIO()
        self.emit_all(out=buf)
        return buf.getvalue()

    def clear(self) -> None:
        self._diagnostics.clear()


# ---------------------------------------------------------------------------
# Helpers para erros comuns do compilador
# ---------------------------------------------------------------------------

def help_for_ownership_error(var_name: str, ownership_kind: str) -> str:
    """Gera sugestão de correção para erros de ownership."""
    if ownership_kind == "sole":
        return (
            f"Para compartilhar '{var_name}', considere mudar para 'co-owned' se múltiplos "
            f"proprietários forem necessários, ou passe como 'whisper {var_name}' se apenas "
            f"leitura for necessária."
        )
    if ownership_kind == "co-owned":
        return (
            f"Se você precisa de propriedade exclusiva, use 'sole'. "
            f"Se apenas leitura for necessária, use 'whisper'."
        )
    return f"Verifique o modificador de ownership aplicado a '{var_name}'."


def help_for_topology_error(from_topo: str, to_topo: str) -> str:
    """Gera sugestão de correção para erros de topologia de ponteiro."""
    conversions = {
        ("*rawphys", "*virtmap"): (
            "Ponteiros físicos requerem mapeamento explícito antes de uso virtual. "
            "Use a função de mapeamento de memória do kernel para obter um '*virtmap'."
        ),
        ("*virtmap", "*rawphys"): (
            "Ponteiros virtuais não podem ser convertidos em físicos diretamente. "
            "Use 'virt_to_phys()' ou a API de tradução do MMU."
        ),
        ("*rawphys", "*portwire"): (
            "Ponteiros físicos de memória e ponteiros de porta I/O são topologias distintas. "
            "Use funções específicas de acesso a portas (__inb, __outb)."
        ),
    }
    key = (from_topo, to_topo)
    return conversions.get(key, (
        f"Ponteiros de topologia '{from_topo}' e '{to_topo}' não são compatíveis. "
        f"Faça a conversão explicitamente com a API de topologia correta."
    ))


def help_for_barecore_error(construct: str) -> str:
    """Gera sugestão de correção para violações barecore."""
    hints = {
        "co-owned": "Em barecore, use 'sole' para propriedade exclusiva sem ARC.",
        "class":    "Em barecore, use 'struct' sem herança dinâmica.",
        "String":   "Em barecore, use '[UInt8; N]' para buffers de texto de tamanho fixo.",
        "Vec":      "Em barecore, use '[T; N]' para arrays de tamanho fixo.",
    }
    return hints.get(construct, f"O construto '{construct}' não é permitido em módulos barecore.")
