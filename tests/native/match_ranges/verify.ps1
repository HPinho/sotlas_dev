param(
    [Parameter(Mandatory=$true, Position=0)][string]$Compiler,
    [Parameter(Mandatory=$true, Position=1)][string]$OutputDirectory
)
$ErrorActionPreference = 'Stop'
$compilerPath = (Resolve-Path -LiteralPath $Compiler).Path
$output = [IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Force -Path $output | Out-Null
$image = Join-Path $output 'match-ranges.exe'
$cases = [IO.File]::ReadAllLines((Join-Path $PSScriptRoot 'cases.txt'))
$savedPath = $env:PATH

function Invoke-Case([string]$Executable, [string[]]$Arguments, [int]$Expected, [string]$Message='') {
    # Capture expected compiler failures without PowerShell treating stderr as
    # a terminating shell error. The process status remains the test result.
    $preference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try { $lines = & $Executable @Arguments 2>&1; $status = $LASTEXITCODE }
    finally { $ErrorActionPreference = $preference }
    $text = ''
    if ($null -ne $lines) { $text = [string]::Join([Environment]::NewLine, [string[]]$lines) }
    if ($status -ne $Expected) { throw "Exit $status, expected $Expected`: $Executable $Arguments`n$text" }
    if ($Message -and (-not $text.Contains($Message) -or -not $text.Contains('.sotlas:'))) {
        throw "Missing located diagnostic '$Message': $text"
    }
}

try {
    $env:PATH = Join-Path $output 'no-host-tools'
    foreach ($line in $cases) {
        if (-not $line) { continue }
        $parts = $line.Split('|')
        $source = Join-Path $PSScriptRoot $parts[0]
        $expected = [int]$parts[1]
        if ($expected -eq 42) {
            Invoke-Case $compilerPath @('--check', $source) 0
            Invoke-Case $compilerPath @($source, $image) 0
            Invoke-Case $image @() 42
        } else {
            $before = [IO.File]::ReadAllBytes($image)
            Invoke-Case $compilerPath @('--check', $source) $expected $parts[2]
            Invoke-Case $compilerPath @($source, $image) $expected $parts[2]
            $after = [IO.File]::ReadAllBytes($image)
            if ([Convert]::ToBase64String($before) -ne [Convert]::ToBase64String($after)) {
                throw "Rejected compilation changed the executable: $source"
            }
        }
        Write-Output "Passed: $($parts[0])"
    }
} finally { $env:PATH = $savedPath }
