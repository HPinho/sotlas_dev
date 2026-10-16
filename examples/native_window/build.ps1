param(
    [Parameter(Mandatory=$true,Position=0)][string]$Compiler,
    [Parameter(Mandatory=$true,Position=1)][string]$OutputDirectory
)
$ErrorActionPreference='Stop'
$native=(Resolve-Path -LiteralPath $Compiler).Path
$output=[IO.Path]::GetFullPath($OutputDirectory)
if(Test-Path -LiteralPath $output){throw 'Choose a fresh output directory.'}
$repository=Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$source=Join-Path $output 'src'
New-Item -ItemType Directory -Force (Join-Path $source 'probe'),(Join-Path $source 'sotlas/runtime') | Out-Null
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'src/probe/main.sotlas') -Destination (Join-Path $source 'probe/main.sotlas')
Copy-Item -LiteralPath (Join-Path $repository 'runtime/native/window_windows.sotlas') -Destination (Join-Path $source 'sotlas/runtime/window_windows.sotlas')
$entry=Join-Path $source 'probe/main.sotlas'
$image=Join-Path $output 'sotlas-window.exe'
$savedPath=$env:PATH
try {
    $env:PATH=Join-Path $output 'no-host-tools'
    & $native --check-build $source $entry
    if($LASTEXITCODE -ne 0){throw 'Window check failed. Use a compiler with the P2 Win64 bridge.'}
    & $native --build-win $image $source $entry
    if($LASTEXITCODE -ne 0){throw 'Window build failed.'}
} finally {$env:PATH=$savedPath}
Write-Output "Window: $image"
