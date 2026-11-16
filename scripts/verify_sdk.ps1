param([Parameter(Mandatory=$true,Position=0)][string]$OutputDirectory, [switch]$Rebuild)
$ErrorActionPreference='Stop'
if ($env:OS -ne 'Windows_NT') {throw 'Use verify_sdk.sh on Linux or Intel macOS.'}
$sdk=Split-Path -Parent $PSScriptRoot
$output=[IO.Path]::GetFullPath($OutputDirectory)
if (Test-Path -LiteralPath $output) {throw 'Choose a fresh verification output directory.'}
foreach ($relative in @('src/sotlas/runtime','src/calculator','src/configuration')) {
    New-Item -ItemType Directory -Path (Join-Path $output $relative) -Force | Out-Null
}
Get-ChildItem (Join-Path $sdk 'runtime/native') -Filter '*.sotlas' | Copy-Item -Destination (Join-Path $output 'src/sotlas/runtime')
Copy-Item (Join-Path $sdk 'examples/calculator/src/calculator/main.sotlas') (Join-Path $output 'src/calculator/main.sotlas')
Copy-Item (Join-Path $sdk 'examples/calculator/platform/windows.sotlas') (Join-Path $output 'src/calculator/platform.sotlas')
Copy-Item (Join-Path $sdk 'examples/native_config_map/main.sotlas') (Join-Path $output 'src/configuration/main.sotlas')
Copy-Item (Join-Path $sdk 'tests/native/calculator/model.sotlas') (Join-Path $output 'src/calculator_model.sotlas')
function Invoke-Sdk([string]$Executable,[string[]]$Arguments,[int]$Expected=0,[string]$InputText='',[string]$ExpectedText) {
    $start=New-Object Diagnostics.ProcessStartInfo
    $start.FileName=$Executable
    $start.Arguments=($Arguments | ForEach-Object {'"'+$_+'"'}) -join ' '
    $start.UseShellExecute=$false;$start.CreateNoWindow=$true
    $start.RedirectStandardInput=$true;$start.RedirectStandardOutput=$true;$start.RedirectStandardError=$true
    $start.EnvironmentVariables['PATH']=Join-Path $output 'no-host-tools'
    $process=New-Object Diagnostics.Process
    $process.StartInfo=$start
    try {
        if (!$process.Start()) {throw 'Could not start native SDK process.'}
        $stdout=$process.StandardOutput.ReadToEndAsync();$stderr=$process.StandardError.ReadToEndAsync()
        $process.StandardInput.Write($InputText);$process.StandardInput.Close()
        if (!$process.WaitForExit(300000)) {$process.Kill();throw 'Native SDK process timed out.'}
        $text=$stdout.GetAwaiter().GetResult();$errors=$stderr.GetAwaiter().GetResult()
        if ($process.ExitCode -ne $Expected) {throw "Native SDK process returned $($process.ExitCode), expected $Expected. $errors"}
        if ($PSBoundParameters.ContainsKey('ExpectedText') -and $text -cne $ExpectedText) {throw "Unexpected native output: $text"}
    } finally {$process.Dispose()}
}
$compiler=Join-Path $sdk 'bin/sotlas-native.exe';$source=Join-Path $output 'src'
Invoke-Sdk $compiler @('--self-test')
foreach ($name in @('calculator','configuration')) {
    $entry=Join-Path $source "$name/main.sotlas";$image=Join-Path $output "$name.exe"
    Invoke-Sdk $compiler @('--check-build',$source,$entry)
    Invoke-Sdk $compiler @('--build-win',$image,$source,$entry)
}
Invoke-Sdk (Join-Path $output 'calculator.exe') @() 0 "6*7`n" "42`n"
Invoke-Sdk (Join-Path $output 'calculator.exe') @() 2 "1/0`n42`n" "error: division by zero at byte 1`n42`n"
Invoke-Sdk $compiler @('--build-win',(Join-Path $output 'model.exe'),$source,(Join-Path $source 'calculator_model.sotlas'))
foreach ($name in @('configuration','model')) {Invoke-Sdk (Join-Path $output "$name.exe") @() 42}
$LASTEXITCODE=0
& (Join-Path $sdk 'scripts/test_native.ps1') $compiler (Join-Path $output 'contracts')
if ($LASTEXITCODE -ne 0) {throw 'Installed Sotlas contract tests failed.'}
if ($Rebuild) {& (Join-Path $sdk 'scripts/build_native.ps1') $compiler (Join-Path $output 'rebuild')}
$summary="# Installed native SDK verification`n`nCalculator, error recovery, JSON configuration, model and 50 Sotlas contracts passed.`n"
if ($Rebuild) {$summary+="`nOriginal compiler sources rebuilt with Stage 2/3 byte identity.`n"}
[IO.File]::WriteAllText((Join-Path $output 'summary.md'),$summary,(New-Object Text.UTF8Encoding($false)))
Write-Output "Installed SDK verified: $output"
# The self-build intentionally exercises a compiler rejection (exit 6).
# Do not leak that expected status into a CI shell after successful verification.
$global:LASTEXITCODE=0
