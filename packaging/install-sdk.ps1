param([Parameter(Mandatory=$true,Position=0)][string]$BundleDirectory,
      [Parameter(Mandatory=$true,Position=1)][string]$Destination)
$ErrorActionPreference='Stop'
if ($env:OS -ne 'Windows_NT') {throw 'Use install-sdk.sh on Linux or Intel macOS.'}
$bundle=(Resolve-Path -LiteralPath $BundleDirectory).Path
$destinationPath=[IO.Path]::GetFullPath($Destination)
if (Test-Path -LiteralPath $destinationPath) {throw 'Choose a fresh installation directory.'}
$metadata=Get-Content -LiteralPath (Join-Path $bundle 'sdk.json') -Raw | ConvertFrom-Json
if ($metadata.format -ne 1 -or $metadata.target -ne 'windows-x64') {throw 'SDK format/host mismatch.'}
foreach ($entry in Get-ChildItem -LiteralPath $bundle -Force -Recurse) {
    if ($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) {throw 'SDK reparse points are not accepted.'}
}
function Sdk-Hash([string]$Path) {
    $stream=[IO.File]::OpenRead($Path);$algorithm=[Security.Cryptography.SHA256]::Create()
    try {return ([BitConverter]::ToString($algorithm.ComputeHash($stream))).Replace('-','').ToLowerInvariant()}
    finally {$stream.Dispose();$algorithm.Dispose()}
}
$seen=@{}
foreach ($line in [IO.File]::ReadAllLines((Join-Path $bundle 'SHA256SUMS'))) {
    if ($line -cnotmatch '^([0-9a-f]{64})  ([a-zA-Z0-9_./-]+)$') {throw 'Invalid SDK checksum row.'}
    $digest=$Matches[1];$relative=$Matches[2]
    if ($relative.StartsWith('/') -or $relative.Contains('..') -or $relative -eq 'SHA256SUMS' -or $seen.ContainsKey($relative)) {throw 'Unsafe or duplicate SDK checksum path.'}
    if ($relative -notmatch '^(bin/|runtime/native/|bootstrap/sotlas/|scripts/|packaging/|docs/|examples/|tests/native/|LICENSE$|README\.md$|sdk\.json$)') {throw 'Unexpected SDK path.'}
    $file=Join-Path $bundle $relative
    if (!(Test-Path -LiteralPath $file -PathType Leaf) -or (Sdk-Hash $file) -cne $digest) {throw "SDK integrity failure: $relative"}
    $seen[$relative]=$true
}
if ($seen.Count -eq 0) {throw 'Empty SDK checksum list.'}
foreach ($file in Get-ChildItem -LiteralPath $bundle -File -Recurse) {
    $relative=$file.FullName.Substring($bundle.Length+1).Replace('\','/')
    if ($relative -ne 'SHA256SUMS' -and !$seen.ContainsKey($relative)) {throw "Unverified SDK file: $relative"}
}
foreach ($required in @('bin/sotlas-native.exe','runtime/native/json.sotlas','scripts/build_native.ps1','scripts/test_native.ps1','scripts/verify_sdk.ps1','tests/native/contracts/manifest.txt','examples/calculator/src/calculator/main.sotlas','examples/native_config_map/main.sotlas','LICENSE')) {
    if (!(Test-Path -LiteralPath (Join-Path $bundle $required) -PathType Leaf)) {throw "Incomplete SDK: $required"}
}
if ($metadata.PSObject.Properties['sdk_version'] -or $metadata.PSObject.Properties['compiler_sha256']) {
    if ($metadata.sdk_version -isnot [string] -or $metadata.sdk_version -cnotmatch '\A[0-9]+\.[0-9]+\.[0-9]+(?:rc[0-9]+)?\z' -or
        $metadata.compiler_sha256 -isnot [string] -or $metadata.compiler_sha256 -cnotmatch '\A[0-9a-f]{64}\z' -or
        (Sdk-Hash (Join-Path $bundle 'bin/sotlas-native.exe')) -cne $metadata.compiler_sha256) {
        throw 'SDK version or compiler identity verification failed.'
    }
}
New-Item -ItemType Directory -Path $destinationPath | Out-Null
Copy-Item -Path (Join-Path $bundle '*') -Destination $destinationPath -Recurse
Write-Output "Installed native SDK: $destinationPath"
