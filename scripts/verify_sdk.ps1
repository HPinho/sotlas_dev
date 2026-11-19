param([Parameter(Mandatory=$true,Position=0)][string]$OutputDirectory, [switch]$Rebuild)
$ErrorActionPreference='Stop'
if ($env:OS -ne 'Windows_NT') {throw 'Use verify_sdk.sh on Linux or Intel macOS.'}
$sdk=Split-Path -Parent $PSScriptRoot
$output=[IO.Path]::GetFullPath($OutputDirectory)
if (Test-Path -LiteralPath $output) {throw 'Choose a fresh verification output directory.'}
foreach ($relative in @('src/sotlas/runtime','src/calculator','src/configuration','src/calculator_app','src/tensor_rows','src/csv_app')) {
    New-Item -ItemType Directory -Path (Join-Path $output $relative) -Force | Out-Null
}
Get-ChildItem (Join-Path $sdk 'runtime/native') -Filter '*.sotlas' | Copy-Item -Destination (Join-Path $output 'src/sotlas/runtime')
Copy-Item (Join-Path $sdk 'examples/calculator/src/calculator/main.sotlas') (Join-Path $output 'src/calculator/main.sotlas')
Copy-Item (Join-Path $sdk 'examples/calculator/platform/windows.sotlas') (Join-Path $output 'src/calculator/platform.sotlas')
Copy-Item (Join-Path $sdk 'examples/native_config_map/main.sotlas') (Join-Path $output 'src/configuration/main.sotlas')
Copy-Item (Join-Path $sdk 'examples/native_tensor_rows/main.sotlas') (Join-Path $output 'src/tensor_rows/main.sotlas')
Copy-Item (Join-Path $sdk 'examples/native_csv/main.sotlas') (Join-Path $output 'src/csv_app/main.sotlas')
Copy-Item (Join-Path $sdk 'examples/native_csv/normalize.sotlas') (Join-Path $output 'src/csv_app/normalize.sotlas')
Copy-Item (Join-Path $sdk 'tests/native/calculator/model.sotlas') (Join-Path $output 'src/calculator_model.sotlas')
foreach ($name in @('main','model')) {Copy-Item (Join-Path $sdk "examples/graphical_calculator/src/calculator_app/$name.sotlas") (Join-Path $output "src/calculator_app/$name.sotlas")}
foreach ($pair in @(@('model','tests'),@('unicode','unicode_tests'),@('render','render_tests'))) {
    Copy-Item (Join-Path $sdk "tests/native/ui/$($pair[0]).sotlas") (Join-Path $output "src/calculator_app/$($pair[1]).sotlas")
}
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
foreach ($name in @('calculator','configuration','tensor_rows','csv_app')) {
    $entry=Join-Path $source "$name/main.sotlas";$image=Join-Path $output "$name.exe"
    Invoke-Sdk $compiler @('--check-build',$source,$entry)
    Invoke-Sdk $compiler @('--build-win',$image,$source,$entry)
}
Invoke-Sdk (Join-Path $output 'calculator.exe') @() 0 "6*7`n" "42`n"
Invoke-Sdk (Join-Path $output 'calculator.exe') @() 2 "1/0`n42`n" "error: division by zero at byte 1`n42`n"
Invoke-Sdk $compiler @('--build-win',(Join-Path $output 'model.exe'),$source,(Join-Path $source 'calculator_model.sotlas'))
foreach ($name in @('configuration','model')) {Invoke-Sdk (Join-Path $output "$name.exe") @() 42}
Invoke-Sdk (Join-Path $output 'tensor_rows.exe') @() 0
Invoke-Sdk (Join-Path $output 'csv_app.exe') @() 0
$csvEntry=Join-Path $source 'csv_app/normalize.sotlas'
$csvNormalizer=Join-Path $output 'csv-normalize.exe'
Invoke-Sdk $compiler @('--check-build',$source,$csvEntry)
Invoke-Sdk $compiler @('--build-win',$csvNormalizer,$source,$csvEntry)
$csvInput='item,count'+"`n"+'"a,b","7"'+"`n"+'"two'+"`n"+'lines",'+"`n"
$csvExpected='item,count'+"`r`n"+'"a,b",7'+"`r`n"+'"two'+"`n"+'lines",""'+"`r`n"
Invoke-Sdk $csvNormalizer @() 0 $csvInput $csvExpected
Invoke-Sdk $csvNormalizer @() 0 $csvExpected $csvExpected
Invoke-Sdk $csvNormalizer @() 0 '' ''
$csvMaximum='x'.PadLeft(4096)
Invoke-Sdk $csvNormalizer @() 0 $csvMaximum ($csvMaximum+"`r`n")
Invoke-Sdk $csvNormalizer @() 2 ('ok'+"`n"+'"unfinished') ''
Invoke-Sdk $csvNormalizer @() 4 ('x'.PadLeft(4097)) ''
foreach ($name in @('tests','unicode_tests','render_tests','main')) {
    $entry=Join-Path $source "calculator_app/$name.sotlas";$image=Join-Path $output "ui-$name.exe"
    Invoke-Sdk $compiler @('--check-build',$source,$entry)
    Invoke-Sdk $compiler @('--build-win',$image,$source,$entry)
    if ($name -ne 'main') {Invoke-Sdk $image @() 42}
}
# Native invocation updates the global automatic variable. A local assignment
# here shadows it in nested build scripts when packaging initialized it first.
$global:LASTEXITCODE=0
& (Join-Path $sdk 'scripts/test_native.ps1') $compiler (Join-Path $output 'contracts')
if ($global:LASTEXITCODE -ne 0) {throw 'Installed Sotlas contract tests failed.'}
if ($Rebuild) {& (Join-Path $sdk 'scripts/build_native.ps1') $compiler (Join-Path $output 'rebuild')}
$summary="# Installed native SDK verification`n`nCalculator, error recovery, JSON configuration, CSV round trip, tensor row preprocessing, UI model/Unicode, Windows rendering/cleanup and installed Sotlas contracts passed. GUI executable: ui-main.exe.`n"
if ($Rebuild) {$summary+="`nOriginal compiler sources rebuilt with Stage 2/3 byte identity.`n"}
[IO.File]::WriteAllText((Join-Path $output 'summary.md'),$summary,(New-Object Text.UTF8Encoding($false)))
Write-Output "Installed SDK verified: $output"
# The self-build intentionally exercises a compiler rejection (exit 6).
# Do not leak that expected status into a CI shell after successful verification.
$global:LASTEXITCODE=0
