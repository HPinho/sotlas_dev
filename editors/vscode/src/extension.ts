import * as vscode from 'vscode';
import {
    CloseAction,
    ErrorAction,
    LanguageClient,
    LanguageClientOptions,
    ServerOptions,
    TransportKind
} from 'vscode-languageclient/node';
import { SotlasValidator } from './validator';
import { SotlasDocumentSymbolProvider, SotlasHoverProvider } from './providers';

let client: LanguageClient | undefined;
let diagnosticCollection: vscode.DiagnosticCollection;
let validator: SotlasValidator;

export async function activate(context: vscode.ExtensionContext) {
    const config = vscode.workspace.getConfiguration('sotlas');
    const compilerPath = config.get<string>('compilerPath') || 'sotlas';
    const enableExternalLsp = config.get<boolean>('enableExternalLsp', false);

    // 1. Inicializa o motor nativo em TypeScript (Diagnósticos, Símbolos e Hover)
    validator = new SotlasValidator();
    diagnosticCollection = vscode.languages.createDiagnosticCollection('sotlas');
    context.subscriptions.push(diagnosticCollection);

    // Registra provedores de símbolos (Outline) e hover nativos
    const docSelector: vscode.DocumentSelector = [
        { scheme: 'file', language: 'sotlas' }
    ];

    context.subscriptions.push(
        vscode.languages.registerDocumentSymbolProvider(
            docSelector,
            new SotlasDocumentSymbolProvider(validator)
        )
    );

    context.subscriptions.push(
        vscode.languages.registerHoverProvider(
            docSelector,
            new SotlasHoverProvider()
        )
    );

    // Debouncer para validação em tempo real durante digitação
    let timeout: NodeJS.Timeout | undefined;
    function triggerValidation(document: vscode.TextDocument) {
        if (document.languageId !== 'sotlas') {
            return;
        }
        if (timeout) {
            clearTimeout(timeout);
        }
        timeout = setTimeout(() => {
            const result = validator.validateDocument(document);
            diagnosticCollection.set(document.uri, result.diagnostics);
        }, 150);
    }

    // Valida documentos ao abrir, alterar ou salvar
    context.subscriptions.push(
        vscode.workspace.onDidOpenTextDocument((doc) => triggerValidation(doc)),
        vscode.workspace.onDidChangeTextDocument((e) => triggerValidation(e.document)),
        vscode.workspace.onDidCloseTextDocument((doc) => diagnosticCollection.delete(doc.uri))
    );

    // Valida todos os documentos já abertos no momento da ativação
    vscode.workspace.textDocuments.forEach((doc) => triggerValidation(doc));

    // Status bar indicator
    const statusBar = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
    statusBar.text = '$(check) Sotlas';
    statusBar.tooltip = 'Motor de Validação Nativo Sotlas Ativo';
    statusBar.command = 'sotlas.check';
    statusBar.show();
    context.subscriptions.push(statusBar);

    // 2. Cliente LSP Externo (Opcional, quando o compilador nativo estiver disponível)
    if (enableExternalLsp) {
        try {
            const serverOptions: ServerOptions = {
                command: compilerPath,
                args: ['lsp', '--stdio'],
                transport: TransportKind.stdio
            };

            const clientOptions: LanguageClientOptions = {
                documentSelector: [{ scheme: 'file', language: 'sotlas' }],
                synchronize: {
                    fileEvents: vscode.workspace.createFileSystemWatcher('**/*.sotlas')
                },
                errorHandler: {
                    error: () => ({ action: ErrorAction.Shutdown }),
                    closed: () => ({ action: CloseAction.DoNotRestart })
                }
            };

            client = new LanguageClient(
                'sotlasLanguageServer',
                'Sotlas Language Server',
                serverOptions,
                clientOptions
            );

            await client.start();
        } catch (e) {
            console.log('Compilador nativo Sotlas LSP não detectado no PATH. Usando motor nativo TypeScript.');
        }
    }

    // 3. Comandos de Compilação e Ferramental
    context.subscriptions.push(
        vscode.commands.registerCommand('sotlas.build', async () => {
            const terminal = vscode.window.createTerminal('Sotlas Build');
            terminal.show();
            terminal.sendText(`${compilerPath} build`);
        }),
        vscode.commands.registerCommand('sotlas.check', async () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor) return;
            // Executa a validação nativa imediatamente
            const result = validator.validateDocument(editor.document);
            diagnosticCollection.set(editor.document.uri, result.diagnostics);
            
            if (result.diagnostics.length === 0) {
                vscode.window.showInformationMessage(`Sotlas: Nenhum erro de sintaxe encontrado em ${editor.document.fileName}.`);
            } else {
                const errors = result.diagnostics.filter(d => d.severity === vscode.DiagnosticSeverity.Error).length;
                const warns = result.diagnostics.filter(d => d.severity === vscode.DiagnosticSeverity.Warning).length;
                vscode.window.showWarningMessage(`Sotlas: ${errors} erro(s) e ${warns} aviso(s) detectados.`);
            }
        }),
        vscode.commands.registerCommand('sotlas.format', async () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor) return;
            const terminal = vscode.window.createTerminal('Sotlas Format');
            terminal.show();
            terminal.sendText(`${compilerPath} fmt "${editor.document.fileName}"`);
        }),
        vscode.commands.registerCommand('sotlas.studio', async () => {
            const terminal = vscode.window.createTerminal('Sotlas Studio');
            terminal.show();
            terminal.sendText(`${compilerPath} studio`);
        }),
        vscode.commands.registerCommand('sotlas.repl', async () => {
            const terminal = vscode.window.createTerminal('Sotlas REPL');
            terminal.show();
            terminal.sendText(`${compilerPath} repl`);
        }),
        vscode.commands.registerCommand('sotlas.dumpWasm', async () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor) return;
            const terminal = vscode.window.createTerminal('Sotlas Wasm');
            terminal.show();
            terminal.sendText(`${compilerPath} compile "${editor.document.fileName}" --emit-wasm`);
        }),
        vscode.commands.registerCommand('sotlas.restartServer', async () => {
            const editor = vscode.window.activeTextEditor;
            if (editor) {
                const result = validator.validateDocument(editor.document);
                diagnosticCollection.set(editor.document.uri, result.diagnostics);
            }
            if (client) {
                await client.stop();
                await client.start();
            }
            vscode.window.showInformationMessage('Motor Sotlas reiniciado com sucesso.');
        })
    );
}

export function deactivate(): Thenable<void> | undefined {
    if (diagnosticCollection) {
        diagnosticCollection.clear();
        diagnosticCollection.dispose();
    }
    if (!client) {
        return undefined;
    }
    return client.stop();
}
