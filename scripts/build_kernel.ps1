param(
    [Parameter(Mandatory=$true,Position=0)][string]$Compiler,
    [Parameter(Mandatory=$true,Position=1)][string]$OutputDirectory,
    [ValidateSet('boot','interrupts','memory','heap','collections','vm','foundation')][string]$KernelProfile='boot'
)
$ErrorActionPreference='Stop'
if ($env:OS -ne 'Windows_NT') {throw 'Use build_kernel.sh on Linux or Intel macOS.'}
$repository=Split-Path -Parent $PSScriptRoot
$native=(Resolve-Path -LiteralPath $Compiler).Path
$output=[IO.Path]::GetFullPath($OutputDirectory)
if (Test-Path -LiteralPath $output) {throw 'Choose a fresh output directory; existing builds are preserved.'}
$runtime=Join-Path $output 'src/sotlas/runtime'
New-Item -ItemType Directory -Path $runtime -Force | Out-Null
Get-ChildItem (Join-Path $repository 'runtime/native') -Filter '*.sotlas' | Copy-Item -Destination $runtime
$source=Join-Path $output 'src';$entry=Join-Path $source 'main.sotlas'
Copy-Item (Join-Path $repository "examples/native_kernel_$KernelProfile/main.sotlas") $entry
if ($KernelProfile -in @('memory','foundation')) {
    # Deterministic newc packaging only; all kernel compilation/linking below
    # uses Sotlas. Header fields and padding match the POSIX build script.
    $archive=New-Object IO.MemoryStream
    function Write-Newc([string]$Name,[uint32]$Mode,[byte[]]$Content,[uint32]$Inode) {
        $nameBytes=[Text.Encoding]::ASCII.GetBytes($Name)
        $header='070701'
        foreach ($field in @($Inode,$Mode,0,0,1,0,$Content.Length,0,0,0,0,($nameBytes.Length+1),0)) {
            $header+=([uint32]$field).ToString('x8',[Globalization.CultureInfo]::InvariantCulture)
        }
        $bytes=[Text.Encoding]::ASCII.GetBytes($header)
        $archive.Write($bytes,0,$bytes.Length);$archive.Write($nameBytes,0,$nameBytes.Length);$archive.WriteByte(0)
        while ($archive.Position%4 -ne 0) {$archive.WriteByte(0)}
        $archive.Write($Content,0,$Content.Length)
        while ($archive.Position%4 -ne 0) {$archive.WriteByte(0)}
    }
    try {
        Write-Newc 'etc' 16877 ([byte[]]@()) 1
        Write-Newc 'etc/boot.cfg' 33188 ([Text.Encoding]::ASCII.GetBytes("SOTLAS-MODULE-RESERVED`n42")) 2
        Write-Newc 'empty' 33188 ([byte[]]@()) 3
        Write-Newc 'TRAILER!!!' 0 ([byte[]]@()) 0
        [IO.File]::WriteAllBytes((Join-Path $output 'boot-module.bin'),$archive.ToArray())
    } finally {$archive.Dispose()}
}
function Invoke-Kernel([string[]]$Arguments) {
    & $native @Arguments
    if ($global:LASTEXITCODE -ne 0) {throw "Kernel command failed (exit $global:LASTEXITCODE): $Arguments"}
}
$savedPath=$env:PATH
try {
    $env:PATH=Join-Path $output 'no-host-tools'
    Invoke-Kernel @('--check-build',$source,$entry)
    Invoke-Kernel @('--build-obj',(Join-Path $output 'kernel.o'),$source,$entry)
    Invoke-Kernel @('--link-kernel',(Join-Path $output 'kernel.o'),(Join-Path $output 'kernel.elf'),'kernel_main')
} finally {$env:PATH=$savedPath}
Write-Output "Kernel image ($KernelProfile): $(Join-Path $output 'kernel.elf')"
$global:LASTEXITCODE=0
