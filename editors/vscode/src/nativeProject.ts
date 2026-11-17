import * as fs from 'fs';
import * as path from 'path';

export interface NativeSdk { root: string; compiler: string; platform: NodeJS.Platform; }
export interface NativeSettings { sourceRoot?: string; entry?: string; output?: string; }
export interface NativePlan { args: string[]; cwd: string; sourceRoot: string; output: string; }

function inside(root: string, file: string): boolean {
    const relative = path.relative(root, file);
    return relative === '' || (!relative.startsWith(`..${path.sep}`) && relative !== '..' && !path.isAbsolute(relative));
}

export function readNativeSdk(directory: string, platform: NodeJS.Platform = process.platform, arch = process.arch): NativeSdk {
    const targets: Partial<Record<NodeJS.Platform, string>> = { win32: 'windows-x64', linux: 'linux-x64', darwin: 'macos-x64' };
    const root = path.resolve(directory);
    const metadata = JSON.parse(fs.readFileSync(path.join(root, 'sdk.json'), 'utf8'));
    if (arch !== 'x64' || !targets[platform] || metadata.format !== 1 || metadata.target !== targets[platform]) {
        throw new Error('Choose a native x86-64 SDK matching this extension host.');
    }
    const compiler = path.join(root, 'bin', platform === 'win32' ? 'sotlas-native.exe' : 'sotlas-native');
    if (!fs.statSync(compiler).isFile() || !fs.statSync(path.join(root, 'runtime', 'native')).isDirectory()) {
        throw new Error('The SDK is missing its compiler or runtime sources.');
    }
    fs.accessSync(compiler, fs.constants.X_OK);
    return { root, compiler, platform };
}

export function nativePlan(action: 'check' | 'build', folder: string, settings: NativeSettings, activeFile?: string, platform: NodeJS.Platform = process.platform): NativePlan {
    const cwd = path.resolve(folder);
    const sourceRoot = path.resolve(cwd, settings.sourceRoot || 'src');
    const entry = path.resolve(cwd, action === 'check' && activeFile ? activeFile : settings.entry || 'src/main.sotlas');
    let output = path.resolve(cwd, settings.output || 'build/app');
    if (platform === 'win32' && !output.toLowerCase().endsWith('.exe')) output += '.exe';
    if (!inside(cwd, sourceRoot) || !inside(sourceRoot, entry) || path.extname(entry).toLowerCase() !== '.sotlas') {
        throw new Error('The saved .sotlas entry must be inside the configured project source directory.');
    }
    if (!inside(path.join(cwd, 'build'), output) || output === path.join(cwd, 'build') || /\.(?:sotlas|sth)$/i.test(output)) {
        throw new Error('Native output must be an executable path under the workspace build directory.');
    }
    if (!fs.statSync(sourceRoot).isDirectory() || !fs.statSync(entry).isFile()) {
        throw new Error('The configured source directory or entry file is missing.');
    }
    const flag = platform === 'win32' ? '--build-win' : platform === 'darwin' ? '--build-mac' : platform === 'linux' ? '--build' : '';
    if (!flag) throw new Error('This native preview supports Linux, Windows and Intel macOS.');
    return { cwd, sourceRoot, output, args: action === 'check' ? ['--check-build', sourceRoot, entry] : [flag, output, sourceRoot, entry] };
}

export function createNativeProject(directory: string, sdk: NativeSdk): void {
    const root = path.resolve(directory);
    if (fs.existsSync(root) && (!fs.statSync(root).isDirectory() || fs.readdirSync(root).length !== 0)) {
        throw new Error('Choose an empty directory. Existing project files are preserved.');
    }
    // Validate inputs before creating any project files.
    const runtime = path.join(sdk.root, 'runtime', 'native');
    const modules = fs.readdirSync(runtime, { withFileTypes: true }).filter(file => file.isFile() && file.name.endsWith('.sotlas'));
    const host = sdk.platform === 'win32' ? 'windows' : sdk.platform === 'darwin' ? 'darwin' : 'linux';
    const adapter = fs.readFileSync(path.join(sdk.root, 'examples', 'calculator', 'platform', `${host}.sotlas`), 'utf8')
        .replace('module calculator::platform;', 'module app::platform;')
        .replace(/\bcalculator_(read|write)\b/g, 'console_$1');
    if (modules.length === 0 || !adapter.includes('module app::platform;')) throw new Error('The SDK project sources are incomplete.');
    fs.mkdirSync(path.join(root, 'src', 'app'), { recursive: true });
    fs.mkdirSync(path.join(root, 'src', 'sotlas', 'runtime'), { recursive: true });
    fs.mkdirSync(path.join(root, '.vscode'), { recursive: true });
    for (const file of modules) fs.copyFileSync(path.join(runtime, file.name), path.join(root, 'src', 'sotlas', 'runtime', file.name), fs.constants.COPYFILE_EXCL);
    fs.writeFileSync(path.join(root, 'src', 'app', 'platform.sotlas'), adapter, { flag: 'wx' });
    fs.writeFileSync(path.join(root, 'src', 'main.sotlas'), 'module app::main;\nimport app::platform::*;\n\npub fn main_entry() -> u32 {\n    let text:*const u8="Hello from Sotlas!\\n";\n    let mut offset:usize=0;\n    while offset < 19 {\n        let count:i64=console_write(unsafe { text+offset },19-offset);\n        if count <= 0 || count as usize > 19-offset { return 1; }\n        offset=offset+count as usize;\n    }\n    return 0;\n}\n', { flag: 'wx' });
    fs.writeFileSync(path.join(root, '.gitignore'), 'build/\n', { flag: 'wx' });
    fs.writeFileSync(path.join(root, '.vscode', 'settings.json'), JSON.stringify({
        'sotlas.toolchain': 'native', 'sotlas.compilerPath': sdk.compiler, 'sotlas.nativeSdkPath': sdk.root,
        'sotlas.nativeSourceRoot': 'src', 'sotlas.nativeEntry': 'src/main.sotlas', 'sotlas.nativeOutput': 'build/app',
        'sotlas.enableExternalLsp': false
    }, null, 2) + '\n', { flag: 'wx' });
    fs.writeFileSync(path.join(root, 'README.md'), '# Native Sotlas console project\n\nUse Sotlas: Check Active File, Build Workspace and Run Native Project in VS Code.\nThe generated platform adapter targets the current host. Runtime sources are copied from the selected SDK.\nCompiler checks and builds require no Python, C compiler or external linker after the seed.\n', { flag: 'wx' });
}

/** Native source columns count UTF-8 bytes; VS Code ranges count UTF-16 units. */
export function nativeColumn(line: string, oneBasedByteColumn: number): number {
    let bytes = 0; let units = 0;
    for (const scalar of line) {
        if (bytes + Buffer.byteLength(scalar, 'utf8') > Math.max(0, oneBasedByteColumn - 1)) break;
        bytes += Buffer.byteLength(scalar, 'utf8'); units += scalar.length;
    }
    return units;
}
