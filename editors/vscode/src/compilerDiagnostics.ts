export interface ParsedCompilerDiagnostic {
    file: string;
    line: number;
    column: number;
    message: string;
    severity: 'error' | 'warning' | 'information';
}

/** Parse source locations from the canonical CLI's `file:line:column` errors. */
export function parseCompilerDiagnostics(output: string): ParsedCompilerDiagnostic[] {
    const diagnostics: ParsedCompilerDiagnostic[] = [];
    for (const line of output.split(/\r?\n/)) {
        const match = line.match(/^(?:sotlas:\s*(erro|error|aviso|warning|note):\s*)?(.+):(\d+):(\d+):\s*(.*)$/i);
        if (!match) continue;

        const [, prefixSeverity, file, lineText, columnText, detail] = match;
        const lineNumber = Number(lineText);
        const columnNumber = Number(columnText);
        if (!file || lineNumber < 1 || columnNumber < 1) continue;

        diagnostics.push({
            file,
            line: lineNumber,
            column: columnNumber,
            message: detail.trim() || 'Compiler rejected this source location.',
            severity: /^(?:aviso|warning)$/i.test(prefixSeverity) || /\bwarning\b/i.test(detail)
                ? 'warning'
                : /^(?:note)$/i.test(prefixSeverity)
                    ? 'information'
                    : 'error'
        });
    }
    return diagnostics;
}
