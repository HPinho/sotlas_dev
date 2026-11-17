param([Parameter(Mandatory=$true,Position=0)][string]$Compiler,
      [Parameter(Mandatory=$true,Position=1)][string]$OutputDirectory)
$ErrorActionPreference='Stop'
if ($env:OS -ne 'Windows_NT') {throw 'Use verify_kernel_sdk.sh on Linux or Intel macOS.'}
$sdk=Split-Path -Parent $PSScriptRoot
$native=(Resolve-Path -LiteralPath $Compiler).Path
$output=[IO.Path]::GetFullPath($OutputDirectory)
if (Test-Path -LiteralPath $output) {throw 'Choose a fresh output directory.'}
New-Item -ItemType Directory -Path $output | Out-Null
$profiles=@('boot','interrupts','memory','heap','collections','vm','foundation')
foreach ($kernelProfile in $profiles) {& (Join-Path $sdk 'scripts/build_kernel.ps1') $native (Join-Path $output $kernelProfile) -KernelProfile $kernelProfile}
function Kernel-Hash([string]$Path) {
    $stream=[IO.File]::OpenRead($Path);$hash=[Security.Cryptography.SHA256]::Create()
    try {return ([BitConverter]::ToString($hash.ComputeHash($stream))).Replace('-','').ToLowerInvariant()}
    finally {$stream.Dispose();$hash.Dispose()}
}
function Invoke-Kernel([string[]]$Arguments,[int]$Expected=0) {
    & $native @Arguments
    $actual=$global:LASTEXITCODE
    if ($Expected -ne 0) {[IO.File]::AppendAllText((Join-Path $output 'rejections.log'),"exit=$actual expected=$Expected $Arguments`n")}
    if ($actual -ne $Expected) {throw "Kernel command returned $actual; expected $Expected. $Arguments"}
}
$image=Join-Path $output 'boot/kernel.elf';$before=Kernel-Hash $image
$savedPath=$env:PATH
try {
    $env:PATH=Join-Path $output 'no-host-tools'
    Invoke-Kernel @('--link-kernel',(Join-Path $output 'boot/kernel.o'),(Join-Path $output 'relinked.elf'),'kernel_main')
    if ((Kernel-Hash (Join-Path $output 'relinked.elf')) -cne $before) {throw 'Repeated kernel linking differs.'}
    $invalid=Join-Path $output 'invalid';New-Item -ItemType Directory -Path $invalid | Out-Null
    foreach ($case in @('bad_abi','hosted')) {
        $entry=Join-Path $invalid "$case.sotlas";$object=Join-Path $output "$case.o"
        Copy-Item (Join-Path $sdk "tests/native/kernel_sdk/$case.sotlas") $entry
        Invoke-Kernel @('--check-build',$invalid,$entry)
        Invoke-Kernel @('--build-obj',$object,$invalid,$entry)
        Invoke-Kernel @('--link-kernel',$object,$image,'kernel_main') 9
        if ((Kernel-Hash $image) -cne $before) {throw 'Rejected kernel link changed the valid image.'}
    }
    Invoke-Kernel @('--link-kernel',(Join-Path $output 'boot/kernel.o'),$image,'missing_entry') 9
    if ((Kernel-Hash $image) -cne $before) {throw 'Missing entry changed the valid image.'}
    $malformed=Join-Path $output 'malformed.o'
    [IO.File]::WriteAllBytes($malformed,[Text.Encoding]::ASCII.GetBytes("not an object`n"))
    Invoke-Kernel @('--link-kernel',$malformed,$image,'kernel_main') 8
    if ((Kernel-Hash $image) -cne $before) {throw 'Malformed object changed the valid image.'}
} finally {$env:PATH=$savedPath}
$encoding=New-Object Text.UTF8Encoding($false)
$rows=foreach ($kernelProfile in $profiles) {(Kernel-Hash (Join-Path $output "$kernelProfile/kernel.elf"))+"  $kernelProfile/kernel.elf"}
[IO.File]::WriteAllText((Join-Path $output 'images.sha256'),(($rows -join "`n")+"`n"),$encoding)
[IO.File]::WriteAllText((Join-Path $output 'summary.md'),"# Installed kernel SDK verification`n`nSeven kernel profiles checked, compiled and linked with the native seed.`nFour invalid links rejected without changing the valid image. Repeated linking is byte-identical.`nBoot execution is certified separately in Linux QEMU.`n",$encoding)
Write-Output "Installed kernel SDK verified: $output"
$global:LASTEXITCODE=0
