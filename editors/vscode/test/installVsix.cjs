const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const { downloadAndUnzipVSCode, runTests, runVSCodeCommand } = require('@vscode/test-electron');

function runInstalledCodeCommand(cliPath, args) {
  const cliScript = process.env.SOTLAS_VSCODE_CLI_SCRIPT;
  assert.ok(
    process.platform !== 'win32' || cliScript,
    'set SOTLAS_VSCODE_CLI_SCRIPT to VS Code resources/app/out/cli.js on Windows',
  );
  const result = spawnSync(cliPath, [
    ...(cliScript ? [cliScript] : []),
    ...args,
  ], {
    encoding: 'utf8',
    env: {
      ...process.env,
      ...(cliScript ? { ELECTRON_RUN_AS_NODE: '1', VSCODE_DEV: '' } : {}),
    },
    shell: false,
    timeout: 60000,
    windowsHide: true,
  });
  if (result.error) throw result.error;
  assert.equal(result.status, 0, result.stderr || result.stdout);
  return result.stdout || '';
}

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
    const localCli = process.env.SOTLAS_VSCODE_CLI;
    const localExecutable = process.env.SOTLAS_VSCODE_EXECUTABLE;
    assert.equal(
      Boolean(localCli), Boolean(localExecutable),
      'set both SOTLAS_VSCODE_CLI and SOTLAS_VSCODE_EXECUTABLE to use an installed VS Code',
    );
    let listing;
    if (localCli && localExecutable) {
      runInstalledCodeCommand(localCli, [
        ...isolatedProfile,
        '--disable-gpu',
        '--install-extension', vsixPath,
        '--force',
      ]);
      listing = runInstalledCodeCommand(localCli, [
        ...isolatedProfile,
        '--disable-gpu',
        '--list-extensions',
      ]);
    } else {
      await runVSCodeCommand([
        ...isolatedProfile,
        '--disable-gpu',
        '--install-extension', vsixPath,
        '--force',
      ], { version: 'stable' });
      const result = await runVSCodeCommand([
        ...isolatedProfile,
        '--disable-gpu',
        '--list-extensions',
      ], { version: 'stable' });
      listing = result.stdout;
    }
    assert.match(String(listing).toLowerCase(), /sotlas-lang\.vscode-sotlas/);

    const executable = localExecutable || await downloadAndUnzipVSCode('stable');

    const installedExtension = fs.readdirSync(extensionsDir)
      .map(name => path.join(extensionsDir, name))
      .find(candidate => candidate.toLowerCase().includes('sotlas-lang.vscode-sotlas'));
    assert.ok(installedExtension, 'VS Code installed the generated Sotlas VSIX');

    fs.mkdirSync(path.join(workspaceDir, '.vscode'), { recursive: true });
    fs.mkdirSync(testExtensionsDir, { recursive: true });
    const sourcePath = path.join(workspaceDir, 'main.sotlas');
    fs.writeFileSync(sourcePath, 'module smoke;\npub fn main() -> i64 { return 0; }\n');
    // Use Node itself as the configured compiler so this fixture works on
    // Windows as well as Unix without relying on shell-script execution.
    fs.writeFileSync(
      path.join(workspaceDir, 'check'),
      'const file = process.argv[2];\n'
        + 'process.stderr.write(`sotlas: erro: ${file}:2:3: installed VSIX diagnostic probe\\n`);\n'
        + 'process.exitCode = 1;\n',
    );
    fs.writeFileSync(
      path.join(workspaceDir, '.vscode', 'settings.json'),
      JSON.stringify({ 'sotlas.compilerPath': process.execPath }, null, 2),
    );

    const testExitCode = await runTests({
      vscodeExecutablePath: executable,
      extensionDevelopmentPath: installedExtension,
      extensionTestsPath: path.join(__dirname, 'vscodeSmokeSuite.cjs'),
      launchArgs: [workspaceDir, '--disable-gpu', `--user-data-dir=${userDataDir}`, `--extensions-dir=${testExtensionsDir}`],
      extensionTestsEnv: { SOTLAS_SMOKE_SOURCE: sourcePath },
    });
    assert.equal(testExitCode, 0, 'the installed VSIX activates and publishes compiler diagnostics');
  } finally {
    fs.rmSync(temporary, {
      recursive: true,
      force: true,
      maxRetries: 20,
      retryDelay: 250,
    });
  }
}

main().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
