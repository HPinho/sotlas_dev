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
New-Item -ItemType Directory -Force (Join-Path $source 'calculator_app'),(Join-Path $source 'sotlas/runtime') | Out-Null
foreach($name in @('main','model')) {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot "src/calculator_app/$name.sotlas") -Destination (Join-Path $source "calculator_app/$name.sotlas")
}
foreach($name in @('calculator','ui','ui_windows','window_windows')) {
    Copy-Item -LiteralPath (Join-Path $repository "runtime/native/$name.sotlas") -Destination (Join-Path $source "sotlas/runtime/$name.sotlas")
}
$entry=Join-Path $source 'calculator_app/main.sotlas'
$image=Join-Path $output 'calculator.exe'
$savedPath=$env:PATH
try {
    $env:PATH=Join-Path $output 'no-host-tools'
    & $native --check-build $source $entry
    if($LASTEXITCODE -ne 0){throw 'Calculator check failed.'}
    & $native --build-win $image $source $entry
    if($LASTEXITCODE -ne 0){throw 'Calculator build failed. A P2 native seed is required.'}
} finally {$env:PATH=$savedPath}
Write-Output "Graphical calculator: $image"
