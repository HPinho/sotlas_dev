import * as vscode from 'vscode';
import { spawn } from 'child_process';
import * as fs from 'fs';
import * as path from 'path';
import { StringDecoder } from 'string_decoder';
import { CloseAction, ErrorAction, LanguageClient, LanguageClientOptions, ServerOptions, TransportKind } from 'vscode-languageclient/node';
import { SotlasValidator } from './validator';
import { SotlasDocumentSymbolProvider, SotlasHoverProvider } from './providers';
import { parseCompilerDiagnostics } from './compilerDiagnostics';
import { createNativeProject, nativeColumn, nativePlan, readNativeSdk } from './nativeProject';

let client: LanguageClient | undefined;
let lspWatcher: vscode.FileSystemWatcher | undefined;
let diagnosticCollection: vscode.DiagnosticCollection;
let validator: SotlasValidator;
let outputChannel: vscode.OutputChannel;
let busy = false;
const compilerDiagnosticUris = new Set<string>();

function resource(): vscode.Uri | undefined {
    return vscode.window.activeTextEditor?.document.uri || vscode.workspace.workspaceFolders?.[0]?.uri;
}
function config(uri = resource()): vscode.WorkspaceConfiguration { return vscode.workspace.getConfiguration('sotlas', uri); }
function isNative(): boolean { return config().get<string>('toolchain', 'reference') === 'native'; }
function trusted(): void {
    if (!vscode.workspace.isTrusted) throw new Error('Trust this workspace before running compiler commands.');
}
function clearCompilerDiagnostics(): void {
    for (const text of compilerDiagnosticUris) {
        const uri = vscode.Uri.parse(text);
        diagnosticCollection.set(uri, (diagnosticCollection.get(uri) || []).filter(item => item.source !== 'Sotlas compiler'));
    }
    compilerDiagnosticUris.clear();
}
function publishCompilerDiagnostics(output: string, cwd: string, native: boolean, versions: Map<string, number>): void {
    const grouped = new Map<string, vscode.Diagnostic[]>();
    for (const parsed of parseCompilerDiagnostics(output)) {
        const file = path.isAbsolute(parsed.file) ? parsed.file : path.resolve(cwd, parsed.file);
        const uri = vscode.Uri.file(file);
        const document = vscode.workspace.textDocuments.find(doc => doc.uri.toString() === uri.toString());
        if (document && versions.has(uri.toString()) && document.version !== versions.get(uri.toString())) continue;
        let column = parsed.column - 1;
        if (native) {
            try {
                const line = document ? document.lineAt(parsed.line - 1).text : fs.readFileSync(file, 'utf8').split(/\r?\n/)[parsed.line - 1];
                if (line !== undefined) column = nativeColumn(line, parsed.column);
            } catch { /* Keep the compiler position if the source is no longer available. */ }
        }
        const severity = parsed.severity === 'warning' ? vscode.DiagnosticSeverity.Warning
            : parsed.severity === 'information' ? vscode.DiagnosticSeverity.Information : vscode.DiagnosticSeverity.Error;
        const diagnostic = new vscode.Diagnostic(new vscode.Range(parsed.line - 1, column, parsed.line - 1, column + 1), parsed.message, severity);
        diagnostic.source = 'Sotlas compiler';
        grouped.set(uri.toString(), [...(grouped.get(uri.toString()) || []), diagnostic]);
    }
    for (const [text, diagnostics] of grouped) {
        const uri = vscode.Uri.parse(text);
        diagnosticCollection.set(uri, [...(diagnosticCollection.get(uri) || []).filter(item => item.source !== 'Sotlas compiler'), ...diagnostics]);
        compilerDiagnosticUris.add(text);
    }
}
async function runCompiler(args: string[], title: string, cwd?: string, uri?: vscode.Uri): Promise<number | null> {
    trusted();
    if (busy) throw new Error('A Sotlas compiler command is already running. Wait for it to finish.');
    const settings = config(uri);
    const executable = settings.get<string>('compilerPath', 'sotlas');
    const native = settings.get<string>('toolchain', 'reference') === 'native';
    const directory = cwd || vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || process.cwd();
    const versions = new Map(vscode.workspace.textDocuments.map(doc => [doc.uri.toString(), doc.version]));
    clearCompilerDiagnostics(); outputChannel.clear();
    outputChannel.appendLine(`$ ${[executable, ...args].map(value => JSON.stringify(value)).join(' ')}`);
    outputChannel.show(true); busy = true;
    return new Promise(resolve => {
        const child = spawn(executable, args, { cwd: directory, shell: false, windowsHide: true });
        const stdout = new StringDecoder('utf8'); const stderr = new StringDecoder('utf8');
        let text = ''; let finished = false;
        const append = (chunk: string) => { text += chunk; outputChannel.append(chunk); };
        const finish = (code: number | null, error?: Error) => {
            if (finished) return;
            finished = true; busy = false; append(stdout.end()); append(stderr.end());
            publishCompilerDiagnostics(text, directory, native, versions);
            if (error) { outputChannel.appendLine(error.message); void vscode.window.showErrorMessage(`Sotlas: could not start '${executable}'. Check the compiler path.`); }
            else {
                outputChannel.appendLine(`\nProcess exited with code ${code === null ? 'unknown' : code}.`);
                if (code === 0) void vscode.window.showInformationMessage(`${title} completed.`);
                else void vscode.window.showErrorMessage(`${title} failed. See Sotlas output and Problems.`);
            }
            resolve(code);
        };
        child.stdout.on('data', data => append(stdout.write(data)));
        child.stderr.on('data', data => append(stderr.write(data)));
        child.on('error', error => finish(null, error));
        child.on('close', code => finish(code));
    });
}
function projectFolder(uri = resource()): vscode.WorkspaceFolder {
    const folder = (uri && vscode.workspace.getWorkspaceFolder(uri)) || vscode.workspace.workspaceFolders?.[0];
    if (!folder || folder.uri.scheme !== 'file') throw new Error('Open a local Sotlas project folder first.');
    return folder;
}
async function nativeBuild(folder = projectFolder()): Promise<string | undefined> {
    trusted();
    const settings = config(folder.uri);
    const plan = nativePlan('build', folder.uri.fsPath, {
        sourceRoot: settings.get<string>('nativeSourceRoot'), entry: settings.get<string>('nativeEntry'), output: settings.get<string>('nativeOutput')
    });
    const documents = vscode.workspace.textDocuments.filter(doc => !doc.isUntitled && doc.uri.scheme === 'file'
        && (doc.uri.fsPath === plan.sourceRoot || doc.uri.fsPath.startsWith(plan.sourceRoot + path.sep)));
    for (const doc of documents) if (doc.isDirty && !await doc.save()) throw new Error('Save the project sources before building.');
    const versions = new Map(documents.map(doc => [doc.uri.toString(), doc.version]));
    fs.mkdirSync(path.dirname(plan.output), { recursive: true });
    if (await runCompiler(plan.args, 'Native build', plan.cwd, folder.uri) !== 0) return undefined;
    if (documents.some(doc => doc.isDirty || versions.get(doc.uri.toString()) !== doc.version)) throw new Error('Sources changed during compilation. Build again before running.');
    if (!fs.existsSync(plan.output)) throw new Error('The compiler did not produce the configured executable.');
    return plan.output;
}
async function configureLanguageServer(): Promise<void> {
    if (client) { await client.stop(); client = undefined; }
    lspWatcher?.dispose(); lspWatcher = undefined;
    const settings = config();
    if (!vscode.workspace.isTrusted || settings.get<string>('toolchain', 'reference') === 'native' || !settings.get<boolean>('enableExternalLsp', false)) return;
    const executable = settings.get<string>('compilerPath', 'sotlas');
    lspWatcher = vscode.workspace.createFileSystemWatcher('**/*.sotlas');
    const serverOptions: ServerOptions = { command: executable, args: ['lsp', '--stdio'], transport: TransportKind.stdio };
    const clientOptions: LanguageClientOptions = {
        documentSelector: [{ scheme: 'file', language: 'sotlas' }], synchronize: { fileEvents: lspWatcher },
        errorHandler: { error: () => ({ action: ErrorAction.Shutdown }), closed: () => ({ action: CloseAction.DoNotRestart }) }
    };
    client = new LanguageClient('sotlasLanguageServer', 'Sotlas Language Server', serverOptions, clientOptions);
    try { await client.start(); }
    catch { void vscode.window.showErrorMessage(`Sotlas LSP could not start using '${executable}'.`); }
}

export async function activate(context: vscode.ExtensionContext) {
    outputChannel = vscode.window.createOutputChannel('Sotlas');
    validator = new SotlasValidator(); diagnosticCollection = vscode.languages.createDiagnosticCollection('sotlas');
    context.subscriptions.push(outputChannel, diagnosticCollection);
    const selector: vscode.DocumentSelector = [{ scheme: 'file', language: 'sotlas' }];
    context.subscriptions.push(vscode.languages.registerDocumentSymbolProvider(selector, new SotlasDocumentSymbolProvider(validator)),
        vscode.languages.registerHoverProvider(selector, new SotlasHoverProvider()));
    const pending = new Map<string, NodeJS.Timeout>();
    const validate = (document: vscode.TextDocument) => {
        if (document.languageId !== 'sotlas') return;
        const key = document.uri.toString(); const previous = pending.get(key); if (previous) clearTimeout(previous);
        pending.set(key, setTimeout(() => {
            pending.delete(key);
            diagnosticCollection.set(document.uri, [...validator.validateDocument(document).diagnostics,
                ...(diagnosticCollection.get(document.uri) || []).filter(item => item.source === 'Sotlas compiler')]);
        }, 150));
    };
    context.subscriptions.push(vscode.workspace.onDidOpenTextDocument(validate),
        vscode.workspace.onDidChangeTextDocument(event => validate(event.document)),
        vscode.workspace.onDidCloseTextDocument(document => {
            const key = document.uri.toString(); const timer = pending.get(key); if (timer) clearTimeout(timer);
            pending.delete(key); compilerDiagnosticUris.delete(key); diagnosticCollection.delete(document.uri);
        }), { dispose: () => { for (const timer of pending.values()) clearTimeout(timer); } });
    vscode.workspace.textDocuments.forEach(validate);
    const status = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
    status.text = '$(check) Sotlas'; status.tooltip = 'Local structural hints; run Check Active File for compiler diagnostics.';
    status.command = 'sotlas.check'; status.show(); context.subscriptions.push(status);
    let lspUpdates = Promise.resolve();
    const updateServer = () => { lspUpdates = lspUpdates.then(configureLanguageServer).catch(error => outputChannel.appendLine(String(error))); return lspUpdates; };
    await updateServer();
    context.subscriptions.push(vscode.workspace.onDidChangeConfiguration(event => { if (event.affectsConfiguration('sotlas')) void updateServer(); }));
    const command = (name: string, action: (...args: any[]) => Promise<unknown>) => context.subscriptions.push(vscode.commands.registerCommand(name, async (...args: any[]) => {
        try { return await action(...args); } catch (error) {
            const message = `Sotlas: ${error instanceof Error ? error.message : String(error)}`;
            outputChannel.appendLine(message); console.warn(message); void vscode.window.showErrorMessage(message); return undefined;
        }
    }));
    let selectedSdkRoot: string | undefined;
    command('sotlas.selectNativeSdk', async (selected?: vscode.Uri) => {
        trusted();
        const uri = selected || (await vscode.window.showOpenDialog({ canSelectFiles: false, canSelectFolders: true, canSelectMany: false, openLabel: 'Select Native SDK' }))?.[0];
        if (!uri) return;
        if (uri.scheme !== 'file') throw new Error('Choose a local SDK directory.');
        const sdk = readNativeSdk(uri.fsPath); selectedSdkRoot = sdk.root;
        await context.globalState.update('nativeSdkPath', sdk.root);
        const current = vscode.workspace.workspaceFolders?.[0];
        // Keep a fresh project directory empty until project creation. Do not
        // change the user's global reference-toolchain configuration.
        if (current && current.uri.scheme === 'file' && fs.realpathSync(current.uri.fsPath) !== fs.realpathSync(sdk.root)
            && fs.readdirSync(current.uri.fsPath).length !== 0) {
            const settings = config();
            await settings.update('toolchain', 'native', vscode.ConfigurationTarget.Workspace);
            await settings.update('compilerPath', sdk.compiler, vscode.ConfigurationTarget.Workspace);
            await settings.update('nativeSdkPath', sdk.root, vscode.ConfigurationTarget.Workspace);
            await updateServer();
        }
        void vscode.window.showInformationMessage('Native SDK selected. Open a native project or create one in an empty directory.');
        return sdk.root;
    });
    command('sotlas.createNativeProject', async (selected?: vscode.Uri) => {
        trusted();
        const sdkRoot = selectedSdkRoot || config().get<string>('nativeSdkPath', '') || context.globalState.get<string>('nativeSdkPath', '');
        if (!sdkRoot) throw new Error('Run Select Native SDK before creating a project.');
        const sdk = readNativeSdk(sdkRoot);
        const uri = selected || (await vscode.window.showOpenDialog({ canSelectFiles: false, canSelectFolders: true, canSelectMany: false, openLabel: 'Create Project in Empty Directory' }))?.[0];
        if (!uri) return;
        if (uri.scheme !== 'file') throw new Error('Choose a local empty project directory.');
        createNativeProject(uri.fsPath, sdk);
        const folder = vscode.workspace.getWorkspaceFolder(uri);
        if (folder?.uri.fsPath === uri.fsPath) {
            const settings = config(uri);
            const target = vscode.workspace.workspaceFolders!.length > 1 ? vscode.ConfigurationTarget.WorkspaceFolder : vscode.ConfigurationTarget.Workspace;
            await settings.update('toolchain', 'native', target);
            await settings.update('compilerPath', sdk.compiler, target);
            await settings.update('nativeSdkPath', sdk.root, target);
        }
        void vscode.window.showInformationMessage('Native project created.', 'Open Project').then(choice => { if (choice) return vscode.commands.executeCommand('vscode.openFolder', uri); });
        return uri.fsPath;
    });
    command('sotlas.build', async () => {
        if (isNative()) return nativeBuild();
        const folder = projectFolder(); return runCompiler(['build', '--path', folder.uri.fsPath], 'Build', folder.uri.fsPath);
    });
    command('sotlas.check', async () => {
        const document = vscode.window.activeTextEditor?.document;
        if (!document || document.uri.scheme !== 'file') throw new Error('Open a saved source file first.');
        const settings = config(document.uri); const native = settings.get<string>('toolchain', 'reference') === 'native';
        const folder = native ? projectFolder(document.uri) : undefined;
        trusted(); if (document.isDirty && !await document.save()) throw new Error('Save the source before checking.');
        diagnosticCollection.set(document.uri, validator.validateDocument(document).diagnostics);
        if (!folder) return runCompiler(['check', document.uri.fsPath], 'Compiler check', path.dirname(document.uri.fsPath), document.uri);
        const plan = nativePlan('check', folder.uri.fsPath, { sourceRoot: settings.get<string>('nativeSourceRoot'), output: settings.get<string>('nativeOutput') }, document.uri.fsPath);
        return runCompiler(plan.args, 'Native check', plan.cwd, document.uri);
    });
    command('sotlas.run', async () => {
        if (!isNative()) throw new Error('Run Native Project requires the native toolchain setting.');
        const folder = projectFolder();
        const executable = await nativeBuild(folder); if (!executable) return;
        const task = new vscode.Task({ type: 'sotlas-native' }, folder, 'Sotlas Native Run', 'Sotlas',
            new vscode.ProcessExecution(executable, config(folder.uri).get<string[]>('nativeRunArguments', []), { cwd: folder.uri.fsPath }));
        task.presentationOptions = { reveal: vscode.TaskRevealKind.Always, focus: true, clear: true };
        await vscode.tasks.executeTask(task); return executable;
    });
    const reference = (name: string, args: () => string[], title: string) => command(name, async () => {
        if (isNative()) throw new Error(`${title} is available through the reference toolchain; the native SDK does not provide this command.`);
        return runCompiler(args(), title, vscode.window.activeTextEditor && path.dirname(vscode.window.activeTextEditor.document.uri.fsPath));
    });
    const activeFile = () => { const file = vscode.window.activeTextEditor?.document.uri.fsPath; if (!file) throw new Error('Open a saved source file first.'); return file; };
    reference('sotlas.format', () => ['fmt', activeFile()], 'Format');
    reference('sotlas.studio', () => ['studio'], 'Studio');
    reference('sotlas.dumpWasm', () => ['dump-wasm', activeFile()], 'WebAssembly emission');
    command('sotlas.repl', async () => {
        trusted(); if (isNative()) throw new Error('The native SDK does not provide a REPL.');
        const task = new vscode.Task({ type: 'sotlas' }, vscode.TaskScope.Workspace, 'Sotlas REPL', 'Sotlas', new vscode.ProcessExecution(config().get<string>('compilerPath', 'sotlas'), ['repl']));
        await vscode.tasks.executeTask(task);
    });
    command('sotlas.restartServer', async () => { clearCompilerDiagnostics(); vscode.workspace.textDocuments.forEach(validate); await updateServer(); void vscode.window.showInformationMessage('Sotlas editor checks refreshed.'); });
}

export function deactivate(): Thenable<void> | undefined {
    lspWatcher?.dispose(); diagnosticCollection?.clear();
    return client?.stop();
}
