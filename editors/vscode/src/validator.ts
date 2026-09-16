import * as vscode from 'vscode';

export interface SymbolInfo {
    name: string;
    kind: vscode.SymbolKind;
    range: vscode.Range;
    selectionRange: vscode.Range;
    detail?: string;
    children?: SymbolInfo[];
}

export interface ValidationResult {
    diagnostics: vscode.Diagnostic[];
    symbols: SymbolInfo[];
}

/**
 * Analisador sintático e semântico nativo em TypeScript para a linguagem Sotlas.
 * Executa 100% dentro do runtime do VS Code/Node.js sem necessidade de Python ou executáveis externos.
 */
export class SotlasValidator {
    public validateDocument(document: vscode.TextDocument): ValidationResult {
        const text = document.getText();
        const diagnostics: vscode.Diagnostic[] = [];
        const symbols: SymbolInfo[] = [];

        // 1. Verificação léxica e de delimitadores balanceados (chaves, parênteses, strings)
        this.checkLexicalAndDelimiters(document, text, diagnostics);

        // 2. Análise linha a linha e estrutural de declarações
        this.checkStructureAndDeclarations(document, text, diagnostics, symbols);

        // 3. Verificação de símbolos duplicados e imports
        this.checkDuplicatesAndImports(document, text, symbols, diagnostics);

        return { diagnostics, symbols };
    }

    private checkLexicalAndDelimiters(
        document: vscode.TextDocument,
        text: string,
        diagnostics: vscode.Diagnostic[]
    ): void {
        interface Delim {
            char: string;
            pos: number;
            line: number;
            col: number;
        }

        const stack: Delim[] = [];
        let inLineComment = false;
        let inBlockComment = false;
        let inString = false;
        let inChar = false;
        let escapeNext = false;

        const lines = text.split(/\r?\n/);

        let globalOffset = 0;
        for (let lineIdx = 0; lineIdx < lines.length; lineIdx++) {
            const line = lines[lineIdx];
            inLineComment = false;

            for (let colIdx = 0; colIdx < line.length; colIdx++) {
                const currentOffset = globalOffset + colIdx;
                const ch = line[colIdx];
                const nextCh = colIdx + 1 < line.length ? line[colIdx + 1] : '';

                // Comentário de bloco
                if (inBlockComment) {
                    if (ch === '*' && nextCh === '/') {
                        inBlockComment = false;
                        colIdx++; // pula barra
                    }
                    continue;
                }

                // Comentário de linha
                if (inLineComment) {
                    break;
                }

                // String literal
                if (inString) {
                    if (escapeNext) {
                        escapeNext = false;
                    } else if (ch === '\\') {
                        escapeNext = true;
                    } else if (ch === '"') {
                        inString = false;
                    }
                    continue;
                }

                // Char literal
                if (inChar) {
                    if (escapeNext) {
                        escapeNext = false;
                    } else if (ch === '\\') {
                        escapeNext = true;
                    } else if (ch === '\'') {
                        inChar = false;
                    }
                    continue;
                }

                // Início de comentários
                if (ch === '/' && nextCh === '/') {
                    inLineComment = true;
                    break;
                }
                if (ch === '/' && nextCh === '*') {
                    inBlockComment = true;
                    colIdx++;
                    continue;
                }

                // Início de strings e chars
                if (ch === '"') {
                    inString = true;
                    escapeNext = false;
                    continue;
                }
                if (ch === '\'') {
                    inChar = true;
                    escapeNext = false;
                    continue;
                }

                // Delimitadores de abertura
                if (ch === '{' || ch === '(' || ch === '[') {
                    stack.push({ char: ch, pos: currentOffset, line: lineIdx, col: colIdx });
                }
                // Delimitadores de fechamento
                else if (ch === '}' || ch === ')' || ch === ']') {
                    const expectedMatch: Record<string, string> = { '}': '{', ')': '(', ']': '[' };
                    const pairNames: Record<string, string> = { '}': 'chave', ')': 'parêntese', ']': 'colchete' };

                    if (stack.length === 0) {
                        const range = new vscode.Range(lineIdx, colIdx, lineIdx, colIdx + 1);
                        diagnostics.push(new vscode.Diagnostic(
                            range,
                            `Fechamento de ${pairNames[ch]} '${ch}' inesperado (nenhuma abertura correspondente).`,
                            vscode.DiagnosticSeverity.Error
                        ));
                    } else {
                        const top = stack.pop()!;
                        if (top.char !== expectedMatch[ch]) {
                            const range = new vscode.Range(lineIdx, colIdx, lineIdx, colIdx + 1);
                            diagnostics.push(new vscode.Diagnostic(
                                range,
                                `Fechamento '${ch}' não corresponde à abertura '${top.char}' da linha ${top.line + 1}.`,
                                vscode.DiagnosticSeverity.Error
                            ));
                        }
                    }
                }
            }

            // String não terminada ao fim da linha
            if (inString && !escapeNext) {
                const range = new vscode.Range(lineIdx, line.length - 1, lineIdx, line.length);
                diagnostics.push(new vscode.Diagnostic(
                    range,
                    "String literal não terminada. Faltando aspas duplas de fechamento (\").",
                    vscode.DiagnosticSeverity.Error
                ));
                inString = false;
            }

            globalOffset += line.length + 1; // +1 para quebra de linha
        }

        // Delimitadores que ficaram abertos até o fim do arquivo
        while (stack.length > 0) {
            const unclosed = stack.pop()!;
            const names: Record<string, string> = { '{': 'Chave \'{\'', '(': 'Parêntese \'(\'', '[': 'Colchete \'[\'' };
            const range = new vscode.Range(unclosed.line, unclosed.col, unclosed.line, unclosed.col + 1);
            diagnostics.push(new vscode.Diagnostic(
                range,
                `${names[unclosed.char] || unclosed.char} aberto na linha ${unclosed.line + 1} não foi fechado.`,
                vscode.DiagnosticSeverity.Error
            ));
        }

        // Comentário de bloco não fechado
        if (inBlockComment) {
            const lastLine = lines.length - 1;
            const range = new vscode.Range(lastLine, 0, lastLine, lines[lastLine].length);
            diagnostics.push(new vscode.Diagnostic(
                range,
                "Comentário de bloco '/*' não fechado até o final do arquivo.",
                vscode.DiagnosticSeverity.Error
            ));
        }
    }

    private checkStructureAndDeclarations(
        document: vscode.TextDocument,
        text: string,
        diagnostics: vscode.Diagnostic[],
        symbols: SymbolInfo[]
    ): void {
        const lines = text.split(/\r?\n/);
        let hasModule = false;
        const isHeaderFile = document.fileName.endsWith('.sth');

        for (let i = 0; i < lines.length; i++) {
            const rawLine = lines[i];
            const trimmed = rawLine.trim();

            // Ignorar linhas vazias ou comentários completos
            if (!trimmed || trimmed.startsWith('//') || trimmed.startsWith('/*') || trimmed.startsWith('*')) {
                continue;
            }

            // 1. Verificação de 'module'
            if (trimmed.startsWith('module ') || trimmed === 'module') {
                hasModule = true;
                const match = trimmed.match(/^module\s+([^;]+?)\s*(;)?$/);
                if (!match) {
                    const startCol = rawLine.indexOf('module');
                    diagnostics.push(new vscode.Diagnostic(
                        new vscode.Range(i, startCol, i, rawLine.length),
                        "Declaração de módulo inválida. Sintaxe esperada: 'module nome::do::modulo;'",
                        vscode.DiagnosticSeverity.Error
                    ));
                } else if (!match[2]) {
                    const col = rawLine.indexOf(trimmed) + trimmed.length;
                    diagnostics.push(new vscode.Diagnostic(
                        new vscode.Range(i, col - 1, i, col),
                        "Ponto e vírgula ';' ausente no final da declaração de módulo.",
                        vscode.DiagnosticSeverity.Error
                    ));
                } else {
                    const modName = match[1].trim();
                    const startCol = rawLine.indexOf(modName);
                    const selRange = new vscode.Range(i, startCol, i, startCol + modName.length);
                    symbols.push({
                        name: modName,
                        kind: vscode.SymbolKind.Module,
                        range: new vscode.Range(i, 0, i, rawLine.length),
                        selectionRange: selRange,
                        detail: 'module'
                    });
                }
                continue;
            }

            // 2. Verificação de 'import'
            if (trimmed.startsWith('import ') || trimmed === 'import') {
                const match = trimmed.match(/^import\s+([^;]+?)\s*(;)?$/);
                if (!match) {
                    const startCol = rawLine.indexOf('import');
                    diagnostics.push(new vscode.Diagnostic(
                        new vscode.Range(i, startCol, i, rawLine.length),
                        "Declaração de import inválida. Sintaxe esperada: 'import caminho::modulo::*;'",
                        vscode.DiagnosticSeverity.Error
                    ));
                } else if (!match[2]) {
                    const col = rawLine.indexOf(trimmed) + trimmed.length;
                    diagnostics.push(new vscode.Diagnostic(
                        new vscode.Range(i, col - 1, i, col),
                        "Ponto e vírgula ';' ausente no final da declaração de import.",
                        vscode.DiagnosticSeverity.Error
                    ));
                }
                continue;
            }

            // 3. Verificação de 'const mut' (conflito ilegal)
            if (/\bconst\s+mut\b/.test(trimmed) || /\bmut\s+const\b/.test(trimmed)) {
                const match = trimmed.match(/\b(const\s+mut|mut\s+const)\b/);
                if (match) {
                    const col = rawLine.indexOf(match[0]);
                    diagnostics.push(new vscode.Diagnostic(
                        new vscode.Range(i, col, i, col + match[0].length),
                        "Conflito de modificadores: uma variável não pode ser 'const' e 'mut' ao mesmo tempo.",
                        vscode.DiagnosticSeverity.Error
                    ));
                }
            }

            // 4. Verificação de 'fn' / 'trapfn'
            const fnMatch = trimmed.match(/^(?:pub\s+)?(?:@(?:system|isr|naked|inline)\s+)?(fn|trapfn)\s+([A-Za-z_][A-Za-z0-9_]*)\s*(\(.*)?$/);
            if (fnMatch) {
                const fnKind = fnMatch[1];
                const fnName = fnMatch[2];
                const rest = fnMatch[3] || '';
                const nameCol = rawLine.indexOf(fnName);

                if (!rest.startsWith('(')) {
                    diagnostics.push(new vscode.Diagnostic(
                        new vscode.Range(i, nameCol + fnName.length, i, rawLine.length),
                        `Parênteses de parâmetros ausentes na função '${fnName}'. Sintaxe esperada: fn ${fnName}(...)`,
                        vscode.DiagnosticSeverity.Error
                    ));
                }

                symbols.push({
                    name: fnName,
                    kind: fnKind === 'trapfn' ? vscode.SymbolKind.Event : vscode.SymbolKind.Function,
                    range: new vscode.Range(i, 0, i, rawLine.length),
                    selectionRange: new vscode.Range(i, nameCol, i, nameCol + fnName.length),
                    detail: fnKind
                });
            }

            // 5. Verificação de 'struct' / 'class' / 'mesh' / 'register'
            const structMatch = trimmed.match(/^(?:pub\s+)?(struct|class|mesh|register)\s+([A-Za-z_][A-Za-z0-9_]*)/);
            if (structMatch) {
                const kindStr = structMatch[1];
                const sName = structMatch[2];
                const nameCol = rawLine.indexOf(sName);

                symbols.push({
                    name: sName,
                    kind: kindStr === 'class' ? vscode.SymbolKind.Class : (kindStr === 'register' ? vscode.SymbolKind.Interface : vscode.SymbolKind.Struct),
                    range: new vscode.Range(i, 0, i, rawLine.length),
                    selectionRange: new vscode.Range(i, nameCol, i, nameCol + sName.length),
                    detail: kindStr
                });
            }

            // 6. Verificação de 'enum'
            const enumMatch = trimmed.match(/^(?:pub\s+)?enum\s+([A-Za-z_][A-Za-z0-9_]*)/);
            if (enumMatch) {
                const eName = enumMatch[1];
                const nameCol = rawLine.indexOf(eName);

                symbols.push({
                    name: eName,
                    kind: vscode.SymbolKind.Enum,
                    range: new vscode.Range(i, 0, i, rawLine.length),
                    selectionRange: new vscode.Range(i, nameCol, i, nameCol + eName.length),
                    detail: 'enum'
                });
            }

            // 7. Verificação de 'const' / 'static'
            const globalMatch = trimmed.match(/^(?:pub\s+)?(const|static)\s+(?:mut\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*:\s*([A-Za-z0-9_\[\]* ]+)/);
            if (globalMatch) {
                const gKind = globalMatch[1];
                const gName = globalMatch[2];
                const nameCol = rawLine.indexOf(gName);

                if (!trimmed.includes(';') && !trimmed.endsWith('{')) {
                    diagnostics.push(new vscode.Diagnostic(
                        new vscode.Range(i, rawLine.length - 1, i, rawLine.length),
                        `Ponto e vírgula ';' ausente na declaração da constante/global '${gName}'.`,
                        vscode.DiagnosticSeverity.Error
                    ));
                }

                symbols.push({
                    name: gName,
                    kind: gKind === 'const' ? vscode.SymbolKind.Constant : vscode.SymbolKind.Variable,
                    range: new vscode.Range(i, 0, i, rawLine.length),
                    selectionRange: new vscode.Range(i, nameCol, i, nameCol + gName.length),
                    detail: gKind
                });
            }

            // 8. Verificação de literais numéricos hexadecimais ou binários malformados
            const badHex = trimmed.match(/\b0x(?![0-9a-fA-F_])([a-zA-Z0-9_]*)\b/);
            if (badHex) {
                const col = rawLine.indexOf(badHex[0]);
                diagnostics.push(new vscode.Diagnostic(
                    new vscode.Range(i, col, i, col + badHex[0].length),
                    `Literal hexadecimal malformado '${badHex[0]}'. Dígitos hexadecimais esperados após '0x'.`,
                    vscode.DiagnosticSeverity.Error
                ));
            }

            const badBin = trimmed.match(/\b0b(?![01_])([a-zA-Z0-9_]*)\b/);
            if (badBin) {
                const col = rawLine.indexOf(badBin[0]);
                diagnostics.push(new vscode.Diagnostic(
                    new vscode.Range(i, col, i, col + badBin[0].length),
                    `Literal binário malformado '${badBin[0]}'. Apenas '0' ou '1' permitidos após '0b'.`,
                    vscode.DiagnosticSeverity.Error
                ));
            }
        }

        // Aviso se arquivo .sotlas não possuir declaração 'module'
        if (!hasModule && !isHeaderFile && lines.length > 5) {
            diagnostics.push(new vscode.Diagnostic(
                new vscode.Range(0, 0, 0, lines[0].length || 1),
                "Aviso de organização: Arquivo Sotlas sem declaração explícita de módulo no topo (ex: 'module meu_modulo;').",
                vscode.DiagnosticSeverity.Warning
            ));
        }
    }

    private checkDuplicatesAndImports(
        document: vscode.TextDocument,
        text: string,
        symbols: SymbolInfo[],
        diagnostics: vscode.Diagnostic[]
    ): void {
        const seenSymbols = new Map<string, SymbolInfo>();

        for (const sym of symbols) {
            if (sym.kind === vscode.SymbolKind.Module) {
                continue;
            }

            if (seenSymbols.has(sym.name)) {
                const prev = seenSymbols.get(sym.name)!;
                diagnostics.push(new vscode.Diagnostic(
                    sym.selectionRange,
                    `Símbolo duplicado: '${sym.name}' já foi declarado na linha ${prev.selectionRange.start.line + 1}.`,
                    vscode.DiagnosticSeverity.Error
                ));
            } else {
                seenSymbols.set(sym.name, sym);
            }
        }
    }
}
