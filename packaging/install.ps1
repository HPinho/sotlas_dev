# ==============================================================================
# Sotlas preview installer for Windows (PowerShell).
# ==============================================================================
# Usage from a source checkout:
#   powershell -ExecutionPolicy Bypass -File .\packaging\install.ps1
# ==============================================================================

param (
    [string]$InstallDir = "$env:LOCALAPPDATA\Programs\Sotlas",
    [string]$SourceZip = "",
    [switch]$Force
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host " =================================================================== " -ForegroundColor Cyan
Write-Host "                 SOTLAS PREVIEW INSTALLER                            " -ForegroundColor White
Write-Host " =================================================================== " -ForegroundColor Cyan
Write-Host ""

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir

# 1. Definir diretorio de instalacao
Write-Host "-> Install directory: $InstallDir" -ForegroundColor Yellow
if (Test-Path $InstallDir) {
    if ($Force) {
        Write-Host "   Removing previous installation (-Force)..." -ForegroundColor DarkGray
        Remove-Item -Path $InstallDir -Recurse -Force
    } else {
        Write-Host "   Updating existing installation..." -ForegroundColor DarkGray
    }
}
New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null

# 2. Copiar / Extrair componentes
if ($SourceZip -and (Test-Path $SourceZip)) {
    Write-Host "-> Extracting package $SourceZip..." -ForegroundColor Green
    Expand-Archive -Path $SourceZip -DestinationPath $InstallDir -Force
} else {
    Write-Host "-> Installing the toolchain from the source checkout..." -ForegroundColor Green
    
    # Executar o gerador de bundle se necessario
    $VersionMatch = Select-String -Path "$RepoRoot\compiler\sotlas\__init__.py" -Pattern '^SOTLAS_VERSION\s*=\s*["'']([^"'']+)["'']' | Select-Object -First 1
    if (-not $VersionMatch) { throw "Unable to determine the current Sotlas version." }
    $Version = $VersionMatch.Matches[0].Groups[1].Value
    $BundlePath = Join-Path "$RepoRoot\dist" "sotlas-v$Version-windows-x64"
    if (-not (Test-Path -LiteralPath $BundlePath -PathType Container)) {
        Write-Host "   Building the current release bundle..." -ForegroundColor DarkGray
        py "$ScriptDir\package.py" --target windows --dist-dir "$RepoRoot\dist"
        if ($LASTEXITCODE -ne 0) { throw "Failed to build the Sotlas Windows bundle." }
    }
    if (-not (Test-Path -LiteralPath $BundlePath -PathType Container)) { throw "The Sotlas Windows bundle for version $Version was not produced." }

    # Copiar conteudo do bundle para $InstallDir
    Copy-Item -Path "$BundlePath\*" -Destination $InstallDir -Recurse -Force
}

# 3. Adicionar ao PATH do Usuario
$BinDir = "$InstallDir\bin"
Write-Host "-> Configuring environment variables..." -ForegroundColor Green

[Environment]::SetEnvironmentVariable("SOTLAS_HOME", $InstallDir, [EnvironmentVariableTarget]::User)
$env:SOTLAS_HOME = $InstallDir

$UserPath = [Environment]::GetEnvironmentVariable("Path", [EnvironmentVariableTarget]::User)
if ($UserPath -notlike "*$BinDir*") {
    $NewPath = "$BinDir;$UserPath"
    [Environment]::SetEnvironmentVariable("Path", $NewPath, [EnvironmentVariableTarget]::User)
    $env:Path = "$BinDir;$env:Path"
    Write-Host "   Added '$BinDir' to the user PATH." -ForegroundColor Cyan
} else {
    Write-Host "   '$BinDir' is already on the PATH." -ForegroundColor DarkGray
}

# 4. Associar extensao .sotlas no Windows Registry (HKCU)
try {
    New-Item -Path "HKCU:\Software\Classes\.sotlas" -Value "SotlasSourceFile" -Force | Out-Null
    New-Item -Path "HKCU:\Software\Classes\SotlasSourceFile" -Value "Sotlas Source File" -Force | Out-Null
    New-Item -Path "HKCU:\Software\Classes\SotlasSourceFile\shell\open\command" -Value "`"$BinDir\sotlas.cmd`" run `"%1`"" -Force | Out-Null
    Write-Host "   Associated .sotlas files with the Sotlas CLI." -ForegroundColor Cyan
} catch {
    Write-Host "   Warning: unable to register .sotlas file association; the compiler is unaffected." -ForegroundColor DarkGray
}

Write-Host ""
Write-Host " =================================================================== " -ForegroundColor Green
Write-Host "                 SOTLAS PREVIEW INSTALLED                           " -ForegroundColor White
Write-Host " =================================================================== " -ForegroundColor Green
Write-Host ""
Write-Host "Try these verified preview commands:" -ForegroundColor Yellow
Write-Host "  sotlas version" -ForegroundColor White
Write-Host "  sotlas check examples/01_hello_systems/main.sotlas" -ForegroundColor White
Write-Host ""
Write-Host "Restart your terminal to reload the PATH, or test now:" -ForegroundColor DarkGray
Write-Host "& `"$BinDir\sotlas.cmd`" version" -ForegroundColor Cyan
Write-Host ""
