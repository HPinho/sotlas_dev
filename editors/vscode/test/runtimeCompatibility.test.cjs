const assert = require('node:assert/strict');
const test = require('node:test');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { downloadDirToExecutablePath } = require('@vscode/test-electron/out/util');

test('the pinned test runner resolves the current macOS application executable', t => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'sotlas-vscode-runtime-'));
  t.after(() => {
    assert.equal(path.dirname(path.resolve(root)), path.resolve(os.tmpdir()));
    assert.ok(path.basename(root).startsWith('sotlas-vscode-runtime-'));
    fs.rmSync(root, { recursive: true, force: true });
  });
  const contents = path.join(root, 'Visual Studio Code.app', 'Contents');
  fs.mkdirSync(path.join(contents, 'MacOS'), { recursive: true });
  const executable = path.join(contents, 'MacOS', 'Code');
  fs.writeFileSync(executable, '');
  fs.writeFileSync(path.join(contents, 'Info.plist'),
    '<plist><dict><key>CFBundleExecutable</key><string>Code</string></dict></plist>');
  assert.equal(downloadDirToExecutablePath(root, 'darwin'), executable);
  assert.equal(downloadDirToExecutablePath(root, 'darwin-arm64'), executable);
});
