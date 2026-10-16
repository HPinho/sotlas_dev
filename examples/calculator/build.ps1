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
New-Item -ItemType Directory -Force (Join-Path $source 'calculator'),(Join-Path $source 'sotlas/runtime') | Out-Null
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'src/calculator/main.sotlas') -Destination (Join-Path $source 'calculator/main.sotlas')
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'platform/windows.sotlas') -Destination (Join-Path $source 'calculator/platform.sotlas')
Copy-Item -LiteralPath (Join-Path $repository 'runtime/native/calculator.sotlas') -Destination (Join-Path $source 'sotlas/runtime/calculator.sotlas')
$entry=Join-Path $source 'calculator/main.sotlas'
$image=Join-Path $output 'calculator.exe'
$savedPath=$env:PATH
try {
    $env:PATH=Join-Path $output 'no-host-tools'
    & $native --check-build $source $entry
    if($LASTEXITCODE -ne 0){throw 'Calculator check failed.'}
    & $native --build-win $image $source $entry
    if($LASTEXITCODE -ne 0){throw 'Calculator build failed.'}
} finally {$env:PATH=$savedPath}
Write-Output "Calculator: $image"
