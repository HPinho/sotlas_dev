# ==============================================================================
# Sotlas preview installer for Windows (PowerShell).
# ==============================================================================
# Usage from a source checkout:
#   powershell -ExecutionPolicy Bypass -File .\packaging\install.ps1
# Or install a downloaded portable release archive:
#   powershell -ExecutionPolicy Bypass -File .\install.ps1 -SourceZip .\sotlas-v1.0.0rc1-windows-x64.zip
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

if (Get-Command py -ErrorAction SilentlyContinue) {
    $PythonCommand = "py"
    $PythonPrefix = @("-3")
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $PythonCommand = "python"
    $PythonPrefix = @()
} else {
    throw "Python 3.10 or newer is required to install the Sotlas preview."
}
& $PythonCommand @PythonPrefix -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)"
if ($LASTEXITCODE -ne 0) {
    $DetectedPython = & $PythonCommand @PythonPrefix -c "import sys; print('.'.join(map(str, sys.version_info[:3])))"
    throw "Python 3.10 or newer is required; found $DetectedPython via $PythonCommand."
}

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
if ($SourceZip) {
    if (-not (Test-Path -LiteralPath $SourceZip -PathType Leaf)) {
        throw "SourceZip does not exist: $SourceZip"
    }

    Write-Host "-> Extracting package $SourceZip..." -ForegroundColor Green
    $ExtractRoot = Join-Path $env:TEMP ("sotlas-preview-" + [Guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $ExtractRoot -Force | Out-Null
    try {
        Expand-Archive -LiteralPath $SourceZip -DestinationPath $ExtractRoot -Force

        $PayloadRoots = @()
        if (Test-Path -LiteralPath (Join-Path $ExtractRoot "bin\sotlas.cmd") -PathType Leaf) {
            $PayloadRoots += Get-Item -LiteralPath $ExtractRoot
        }
        Get-ChildItem -LiteralPath $ExtractRoot -Directory | ForEach-Object {
            if (Test-Path -LiteralPath (Join-Path $_.FullName "bin\sotlas.cmd") -PathType Leaf) {
                $PayloadRoots += $_
            }
        }

        if ($PayloadRoots.Count -ne 1) {
            throw "Portable archive must contain exactly one Sotlas toolchain root; found $($PayloadRoots.Count)."
        }

        $PayloadRoot = $PayloadRoots[0].FullName
        Copy-Item -Path (Join-Path $PayloadRoot "*") -Destination $InstallDir -Recurse -Force
    } finally {
        if (Test-Path -LiteralPath $ExtractRoot) {
            Remove-Item -LiteralPath $ExtractRoot -Recurse -Force
        }
    }
} else {
    Write-Host "-> Installing the toolchain from the source checkout..." -ForegroundColor Green

    $VersionFile = Join-Path $RepoRoot "compiler\sotlas\__init__.py"
    if (-not (Test-Path -LiteralPath $VersionFile -PathType Leaf)) {
        throw "Source checkout not found. Pass -SourceZip when running the installer outside the repository."
    }

    $VersionMatch = Select-String -Path $VersionFile -Pattern '^SOTLAS_VERSION\s*=\s*["'']([^"'']+)["'']' | Select-Object -First 1
    if (-not $VersionMatch) { throw "Unable to determine the current Sotlas version." }
    $Version = $VersionMatch.Matches[0].Groups[1].Value
    $BundlePath = Join-Path "$RepoRoot\dist" "sotlas-v$Version-windows-x64"
    if (-not (Test-Path -LiteralPath $BundlePath -PathType Container)) {
        Write-Host "   Building the current release bundle..." -ForegroundColor DarkGray
        & $PythonCommand @PythonPrefix "$ScriptDir\package.py" --target windows --dist-dir "$RepoRoot\dist"
        if ($LASTEXITCODE -ne 0) { throw "Failed to build the Sotlas Windows bundle." }
    }
    if (-not (Test-Path -LiteralPath $BundlePath -PathType Container)) {
        throw "The Sotlas Windows bundle for version $Version was not produced."
    }

    Copy-Item -Path "$BundlePath\*" -Destination $InstallDir -Recurse -Force
}

$BinDir = "$InstallDir\bin"
$SotlasLauncher = Join-Path $BinDir "sotlas.cmd"
if (-not (Test-Path -LiteralPath $SotlasLauncher -PathType Leaf)) {
    throw "Installation is incomplete: missing $SotlasLauncher"
}

# 3. Adicionar ao PATH do Usuario
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

# 4. Verificar o frontend instalado usando a mesma precedencia do bundle.
$OldPythonPath = $env:PYTHONPATH
$env:PYTHONPATH = "$InstallDir\compiler;$InstallDir\tools;$OldPythonPath"
try {
    Write-Host "-> Running Sotlas preview doctor..." -ForegroundColor Green
    & $PythonCommand @PythonPrefix -m sotlas.doctor
    if ($LASTEXITCODE -ne 0) {
        throw "Sotlas doctor reported an invalid core installation."
    }
} finally {
    $env:PYTHONPATH = $OldPythonPath
}

# 5. Associar extensao .sotlas no Windows Registry (HKCU)
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
Write-Host "  py -3 -m sotlas.doctor" -ForegroundColor White
Write-Host "  sotlas check examples/01_hello_systems/main.sotlas" -ForegroundColor White
Write-Host ""
Write-Host "Restart your terminal to reload the PATH, or test now:" -ForegroundColor DarkGray
Write-Host "& `"$BinDir\sotlas.cmd`" version" -ForegroundColor Cyan
Write-Host ""
