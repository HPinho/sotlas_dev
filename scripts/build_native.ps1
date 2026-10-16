param(
    [Parameter(Mandatory = $true, Position = 0)][string]$Seed,
    [Parameter(Position = 1)][string]$OutputDirectory
)

# Shell orchestration only. Every compilation uses the Sotlas-written compiler.
$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT') { throw 'Use build_native.sh on Linux or Intel macOS.' }
$repository = Split-Path -Parent $PSScriptRoot
$seedPath = (Resolve-Path -LiteralPath $Seed).Path
if (-not $OutputDirectory) { $OutputDirectory = Join-Path $repository 'build/native-selfhost' }
$output = [IO.Path]::GetFullPath($OutputDirectory)
if (Test-Path -LiteralPath $output) {
    throw 'Choose a fresh output directory; existing builds are preserved.'
}
$namespace = Join-Path $output 'src/sotlas/compiler'
New-Item -ItemType Directory -Path (Join-Path $namespace 'backend') -Force | Out-Null
foreach ($name in @('token','ast','lexer','parser','sema','backend/target_ir','backend/lower_scalar','backend/x86_64_scalar')) {
    Copy-Item -LiteralPath (Join-Path $repository "bootstrap/sotlas/native_compiler/$name.sotlas") -Destination (Join-Path $namespace "$name.sotlas")
}
Copy-Item -LiteralPath (Join-Path $repository 'bootstrap/sotlas/native_driver/windows.sotlas') -Destination (Join-Path $namespace 'windows_driver.sotlas')
$runtime = Join-Path $output 'src/sotlas/runtime'
New-Item -ItemType Directory -Path $runtime | Out-Null
Get-ChildItem -LiteralPath (Join-Path $repository 'runtime/native') -Filter '*.sotlas' | Copy-Item -Destination $runtime
$application = Join-Path $output 'src/native_config.sotlas'
Copy-Item -LiteralPath (Join-Path $repository 'examples/native_config.sotlas') -Destination $application
$negative = Join-Path $output 'use_after_move.sotlas'
Copy-Item -LiteralPath (Join-Path $repository 'tests/native/use_after_move.sotlas') -Destination $negative
$sourceRoot = Join-Path $output 'src'
$entry = Join-Path $namespace 'windows_driver.sotlas'
$stage2 = Join-Path $output 'stage2.exe'
$stage3 = Join-Path $output 'sotlas-native.exe'
$program = Join-Path $output 'native-config.exe'

function Invoke-Native([string]$Executable, [string[]]$Arguments, [int]$Expected = 0) {
    & $Executable @Arguments
    if ($LASTEXITCODE -ne $Expected) {
        throw "Native command failed: $Executable $Arguments (exit $LASTEXITCODE; expected $Expected)"
    }
}

function Get-NativeHash([string]$Path) {
    $hash = [Security.Cryptography.SHA256]::Create()
    $stream = [IO.File]::OpenRead($Path)
    try { return [BitConverter]::ToString($hash.ComputeHash($stream)).Replace('-', '') }
    finally { $stream.Dispose(); $hash.Dispose() }
}

$savedPath = $env:PATH
try {
    # Both generations and the application run without host build tools on PATH.
    $env:PATH = Join-Path $output 'no-host-tools'
    Invoke-Native $seedPath @('--build-cc', $stage2, $sourceRoot, $entry)
    Invoke-Native $stage2 @('--build-cc', $stage3, $sourceRoot, $entry)
    if ((Get-NativeHash $stage2) -ne (Get-NativeHash $stage3)) {
        throw 'Stage 2 and Stage 3 differ.'
    }
    Invoke-Native $stage3 @('--self-test')
    Invoke-Native $stage3 @('--check-build', $sourceRoot, $application)
    Invoke-Native $stage3 @('--build-win', $program, $sourceRoot, $application)
    Invoke-Native $program @() 42
    $before = Get-NativeHash $program
    Invoke-Native $stage3 @('--check', $negative) 6
    Invoke-Native $stage3 @($negative, $program) 6
    if ((Get-NativeHash $program) -ne $before) {
        throw 'Rejected compilation modified the existing executable.'
    }
} finally {
    $env:PATH = $savedPath
}
foreach ($artifact in @($seedPath, $stage2, $stage3)) {
    Write-Output "$(Get-NativeHash $artifact)  $artifact"
}
Write-Output "Native self-build verified. Compiler: $stage3"
