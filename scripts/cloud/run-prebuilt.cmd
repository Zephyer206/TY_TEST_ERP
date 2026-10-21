@echo off
setlocal
for %%I in ("%~dp0..\..") do set "erpRoot=%%~fI"
set "ENVIRONMENT=production"
if /i "%~1"=="development" set "ENVIRONMENT=development"
if /i "%~1"=="staging" set "ENVIRONMENT=staging"
set "DEBUG=false"
set "erpPort=8080"
if not "%~2"=="" set "erpPort=%~2"
if not exist "%erpRoot%\logs\cloud-runtime\logs" mkdir "%erpRoot%\logs\cloud-runtime\logs"
cd /d "%erpRoot%\backend"
if errorlevel 1 exit /b 1
"%erpRoot%\.venv\Scripts\python.exe" -X utf8 "%erpRoot%\scripts\cloud\serve.py" --port %erpPort% --managed 1>"%erpRoot%\logs\cloud-runtime\logs\server.stdout.log" 2>"%erpRoot%\logs\cloud-runtime\logs\server.stderr.log"
rem Any exit is unexpected while the availability task is active.
exit /b 1
