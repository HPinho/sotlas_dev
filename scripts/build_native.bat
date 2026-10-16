@echo off
rem Existing Sotlas native seed required; no hosted bootstrap fallback.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_native.ps1" %*
exit /b %ERRORLEVEL%
