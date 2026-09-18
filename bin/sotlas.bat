@echo off
setlocal
set "BIN_DIR=%~dp0"

if exist "%BIN_DIR%sotlas.exe" (
    "%BIN_DIR%sotlas.exe" %*
    exit /b %ERRORLEVEL%
)

if exist "%BIN_DIR%sotlas_native.exe" (
    "%BIN_DIR%sotlas_native.exe" %*
    exit /b %ERRORLEVEL%
)

set PYTHONUNBUFFERED=1
set "SOTLAS_ROOT=%BIN_DIR%.."
python "%SOTLAS_ROOT%\tools\sotlas_compile\cli.py" %*
exit /b %ERRORLEVEL%

