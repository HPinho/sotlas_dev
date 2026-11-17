const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { nativePlan, readNativeSdk, createNativeProject, nativeColumn } = require('../out/nativeProject');

function fixture(t, platform = process.platform) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'sotlas-native-editor-'));
  t.after(() => {
    assert.equal(path.dirname(path.resolve(root)), path.resolve(os.tmpdir()));
    assert.ok(path.basename(root).startsWith('sotlas-native-editor-'));
    fs.rmSync(root, { recursive: true, force: true });
  });
  const sdk = path.join(root, 'SDK with spaces');
  for (const dir of ['bin', 'runtime/native', 'examples/calculator/platform']) fs.mkdirSync(path.join(sdk, dir), { recursive: true });
  fs.writeFileSync(path.join(sdk, 'sdk.json'), JSON.stringify({ format: 1, target: { linux: 'linux-x64', win32: 'windows-x64', darwin: 'macos-x64' }[platform] }));
  fs.writeFileSync(path.join(sdk, 'bin', platform === 'win32' ? 'sotlas-native.exe' : 'sotlas-native'), '', { mode: 0o755 });
  fs.writeFileSync(path.join(sdk, 'runtime/native/text.sotlas'), 'module sotlas::runtime::text;');
  const host = platform === 'win32' ? 'windows' : platform === 'darwin' ? 'darwin' : 'linux';
  fs.writeFileSync(path.join(sdk, 'examples/calculator/platform', `${host}.sotlas`), 'module calculator::platform;\npub fn calculator_write(data:*const u8,length:usize)->i64{return length as i64;}');
  return { root, sdk, native: readNativeSdk(sdk, platform, 'x64') };
}

test('SDK selection checks metadata, host and required files', t => {
  const f = fixture(t);
  assert.equal(f.native.root, f.sdk);
  assert.throws(() => readNativeSdk(f.sdk, process.platform, 'arm64'), /matching this extension host/);
  const wrong = process.platform === 'win32' ? 'linux' : 'win32';
  assert.throws(() => readNativeSdk(f.sdk, wrong, 'x64'), /matching this extension host/);
  fs.unlinkSync(path.join(f.sdk, 'runtime/native/text.sotlas'));
  assert.throws(() => createNativeProject(path.join(f.root, 'missing runtime'), f.native), /incomplete/);
  assert.equal(fs.existsSync(path.join(f.root, 'missing runtime')), false);
});

test('native project creation copies runtime and configures a saved source project', t => {
  const f = fixture(t); const project = path.join(f.root, 'new app');
  createNativeProject(project, f.native);
  const settings = JSON.parse(fs.readFileSync(path.join(project, '.vscode/settings.json'), 'utf8'));
  assert.equal(settings['sotlas.toolchain'], 'native');
  assert.equal(settings['sotlas.compilerPath'], f.native.compiler);
  assert.ok(fs.existsSync(path.join(project, 'src/sotlas/runtime/text.sotlas')));
  assert.match(fs.readFileSync(path.join(project, 'src/main.sotlas'), 'utf8'), /Hello from Sotlas!/);
  assert.match(fs.readFileSync(path.join(project, 'src/app/platform.sotlas'), 'utf8'), /module app::platform;[\s\S]*console_write/);
});

test('project creation preserves an existing directory and its contents', t => {
  const f = fixture(t); const project = path.join(f.root, 'existing'); fs.mkdirSync(project);
  fs.writeFileSync(path.join(project, 'keep.txt'), 'keep');
  assert.throws(() => createNativeProject(project, f.native), /empty directory/);
  assert.equal(fs.readFileSync(path.join(project, 'keep.txt'), 'utf8'), 'keep');
  assert.deepEqual(fs.readdirSync(project), ['keep.txt']);
});

test('native check/build plans use each host ABI and preserve argument boundaries', t => {
  const f = fixture(t); const project = path.join(f.root, 'app ; spaces'); createNativeProject(project, f.native);
  const root = path.join(project, 'src'); const entry = path.join(root, 'main.sotlas');
  assert.deepEqual(nativePlan('check', project, {}, entry).args, ['--check-build', root, entry]);
  for (const [host, flag] of [['linux', '--build'], ['darwin', '--build-mac'], ['win32', '--build-win']]) {
    const result = nativePlan('build', project, {}, undefined, host);
    assert.deepEqual(result.args, [flag, path.join(project, 'build', host === 'win32' ? 'app.exe' : 'app'), root, entry]);
  }
});

test('native plans reject output/source collisions and escaped project paths', t => {
  const f = fixture(t); const project = path.join(f.root, 'app'); createNativeProject(project, f.native);
  for (const output of ['src/main.sotlas', '../outside', 'build/source.sotlas', 'build']) {
    assert.throws(() => nativePlan('build', project, { output }, undefined, 'linux'), /output/);
  }
  assert.throws(() => nativePlan('check', project, {}, path.join(f.root, 'outside.sotlas')), /source directory/);
  assert.throws(() => nativePlan('build', project, { sourceRoot: '../outside' }), /source directory/);
});

test('native byte columns map BMP and supplementary characters to UTF-16 ranges', () => {
  const line = 'let value="Ω😀"; unknown'; const prefix = line.slice(0, line.indexOf('unknown'));
  assert.equal(nativeColumn(line, Buffer.byteLength(prefix) + 1), prefix.length);
  assert.equal(nativeColumn('Ωx', 2), 0);
  assert.equal(nativeColumn('😀x', 5), 2);
  assert.equal(nativeColumn(line, 10000), line.length);
});
