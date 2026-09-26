const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { downloadAndUnzipVSCode, runTests, runVSCodeCommand } = require('@vscode/test-electron');

async function main() {
  const extensionRoot = path.resolve(__dirname, '..');
  const vsixPath = path.join(extensionRoot, 'sotlas-preview.vsix');
  assert.ok(fs.existsSync(vsixPath), 'build the preview VSIX before running this smoke test');

  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'sotlas-vsix-install-'));
  const extensionsDir = path.join(temporary, 'extensions');
  const testExtensionsDir = path.join(temporary, 'test-extensions');
  const userDataDir = path.join(temporary, 'user-data');
  const workspaceDir = path.join(temporary, 'workspace');
  try {
    const isolatedProfile = [`--user-data-dir=${userDataDir}`, `--extensions-dir=${extensionsDir}`];
    await runVSCodeCommand([
      ...isolatedProfile,
      '--install-extension', vsixPath,
      '--force',
    ], { version: 'stable' });
    const listing = await runVSCodeCommand([
      ...isolatedProfile,
      '--list-extensions',
    ], { version: 'stable' });
    assert.match(listing.stdout.toLowerCase(), /sotlas-lang\.vscode-sotlas/);

    const executable = await downloadAndUnzipVSCode('stable');

    const installedExtension = fs.readdirSync(extensionsDir)
      .map(name => path.join(extensionsDir, name))
      .find(candidate => candidate.toLowerCase().includes('sotlas-lang.vscode-sotlas'));
    assert.ok(installedExtension, 'VS Code installed the generated Sotlas VSIX');

    fs.mkdirSync(path.join(workspaceDir, '.vscode'), { recursive: true });
    fs.mkdirSync(testExtensionsDir, { recursive: true });
    const sourcePath = path.join(workspaceDir, 'main.sotlas');
    fs.writeFileSync(sourcePath, 'module smoke;\npub fn main() -> i64 { return 0; }\n');
    const compilerPath = path.join(temporary, 'sotlas-diagnostic-fixture.sh');
    fs.writeFileSync(compilerPath, '#!/bin/sh\nprintf "sotlas: erro: %s:2:3: installed VSIX diagnostic probe\\n" "$2"\nexit 1\n');
    fs.chmodSync(compilerPath, 0o755);
    fs.writeFileSync(
      path.join(workspaceDir, '.vscode', 'settings.json'),
      JSON.stringify({ 'sotlas.compilerPath': compilerPath }, null, 2),
    );

    const testExitCode = await runTests({
      vscodeExecutablePath: executable,
      extensionDevelopmentPath: installedExtension,
      extensionTestsPath: path.join(__dirname, 'vscodeSmokeSuite.cjs'),
      launchArgs: [workspaceDir, `--user-data-dir=${userDataDir}`, `--extensions-dir=${testExtensionsDir}`],
      extensionTestsEnv: { SOTLAS_SMOKE_SOURCE: sourcePath },
    });
    assert.equal(testExitCode, 0, 'the installed VSIX activates and publishes compiler diagnostics');
  } finally {
    fs.rmSync(temporary, { recursive: true, force: true });
  }
}

main().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
