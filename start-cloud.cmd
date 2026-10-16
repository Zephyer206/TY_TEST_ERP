@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\cloud\manage.ps1" -Action Start %*
set "zephyr_exit=%errorlevel%"
echo.
if "%zephyr_exit%"=="0" (
    echo ERP is running in the background. Press any key to close this window.
) else (
    echo Startup failed. Review the error above and logs\cloud-runtime\logs.
    echo Press any key to close this window.
)
pause >nul
exit /b %zephyr_exit%
