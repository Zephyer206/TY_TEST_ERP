@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\cloud\manage.ps1" -Action Stop %*
set "zephyr_exit=%errorlevel%"
echo.
pause
exit /b %zephyr_exit%
