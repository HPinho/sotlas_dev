const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { spawnSync } = require('node:child_process');
const vscode = require('vscode');

exports.run = async function run() {
  const extension = vscode.extensions.getExtension('sotlas-lang.vscode-sotlas');
  assert.ok(extension); await extension.activate();
  const source = process.env.SOTLAS_SMOKE_SOURCE;
  const sdk = process.env.SOTLAS_NATIVE_SDK;
  const directory = path.dirname(path.dirname(source));
  assert.equal(await vscode.commands.executeCommand('sotlas.selectNativeSdk', vscode.Uri.file(sdk)), sdk);
  assert.deepEqual(fs.readdirSync(directory), [], 'selecting an SDK preserves the empty project directory');
  assert.equal(await vscode.commands.executeCommand('sotlas.createNativeProject', vscode.Uri.file(directory)), directory);
  const document = await vscode.workspace.openTextDocument(vscode.Uri.file(source));
  await vscode.window.showTextDocument(document);
  assert.equal(await vscode.commands.executeCommand('sotlas.check'), 0);
  const executable = await vscode.commands.executeCommand('sotlas.build');
  assert.ok(executable && fs.existsSync(executable), 'native build emits the executable');
  const application = spawnSync(executable, [], { encoding: 'utf8', shell: false, windowsHide: true, env: { ...process.env, PATH: path.join(directory, 'no-host-tools') } });
  assert.equal(application.status, 0, application.stderr);
  assert.equal(application.stdout, 'Hello from Sotlas!\n');
  const taskEnded = new Promise((resolve, reject) => {
    const timer = setTimeout(() => { listener.dispose(); reject(new Error('Native run task timed out')); }, 30000);
    const listener = vscode.tasks.onDidEndTaskProcess(event => {
      if (event.execution.task.name === 'Sotlas Native Run') { clearTimeout(timer); listener.dispose(); resolve(event.exitCode); }
    });
  });
  assert.equal(await vscode.commands.executeCommand('sotlas.run'), executable);
  assert.equal(await taskEnded, 0, 'the ProcessExecution task runs the native program');
  const original = document.getText();
  const bad = 'module app::main;\nstruct Token { pub value:u32; }\nfn consume(value:sole Token)->u32 { return value.value; }\npub fn main_entry()->u32 {\n    let owner:sole Token=Token{value:42};consume(owner);\n    let label:*const u8="Ω😀"; return owner.value;\n}\n';
  async function replace(text) {
    const edit = new vscode.WorkspaceEdit();
    edit.replace(document.uri, new vscode.Range(document.positionAt(0), document.positionAt(document.getText().length)), text);
    assert.ok(await vscode.workspace.applyEdit(edit)); assert.ok(await document.save());
  }
  await replace(bad);
  assert.notEqual(await vscode.commands.executeCommand('sotlas.check'), 0);
  const diagnostics = vscode.languages.getDiagnostics(document.uri);
  const diagnostic = diagnostics.find(item => item.source === 'Sotlas compiler' && /moved/.test(item.message));
  assert.ok(diagnostic, `actual native ownership diagnostics appear in Problems: ${JSON.stringify(diagnostics)}`);
  assert.equal(diagnostic.range.start.line, 5);
  assert.equal(diagnostic.range.start.character, bad.split('\n')[5].indexOf('owner.value'), 'UTF-8 compiler columns map to UTF-16 editor positions');
  const before = crypto.createHash('sha256').update(fs.readFileSync(executable)).digest('hex');
  let starts = 0;
  const listener = vscode.tasks.onDidStartTask(event => { if (event.execution.task.name === 'Sotlas Native Run') starts++; });
  try { assert.equal(await vscode.commands.executeCommand('sotlas.run'), undefined); assert.equal(starts, 0, 'failed builds never execute the old artifact'); }
  finally { listener.dispose(); }
  assert.equal(crypto.createHash('sha256').update(fs.readFileSync(executable)).digest('hex'), before);
  await replace(original); assert.equal(await vscode.commands.executeCommand('sotlas.check'), 0);
  assert.equal(vscode.languages.getDiagnostics(document.uri).filter(item => item.source === 'Sotlas compiler').length, 0, 'fixed errors clear');
  const created = path.join(directory, 'second native project');
  assert.equal(await vscode.commands.executeCommand('sotlas.createNativeProject', vscode.Uri.file(created)), created);
  const entry = path.join(created, 'src/main.sotlas'); const saved = fs.readFileSync(entry, 'utf8');
  assert.equal(await vscode.commands.executeCommand('sotlas.createNativeProject', vscode.Uri.file(created)), undefined);
  assert.equal(fs.readFileSync(entry, 'utf8'), saved, 'occupied project directories are preserved');
};
