param(
    [Parameter(Mandatory=$true,Position=0)][string]$CiAssets,
    [Parameter(Mandatory=$true,Position=1)][string]$Destination
)

$ErrorActionPreference='Stop'
$targetArchives=[ordered]@{
    'windows-x64'='sotlas-sdk-windows-x64.zip'
    'linux-x64'='sotlas-sdk-linux-x64.tar.gz'
    'macos-x64'='sotlas-sdk-macos-x64.tar.gz'
}
$files=@()
foreach ($target in $targetArchives.Keys) {
    $name=$targetArchives[$target]
    $folder=Join-Path $CiAssets "sotlas-terminal-sdk-$target"
    $archive=Join-Path $folder $name
    $checksum="$archive.sha256"
    if (!(Test-Path -LiteralPath $archive -PathType Leaf) -or
        !(Test-Path -LiteralPath $checksum -PathType Leaf)) {
        throw "Missing certified SDK archive or checksum for $target."
    }
    $digest=(Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant()
    if ((Get-Content -LiteralPath $checksum -Raw).TrimEnd() -cne "$digest  $name") {
        throw "Certified SDK checksum mismatch for $target."
    }
    $files+=$archive
}
$vsix=Join-Path $CiAssets 'sotlas-vscode-preview/sotlas-preview.vsix'
if (!(Test-Path -LiteralPath $vsix -PathType Leaf)) { throw 'Missing certified preview VSIX.' }
$files+=$vsix

foreach ($file in $files) {
    $path=Join-Path $Destination (Split-Path $file -Leaf)
    if (Test-Path -LiteralPath $path) { throw "Preview asset already exists at $path." }
}
New-Item -ItemType Directory -Path $Destination -Force | Out-Null
foreach ($file in $files) {
    Copy-Item -LiteralPath $file -Destination $Destination
}
