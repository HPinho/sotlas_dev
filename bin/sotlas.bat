@echo off
setlocal
set PYTHONUNBUFFERED=1
set SOTLAS_ROOT=%~dp0..
python "%SOTLAS_ROOT%\tools\sotlas_compile\cli.py" %*
endlocal
