param([Parameter(Mandatory=$true,Position=0)][string]$Seed,
      [Parameter(Mandatory=$true,Position=1)][string]$OutputDirectory)
$ErrorActionPreference='Stop'
if ($env:OS -ne 'Windows_NT') {throw 'Use pack-sdk.sh on Linux or Intel macOS.'}
$repository=Split-Path -Parent $PSScriptRoot
$seedPath=(Resolve-Path -LiteralPath $Seed).Path
$bundle=[IO.Path]::GetFullPath($OutputDirectory)
if ((Test-Path -LiteralPath $bundle) -or (Test-Path -LiteralPath "$bundle.zip")) {throw 'Choose fresh bundle/archive paths.'}
$savedPath=$env:Path
try {$env:Path='C:\no-host-tools'; & $seedPath --self-test; if ($LASTEXITCODE -ne 0) {throw 'Native seed self-test failed.'}}
finally {$env:Path=$savedPath}
function Copy-Sdk([string]$Relative) {
    $source=Join-Path $repository $Relative;$destination=Join-Path $bundle $Relative
    New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
    Copy-Item -LiteralPath $source -Destination $destination
}
New-Item -ItemType Directory -Path (Join-Path $bundle 'bin') -Force | Out-Null
Copy-Item -LiteralPath $seedPath -Destination (Join-Path $bundle 'bin/sotlas-native.exe')
foreach ($file in Get-ChildItem (Join-Path $repository 'runtime/native') -Filter '*.sotlas') {Copy-Sdk ('runtime/native/'+$file.Name)}
foreach ($name in @('token','ast','lexer','parser','sema','backend/target_ir','backend/lower_scalar','backend/x86_64_scalar')) {Copy-Sdk "bootstrap/sotlas/native_compiler/$name.sotlas"}
foreach ($name in @('linux','windows','darwin')) {Copy-Sdk "bootstrap/sotlas/native_driver/$name.sotlas"}
foreach ($name in @('build_native.sh','build_native.ps1','test_native.sh','test_native.ps1','verify_sdk.sh','verify_sdk.ps1','build_kernel.sh','build_kernel.ps1','verify_kernel_sdk.sh','verify_kernel_sdk.ps1')) {Copy-Sdk "scripts/$name"}
foreach ($name in @('install-sdk.sh','install-sdk.ps1')) {Copy-Sdk "packaging/$name"}
foreach ($name in @('native_json.md','native_narrow_division.md','native_seed_workflow.md','native_ui_snapshots.md','native_ui_editing.md','native_ui_layout.md','native_vscode_sdk.md','native_tensor_ops.md','native_csv.md')) {Copy-Sdk "docs/$name"}
foreach ($file in Get-ChildItem (Join-Path $repository 'docs') -Filter 'native_kernel*.md') {Copy-Sdk ('docs/'+$file.Name)}
foreach ($kernelProfile in @('boot','interrupts','memory','heap','collections','vm','foundation')) {
    Copy-Sdk "examples/native_kernel_$kernelProfile/main.sotlas";Copy-Sdk "examples/native_kernel_$kernelProfile/README.md"
}
Copy-Sdk 'tests/native/kernel_sdk/bad_abi.sotlas';Copy-Sdk 'tests/native/kernel_sdk/hosted.sotlas'
Copy-Sdk 'examples/calculator/src/calculator/main.sotlas'
foreach ($name in @('linux','windows','darwin')) {Copy-Sdk "examples/calculator/platform/$name.sotlas"}
Copy-Sdk 'examples/native_config.sotlas'
Copy-Sdk 'examples/native_config_map/main.sotlas';Copy-Sdk 'examples/native_config_map/README.md'
Copy-Sdk 'examples/native_tensor_rows/main.sotlas';Copy-Sdk 'examples/native_tensor_rows/README.md'
Copy-Sdk 'examples/native_csv/main.sotlas';Copy-Sdk 'examples/native_csv/README.md'
Copy-Sdk 'examples/native_csv/normalize.sotlas'
Copy-Sdk 'tests/native/use_after_move.sotlas';Copy-Sdk 'tests/native/calculator/model.sotlas'
foreach ($name in @('model','unicode','render')) {Copy-Sdk "tests/native/ui/$name.sotlas"}
foreach ($name in @('main','model')) {Copy-Sdk "examples/graphical_calculator/src/calculator_app/$name.sotlas"}
Copy-Sdk 'examples/graphical_calculator/README.md';Copy-Sdk 'examples/graphical_calculator/build.ps1'
foreach ($file in Get-ChildItem (Join-Path $repository 'tests/native/contracts') -File -Recurse) {
    $relative=$file.FullName.Substring($repository.Length+1).Replace('\','/');Copy-Sdk $relative
}
Copy-Sdk 'LICENSE'
Copy-Item -LiteralPath (Join-Path $repository 'packaging/SDK_README.md') -Destination (Join-Path $bundle 'README.md')
$revision='local';if ($env:GITHUB_SHA) {$revision=$env:GITHUB_SHA}
if ($revision -notmatch '^[a-zA-Z0-9_-]+$') {throw 'Invalid source revision.'}
$encoding=New-Object Text.UTF8Encoding($false)
function Sdk-Hash([string]$Path) {
    $stream=[IO.File]::OpenRead($Path);$algorithm=[Security.Cryptography.SHA256]::Create()
    try {return ([BitConverter]::ToString($algorithm.ComputeHash($stream))).Replace('-','').ToLowerInvariant()}
    finally {$stream.Dispose();$algorithm.Dispose()}
}
$project = [regex]::Match((Get-Content -LiteralPath (Join-Path $repository 'pyproject.toml') -Raw),
    '(?ms)^\[project\]\r?\n(?<body>.*?)(?=^\[|\z)')
$version = [regex]::Match($project.Groups['body'].Value, '(?m)^version = "([0-9]+\.[0-9]+\.[0-9]+(?:rc[0-9]+)?)"\r?$')
if (!$version.Success) {throw 'Invalid project version for native SDK.'}
$metadata = [ordered]@{
    format = 1
    target = 'windows-x64'
    source_revision = $revision
    channel = 'preview'
    sdk_version = $version.Groups[1].Value
    compiler_sha256 = Sdk-Hash (Join-Path $bundle 'bin/sotlas-native.exe')
}
[IO.File]::WriteAllText((Join-Path $bundle 'sdk.json'),($metadata | ConvertTo-Json -Compress),$encoding)
$rows=foreach ($file in Get-ChildItem -LiteralPath $bundle -File -Recurse | Sort-Object FullName) {
    (Sdk-Hash $file.FullName)+'  '+$file.FullName.Substring($bundle.Length+1).Replace('\','/')
}
[IO.File]::WriteAllText((Join-Path $bundle 'SHA256SUMS'),(($rows -join "`n")+"`n"),$encoding)
Compress-Archive -Path (Join-Path $bundle '*') -DestinationPath "$bundle.zip"
[IO.File]::WriteAllText("$bundle.zip.sha256",((Sdk-Hash "$bundle.zip")+'  '+[IO.Path]::GetFileName("$bundle.zip")+"`n"),$encoding)
Write-Output "Native SDK candidate: $bundle.zip"
