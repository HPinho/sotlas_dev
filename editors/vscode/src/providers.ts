import * as vscode from 'vscode';
import { SotlasValidator, SymbolInfo } from './validator';

/**
 * Provedor nativo de Outline / Símbolos do Documento para Sotlas.
 */
export class SotlasDocumentSymbolProvider implements vscode.DocumentSymbolProvider {
    constructor(private validator: SotlasValidator) {}

    public provideDocumentSymbols(
        document: vscode.TextDocument,
        token: vscode.CancellationToken
    ): vscode.ProviderResult<vscode.DocumentSymbol[]> {
        const result = this.validator.validateDocument(document);
        return result.symbols.map(sym => this.toDocumentSymbol(sym));
    }

    private toDocumentSymbol(sym: SymbolInfo): vscode.DocumentSymbol {
        const docSym = new vscode.DocumentSymbol(
            sym.name,
            sym.detail || '',
            sym.kind,
            sym.range,
            sym.selectionRange
        );
        if (sym.children && sym.children.length > 0) {
            docSym.children = sym.children.map(c => this.toDocumentSymbol(c));
        }
        return docSym;
    }
}

/**
 * Provedor nativo de Hover (Tooltips informativos ao passar o mouse) para Sotlas.
 */
export class SotlasHoverProvider implements vscode.HoverProvider {
    private static readonly DOCS: Record<string, string> = {
        // Ownership & Modifiers
        'sole': '**sole (Ownership Exclusivo)**\n\nDeclara que este recurso/ponteiro possui um único proprietário no sistema. Não pode ser clonado ou compartilhado sem transferência explícita de posse (*move semantics*).',
        'co-owned': '**co-owned (Ownership Compartilhado)**\n\nPermite múltiplos proprietários sobre a mesma região de memória de forma segura, com contagem atômica ou barreiras de sincronização.',
        'island': '**island (Isolamento de Memória)**\n\nRegião de memória ou ator estritamente isolado que não compartilha referências diretas com outras partes do sistema.',
        'whisper': '**whisper (Comunicação Assíncrona Leve)**\n\nPrimitiva de passagem de mensagens ou sincronização não bloqueante entre domínios.',
        'direct': '**direct (Acesso Direto)**\n\nPonteiro ou chamada direta sem despacho dinâmico ou indireções intermediárias.',
        'mut': '**mut (Mutabilidade)**\n\nEspecifica que o valor, ponteiro ou campo pode sofrer mutação após a inicialização.',

        // Pointers
        '*rawphys': '**\*rawphys (Ponteiro Físico Direto)**\n\nEndereçamento físico de hardware (Bare-Metal / Driver). Utilizado para mapeamento MMIO e periféricos.',
        '*virtmap': '**\*virtmap (Ponteiro Virtual Mapeado)**\n\nPonteiro que opera em espaço de memória virtual paginado pelo MMU.',
        '*portwire': '**\*portwire (Porta de I/O de Hardware)**\n\nInteração direta com portas de I/O (ex: arquiteturas x86 `in/out` ou registradores de barramento).',
        '*dmazone': '**\*dmazone (Zona de Acesso Direto à Memória)**\n\nRegião de memória contígua alinhada para transferências DMA de alto desempenho pelo hardware.',
        '*voidzero': '**\*voidzero (Ponteiro Sentinela/Zero-Safe)**\n\nReferência a blocos garantidamente preenchidos com zeros ou sentinela nulo sem overhead.',

        // Keywords & Declarations
        'barecore': '**barecore (Ambiente Bare-Metal)**\n\nIndica que a rotina ou módulo opera sem sistema operacional subjacente e sem runtime padrão.',
        'quarantine': '**quarantine (Isolamento de Falhas)**\n\nIsola temporariamente um periférico ou região de memória instável para evitar que erros de hardware propaguem no sistema.',
        'handover': '**handover (Transferência de Controle/Posse)**\n\nTransfere de forma atômica o ownership de um recurso entre dois domínios ou threads.',
        'gate': '**gate (Portão de Sincronização)**\n\nBarreira de sincronização concorrente para seções críticas e acesso a hardware compartilhado.',
        'discern': '**discern (Correspondência Padrão / Pattern Matching)**\n\nDespacho estático e exaustivo de padrões em enums e uniões discriminadas.',
        'guard': '**guard (Garantia Prévia)**\n\nCondição obrigatória que deve ser verdadeira para prosseguir, garantindo saída antecipada em falha.',
        'defer': '**defer (Execução Tardia)**\n\nAgenda a execução de uma instrução ou bloco para o momento em que o escopo atual for encerrado.',
        'trapfn': '**trapfn (Manipulador de Interrupção / Trap)**\n\nFunção de baixo nível executada em contexto de interrupção ou exceção de CPU.',
        'fn': '**fn (Função)**\n\nDeclaração padrão de função com tipagem estática e verificação de ownership.',
        'mesh': '**mesh (Topologia de Módulos)**\n\nDeclaração de interconexão entre módulos e domínios do sistema.',
        'register': '**register (Registrador de Hardware MMIO)**\n\nDeclaração determinística de registrador de hardware com campos de bits mapeados (`campo: lo..hi;`). Permite leitura e escrita volátil atômica garantida pelo compilador sem necessidade de macros manuais.',
        'mould': '**mould (Bloco Comptime)**\n\nAvaliação de expressões constantes e asserções estáticas (`probe <cond>, "<msg>";`) diretamente em tempo de compilação.'
    };

    public provideHover(
        document: vscode.TextDocument,
        position: vscode.Position,
        token: vscode.CancellationToken
    ): vscode.ProviderResult<vscode.Hover> {
        const range = document.getWordRangeAtPosition(position, /[*A-Za-z_][*A-Za-z0-9_-]*/);
        if (!range) {
            return null;
        }

        const word = document.getText(range);
        const doc = SotlasHoverProvider.DOCS[word];
        if (doc) {
            const md = new vscode.MarkdownString(doc);
            md.isTrusted = true;
            return new vscode.Hover(md, range);
        }

        return null;
    }
}
