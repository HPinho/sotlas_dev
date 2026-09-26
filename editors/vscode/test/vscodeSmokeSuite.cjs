const assert = require('node:assert/strict');
const vscode = require('vscode');

exports.run = async function run() {
  const extension = vscode.extensions.getExtension('sotlas-lang.vscode-sotlas');
  assert.ok(extension, 'the installed Sotlas VSIX is available in the extension host');
  await extension.activate();

  const sourcePath = process.env.SOTLAS_SMOKE_SOURCE;
  assert.ok(sourcePath, 'the smoke test source path is configured');
  const document = await vscode.workspace.openTextDocument(vscode.Uri.file(sourcePath));
  await vscode.window.showTextDocument(document);
  await vscode.commands.executeCommand('sotlas.check');

  const deadline = Date.now() + 10_000;
  let diagnostics = [];
  while (Date.now() < deadline) {
    diagnostics = vscode.languages.getDiagnostics(document.uri);
    if (diagnostics.some(item => item.message === 'installed VSIX diagnostic probe')) break;
    await new Promise(resolve => setTimeout(resolve, 50));
  }

  const compilerDiagnostic = diagnostics.find(item => item.message === 'installed VSIX diagnostic probe');
  assert.ok(compilerDiagnostic, 'the compiler output appears in the Problems diagnostics');
  assert.equal(compilerDiagnostic.source, 'Sotlas compiler');
  assert.equal(compilerDiagnostic.range.start.line, 1);
  assert.equal(compilerDiagnostic.range.start.character, 2);
};
