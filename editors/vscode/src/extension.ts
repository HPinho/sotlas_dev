import * as vscode from 'vscode';
import { spawn } from 'child_process';
import * as path from 'path';
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
let outputChannel: vscode.OutputChannel;
let compilerPath = 'sotlas';

function runCompiler(args: string[], title: string, cwd?: string): void {
    outputChannel.clear();
    outputChannel.appendLine(`$ ${compilerCommandForDisplay(args)}`);
    outputChannel.show(true);

    const process = spawn(compilerPath, args, {
        cwd: cwd || vscode.workspace.workspaceFolders?.[0]?.uri.fsPath,
        shell: false
    });
    process.stdout.on('data', data => outputChannel.append(data.toString()));
    process.stderr.on('data', data => outputChannel.append(data.toString()));
    process.on('error', error => {
        outputChannel.appendLine(`\n${error.message}`);
        vscode.window.showErrorMessage(
            `Sotlas: não foi possível iniciar '${compilerPath}'. Confira sotlas.compilerPath e o PATH.`
        );
    });
    process.on('close', code => {
        outputChannel.appendLine(`\nProcesso encerrado com código ${code ?? 'desconhecido'}.`);
        if (code === 0) {
            vscode.window.showInformationMessage(`${title}: concluído.`);
        } else if (code !== null) {
            vscode.window.showErrorMessage(`${title}: falhou. Consulte o canal de saída Sotlas.`);
        }
    });
}

function compilerCommandForDisplay(args: string[]): string {
    return [compilerPath, ...args].map(value => JSON.stringify(value)).join(' ');
}

export async function activate(context: vscode.ExtensionContext) {
    const config = vscode.workspace.getConfiguration('sotlas');
    compilerPath = config.get<string>('compilerPath') || 'sotlas';
    const enableExternalLsp = config.get<boolean>('enableExternalLsp', false);
    outputChannel = vscode.window.createOutputChannel('Sotlas');
    context.subscriptions.push(outputChannel);

    // 1. Inicializa dicas estruturais locais, navegação por símbolos e hover
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
    statusBar.tooltip = 'Verificações estruturais locais; use Sotlas: Check Active File para executar o compilador';
    statusBar.command = 'sotlas.check';
    statusBar.show();
    context.subscriptions.push(statusBar);

    // 2. Cliente LSP do compilador (opcional)
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
            vscode.window.showErrorMessage(
                `Sotlas LSP não iniciou usando '${compilerPath}'. Confira sotlas.compilerPath e o PATH.`
            );
        }
    }

    // 3. Comandos de Compilação e Ferramental
    context.subscriptions.push(
        vscode.commands.registerCommand('sotlas.build', async () => {
            const folder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
            if (!folder) {
                vscode.window.showErrorMessage('Sotlas: abra uma pasta de projeto para compilar o pacote.');
                return;
            }
            runCompiler(['build', '--path', folder], 'Build');
        }),
        vscode.commands.registerCommand('sotlas.check', async () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor) return;
            const result = validator.validateDocument(editor.document);
            diagnosticCollection.set(editor.document.uri, result.diagnostics);
            runCompiler(['check', editor.document.uri.fsPath], 'Compiler check', path.dirname(editor.document.uri.fsPath));
        }),
        vscode.commands.registerCommand('sotlas.format', async () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor) return;
            runCompiler(['fmt', editor.document.uri.fsPath], 'Format', path.dirname(editor.document.uri.fsPath));
        }),
        vscode.commands.registerCommand('sotlas.studio', async () => {
            runCompiler(['studio'], 'Studio');
        }),
        vscode.commands.registerCommand('sotlas.repl', async () => {
            const task = new vscode.Task(
                { type: 'sotlas' },
                vscode.TaskScope.Workspace,
                'Sotlas REPL',
                'Sotlas',
                new vscode.ShellExecution(compilerPath, ['repl'])
            );
            await vscode.tasks.executeTask(task);
        }),
        vscode.commands.registerCommand('sotlas.dumpWasm', async () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor) return;
            runCompiler(['dump-wasm', editor.document.uri.fsPath], 'WebAssembly emission', path.dirname(editor.document.uri.fsPath));
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
            vscode.window.showInformationMessage('Verificações estruturais do Sotlas atualizadas.');
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
